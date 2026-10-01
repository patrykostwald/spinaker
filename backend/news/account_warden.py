"""Autonomous, evidence-based account warden. No timeline reads and no paid LLMs."""
import calendar
import math
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from contextvars import ContextVar

import requests
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from news import account_warden_sources as sources
from news.management.commands.link_official_x_accounts import USER_FIELDS, TechnicalError, identity_problem, _fold
from news.models import ImportState
from news.political_candidates import CandidateResolutionError, resolve_candidate
from news.political_models import AccountWardenRun, PoliticalAccount, PoliticalAccountCandidate, PublicFigure, SocialHandleEvidence
from news.political_polling import POST_PRICE, USER_PRICE, configuration

STATE = 'account-warden'
AGENT = 'system-account-warden'
RUN_ID = ContextVar('account_warden_run_id', default=None)
GROUP_LABELS = {'sejm': 'Posłowie', 'senat': 'Senatorowie', 'ep': 'Europosłowie', 'cabinet': 'Rząd',
                'voivodes': 'Wojewodowie', 'leaders': 'Liderzy partii i klubów', 'parties': 'Partie'}
EVENT_LABELS = {'added': 'Dodane konto', 'renamed': 'Zmiana nazwy konta', 'disabled': 'Wyłączone konto',
                'pending': 'Do decyzji', 'rejected': 'Odrzucone konto', 'camp': 'Zmiana obozu do decyzji',
                'former': 'Utrata funkcji', 'inactive': 'Nieaktywne konto', 'interval': 'Rzadsze czytanie',
                'capacity': 'Dostępny budżet', 'error': 'Błąd przebiegu'}


def daily_limit():
    return max(0, int(os.environ.get('ACCOUNT_WARDEN_DAILY_X_LOOKUPS', '150')))


def reserve_units(kind, count=1):
    """Count users (not HTTP batches); reservations survive failures and restarts."""
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=STATE + '-budget')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        day = timezone.now().date().isoformat()
        data = dict(state.cursor) if state.cursor.get('day') == day else {'day': day}
        ceiling = daily_limit() if kind == 'x' else 30
        if data.get(kind, 0) + count > ceiling:
            return False
        data[kind] = data.get(kind, 0) + count
        if kind == 'x' and RUN_ID.get():
            AccountWardenRun.objects.filter(pk=RUN_ID.get()).update(lookups=F('lookups') + count)
        state.cursor = data
        state.save(update_fields=['cursor'])
        return True


def remaining():
    state = ImportState.objects.filter(name=STATE + '-budget').first()
    used = state.cursor.get('x', 0) if state and state.cursor.get('day') == timezone.now().date().isoformat() else 0
    return max(0, daily_limit() - used)


def x_lookup(*, handle=None, ids=None):
    """Only user metadata from fixed X endpoints; never fetch posts."""
    token = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
    if not token:
        raise TechnicalError('Brak X_POLITICAL_BEARER_TOKEN.')
    endpoint = 'https://api.x.com/2/users'
    params = {'user.fields': USER_FIELDS}
    if handle:
        if not sources.HANDLE.fullmatch(handle):
            raise TechnicalError('Nieprawidłowy handle.')
        endpoint += '/by/username/' + handle
    else:
        params['ids'] = ','.join(ids)
    try:
        response = requests.get(endpoint, params=params, headers={'Authorization': 'Bearer ' + token},
                                timeout=(5, 20), allow_redirects=False)
        if response.status_code == 404 and handle:
            return {'data': None}
        if response.status_code != 200:
            raise TechnicalError(f'X: HTTP {response.status_code}; ponowienie później.')
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError()
        return payload
    except (requests.RequestException, ValueError) as exc:
        raise TechnicalError('Niepełna odpowiedź X; ponowienie później.') from exc


