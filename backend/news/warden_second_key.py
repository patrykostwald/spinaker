"""Independent, delayed second key. Ambiguous evidence never disables an account."""
import os
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from news.management.commands.link_official_x_accounts import _fold, TechnicalError
from news.models import ImportState
from news.political_models import PoliticalAccount, WardenReview, SocialHandleEvidence, AccountWardenRun

AGENT_INFO = {'name': 'Drugi klucz', 'what': 'Niezależnie weryfikuje decyzje Strażnika kont.',
              'task': 'news.tasks.warden_second_key_task', 'flag': 'WARDEN_SECOND_KEY_ENABLED'}
HARD_STATES = {'unavailable', 'protected'}


def enabled():
    return os.environ.get('WARDEN_SECOND_KEY_ENABLED', 'true').lower() == 'true'


def safe_profile(payload, uid):
    """Allowlist per-account API evidence. Never persist headers, tokens or arbitrary errors."""
    if not isinstance(payload, dict):
        return {'data': [], 'errors': []}
    data = payload.get('data') or []
    data = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
    fields = ('id', 'username', 'name', 'protected', 'created_at', 'verified')
    users = [{k: row[k] for k in fields if k in row and isinstance(row[k], (str, bool))}
             for row in data if isinstance(row, dict) and str(row.get('id')) == uid]
    errors = [{'type': row['type'], 'resource_id': uid} for row in (payload.get('errors') or [])
              if isinstance(row, dict) and str(row.get('resource_id') or row.get('value')) == uid
              and row.get('type') in ('https://api.twitter.com/2/problems/resource-not-found',
                  'https://api.twitter.com/2/problems/resource-unavailable',
                  'https://api.x.com/2/problems/resource-not-found',
                  'https://api.x.com/2/problems/resource-unavailable')]
    return {'data': users, 'errors': errors}


def profile_state(payload):
    data = payload.get('data') or []
    if data:
        row = data[0]
        if row.get('protected') is True:
            return 'protected', row
        if row.get('protected') is False and row.get('name') and row.get('username'):
            return 'available', row
        return 'unknown', row
    return ('unavailable' if payload.get('errors') else 'unknown'), {}


