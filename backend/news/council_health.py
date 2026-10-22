"""Local observations only. Error codes are allowlisted; never retain API bodies."""
import hashlib
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')


def error_kind(error):
    text = str(error or '').lower()
    if not text:
        return 'ok'
    for code in ('402', '429', '401', '403', '404'):
        if re.search(rf'(?<!\d){code}(?!\d)', text):
            return code
    for token, kind in (('timeout', 'timeout'), ('timed out', 'timeout'),
                        ('daily_limit', 'daily_limit'), ('rate_limit', '429'),
                        ('council_too_few_members', 'too_few'), ('connection', 'connection'),
                        ('key_missing', 'configuration'), ('invalid', 'invalid')):
        if token in text:
            return kind
    if re.search(r'(?<!\d)5\d\d(?!\d)', text):
        return 'server'
    return 'other'


def day_start(now):
    return now.astimezone(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)


def bench_key(member, now=None):
    now = now or timezone.now()
    digest = hashlib.sha256(':'.join(member).encode()).hexdigest()[:24]
    return f'council:bench:{day_start(now).date()}:{digest}'


QUORUM = 3  # tyle członków musi zostać poza ławką (MIN_MEMBERS w clinic_council)


def bench(member, now, kind='402'):
    """Brak środków (402): ławka do północy. Chwilowe limity (429) i przekroczenia czasu: tylko godzina."""
    until_midnight = max(1, int((day_start(now) + timedelta(days=1) - now).total_seconds()))
    ttl = until_midnight if kind == '402' else min(3600, until_midnight)
    return cache.add(bench_key(member, now), True, ttl)


def adjust_roles(name, members):
    now = timezone.now()
    active = [m for m in members if not cache.get(bench_key(m, now))]
    # Ławka nigdy nie może odebrać Konsylium kworum — wtedy pytamy wszystkich, jak przed audytorem.
    members = active if name != 'CLINIC_COUNCIL' or len(active) >= QUORUM else members
    if name != 'CLINIC_COUNCIL':
        scores = cache.get(f'council:ranking:{day_start(now).date()}', {})
        members.sort(key=lambda m: -scores.get(':'.join(m), 0))
    return members


def record(member, error, seconds):
    from news.clinic_models import CouncilCall
    # Telemetry must not turn a successful model answer into a failed diagnosis.
    try:
        CouncilCall.objects.create(provider=member[0], model=member[1],
                                   outcome=error_kind(error), seconds=max(0, seconds))
    except Exception:
        pass
    if error is None:
        cache.delete(bench_key(member))  # udana odpowiedź od razu zdejmuje z ławki (np. po doładowaniu)
    from news.repairer import provider_event
    provider_event(member[0], error)


def record_run(result):
    from django.db import transaction
    from news.models import RepairerState
    from news.task_heartbeat import summary
    try:
        with transaction.atomic():
            state, _ = RepairerState.objects.get_or_create(key='diagnosis-runs')
            state = RepairerState.objects.select_for_update().get(pk=state.pk)
            status = result.get('status', 'unknown')
            if status not in ('ok', 'disabled', 'budget', 'night', 'too_many_failures', 'limit', 'locked', 'error', 'quorum'):
                status = 'unknown'
            if status == 'ok' and result.get('budget_left') == 0:
                status = 'limit'
            state.data = {'runs': [{'at': timezone.now().isoformat(), 'status': status,
                'summary': summary(result)}, *state.data.get('runs', [])][:12]}
            state.save(update_fields=['data'])
    except Exception:
        pass  # A telemetry outage must not stop diagnoses.