def check_candidate(data, target, source):
    """Identical conditions for all camps. Hard failures cannot be auto-approved."""
    if not data:
        return 'rejected', 'Konto nie istnieje.'
    if not isinstance(data, dict) or not all(k in data for k in ('id', 'username', 'name', 'protected')):
        return 'pending', 'Niepełne dane tożsamości z X.'
    expected = identity_name(data, target.name, target.party_handle)
    problem = identity_problem(data, expected)
    combined = _fold(data.get('name', '') + ' ' + data.get('description', ''))
    if any(s in combined for s in ('parod', 'fanpage', 'fan ', 'nieoficjaln', 'not affiliated')):
        return 'rejected', 'Parodia lub konto nieoficjalne.'
    if problem:
        return 'rejected', problem
    if not display_matches(data, expected):
        return 'pending', 'Nazwa wyświetlana nie potwierdza nazwiska lub nazwy partii.'
    try:
        born = datetime.fromisoformat(str(data['created_at']).replace('Z', '+00:00'))
        now = timezone.now()
        month = now.month - 6
        year = now.year - (month <= 0)
        month = month if month > 0 else month + 12
        cutoff = now.replace(year=year, month=month, day=min(now.day, calendar.monthrange(year, month)[1]))
        if born.tzinfo is None:
            raise ValueError()
        if born >= cutoff:
            return 'rejected', 'Konto ma najwyżej sześć miesięcy.'
    except (ValueError, KeyError, TypeError):
        return 'pending', 'Brak wiarygodnej daty utworzenia konta.'
    if not target.camp:
        return 'pending', 'Brak jednoznacznego obozu w oficjalnym rejestrze.'
    if source == 'search':
        followers = (data.get('public_metrics') or {}).get('followers_count', 0)
        if data.get('verified') is not True and (not isinstance(followers, int) or followers < 500):
            return 'pending', 'Zasięg poniżej 500 i brak weryfikacji X.'
        if not re.search(r'\b(?:posel|poslanka|senator\w*|minister\w*|premier\w*|parlament\w*|wojewod\w*|parti\w*|'
                         r'lewica|konfederac\w*|obywatelsk\w*|pis|psl|2050|razem)\b', combined):
            return 'pending', 'Opis i nazwa nie wskazują funkcji publicznej ani partii.'
    return 'accepted', ''


def agent_user():
    user, created = get_user_model().objects.get_or_create(username=AGENT, defaults={'is_staff': True, 'is_active': True})
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    if user.has_usable_password() or not user.is_staff or not user.is_active:
        raise TechnicalError('Techniczne konto strażnika jest nieprawidłowe; wymaga naprawy konfiguracji.')
    return user


def observed():
    from news.clinic import figures_by_account
    accounts = list(PoliticalAccount.objects.filter(enabled=True).select_related('confirmed_by'))
    accounts = [a for a in accounts if a.is_confirmed()]
    figures = figures_by_account(a.pk for a in accounts)
    return accounts, {figure.pk for figure in figures.values()}


def covered(target, accounts, figure_ids):
    if target.figure:
        return target.figure.pk in figure_ids
    return any(a.handle.casefold() == target.party_handle.casefold() for a in accounts)


def coverage(targets):
    accounts, figure_ids = observed()
    result = {}
    for target in targets:
        for group in target.groups:
            row = result.setdefault(group, {'total': 0, 'observed': 0, 'missing': []})
            row['total'] += 1
            if covered(target, accounts, figure_ids):
                row['observed'] += 1
            else:
                row['missing'].append(target.name)
    return result