def tolerant_name(left, right):
    def words(value):
        value = _fold(value.split('|')[0])
        value = re.sub(r'\b(kancelaria (prezesa rady ministrow|premiera))\b', 'kprm', value)
        return [w for w in re.findall(r'[a-z0-9]+', value)
                if w not in {'dr', 'prof', 'mgr', 'inz', 'hab', 'posel', 'poslanka', 'senator', 'rp'}]
    a, b = words(left), words(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # A surname alone is not identity evidence. Accept initials plus the same surname.
    return (len(a) >= 2 and len(b) >= 2 and a[-1] == b[-1]
            and (a[0] == b[0] or (min(len(a[0]), len(b[0])) == 1 and a[0][0] == b[0][0])))


def database_evidence(account, shown=''):
    from news.clinic import figures_by_account
    figure = figures_by_account([account.pk]).get(account.pk)
    names = [account.display_name] + [row['name'] for row in account.name_history if row.get('name')]
    roster = None
    if figure:
        names.append(figure.canonical_name)
        entry = figure.parliamentary_roster_entry
        if entry:
            names.append(entry.full_name)
            roster = {'name': entry.full_name, 'source': entry.source, 'url': entry.source_url,
                      'checked_at': entry.last_seen_at.isoformat(), 'active': entry.active}
    links = list(SocialHandleEvidence.objects.filter(platform='x', handle__iexact=account.handle)
                 .exclude(status='rejected').values('evidence_url', 'extracted_url', 'observed_at'))
    for link in links:
        link['observed_at'] = link['observed_at'].isoformat()
    return {'names': names, 'name_matches': any(tolerant_name(shown, name) for name in names),
            'roster': roster, 'official_links': links, 'confirmation_url': account.confirmation_url,
            'note': 'Zapisane źródła są dowodem historycznym, nie nowym odczytem strony.'}


def submit(account, category, reason, payload, expected='', decision='disable'):
    now = timezone.now()
    with transaction.atomic():
        current = PoliticalAccount.objects.select_for_update().get(pk=account.pk)
        if current.identity_fingerprint() != account.identity_fingerprint():
            return None
        existing = WardenReview.objects.filter(account=current, status__in=['pending', 'owner']).first()
        if existing and existing.fingerprint == current.identity_fingerprint():
            # New observations are retained without moving the six-hour deadline.
            evidence = dict(existing.evidence)
            observations = evidence.get('observations', [])
            observations.append({'at': now.isoformat(), 'api': safe_profile(payload, current.user_id),
                                 'category': category, 'reason': reason})
            evidence['observations'] = observations[-30:]
            existing.evidence = evidence
            existing.save(update_fields=['evidence'])
            return existing
        if existing:
            existing.status = 'superseded'
            existing.save(update_fields=['status'])
        safe = safe_profile(payload, current.user_id)
        shown = (safe['data'] or [{}])[0].get('name', '')
        return WardenReview.objects.create(account=current, category=category, reason=reason,
            first_decision=decision, fingerprint=current.identity_fingerprint(),
            due_at=now + timedelta(hours=6), evidence={'api': safe, 'at': now.isoformat(),
                'user_id': current.user_id, 'old_name': current.display_name, 'new_name': shown,
                'expected_name': expected, 'database': database_evidence(current, shown)})


def reserve_lookup():
    """Separate hard USD budget for extra paid X reads, disabled by default."""
    from news.account_warden import reserve_units
    from news.political_polling import USER_PRICE
    try:
        limit = Decimal(os.environ.get('WARDEN_SECOND_KEY_DAILY_X_USD', '0'))
        if not limit.is_finite() or limit <= 0:
            return False
    except InvalidOperation:
        return False
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='warden-second-key-x-budget')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        day = timezone.localdate().isoformat()
        used = Decimal(state.cursor.get('usd', '0')) if state.cursor.get('day') == day else Decimal(0)
        if used + USER_PRICE > limit or not reserve_units('x'):
            return False
        state.cursor = {'day': day, 'usd': str(used + USER_PRICE)}
        state.save(update_fields=['cursor'])
        return True


def verify(review_id):
    from news.account_warden import x_lookup
    if not enabled():
        return 'disabled'
    now, token = timezone.now(), uuid4().hex
    with transaction.atomic():
        review = WardenReview.objects.select_for_update().select_related('account').get(pk=review_id)
        if review.status != 'pending' or review.due_at > now or review.created_at + timedelta(hours=6) > now:
            return 'waiting'
        if review.lease_until and review.lease_until > now:
            return 'busy'
        review.lease_token, review.lease_until = token, now + timedelta(minutes=10)
        review.save(update_fields=['lease_token', 'lease_until'])
    try:
        if not reserve_lookup():
            raise TechnicalError('Brak budżetu drugiego odczytu X. Wniosek czeka.')
        journal = AccountWardenRun.objects.create(lookups=1, report={'source': 'second-key'})
        try:
            payload = safe_profile(x_lookup(ids=[review.account.user_id]), review.account.user_id)
        finally:
            journal.finished_at = timezone.now()
            journal.save(update_fields=['finished_at'])
        state, row = profile_state(payload)
        database = database_evidence(review.account, row.get('name', ''))
        original_state, _ = profile_state(review.evidence.get('api', {}))
        agree = (review.first_decision == 'disable' and state in HARD_STATES
                 and state == original_state and state == review.category)
        decision = 'disable' if agree else 'keep' if state == 'available' else 'uncertain'
        detail = {'api': payload, 'at': timezone.now().isoformat(), 'database': database,
                  'state': state, 'reason': 'Stan potwierdzony dwoma odczytami.' if agree else
                  'Drugi klucz nie potwierdza wyłączenia. Wymaga Ciebie.'}
        if os.environ.get('WARDEN_SECOND_KEY_AI', 'false').lower() == 'true':
            from news.seba import advisory
            detail['ai'] = advisory({'first': review.evidence, 'second': detail.copy()})
        with transaction.atomic():
            current = WardenReview.objects.select_for_update().get(pk=review.pk)
            account = PoliticalAccount.objects.select_for_update().get(pk=current.account_id)
            if current.status != 'pending' or current.lease_token != token:
                return 'stale'
            if current.fingerprint != account.identity_fingerprint():
                current.status = 'superseded'
            else:
                current.second_decision, current.second_evidence = decision, detail
                current.status = 'disabled' if agree else 'owner'
                if agree:
                    account.enabled, account.last_error = False, ('warden: ' + current.reason)[:120]
                    account.save(update_fields=['enabled', 'last_error'])
                    current.decided_at = timezone.now()
                else:
                    from news.seba import enqueue_warden
                    enqueue_warden(current)
            current.checked_at, current.lease_until, current.lease_token, current.last_error = timezone.now(), None, '', ''
            current.save()
            return current.status
    except TechnicalError:
        WardenReview.objects.filter(pk=review_id, lease_token=token, status='pending').update(
            lease_until=None, lease_token='', due_at=timezone.now() + timedelta(hours=1),
            last_error='Odczyt niedostępny lub brak budżetu. Ponowienie w następnym oknie.')
        return 'queued'


