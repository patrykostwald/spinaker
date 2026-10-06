"""Deterministic duty officer: database/cache only, no model or mail calls."""
import math
import os
import re
from datetime import timedelta
from statistics import median
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.models import DutyAlarm, ImportState, RepairerState, Source
from news.political_models import AccountWardenRun, PoliticalAccount
from news.repairer import Run, SAFE_TASKS, compare_delete, flag, importer_entry, permanent, retry_task, stamp
from news.task_heartbeat import cadence

WARSAW = ZoneInfo('Europe/Warsaw')


def budget_limit():
    try:
        value = float(os.environ.get('CLINIC_DAILY_BUDGET_USD', '0'))
        return max(0, value) if math.isfinite(value) else 0
    except ValueError:
        return 0


def diagnosis_costs(now, days=7):
    # Pure local tariff calculation; cost_usd does not call a provider.
    from news.clinic_ai import cost_usd
    return [(row['pk'], row['diagnosed_at'], cost_usd(row['usage'] or {})) for row in
            SpinDiagnosis.objects.filter(diagnosed_at__gte=now - timedelta(days=days), diagnosed_at__lte=now)
            .values('pk', 'diagnosed_at', 'usage')]


def daily_costs(now):
    from news.clinic_ai import cost_usd
    from news.account_warden import USER_PRICE
    start = now.astimezone(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)
    interviews = ClinicInterview.objects.filter(diagnosed_at__gte=start, diagnosed_at__lte=now)
    return {'diagnoses': round(sum(cost for _, at, cost in diagnosis_costs(now, 1) if at >= start), 6),
            'interviews': round(sum(cost_usd((u or {}).get(part) or {}) for u in interviews.values_list('usage', flat=True)
                                    for part in ('claude', 'gemini')), 6),
            'warden': float(sum(AccountWardenRun.objects.filter(started_at__gte=start, started_at__lte=now)
                                .values_list('lookups', flat=True)) * USER_PRICE),
            'replies': _replies_cost(now),
            'krs': cache.get(f'krs-agent-spent:{start.date().isoformat()}')}


def _replies_cost(now):
    try:
        from news.odbior_spinu import daily_cost
        return daily_cost(now)['usd']
    except Exception:  # noqa: BLE001 - koszt pomocniczy nie zatrzymuje Dyżurnego
        return None


class Context:
    def __init__(self, now):
        from config.celery import app
        self.now = now
        self.entries = app.conf.beat_schedule
        self.pulses = cache.get_many(['heartbeat:' + name for name in self.entries])
        self.state, _ = RepairerState.objects.get_or_create(key='duty-observations')
        self.observations = dict(self.state.data)
        self.seen = set()

    def since(self, key, seed=None):
        self.seen.add(key)
        previous = stamp(self.observations.get(key))
        value = previous or min(seed or self.now, self.now)
        self.observations[key] = value.isoformat()
        return value

    def save(self):
        self.state.data = {key: value for key, value in self.observations.items() if key in self.seen}
        self.state.save(update_fields=['data'])


def alarm(key, severity, title, details, since, instruction, repairer=''):
    return dict(key=key, severity=severity, title=title, details=details, since=since,
                instruction=instruction, repairer=repairer)


def check_budget(ctx):
    start = ctx.now.astimezone(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)
    costs = diagnosis_costs(ctx.now)
    today = [(pk, at, cost) for pk, at, cost in costs if at >= start]
    spent, limit = sum(c for _, _, c in today), budget_limit()
    alarms = []
    if spent > limit or (limit > 0 and spent >= .8 * limit):
        alarms.append(alarm('budget:daily', 'critical' if spent > limit else 'warning',
            'Budżet diagnoz: przekroczony' if spent > limit else 'Budżet diagnoz: co najmniej 80%',
            {'spent_usd': round(spent, 6), 'limit_usd': limit, 'percent': round(100 * spent / limit, 1) if limit else None},
            start, 'Sprawdź koszty diagnoz i ustaw twardy dzienny limit w USD.'))
    baseline = [cost for _, at, cost in costs if at < start]
    if baseline:
        typical = median(baseline)
        for pk, at, cost in today:
            if cost > 2 * typical:
                alarms.append(alarm(f'budget:diagnosis:{pk}', 'warning', 'Diagnoza droższa niż dwie mediany',
                    {'diagnosis_id': pk, 'cost_usd': round(cost, 6), 'median_usd': round(typical, 6), 'sample': len(baseline)},
                    at, 'Sprawdź zapisane zużycie i model tej diagnozy.'))
    return alarms


