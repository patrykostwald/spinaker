"""Local Celery telemetry only; never retain task arguments or arbitrary results."""
import logging
from functools import lru_cache

from celery.signals import task_prerun, task_success, task_failure
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
TTL = 7 * 86400


def cadence(schedule):
    """Longest weekly gap, including night/weekend pauses, for our beat crontabs."""
    if hasattr(schedule, 'run_every'):
        return schedule.run_every.total_seconds()
    if schedule.day_of_month != set(range(1, 32)) or schedule.month_of_year != set(range(1, 13)):
        return None
    return _weekly_cadence(tuple(sorted(schedule.day_of_week)), tuple(sorted(schedule.hour)), tuple(sorted(schedule.minute)))


@lru_cache(maxsize=128)
def _weekly_cadence(days, hours, mins):
    minutes = sorted(d * 1440 + h * 60 + m for d in days for h in hours for m in mins)
    return max(b - a for a, b in zip(minutes, minutes[1:] + [minutes[0] + 10080])) * 60


def summary(result):
    # Results may contain personal data, credentials or entire model responses.
    if isinstance(result, dict):
        safe = [f'{key}: {value}' for key, value in result.items()
                if isinstance(key, str) and key.isidentifier() and len(key) <= 40
                and isinstance(value, (int, float, bool))]
        states = {'ok': 'OK', 'disabled': 'Wyłączone', 'not_configured': 'Nieskonfigurowane',
                  'locked': 'Zajęta blokada', 'already_running': 'Już działa', 'failed': 'Błąd',
                  'error': 'Błąd', 'too_many_failures': 'Zbyt wiele błędów', 'pominięto': 'Pominięto',
                  'blocked_access_review': 'Zablokowane: przegląd dostępu', 'brak odpowiedzi': 'Brak odpowiedzi'}
        if result.get('status') in states:
            safe.insert(0, states[result['status']])
        for key in ('completed', 'failed', 'errors', 'screened'):
            if isinstance(result.get(key), (dict, list)):
                safe.append(f'{key}: {len(result[key])}')
        return '; '.join(safe)[:240] or 'Zakończono; wynik szczegółowy nie jest zapisywany.'
    return 'Zakończono; wynik szczegółowy nie jest zapisywany.'


def record(sender, phase, task_id=None, args=None, kwargs=None, result=None, exception=None):
    from config.celery import app
    request = getattr(sender, 'request', None)
    args = args if args is not None else getattr(request, 'args', ()) or ()
    kwargs = kwargs if kwargs is not None else getattr(request, 'kwargs', {}) or {}
    task_id = task_id or getattr(request, 'id', None)
    try:
        for name, entry in app.conf.beat_schedule.items():
            if entry['task'] != sender.name or tuple(entry.get('args', ())) != tuple(args) or entry.get('kwargs', {}) != kwargs:
                continue
            key = f'heartbeat:{name}'
            previous = cache.get(key, {})
            if phase != 'running' and previous.get('task_id') not in (None, task_id):
                continue  # Do not overwrite a newer concurrent run.
            now = timezone.now().isoformat()
            data = {**previous, 'task_id': task_id, 'phase': phase, 'last_event': now}
            if phase == 'running':
                data.update(started_at=now, summary='Zadanie w toku.')
            else:
                data.update(finished_at=now, result=phase,
                            summary=type(exception).__name__ if exception else summary(result))
                # Retain a classification, never the exception message or a
                # provider response. Generic HTTPError can otherwise hide 402.
                from news.repairer import permanent, transient
                from news.admin_telemetry import safe_error
                error = (str(getattr(getattr(exception, 'response', None), 'status_code', '')) + ' ' + str(exception)
                         if exception else str(result.get('error', '')) if isinstance(result, dict) else '')
                data['repair_error'] = 'permanent' if permanent(error) else 'transient' if transient(error) else 'unknown'
                data['repair_hint'] = safe_error(error) if error.strip() else ''
            cache.set(key, data, TTL)
    except Exception:
        logger.warning('Nie udało się zapisać pulsu Celery.', exc_info=False)


@task_prerun.connect(weak=False)
def started(sender=None, task_id=None, args=None, kwargs=None, **extra):
    record(sender, 'running', task_id, args, kwargs)


@task_success.connect(weak=False)
def succeeded(sender=None, result=None, **extra):
    failed_result = isinstance(result, dict) and (result.get('status') in ('error', 'failed', 'too_many_failures') or bool(result.get('error')) or bool(result.get('failed')) or bool(result.get('errors')))
    record(sender, 'error' if failed_result else 'ok', result=result)


@task_failure.connect(weak=False)
def failed(sender=None, task_id=None, exception=None, args=None, kwargs=None, **extra):
    record(sender, 'error', task_id, args, kwargs, exception=exception)
