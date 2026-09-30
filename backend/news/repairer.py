"""Bounded repairs of local state. Never invoke a model or publish content here.

Only reviewed beat tasks can be resubmitted. New tasks default to owner review.
"""
import hashlib
import json
import os
import pickle
import re
import time
from collections import Counter
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.core.cache import cache, caches
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.admin_telemetry import safe_error
from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.models import ArchiveJob, FetchRequest, ImportState, RepairAction, RepairerState
from news.task_heartbeat import cadence

WARSAW = ZoneInfo('Europe/Warsaw')
RUN_LOCK = 'repairer-run-lock'
MAX_ACTIONS = 20
# Reviewed in scraper/tasks.py: source access, leases and HTTP budgets remain in
# the called adapters. No model calls or external publication in these tasks.
SAFE_SCRAPER = {
    'import_official_task', 'scrape_rss_sources_task', 'scrape_newsapi_batch_task',
    'gdelt_daily_topics', 'discover_archives', 'archive_batch', 'discover_kprm_html',
    'discover_mswia_metadata', 'discover_ministry_finance_metadata',
    'discover_named_gov_metadata', 'discover_senat_metadata', 'check_data_quality',
    'enrich_data_quality', 'audit_source_access', 'backfill_voting_history',
    'preflight_structured_metadata_source', 'import_bzp_metadata',
}
SAFE_TASKS = {'scraper.tasks.' + name for name in SAFE_SCRAPER} | {
    'news.tasks.clinic_screen_task', 'news.tasks.clinic_diagnose_task',
    'news.tasks.youtube_official_task', 'news.tasks.youtube_leftover_task',
    'news.tasks.deleted_posts_task', 'news.tasks.source_social_task',
    'news.tasks.sejm_career_task', 'news.tasks.sync_live_public_rosters_task',
}
# Locks and hard timeouts are explicit, reviewed against tasks.py; never scan or
# delete arbitrary Redis keys. Shared locks include ALL matching beat pulses.
LOCKS = {
    'clinic-diagnose-lock': ('news.tasks.clinic_diagnose_task', 1600),
    'clinic-screen-lock': ('news.tasks.clinic_screen_task', 660),
    'clinic-interview-lock': ('news.tasks.clinic_interview_task', 1800),
    'deleted-posts-lock': ('news.tasks.deleted_posts_task', 660),
    'source-social-lock': ('news.tasks.source_social_task', 1600),
    'youtube-leftover-lock': ('news.tasks.youtube_leftover_task', 1600),
    'krs-agent-lock': ('news.tasks.krs_agent_task', 1600),
    'social-publish-lock': ('news.tasks.social_publish_task', 960),
    'x-publish-lock': ('news.tasks.x_publish_task', 360),
    'dr-spin-thread-lock': ('news.tasks.dr_spin_thread_task', 360),
    'council-recruiter-lock': ('news.tasks.council_recruiter_task', 1600),
    'lock:rss': ('scraper.tasks.scrape_rss_sources_task', 3300),
    'lock:archives': ('scraper.tasks.archive_batch', 360),
    'lock:archive-discovery': ('scraper.tasks.discover_archives', 3300),
    'lock:source-access': ('scraper.tasks.audit_source_access', 540),
    'lock:quality-enrichment': ('scraper.tasks.enrich_data_quality', 300),
    'lock:live-public-rosters': ('news.tasks.sync_live_public_rosters_task', 660),
}