def check_warden(ctx):
    rows = AccountWardenRun.objects.filter(started_at__gte=ctx.now - timedelta(days=1), started_at__lte=ctx.now)
    disabled = sum(sum(e.get('kind') == 'disabled' for e in (row.report or {}).get('events', [])) for row in rows)
    public_ids = set(PoliticalAccount.objects.filter(camp='public', enabled=False).values_list('pk', flat=True))
    if disabled > 3 or public_ids:
        return [alarm('warden:disabled', 'critical', 'Strażnik kont: sprawdź wyłączenia',
            {'disabled_24h': disabled, 'public_disabled': len(public_ids), 'account_ids': sorted(public_ids)},
            ctx.since('warden:disabled'), 'Zweryfikuj wyłączone konta w panelu i przywróć błędnie wyłączone.')]
    return []


def check_importers(ctx):
    alarms = []
    for row in ImportState.objects.filter(last_success__isnull=True):
        if 'no_approved_instruction' in row.last_error:
            # An owner decision is pending, not a failed importer.
            continue
        name, entry = importer_entry(row.name, ctx.entries)
        since = ctx.since(f'import:{row.pk}', row.last_started)
        interval = cadence(entry['schedule']) if entry else None
        age = (ctx.now - since).total_seconds()
        if (row.last_error and age > 86400) or (interval and age > 3 * interval):
            repair = name if name and not permanent(row.last_error) and 'host_rate_limited' not in row.last_error else ''
            alarms.append(alarm(f'import:{row.pk}', 'critical' if row.last_error else 'warning',
                'Importer nigdy nie zakończył się sukcesem',
                {'importer': row.name, 'hours': round(age / 3600, 1), 'cadence_seconds': interval, 'imported': row.imported},
                since, 'Sprawdź konfigurację i zatwierdzony dostęp importera.', repair or ''))
    return alarms


def check_tasks(ctx):
    from news.agent_registry import task_enabled
    alarms = []
    for name, entry in ctx.entries.items():
        if not task_enabled(entry['task']):
            continue
        pulse = ctx.pulses.get('heartbeat:' + name, {})
        interval = cadence(entry['schedule'])
        last = stamp(pulse.get('last_event')) or ctx.since('task:' + name)
        failures = pulse.get('consecutive_errors', 0)
        if (interval and (ctx.now - last).total_seconds() > 3 * interval) or failures >= 3:
            repair = name if pulse.get('repair_error') != 'permanent' else ''
            alarms.append(alarm('task:' + name, 'critical' if failures >= 3 else 'warning',
                'Zadanie bez pulsu lub z serią błędów',
                {'beat': name, 'hours': round((ctx.now - last).total_seconds() / 3600, 1),
                 'cadence_seconds': interval, 'consecutive_errors': failures},
                stamp(pulse.get('error_since')) or last, 'Sprawdź zadanie i konfigurację workera w panelu.', repair))
    if flag('AGENTS_ENABLED', False):
        row = RepairerState.objects.filter(key='agents-window').first()
        data = row.data if row else {}
        last = stamp(data.get('last_success')) or ctx.since('agents:no-success', stamp(data.get('first_attempt')))
        if ctx.now - last >= timedelta(hours=24):
            alarms.append(alarm('agents:no-success', 'critical', 'Strateg i Pielgrzym: doba bez udanego biegu',
                {'hours': round((ctx.now - last).total_seconds() / 3600, 1)}, last,
                'Sprawdź dostępność i limity darmowych modeli Konsylium.'))
    return alarms