def save_candidate(target, lead, data, verdict, reason):
    """Atomically attach evidence and reuse the normal resolution path, without a second lookup."""
    with transaction.atomic():
        staff = agent_user()
        existing = PoliticalAccount.objects.filter(handle__iexact=lead.handle).first()
        if existing and (not existing.enabled or not existing.is_confirmed()):
            return None, 'Istniejące konto jest wyłączone lub niepotwierdzone; do decyzji.'
        candidate = PoliticalAccountCandidate.objects.filter(handle__iexact=lead.handle).first()
        if candidate and candidate.resolved_account_id:
            account = candidate.resolved_account
            if not data or account.user_id != str(data.get('id')) or not account.enabled or not account.is_confirmed():
                return None, 'Istniejące konto ma inną tożsamość albo jest wyłączone; do decyzji.'
            if account.camp != target.camp:
                return None, 'Istniejące konto: zmiana obozu do decyzji.'
        elif candidate and candidate.resolution_error and not candidate.resolution_error.startswith('Strażnik:'):
            return None, 'Kandydat ma wcześniejszą decyzję zespołu.'
        if candidate is None:
            candidate = PoliticalAccountCandidate.objects.create(handle=lead.handle, display_name=target.name[:150],
                classification=target.camp or 'independent', proposed_camp=target.camp,
                confirmation_url=lead.url, confirmation_note=f'Strażnik: {lead.source}; {target.role}; {lead.url}')
        evidence = None
        if target.figure:
            evidence, _ = SocialHandleEvidence.objects.get_or_create(platform='x', handle__iexact=lead.handle,
                subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=target.figure.pk,
                defaults={'handle': lead.handle, 'evidence_url': lead.url, 'extracted_url': f'https://x.com/{lead.handle}'})
            if evidence.status == 'rejected':
                return None, 'Dowód odrzucony wcześniej; do decyzji.'
            # Do not bind a second person to an already attributed account.
            other = candidate.social_evidence.filter(status='candidate_created').exclude(pk=evidence.pk)
            if other.exclude(subject_object_id=target.figure.pk,
                             subject_content_type=ContentType.objects.get_for_model(PublicFigure)).exists():
                return None, 'Konto powiązano już z innym profilem; do decyzji.'
            evidence.candidate = candidate
            evidence.evidence_url = lead.url
            evidence.status = 'rejected' if verdict == 'rejected' else 'pending_review'
            evidence.reviewed_by, evidence.reviewed_at = staff, timezone.now()
            evidence.save()
        if verdict != 'accepted':
            candidate.resolution_error = ('Strażnik: ' + reason)[:240]
            candidate.save(update_fields=['resolution_error'])
            return None, reason
        if not candidate.resolved_account_id:
            candidate.proposed_camp = candidate.classification = target.camp
            candidate.confirmation_url = lead.url
            candidate.save(update_fields=['proposed_camp', 'classification', 'confirmation_url'])
        account = resolve_candidate(candidate, staff, verified_data=data)
        if str(data.get('id')) != account.user_id or account.camp != target.camp:
            raise CandidateResolutionError('Tożsamość lub obóz istniejącego konta wymagają decyzji.')
        account.enabled = True
        account.last_verified_at = timezone.now()
        account.save(update_fields=['enabled', 'last_verified_at'])
        if evidence:
            evidence.status = 'candidate_created'
            evidence.save(update_fields=['status'])
        return account, ''