def flag(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes')


def permanent(error):
    text = str(error).lower()
    return bool(re.search(r'(?<!\d)4(?!29)\d\d(?!\d)', text) or any(word in text for word in (
        'missing_key', 'key_missing', 'no_key', 'api_key', 'not_configured', 'invalid', 'malformed',
        'rejected', 'refusal', 'odrzuc', 'brak klucza', 'no_approved_instruction',
        'credit balance', 'insufficient', 'unauthorized', 'authentication', 'permission',
        'configuration', 'not_found', 'not found', 'disabled', 'wyłączone', 'nieskonfigurowane')))


def transient(error):
    text = str(error).lower()
    return not permanent(text) and bool(re.search(r'(?<!\d)(429|5\d\d)(?!\d)', text) or any(
        word in text for word in ('timeout', 'timed out', 'connection', 'council_too_few_members', '_daily_limit')))


def stamp(value):
    try:
        parsed = parse_datetime(value or '')
        return parsed if parsed and timezone.is_aware(parsed) else None
    except (TypeError, ValueError):
        return None


def compare_delete(key, expected, guards=None):
    """Atomic compare-and-delete including pulse guards (no GET/DELETE race).

    These are the two backends configured in config/settings.py. Unsupported
    backends fail closed. Internal backend access is isolated and tested here.
    """
    backend = caches['default']
    expected = {key: expected, **(guards or {})}
    keys = [backend.make_and_validate_key(k) for k in expected]
    if isinstance(backend, RedisCache):
        client = backend._cache.get_client(keys[0], write=True)
        raw = client.mget(keys)
        if any(v is None or backend._cache._serializer.loads(v) != wanted
               for v, wanted in zip(raw, expected.values())):
            return False
        return bool(client.eval("""
            for i = 1, #KEYS do
                if redis.call('get', KEYS[i]) ~= ARGV[i] then return 0 end
            end
            return redis.call('del', KEYS[1])
        """, len(keys), *keys, *raw))
    if isinstance(backend, LocMemCache):
        with backend._lock:
            if any(backend._has_expired(k) or pickle.loads(backend._cache[k]) != wanted
                   for k, wanted in zip(keys, expected.values())):
                return False
            backend._delete(keys[0])
            return True
    return False


class Run:
    def __init__(self, now, dry_run=False):
        self.now, self.dry_run = now, dry_run
        self.actions = []
        self.sent = set()
        self.deadline = time.monotonic() + 180

    @property
    def room(self):
        return len(self.actions) < MAX_ACTIONS and time.monotonic() < self.deadline

    def record(self, rule, target, result, description):
        if len(self.actions) >= MAX_ACTIONS:
            return
        # Callers supply code-owned descriptions; exception text only via safe_error.
        row = dict(rule=rule, target=str(target)[:160], result=result, description=description[:300])
        if result in ('needs_owner', 'skipped') and RepairAction.objects.filter(
                **row, created_at__gte=self.now - timedelta(days=1)).exists():
            return  # A persistent manual issue must not starve later repair rules.
        if not self.dry_run:
            RepairAction.objects.create(created_at=self.now, **row)
        self.actions.append(row)

    def apply(self, rule, target, fn, result, description):
        if not self.room:
            return
        try:
            if self.dry_run:
                self.record(rule, target, result, 'DRY RUN: ' + description)
            else:
                with transaction.atomic():
                    changed = fn()
                    self.record(rule, target, result if changed else 'skipped',
                                description if changed else 'Stan zmienił się lub limit został osiągnięty.')
        except Exception as exc:
            self.record(rule, target, 'failed', safe_error(exc))


def retry_task(run, name, entry):
    from config.celery import app
    identity = json.dumps([entry['task'], entry.get('args', ()), entry.get('kwargs', {})], sort_keys=True)
    aliases = {name} | {n for n, e in app.conf.beat_schedule.items()
        if e['task'] == entry['task'] and tuple(e.get('args', ())) == tuple(entry.get('args', ()))
        and e.get('kwargs', {}) == entry.get('kwargs', {})}
    if identity in run.sent or not run.room:
        return
    pulse = cache.get('heartbeat:' + name, {})
    if any(word in pulse.get('summary', '').lower()
            for word in ('wyłączone', 'nieskonfigurowane', 'disabled', 'not_configured')):
        return
    if entry['task'] not in SAFE_TASKS:
        run.record('task', name, 'needs_owner', 'Ponowienie nie jest zatwierdzone: sprawdź koszty, konfigurację i skutki zadania.')
        return
    if pulse.get('phase') == 'running':
        # A lost worker can leave a running pulse forever. Only its registered
        # hard timeout AND two beat intervals provide evidence to retry safely.
        task = getattr(app, 'tasks', {}).get(entry['task'])
        timeout = getattr(task, 'time_limit', None)
        interval = cadence(entry['schedule'])
        started = stamp(pulse.get('started_at'))
        if not timeout or not interval or not started or (run.now - started).total_seconds() <= max(timeout, 2 * interval):
            return
    if pulse.get('repair_error') == 'permanent' or permanent(pulse.get('summary', '')):
        run.record('task', name, 'needs_owner', pulse.get('repair_hint') or safe_error(pulse.get('summary')))
        return
    recent = RepairAction.objects.filter(rule='task', target__in=aliases, result__in=['retried', 'failed'])
    if (recent.filter(created_at__gt=run.now - timedelta(hours=1)).exists()
            or recent.filter(created_at__gt=run.now - timedelta(days=1)).count() >= 3):
        return
    run.sent.add(identity)
    # Commit an attempt BEFORE dispatch: a broker timeout can mean it accepted
    # the message. Counting failed dispatches prevents a redelivery storm.
    run.record('task', name, 'failed' if not run.dry_run else 'retried',
               'DRY RUN: ponowiłby zadanie z beat.' if run.dry_run else 'Zarezerwowano próbę zlecenia zadania z beat.')
    if run.dry_run:
        return
    row = RepairAction.objects.filter(rule='task', target=name).first()
    try:
        options = {**entry.get('options', {}), 'retry': False}
        app.send_task(entry['task'], args=entry.get('args', ()), kwargs=entry.get('kwargs', {}), **options)
        result, description = 'retried', 'Ponownie zlecono zadanie z beat.'
    except Exception as exc:
        result, description = 'failed', safe_error(exc)
    row.result, row.description = result, description
    row.save(update_fields=['result', 'description'])
    run.actions[-1].update(result=result, description=description)


def repair_tasks(run, snapshot):
    from config.celery import app
    section = next((s for s in snapshot['sections'] if s['title'] == 'Zadania w tle'), {})
    for row in section.get('items', []):
        name = row['title']
        if row['status'] in ('warn', 'error') and name in app.conf.beat_schedule and name != 'repairer-15m':
            retry_task(run, name, app.conf.beat_schedule[name])


def repair_locks(run, snapshot):
    from config.celery import app
    entries = app.conf.beat_schedule
    specs = [(key, [n for n, e in entries.items() if e['task'] == task], timeout)
             for key, (task, timeout) in LOCKS.items()]
    specs += [('lock:official:' + e['args'][0], [n], 3500) for n, e in entries.items()
              if e['task'] == 'scraper.tasks.import_official_task' and e.get('args')]
    for key, names, timeout in specs:
        value = cache.get(key)
        if value is None or not names:
            continue
        if key == 'clinic-diagnose-lock' and str(value).startswith('inquisitor:'):
            continue  # Independent control owns this bounded lease; diagnosis pulse cannot prove it stale.
        guards = {f'heartbeat:{n}': cache.get(f'heartbeat:{n}', {}) for n in names}
        if any(p.get('phase') not in ('ok', 'error') or not stamp(p.get('last_event'))
               or (run.now - stamp(p['last_event'])).total_seconds() <= timeout for p in guards.values()):
            continue
        run.apply('lock', key, lambda: compare_delete(key, value, guards), 'fixed', 'Usunięto osieroconą blokadę; puls bez aktywnego zadania.')


def repair_fetches(run, snapshot):
    from scraper.fetch_reaper import reap_incomplete_fetches
    # Existing reaper defaults to 5 minutes; repairer deliberately waits 1 hour.
    rows = FetchRequest.objects.filter(state='reserved', reserved_at__lte=run.now - timedelta(hours=1)).order_by('reserved_at')
    for request_id in rows.values_list('request_id', flat=True)[:MAX_ACTIONS]:
        run.apply('fetch', request_id, lambda: reap_incomplete_fetches(
            now=run.now, max_age_seconds=3600, request_ids=[request_id], limit=1)['reaped'],
            'fixed', 'Zamknięto rezerwację jako abandoned istniejącym mechanizmem audytu.')


def repair_diagnoses(run, snapshot):
    from news.clinic import queue_for_diagnosis
    rows = SpinDiagnosis.objects.filter(status='failed', hidden_at__isnull=True,
        diagnosed_at__gte=run.now - timedelta(hours=48), diagnosed_at__lte=run.now,
        repair_attempts__lt=2).order_by('diagnosed_at')
    for candidate in rows.iterator():
        if not run.room:
            break
        if not transient(candidate.error):
            continue
        if '_daily_limit' in candidate.error and candidate.diagnosed_at.astimezone(WARSAW).date() == run.now.astimezone(WARSAW).date():
            continue
        def retry():
            row = SpinDiagnosis.objects.select_for_update().get(pk=candidate.pk)
            if row.status != 'failed' or row.repair_attempts >= 2 or row.hidden_at or not transient(row.error):
                return False
            queue_for_diagnosis(row)
            row.repair_attempts += 1
            row.save(update_fields=['repair_attempts'])
            return True
        run.apply('diagnosis', candidate.pk, retry, 'retried', 'Wpis wrócił do kolejki diagnoz; budżety obsługuje zwykły worker.')


def repair_archives(run, snapshot):
    from scraper.archive import MAX_ARCHIVE_ATTEMPTS
    rows = ArchiveJob.objects.filter(status='failed', attempts__lt=MAX_ARCHIVE_ATTEMPTS,
        available_at__lte=run.now, source__is_active=True, source__scrape_enabled=True).order_by('available_at')
    planned = 0
    for candidate in rows.iterator():
        if not run.room or planned >= 50:
            break
        if not transient(candidate.last_error):
            continue
        planned += 1
        def retry():
            # Preserve the backoff and attempts. The normal worker increments
            # attempts and enforces approved access before any network request.
            return ArchiveJob.objects.filter(pk=candidate.pk, status='failed',
                attempts=candidate.attempts, last_error=candidate.last_error,
                available_at__lte=run.now, source__is_active=True, source__scrape_enabled=True).update(status='pending')
        run.apply('archive', candidate.pk, retry, 'retried', 'Archiwum wróciło do kolejki; zachowano attempts i available_at.')


def importer_entry(name, entries):
    # Match only identities actually written by these importers.
    exact = {'official:votings': 'sejm-votes-15m', 'official:prints': 'sejm-prints-hourly',
             'official:eli': 'eli-hourly', 'quality:metadata': 'quality-5m',
             'quality:enrichment': 'quality-enrichment-5m',
             'public-figure:live-rosters': 'live-public-rosters-daily',
             'official-backfill:bzp:v1': 'bzp-metadata-3m'}
    key = exact.get(name)
    for prefix, beat in (('html-archive:kprm:', 'kprm-listing-minute'),
                         ('archive-discovery:', 'archive-discovery-daily'),
                         ('gdelt:', 'gdelt-2h'), ('official-backfill:votings:', 'voting-history-5m')):
        if name.startswith(prefix):
            key = beat
    return (key, entries[key]) if key in entries else (None, None)


def repair_importers(run, snapshot):
    from config.celery import app
    for row in ImportState.objects.exclude(last_error='').order_by('pk').iterator():
        if not run.room:
            break
        if not transient(row.last_error):
            continue
        name, entry = importer_entry(row.name, app.conf.beat_schedule)
        if not name:
            run.record('importer', row.pk, 'needs_owner', 'Brak jednoznacznego zadania beat dla importera; sprawdź jego konfigurację.')
            continue
        interval = cadence(entry['schedule'])
        last = row.last_success or row.last_started
        if interval and last and (run.now - last).total_seconds() > 2 * interval:
            retry_task(run, name, entry)


def repair_interviews(run, snapshot):
    from news.clinic_interview import enabled, queue_interview, video_id
    if not enabled():
        return
    # Only the latest material is the panel's interview of the day.
    row = ClinicInterview.objects.order_by('-day', '-created_at').first()
    if not row or row.status != 'failed' or row.hidden_at or row.repair_attempts >= 1 or not transient(row.error):
        return
    def retry():
        current = ClinicInterview.objects.select_for_update().get(pk=row.pk)
        if current.status != 'failed' or current.repair_attempts or current.hidden_at or not transient(current.error):
            return False
        if video_id(current.url) != current.video_id:
            return False  # Never let update_or_create create a different interview.
        queue_interview(current.url, day=current.day, user=current.created_by)
        current.repair_attempts += 1
        current.save(update_fields=['repair_attempts'])
        return True
    run.apply('interview', row.pk, retry, 'retried', 'Wywiad wrócił do kolejki (jedyne automatyczne ponowienie).')


def owner_items(snapshot):
    """Classified, stable instructions only: no arbitrary titles/errors in mail."""
    from config.celery import app
    result = {}
    for action in snapshot.get('actions', []):
        section = action.get('section', '')
        detail = action.get('detail', '')
        display = section
        if section == 'Naprawiacz':
            continue
        if section == 'Konsylium' and '429' in detail:
            continue
        if section == 'Zadania w tle':
            title = action['title'].removesuffix(' — naprawiacz ponawia')
            name = next((n for n in app.conf.beat_schedule if title == 'Sprawdź ' + n), None)
            pulse = cache.get('heartbeat:' + name, {}) if name else {}
            if name and app.conf.beat_schedule[name]['task'] in SAFE_TASKS and not permanent(detail) and pulse.get('repair_error') != 'permanent':
                continue
            detail = pulse.get('repair_hint') or detail
            display = name or section
        if section == 'Portfele':
            from news.wallet_models import PROVIDERS
            display = next((label for _, label in PROVIDERS if action['title'] == 'Sprawdź saldo / doładuj ' + label), section)
            hint = 'Sprawdź saldo dostawcy, doładuj konto i uaktualnij portfel w panelu.'
        elif '402' in detail:
            hint = '402: doładuj konto dostawcy; naprawiacz nie wydaje pieniędzy.'
        elif section == 'Serwer (VPS)':
            hint = 'Sprawdź wolny dysk i RAM na VPS; zwolnij miejsce lub zwiększ zasoby.'
        elif section == 'Konsylium':
            hint = 'Sprawdź konfigurację i środki dostawcy; skład obsługuje Rekruter.'
        elif permanent(detail) or any(w in detail.lower() for w in ('klucza', 'autoryzacji', 'uprawnień', 'konfigur')):
            hint = 'Sprawdź klucz, uprawnienia i konfigurację dostawcy na serwerze.'
        elif section == 'Zadania w tle':
            hint = 'Sprawdź zadanie w panelu i logach; automatyczne ponowienie nie ma potwierdzonego bezpieczeństwa kosztów.'
        else:
            continue
        identity = hashlib.sha256((section + action['title'] + hint).encode()).hexdigest()[:16]
        result[identity] = {'id': identity, 'title': display, 'hint': hint}
    # Raw stored errors are classified locally; safe_error intentionally hides
    # e.g. missing_key, so the panel alone cannot identify all permanent errors.
    for label, query, field in (
        ('Diagnoza', SpinDiagnosis.objects.filter(status='failed'), 'error'),
        ('Wywiad', ClinicInterview.objects.filter(status='failed'), 'error'),
        ('Importer', ImportState.objects.exclude(last_error=''), 'last_error'),
        ('Archiwum', ArchiveJob.objects.filter(status='failed'), 'last_error'),
    ):
        for row in query.only('pk', field).iterator():
            error = getattr(row, field)
            if permanent(error):
                identity = f'{label}:{row.pk}'
                hint = safe_error(error) + ' Sprawdź środki, klucz i konfigurację; decyzja należy do właściciela.'
                result[identity] = {'id': identity, 'title': identity, 'hint': hint}
    for row in ImportState.objects.exclude(last_error='').only('pk', 'name', 'last_error'):
        if transient(row.last_error) and importer_entry(row.name, app.conf.beat_schedule)[0] is None:
            identity = f'Importer:{row.pk}'
            result[identity] = {'id': identity, 'title': identity,
                                'hint': 'Sprawdź konfigurację importera: brak jednoznacznego zadania beat do ponowienia.'}
    pulses = cache.get_many(['heartbeat:' + name for name in app.conf.beat_schedule])
    for name in app.conf.beat_schedule:
        pulse = pulses.get('heartbeat:' + name, {})
        if 'nieskonfigurowane' in pulse.get('summary', '').lower():
            identity = 'task-config:' + name
            result[identity] = {'id': identity, 'title': name,
                                'hint': 'Zadanie zgłasza brak konfiguracji. Sprawdź wymagane klucze i ustawienia na serwerze.'}
    # New, nonurgent automatic actions join the existing morning digest.
    from news.council_health import day_start
    for row in RepairAction.objects.filter(created_at__gte=day_start(timezone.now()) - timedelta(days=1),
            rule__in=['auditor:bench', 'auditor:roles', 'auditor:diagnose']):
        identity = 'audit:' + str(row.pk)
        result[identity] = {'id': identity, 'title': 'Audytor wykonał odwracalne działanie.',
            'automatic': {'auditor:bench': 'Model trafił na ławkę do północy.',
                          'auditor:roles': 'Ustalono kolejność zapasowych według sukcesów.',
                          'auditor:diagnose': 'Zlecono dodatkowy przebieg diagnoz.'}[row.rule],
            'hint': 'Nie musisz nic robić; szczegóły: https://spin.clinic/admin/'}
    return sorted(result.values(), key=lambda item: item['id'])


def notify_problem(run, identity, active, happened, automatic, next_step):
    """One shared urgent/resolved mail channel. Inputs must be code-owned text.

    None means unknown: absence of observations is never recovery evidence.
    Reserve durably before SMTP, so concurrent workers cannot duplicate mail.
    """
    if active is None:
        return
    from news.council_recruiter import _owner_email
    from news.social_publish import _mail
    key = 'alert:' + hashlib.sha256(identity.encode()).hexdigest()[:32]
    if run.dry_run:
        return
    with transaction.atomic():
        row, _ = RepairerState.objects.get_or_create(key=key)
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        data = row.data or {}
        last = stamp(data.get('attempted_at'))
        resolved = not active and data.get('reported', False) and not data.get('resolved', False)
        due = active and (not last or run.now - last >= timedelta(hours=6))
        if not (due or resolved):
            return
        # Recovery reserves its own transition before SMTP. A failed recovery
        # is retried on the next observation, without marking it delivered.
        if data.get('sending_until') and stamp(data['sending_until']) > run.now:
            return
        data.update(sending_until=(run.now + timedelta(minutes=5)).isoformat())
        if due:
            data.update(attempted_at=run.now.isoformat(), resolved=False)
        row.data = data
        row.save(update_fields=['data'])
    subject = 'spin.clinic · Naprawiacz: ' + ('rozwiązane' if resolved else 'pilne — wymaga Ciebie')
    body = (f'Co się stało: {happened}\nCo zrobiono automatycznie: {automatic}\n'
            f'Co dalej: {"Problem ustąpił. Nie musisz nic robić." if resolved else next_step}')
    try:
        ok = _mail(_owner_email(), subject, body)
    except Exception:
        ok = False
    with transaction.atomic():
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        data = {**row.data, 'sending_until': None}
        if ok:
            data.update(reported=True, resolved=resolved)
        row.data = data
        row.save(update_fields=['data'])
    run.record('owner_mail', identity, 'needs_owner' if ok and not resolved else 'fixed' if ok else 'failed',
               'Wysłano mail: rozwiązane.' if ok and resolved else 'Wysłano pilne zgłoszenie.' if ok else 'Nie wysłano maila; sprawdź SMTP.')


def provider_event(provider, error=None):
    """Called on real provider outcomes, including failures swallowed by fallbacks."""
    if provider not in ('x', 'gemini', 'anthropic'):
        return
    from news.council_health import error_kind
    code = error_kind(error)
    active = code == '402' or 'credit balance' in str(error).lower()
    if not active and error is not None:
        return  # 429/timeout does not prove the wallet recovered.
    try:
        now = timezone.now()
        RepairerState.objects.update_or_create(key='wallet-event:' + provider,
            defaults={'data': {'active': active, 'at': now.isoformat()}})
        notify_problem(Run(now), 'wallet:' + provider, active,
            f'{provider}: brak środków (402).' if active else f'{provider}: dostawca znów przyjmuje zapytania.',
            'Zapisano stan portfela; automatyka nie doładowuje kont.',
            f'Doładuj konto {provider} u dostawcy.')
    except Exception:
        pass  # Provider outcomes must not depend on SMTP or telemetry storage.


def wallet_observed(provider):
    from functools import wraps
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                provider_event(provider, getattr(exc, 'code', str(exc)))
                raise
            provider_event(provider)
            return result
        return call
    return decorate


def operational_notifications(run, snapshot=None):
    from news import clinic, clinic_council as council, council_registry as registry
    from news.council_auditor import pending
    from news.council_health import day_start, error_kind
    from news.clinic_models import CouncilSeat, InquisitorReview
    from news.political_models import PoliticalPost
    from django.db.models import Max
    local = run.now.astimezone(WARSAW)
    daytime = 7 <= local.hour <= 23
    if daytime:
        start = day_start(run.now).replace(hour=7)
        queue = pending(run.now)
        last = SpinDiagnosis.objects.exclude(verdict='').exclude(status='failed').aggregate(last=Max('diagnosed_at'))['last']
        oldest = queue.order_by('created_at').values_list('created_at', flat=True).first()
        stalled = bool(oldest and run.now - max(start, oldest, last or start) >= timedelta(hours=3))
        diagnosis_state = True if stalled else False if not oldest or (last and last >= start and run.now - last < timedelta(hours=3)) else None
        retried = RepairAction.objects.filter(rule='auditor:diagnose', result='retried', created_at__gte=run.now - timedelta(hours=1)).exists()
        notify_problem(run, 'diagnoses-stalled', diagnosis_state, 'Brak diagnoz od co najmniej 3 godzin przy niepustej kolejce.',
            'Zlecono dodatkowy przebieg diagnoz.' if retried else 'Sprawdzono kolejkę i czas ostatniej diagnozy; brak potwierdzonego dodatkowego przebiegu w ostatniej godzinie.',
            'Uruchom: python manage.py council_audit --dry-run')
        last_x = PoliticalPost.objects.aggregate(last=Max('fetched_at'))['last']
        stale_x = run.now - max(start, last_x or start) >= timedelta(hours=2)
        x_state = True if stale_x else False if last_x and last_x >= start and run.now - last_x < timedelta(hours=2) else None
        notify_problem(run, 'x-stalled', x_state, 'Brak nowych wpisów z X od co najmniej 2 godzin.',
            'Naprawiacz sprawdza zadania pobierania; nie zmienia limitów X.',
            'Sprawdź odczyty X w panelu: https://spin.clinic/admin/')
    members = council._members('CLINIC_COUNCIL', council.DEFAULT_COUNCIL)
    available = sum(registry.available(m) for m in members)
    state = RepairerState.objects.filter(key='council-low-since').first()
    since = stamp((state.data if state else {}).get('since'))
    low = available < council.MIN_MEMBERS
    if low and not since:
        since = run.now
    if not run.dry_run:
        RepairerState.objects.update_or_create(key='council-low-since', defaults={'data': {'since': since.isoformat() if low else None}})
    if not low or run.now - since >= timedelta(hours=2):
        reasons = Counter(error_kind(s.last_error) if s.status != 'suspended' else 'suspended' for s in CouncilSeat.objects.all())
        reasons.update('daily_limit' if registry.configured(m) else 'configuration' for m in members if not registry.available(m))
        description = f'Dostępnych członków: {available}; wymagane {council.MIN_MEMBERS}. Przyczyny: {dict(reasons)}.'
        if low:
            run.record('auditor:quorum', 'council', 'needs_owner', description)
        notify_problem(run, 'council-quorum', low, description,
            'Sprawdzono dostępność, limity i ławkę; skład bez zmian.',
            'Sprawdź konfigurację i limity dostawców: python manage.py council_audit --dry-run')
    # Adopt already recorded wallet failures after deployment; later recovery
    # requires a real success (never simply expiry of the historical window).
    from news.admin_finance import provider_signals
    for provider in provider_signals(run.now):
        if not run.dry_run:
            RepairerState.objects.get_or_create(key='wallet-event:' + provider,
                defaults={'data': {'active': True, 'at': run.now.isoformat()}})
    for state in RepairerState.objects.filter(key__startswith='wallet-event:'):
        provider = state.key.split(':', 1)[1]
        if provider in ('x', 'gemini', 'anthropic'):
            notify_problem(run, 'wallet:' + provider, state.data['active'], f'{provider}: brak środków (402).',
                'Zapisano stan portfela; nie zmieniono budżetu.', f'Doładuj konto {provider} u dostawcy.')
    from news.inquisitor import review_url
    for review in InquisitorReview.objects.filter(verdict='error'):
        notify_problem(run, f'inquisitor:{review.pk}', not bool(review.decided_at), 'Obaj recenzenci wskazali błąd diagnozy.',
            'Zapisano kontrolę do decyzji; treść diagnozy bez zmian.', 'Zatwierdź albo odrzuć: ' + review_url(review))


def owner_digest(run, snapshot):
    from news.council_recruiter import _owner_email
    from news.social_publish import _mail
    local = run.now.astimezone(WARSAW)
    if local.hour != 8 or not run.room:
        return
    items = owner_items(snapshot)
    day = local.date().isoformat()
    state = RepairerState.objects.filter(key='owner-mail').first()
    previous = state.data if state else {}
    hashes = sorted(hashlib.sha256(json.dumps(i, sort_keys=True).encode()).hexdigest() for i in items)
    if previous.get('day') == day:
        return
    new = set(hashes) - set(previous.get('hashes', []))
    if not items or not new:
        if not run.dry_run:
            RepairerState.objects.update_or_create(key='owner-mail', defaults={'data': {'day': day, 'hashes': hashes}})
        return
    if run.dry_run:
        run.record('owner_mail', day, 'needs_owner', f'DRY RUN: wysłałby zbiorczy mail; pozycji: {len(items)}.')
        return
    # Persist before SMTP: no duplicate mail after a worker crash/ambiguous SMTP
    # response. On failure retain old hashes and try on the next day only.
    RepairerState.objects.update_or_create(key='owner-mail', defaults={'data': {'day': day, 'hashes': previous.get('hashes', [])}})
    body = 'Wymaga Ciebie:\n\n' + '\n\n'.join(
        f"Co się stało: {i['title']}\nCo zrobiono automatycznie: {i.get('automatic', 'Naprawiacz sprawdził problem; nie zmienia środków ani konfiguracji.')}\nCo dalej: {i['hint']}" for i in items)
    ok = _mail(_owner_email(), 'spin.clinic · Naprawiacz: wymaga Ciebie', body)
    if ok:
        RepairerState.objects.filter(key='owner-mail').update(data={'day': day, 'hashes': hashes})
    run.record('owner_mail', day, 'needs_owner' if ok else 'failed',
               f'Wysłano zbiorczy mail; pozycji: {len(items)}.' if ok else 'Nie wysłano maila; sprawdź SMTP i adres właściciela.')


def panel_section(now, snapshot):
    from news.admin_status import card, metric
    recent = RepairAction.objects.filter(created_at__gte=now - timedelta(hours=24))
    counts = dict(recent.order_by().values_list('result').annotate(count=Count('pk')))
    last = RepairerState.objects.filter(key='last-run').first()
    items = [card(f'{r.rule} · {r.target}', 'error' if r.result == 'failed' else 'warn' if r.result == 'needs_owner' else 'ok',
                  f'{r.result}: {r.description}', r.created_at) for r in RepairAction.objects.all()[:10]]
    needs = owner_items(snapshot)
    items.append(card('Wymaga Ciebie', 'warn' if needs else 'ok',
                      'Pieniądze, klucze, zasoby i decyzje właściciela.', items=[
                          card(i['title'], 'warn', i['hint']) for i in needs]))
    return card('Naprawiacz', 'ok' if last else 'unknown',
                'Bezpieczne naprawy co 15 minut. Limit 20 działań; dziennik 30 dni.',
                last.data.get('at') if last else None,
                [metric('Włączony', flag('REPAIRER_ENABLED', True)), metric('Tryb próbny', flag('REPAIRER_DRY_RUN', False))] +
                [metric(s, counts.get(s, 0)) for s in ('fixed', 'retried', 'skipped', 'failed', 'needs_owner')], items)


def annotate_actions(actions, now):
    targets = set(RepairAction.objects.filter(rule='task', result='retried',
        created_at__gte=now - timedelta(hours=1)).values_list('target', flat=True))
    for action in actions:
        if action.get('section') == 'Zadania w tle' and action['title'] in {'Sprawdź ' + n for n in targets}:
            action['title'] += ' — naprawiacz ponawia'
        elif action.get('section') == 'Źródła / harvestery':
            from config.celery import app
            name = action['title'].removeprefix('Sprawdź ')
            if importer_entry(name, app.conf.beat_schedule)[0] in targets:
                action['title'] += ' — naprawiacz ponawia'
        elif action.get('section') in ('Diagnozy', 'Wywiad dnia'):
            model, rule = (SpinDiagnosis, 'diagnosis') if action['section'] == 'Diagnozy' else (ClinicInterview, 'interview')
            ids = RepairAction.objects.filter(rule=rule, result='retried', created_at__gte=now - timedelta(hours=1)).values_list('target', flat=True)
            queued_errors = model.objects.filter(pk__in=[int(i) for i in ids if i.isdigit()], status='queued').values_list('error', flat=True)
            if any(safe_error(e) == action.get('detail') for e in queued_errors if e):
                action['title'] += ' — naprawiacz ponawia'
    return actions


RULES = (repair_locks, repair_fetches, repair_diagnoses, repair_archives, repair_importers, repair_interviews, repair_tasks)


def run(*, dry_run=False, now=None):
    if not flag('REPAIRER_ENABLED', True):
        return {'status': 'disabled', 'actions': []}
    ctx = Run(now or timezone.now(), dry_run or flag('REPAIRER_DRY_RUN', False))
    token = uuid4().hex
    if not cache.add(RUN_LOCK, token, 600):
        return {'status': 'locked', 'actions': []}
    try:
        from news.admin_status import snapshot
        data = snapshot(ctx.now)
        # Daily mail gets a slot even when there is a large repair backlog.
        for rule in (operational_notifications, owner_digest, *RULES):
            if not ctx.room:
                break
            try:
                rule(ctx, data)
            except Exception as exc:
                ctx.record(rule.__name__, 'rule', 'failed', safe_error(exc))
        if not ctx.dry_run:
            RepairAction.objects.filter(created_at__lt=ctx.now - timedelta(days=30)).delete()
            RepairerState.objects.update_or_create(key='last-run', defaults={'data': {'at': ctx.now.isoformat()}})
        return {'status': 'ok', 'dry_run': ctx.dry_run, 'actions': ctx.actions,
                'failed': sum(a['result'] == 'failed' for a in ctx.actions)}
    finally:
        compare_delete(RUN_LOCK, token)