def check_interviews(ctx):
    from django.db.models.functions import Coalesce
    rows = list(ClinicInterview.objects.exclude(status__in=['queued', 'flagged']).filter(created_at__lte=ctx.now)
                .annotate(at=Coalesce('diagnosed_at', 'created_at')).order_by('-at', '-pk')[:3])
    failures = []
    for row in rows:
        if row.status != 'failed':
            break
        failures.append(row)
    wallet = any(re.search(r'(?<!\d)402(?!\d)|insufficient|billing|credit balance', row.error, re.I) for row in failures)
    if wallet or len(failures) >= 3:
        return [alarm('interviews:failures', 'critical', 'Wywiady: doładuj portfel' if wallet else 'Wywiady: seria błędów',
            {'consecutive_errors': len(failures), 'billing': wallet}, failures[-1].at,
            'Doładuj portfel dostawcy wywiadów i ponów wywiad w panelu.' if wallet else 'Sprawdź błąd i konfigurację wywiadów w panelu.')]
    return []


def check_diagnoses(ctx):
    from news.clinic import budget_left, diagnosis_reserve
    if budget_left() < diagnosis_reserve():
        return []
    local = ctx.now.astimezone(WARSAW)
    if not 8 <= local.hour < 22:
        return []
    queue = SpinDiagnosis.objects.filter(status__in=['queued', 'flagged'], hidden_at__isnull=True, post__available=True)
    oldest = queue.order_by('created_at').values_list('created_at', flat=True).first()
    last = SpinDiagnosis.objects.exclude(verdict='').exclude(status='failed').filter(diagnosed_at__lte=ctx.now).aggregate(at=Max('diagnosed_at'))['at']
    since = max(oldest, last or oldest) if oldest else None
    if since and ctx.now - since >= timedelta(hours=3):
        return [alarm('diagnoses:stalled', 'critical', 'Diagnozy: kolejka stoi od trzech godzin',
            {'queued': queue.count(), 'hours': round((ctx.now - since).total_seconds() / 3600, 1)}, since,
            'Sprawdź budżet i dostępność modeli diagnoz.', 'clinic-diagnoses-day')]
    return []


def check_rate_limits(ctx):
    alarms = []
    for row in ImportState.objects.filter(name__in=['official:votings', 'official:prints', 'official:eli'],
                                           last_error__startswith='host_rate_limited'):
        since = ctx.since(f'host:{row.pk}', row.last_started)
        if row.last_success and row.last_success > since:
            since = row.last_started or ctx.now
            ctx.observations[f'host:{row.pk}'] = since.isoformat()
        if ctx.now - since > timedelta(hours=6):
            alarms.append(alarm(f'host:{row.pk}', 'critical', 'Oficjalne źródło: blokada limitu ponad sześć godzin',
                {'importer': row.name, 'hours': round((ctx.now - since).total_seconds() / 3600, 1)}, since,
                'Sprawdź limit hosta Sejmu lub ELI i termin wznowienia, zachowując blokady dostępu.'))
    return alarms


from news import duty_extra  # noqa: E402 - kontrole dopisane 5.10 (zbieracz X, dostawcy modeli, spinki, produkty dnia)

CHECKS = (check_budget, check_warden, check_importers, check_tasks, check_interviews, check_diagnoses, check_rate_limits,
          *duty_extra.CHECKS)


def dispatch(row, ctx, repair_run):
    if not row.repairer:
        return
    # Naprawiacz opisuje propozycję; tylko Ratownik uruchamia naprawy harmonogramu.
    row.dispatch_note = 'Propozycja: sprawdź zadanie ' + row.repairer + '. Decyzja należy do właściciela.'
    row.save(update_fields=['dispatch_note'])