def discover_missing(targets, report, limit):
    accounts, figure_ids = observed()
    missing = [t for t in targets if not covered(t, accounts, figure_ids) and
               not (t.figure and t.figure.account_discovery_at and
                    t.figure.account_discovery_at > timezone.now() - timedelta(days=7))]
    # Age eventually wins over priority: a large MP backlog must not starve senators forever.
    epoch = datetime(1970, 1, 1, tzinfo=timezone.now().tzinfo)
    missing.sort(key=lambda t: ((t.figure.account_discovery_at if t.figure and t.figure.account_discovery_at else epoch)
                               + timedelta(days=t.priority), t.priority, t.key))
    wikidata, seen = None, {}
    for target in missing[:limit]:
        if not remaining():
            break
        if wikidata is None:
            try:
                wikidata = sources.wikidata_leads()
            except (requests.RequestException, KeyError, ValueError, TypeError):
                wikidata = {}
                report['events'].append({'kind': 'error', 'detail': 'Wikidane niedostępne; użyto kolejnych źródeł.'})
        found = False
        if target.figure and target.figure.parliamentary_roster_entry and not target.camp:
            entry = target.figure.parliamentary_roster_entry
            if entry.source == 'senat':
                from news.management.commands.link_official_x_accounts import senate_club, CLUB_CAMPS
                club = senate_club(entry)
                target.camp = CLUB_CAMPS.get(club, '')
                if club and not entry.club:
                    entry.club = club
                    entry.save(update_fields=['club'])
        stages = (lambda: wikidata.get(_fold(target.name), []), lambda: sources.official_leads(target),
                  lambda: sources.search_leads(target, lambda: reserve_units('search')), lambda: sources.party_leads(target))
        for stage in stages:
            try:
                leads = stage()
            except (requests.RequestException, KeyError, ValueError, TypeError):
                report['events'].append({'kind': 'error', 'detail': f'{target.name}: źródło niedostępne; ponowienie później.'})
                continue
            for lead in leads:
                key = lead.handle.casefold()
                if key in seen:
                    data = seen[key]
                else:
                    if not reserve_units('x'):
                        return
                    report['lookups'] += 1
                    data = x_lookup(handle=lead.handle).get('data')
                    seen[key] = data
                verdict, reason = check_candidate(data, target, lead.source)
                if data and str(data.get('username', '')).casefold() != lead.handle.casefold():
                    verdict, reason = 'pending', 'X zwrócił inny handle.'
                try:
                    account, reason = save_candidate(target, lead, data, verdict, reason)
                except (CandidateResolutionError, ValidationError) as exc:
                    account, reason = None, str(exc)
                report['events'].append({'kind': 'added' if account else 'rejected' if verdict == 'rejected' else 'pending',
                    'detail': f'{target.name} · {target.role} · {target.camp or "nieustalony obóz"} · @{lead.handle}: '
                              + ('dodane do czytania' if account else reason), 'source': lead.url})
                if account:
                    report['added_ids'].append(account.pk)
                    found = True
                    break
            if found:
                break
        if target.figure:
            PublicFigure.objects.filter(pk=target.figure.pk).update(account_discovery_at=timezone.now())


def identity_name(data, name, party_handle=''):
    """Use a catalogued party abbreviation only when it is present as a whole word."""
    party = next((p for p in sources.PARTIES if p[3].casefold() == party_handle.casefold()), None) if party_handle else None
    if party:
        alias = _fold(party[0].split('-')[0])
        if alias in set(re.findall(r'[a-z0-9]+', _fold(data.get('name', '')))):
            return alias
    return name


def display_matches(data, name):
    """A stable handle must not hide a changed, unrelated display name."""
    parts = _fold(name).replace('-', ' ').split()
    words = set(re.findall(r'[a-z0-9]+', _fold(data.get('name', ''))))
    compact = re.sub(r'[^a-z0-9]', '', _fold(name))
    shown = re.sub(r'[^a-z0-9]', '', _fold(data.get('name', '')))
    return bool(parts and (parts[-1] in words or (len(compact) >= 5 and compact == shown)))


def verify_days():
    """Co ile dni każde obserwowane konto jest sprawdzane w X (właściciel, 1.10.2026: co 2 dni)."""
    try:
        return max(1, min(30, int(os.environ.get('ACCOUNT_WARDEN_VERIFY_DAYS', '2'))))
    except ValueError:
        return 2