def run(limit=50):
    if not enabled():
        return {'status': 'disabled'}
    ids = WardenReview.objects.filter(status='pending', due_at__lte=timezone.now()).order_by('due_at').values_list('pk', flat=True)[:limit]
    results = [verify(pk) for pk in ids]
    return {'status': 'ok', 'checked': results.count('disabled') + results.count('owner'), 'queued': results.count('queued')}


def recheck(apply=False):
    """Read-only preview uses stored evidence. Only warden decisions are eligible."""
    cutoff = timezone.now() - timedelta(days=14)
    accounts = PoliticalAccount.objects.filter(enabled=False, last_error__startswith='warden:').filter(
        Q(disabled_at__gte=cutoff) | Q(disabled_at__isnull=True, last_verified_at__gte=cutoff))
    result = []
    for account in accounts:
        review = account.warden_reviews.order_by('-created_at').first()
        reason = _fold(account.last_error)
        name_only = any(word in reason for word in ('nazw', 'name', 'identity', 'tozsamos')) and not any(
            word in reason for word in ('chronion', 'zawiesz', 'usuniet', 'nie istnieje'))
        restore = name_only or bool(review and review.fingerprint == account.identity_fingerprint()
                                   and review.second_decision == 'keep')
        row = {'account': account.pk, 'handle': account.handle, 'restore': restore,
               'reason': 'Brak potwierdzenia wyłączenia za nazwę.' if name_only else
                         'Drugi klucz potwierdził dostępność.' if restore else 'Brak wystarczających danych. Potrzebny odczyt X.'}
        if apply and restore:
            with transaction.atomic():
                current = PoliticalAccount.objects.select_for_update().get(pk=account.pk)
                if current.enabled or current.identity_fingerprint() != account.identity_fingerprint() or current.last_error != account.last_error:
                    continue
                current.enabled, current.last_error = True, ''
                current.save(update_fields=['enabled', 'last_error'])
                current.warden_reviews.filter(status__in=['pending', 'owner']).update(status='superseded')
                WardenReview.objects.create(account=current, reason=account.last_error, category='legacy_name' if name_only else 'legacy',
                    fingerprint=current.identity_fingerprint(), evidence={'legacy_error': account.last_error,
                        'old_name': account.display_name, 'disabled_at': (account.disabled_at or account.last_verified_at).isoformat()},
                    second_decision='keep', second_evidence=row, status='kept', due_at=timezone.now(), decided_at=timezone.now())
        result.append(row)
    return result