def run(now=None):
    """Każda kontrola osobno (właściciel 6.10): błąd jednej zapisuje własny alarm z powodem, reszta działa dalej.
    Bieg z błędami części kontroli kończy się „partial” (zielony puls z notatką), a nie błędem całego Dyżurnego."""
    if not flag('DUTY_ENABLED', True):
        return {'status': 'disabled'}
    from news.task_heartbeat import error_text
    now = now or timezone.now()
    token = uuid4().hex
    if not cache.add('duty:lock', token, 180):
        return {'status': 'locked'}
    try:
        ctx, repair_run = Context(now), Run(now)
        failed = []

        def guarded(name, step):
            try:
                step()
            except Exception as error:  # noqa: BLE001 - jedna kontrola nie zatrzymuje pozostałych
                failed.append(f'{name}: {error_text(error)}')
                return False
            return True

        for check in CHECKS:
            name = check.__name__
            found = []
            if not guarded(name, lambda: found.extend(check(ctx))):
                # Brak dowodu nie zamyka alarmów tej kontroli; powód błędu w szczegółach alarmu.
                guarded(name + ':health', lambda: reconcile(name + ':health', [alarm(
                    'check:' + name, 'warning', 'Dyżurny: nie udało się wykonać kontroli',
                    {'check': name, 'error': failed[-1].split(': ', 1)[1]}, now, 'Sprawdź logi workera Dyżurnego.')],
                    ctx, repair_run))
                continue
            guarded(name + ':health', lambda: reconcile(name + ':health', [], ctx, repair_run))
            guarded(name, lambda: reconcile(name, found, ctx, repair_run))
        guarded('observations', ctx.save)
        guarded('notify_owner', lambda: duty_extra.notify_owner(now))  # mail: nowe alarmy krytyczne od razu, otwarte co 6 h
        from news.rescuer import guard
        guarded('rescuer', lambda: guard(now))
        open_count = DutyAlarm.objects.filter(status='open').count()
        if failed:
            return {'status': 'partial', 'check_errors': len(failed), 'partial': '; '.join(failed)[:400], 'open': open_count}
        return {'status': 'ok', 'check_errors': 0, 'open': open_count}
    finally:
        compare_delete('duty:lock', token)


def reconcile(check, alarms, ctx, repair_run):
    keys = []
    for data in alarms:
        keys.append(data['key'])
        with transaction.atomic():
            row, _ = DutyAlarm.objects.get_or_create(key=data['key'], defaults={'rule': check, 'first_seen': ctx.now, **data})
            row = DutyAlarm.objects.select_for_update().get(pk=row.pk)
            for key, value in data.items():
                setattr(row, key, value)
            row.status, row.closed_at, row.last_seen = 'open', None, ctx.now
            row.occurrences += 1
            row.save()
        dispatch(row, ctx, repair_run)
    DutyAlarm.objects.filter(rule=check, status='open').exclude(key__in=keys).update(status='closed', closed_at=ctx.now, last_dispatch_at=None)


def panel_section(now):
    from news.admin_status import card, metric
    rows = list(DutyAlarm.objects.filter(status='open'))
    critical = sum(row.severity == 'critical' for row in rows)
    items = [card(row.title, 'error' if row.severity == 'critical' else 'warn',
                  row.instruction + (' ' + row.dispatch_note if row.dispatch_note else ''), row.since,
                  [metric(key, value) for key, value in row.details.items()]) for row in rows]
    return card('Dyżurny', 'error' if critical else 'warn' if rows else 'ok',
        'Kontrola wyników co 15 min, bez wywołań modeli.', metrics=[metric('Krytyczne', critical),
        metric('Uwagi', len(rows) - critical), metric('Najstarszy alarm', min((row.since for row in rows), default=None)),
        metric('Źródła bez karty dostępu', Source.objects.filter(access_instructions__isnull=True).exclude(catalog_stage='excluded').count()),
        metric('Importery bez zatwierdzonej karty', ImportState.objects.filter(last_error__contains='no_approved_instruction').count()),
        metric('Włączony', flag('DUTY_ENABLED', True))], items=items)