def verify_accounts(report, limit):
    from news.clinic import figures_by_account
    now = timezone.now()
    due = PoliticalAccount.objects.filter(enabled=True).filter(
        Q(last_verified_at__isnull=True) | Q(last_verified_at__lte=now - timedelta(days=verify_days()))).order_by(
            F('last_verified_at').asc(nulls_first=True), 'pk')
    accounts = list(due[:min(limit, remaining())])
    figures = figures_by_account(a.pk for a in accounts)
    for start in range(0, len(accounts), 100):
        batch = accounts[start:start + 100]
        if not reserve_units('x', len(batch)):
            return
        report['lookups'] += len(batch)
        payload = x_lookup(ids=[a.user_id for a in batch])
        users = {str(row['id']): row for row in payload.get('data', []) if isinstance(row, dict) and row.get('id')}
        # Only explicit per-resource unavailability disables accounts. A missing
        # row, authentication error or partial transport response is not deletion.
        missing = {str(row.get('resource_id') or row.get('value')) for row in payload.get('errors', [])
                   if row.get('type', '').endswith(('/resource-not-found', '/resource-unavailable'))}
        for account in batch:
            data, figure = users.get(account.user_id), figures.get(account.pk)
            expected = figure.canonical_name if figure else account.display_name
            party_handle = next((p[3] for p in sources.PARTIES if p[1] == expected), '')
            if data:
                expected = identity_name(data, expected, party_handle)
            problem = ''
            if data is None:
                if account.user_id not in missing:
                    report['events'].append({'kind': 'error', 'detail': f'@{account.handle}: brak pełnej odpowiedzi X; bez wyłączania.'})
                    continue
                problem = 'konto usunięte lub zawieszone'
            elif data.get('protected') is True:
                problem = 'konto chronione'
            elif not all(k in data for k in ('name', 'username', 'protected')):
                report['events'].append({'kind': 'error', 'detail': f'@{account.handle}: niepełne dane X.'})
                continue
            elif not display_matches(data, expected):
                problem = 'nazwa wyświetlana nie pasuje do osoby lub partii'
            else:
                problem = identity_problem(data, expected)
            with transaction.atomic():
                current = PoliticalAccount.objects.select_for_update().get(pk=account.pk)
                if current.identity_fingerprint() != account.identity_fingerprint() or not current.enabled:
                    continue
                if problem:
                    current.enabled, current.last_error = False, ('warden: ' + problem)[:120]
                    report['events'].append({'kind': 'disabled', 'detail': f'@{account.handle}: {problem}.'})
                elif data['username'].casefold() != account.handle.casefold():
                    if PoliticalAccount.objects.filter(handle__iexact=data['username']).exclude(pk=account.pk).exists():
                        current.enabled = False
                        report['events'].append({'kind': 'disabled', 'detail': f'@{account.handle}: nowy handle koliduje z innym ID; do decyzji.'})
                    elif current.is_confirmed():
                        current.handle = data['username']
                        current.confirmation_fingerprint = current.identity_fingerprint()
                        report['events'].append({'kind': 'renamed', 'detail': f'@{account.handle} → @{current.handle} (to samo ID).'} )
                current.last_verified_at = now
                current.save(update_fields=['enabled', 'last_error', 'handle', 'confirmation_fingerprint', 'last_verified_at'])
            cutoff = now - timedelta(days=30)
            if (account.created_at < cutoff and account.last_polled_at and account.last_polled_at >= cutoff
                    and account.api_reads.filter(status='ok', started_at__lte=cutoff).exists()
                    and not account.posts.filter(published_at__gte=cutoff).exists()):
                report['events'].append({'kind': 'inactive', 'detail': f'@{account.handle}: nieaktywne — 0 wpisów przez 30 dni mimo czytania.'})
    overdue = due.count()
    if overdue:
        report['events'].append({'kind': 'capacity', 'detail': f'{overdue} kont czeka na kontrolę w kolejnych partiach.'})
    if PoliticalAccount.objects.filter(enabled=True).count() > daily_limit() * verify_days():
        report['events'].append({'kind': 'capacity', 'detail': f'Dzienny limit X nie wystarcza na kontrolę wszystkich kont co {verify_days()} dni.'})


def fit_polling_budget(targets, report):
    """Conservative full-page estimate; the poller's actual hard limits remain authoritative."""
    from news.clinic import figures_by_account
    config = configuration()
    if not config:
        report['events'].append({'kind': 'capacity', 'detail': 'Polling X wyłączony lub nieskonfigurowany; nowe konta czekają na uruchomienie czytania.'})
        return
    accounts, _ = observed()
    figures = figures_by_account(a.pk for a in accounts)
    priority = {t.figure.pk: t.priority for t in targets if t.figure}
    weights = {a.pk: 4 if priority.get(getattr(figures.get(a.pk), 'pk', None), 2) == 0 else
               2 if priority.get(getattr(figures.get(a.pk), 'pk', None), 2) == 1 else 1 for a in accounts}
    # Include all confirmed accounts, not just the newly added ones.
    cost = POST_PRICE * config['page_size'] + USER_PRICE
    capacity = min(config['daily_requests'], config['daily_posts'] / config['page_size'],
                   float(config['monthly_usd'] / (Decimal(31) * cost)))
    total_weight = sum(weights.values())
    before = sum(1440 / a.poll_interval_minutes for a in accounts)
    if before > capacity:
        for account in accounts:
            interval = max(account.poll_interval_minutes, math.ceil(1440 * total_weight / (capacity * weights[account.pk])))
            if interval > 525600:
                raise TechnicalError('Budżet pollingu wymaga interwału ponad rok; zmniejsz zakres kont lub zmień budżet.')
            if interval != account.poll_interval_minutes:
                changes = {'poll_interval_minutes': interval}
                if account.pk not in report['added_ids']:
                    changes['next_poll_at'] = timezone.now() + timedelta(minutes=interval * ((account.pk % 997) + 1) / 998)
                PoliticalAccount.objects.filter(pk=account.pk).update(**changes)
                report['events'].append({'kind': 'interval', 'detail': f'@{account.handle}: czytanie co {interval} min (budżet i priorytet).'})
                account.poll_interval_minutes = interval
    added = [a for a in accounts if a.pk in report['added_ids']]
    report['polling'] = {'new_accounts': len(added), 'added_requests_day': round(sum(1440 / a.poll_interval_minutes for a in added), 4),
        'total_requests_day': round(sum(1440 / a.poll_interval_minutes for a in accounts), 4),
        'budget_requests_day': round(capacity, 4), 'usd_per_full_page': str(cost)}


def _notify(report):
    from news.council_recruiter import _owner_email
    from news.social_publish import _mail
    recipient = os.environ.get('ACCOUNT_WARDEN_EMAIL', '').strip() or _owner_email()
    body = ['Strażnik kont', f'Odczyty X: {report["lookups"]}; szacunek: {report["lookup_usd"]} USD.']
    for name, row in report['coverage'].items():
        body.append(f'{GROUP_LABELS.get(name, name)}: {row["observed"]} z {row["total"]}; '
                    + ('wszyscy obserwowani' if not row['missing'] else 'brakuje: ' + ', '.join(row['missing'])))
    body.extend(e['detail'] + (' · ' + e['source'] if e.get('source') else '') for e in report['events'])
    polling = report.get('polling')
    if polling:
        body.append(f'Nowe konta: {polling["new_accounts"]}; przyrost: około {polling["added_requests_day"]} odczytów/dobę. '
                    f'Łącznie: {polling["total_requests_day"]}, budżet: {polling["budget_requests_day"]} odczytów/dobę '
                    f'(szacunek pełnych stron po {polling["usd_per_full_page"]} USD).')
    try:
        return _mail(recipient, 'spin.clinic · Strażnik kont', '\n'.join(body))
    except Exception:
        return False


def run(*, dry_run=False, only_missing=False, limit=60):
    if limit < 1:
        raise ValueError('Limit musi być dodatni.')
    if dry_run:
        scope = sources.targets(persist=False)
        return {'status': 'dry_run', 'coverage': coverage(scope), 'lookups': 0,
                'detail': 'Bez zapisu, synchronizacji, X, wyszukiwarki i maila. Pokrycie według ostatniego rejestru.'}
    lease, now = uuid4().hex, timezone.now()
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=STATE)
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        if state.cursor.get('lease_until', '') > now.isoformat():
            return {'status': 'already_running'}
        state.cursor = {**state.cursor, 'lease': lease, 'lease_until': (now + timedelta(hours=2)).isoformat()}
        state.last_started = now
        state.save(update_fields=['cursor', 'last_started'])
    journal = AccountWardenRun.objects.create()
    run_token = RUN_ID.set(journal.pk)
    report = {'status': 'ok', 'events': [], 'lookups': 0, 'added_ids': [], 'coverage': {}}
    scope = []
    try:
        sources.sync_rosters(report['events'])
        scope = sources.targets()
        # Spread the population over ACCOUNT_WARDEN_VERIFY_DAYS (owner: every 2 days), leaving the rest for discovery.
        if not only_missing:
            rotation = max(1, math.ceil(PoliticalAccount.objects.filter(enabled=True).count() / verify_days()))
            verify_accounts(report, min(limit, rotation))
        discover_missing(scope, report, limit)
    except Exception as exc:
        report['status'] = 'error'
        report['events'].append({'kind': 'error', 'detail': str(exc) if isinstance(exc, TechnicalError) else
                                f'Przebieg przerwany ({type(exc).__name__}); zapisane zmiany pozostają w dzienniku.'})
    finally:
        try:
            if report['added_ids']:
                fit_polling_budget(scope, report)
            report['coverage'] = coverage(scope)
        except Exception as exc:
            report['status'] = 'error'
            report['events'].append({'kind': 'error', 'detail': f'Nie udało się obliczyć pokrycia lub interwałów ({type(exc).__name__}). Limity pollingu pozostają aktywne.'})
        report['lookup_usd'] = str(USER_PRICE * report['lookups'])
        RUN_ID.reset(run_token)
        journal.refresh_from_db()
        journal.report, journal.finished_at = report, timezone.now()
        journal.save(update_fields=['report', 'finished_at'])
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name=STATE)
            if state.cursor.get('lease') == lease:
                history = state.cursor.get('history', [])
                changes = [{**e, 'at': timezone.now().isoformat()} for e in report['events']]
                state.cursor = {'report': report, 'history': (changes + history)[:300], 'run_id': journal.pk}
                state.last_success = timezone.now() if report['status'] == 'ok' else state.last_success
                state.last_error = '' if report['status'] == 'ok' else 'account_warden_run_error'
                state.save(update_fields=['cursor', 'last_success', 'last_error'])
        if report['events']:
            report['mail_sent'] = _notify(report)
            journal.report = report
            journal.save(update_fields=['report'])
            with transaction.atomic():
                state = ImportState.objects.select_for_update().get(name=STATE)
                if state.cursor.get('run_id') == journal.pk:
                    state.cursor = {**state.cursor, 'mail_sent': report['mail_sent']}
                    state.save(update_fields=['cursor'])
    return report


def panel_section(now):
    from news.admin_status import card, metric
    state = ImportState.objects.filter(name=STATE).first()
    report = state.cursor.get('report', {}) if state else {}
    metrics = [metric(GROUP_LABELS.get(key, key), f'{row["observed"]} z {row["total"]}') for key, row in report.get('coverage', {}).items()]
    metrics += [metric('Odczyty X (ostatni przebieg)', report.get('lookups')), metric('Koszt X · USD (szacunek)', report.get('lookup_usd'))]
    if state and 'mail_sent' in state.cursor:
        metrics.append(metric('Raport mailowy wysłany', state.cursor['mail_sent']))
    queue = PoliticalAccountCandidate.objects.filter(resolved_account__isnull=True, resolution_error__startswith='Strażnik:').exclude(
        social_evidence__status='rejected').distinct()
    items = [card(f'@{c.handle} · {c.display_name}', 'warn', c.resolution_error, c.created_at) for c in queue[:50]]
    for item, candidate in zip(items, queue[:50]):
        item.update(href=candidate.confirmation_url, link_label='Źródło dowodu')
    for key, row in report.get('coverage', {}).items():
        if row['missing']:
            items.append(card('Braki: ' + GROUP_LABELS.get(key, key), 'warn', ', '.join(row['missing']),
                              state.last_started if state else None))
    items += [card(EVENT_LABELS.get(e['kind'], e['kind']), 'ok' if e['kind'] in ('added', 'renamed', 'interval') else 'warn', e['detail'], e['at'])
              for e in (state.cursor.get('history', []) if state else [])[:50]]
    metrics.append(metric('Niepewne konta do decyzji', queue.count()))
    return card('Strażnik kont', 'unknown' if not state else 'warn' if state.last_error or queue.exists() or
                state.cursor.get('mail_sent') is False else 'ok',
        'Automatyczna kontrola kont codziennie o 03:10. Niepewne konta pozostają poza czytaniem. '
        'Pokrycie według ostatniego przebiegu; liderzy według listy priorytetowej.',
        state.last_started if state else None, metrics, items)
