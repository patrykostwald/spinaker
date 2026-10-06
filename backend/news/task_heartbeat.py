"""Local Celery telemetry only; never retain task arguments or arbitrary results."""
import logging
import re
from datetime import timedelta
from functools import lru_cache

from celery.signals import task_prerun, task_success, task_failure
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
TTL = 90 * 86400  # Monthly jobs need history longer than one cadence.
ERROR_MAX = 200
_SECRET = re.compile(r'(sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{32,}|[\w.+-]+@[\w-]+\.[\w.]+)')
_SECRET_AFTER = re.compile(r'(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|key|authorization|bearer|cookie)(\s*[:=]\s*|\s+)\S+')
_QUERY = re.compile(r'\?\S+')


def error_text(value):
    """Powód błędu do pulsu i Raportu pętli: klasa wyjątku i skrócony komunikat, bez sekretów (właściciel 6.10:
    „raport ma mówić DLACZEGO”). Najwyżej ERROR_MAX znaków."""
    if value is None or value == '':
        return ''
    if isinstance(value, BaseException):
        message = ' '.join(str(value).split())
        value = f'{type(value).__name__}: {message}' if message else type(value).__name__
    text = _SECRET_AFTER.sub(lambda m: m.group(1) + ' [ukryte]', ' '.join(str(value).split()))
    return _SECRET.sub('[ukryte]', _QUERY.sub('?[ukryte]', text))[:ERROR_MAX]


def cadence(schedule):
    """Longest weekly gap, including night/weekend pauses, for our beat crontabs.

    Tryb ciągły zbieracza X zapisuje harmonogram jako zwykły timedelta (X_POLL_MODE=batched). Bez tej gałęzi
    kontrola zadań Dyżurnego padała przy każdym biegu (AttributeError: day_of_month) - Raport pętli 6.10."""
    if isinstance(schedule, timedelta):
        return schedule.total_seconds()
    if hasattr(schedule, 'run_every'):
        return schedule.run_every.total_seconds()
    if not hasattr(schedule, 'day_of_month'):
        return None
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
                  'no_free_models': 'Pominięto: brak wolnych modeli',
                  'blocked_access_review': 'Zablokowane: przegląd dostępu', 'brak odpowiedzi': 'Brak odpowiedzi'}
        states.update(partial='Porcja zakończona', deferred='Odroczone: limit lub odstęp',
                      idle='Oczekuje na następny cykl', needs_review='Dokumenty wymagają kontroli',
                      waiting='Czeka na okno modeli', closed='Okno modeli zamknięte', quorum='Czeka na kworum Konsylium')
        if result.get('status') in states:
            safe.insert(0, states[result['status']])
        for key in ('completed', 'failed', 'errors', 'screened'):
            if isinstance(result.get(key), (dict, list)):
                safe.append(f'{key}: {len(result[key])}')
        return '; '.join(safe)[:240] or 'Zakończono; wynik szczegółowy nie jest zapisywany.'
    return 'Zakończono; wynik szczegółowy nie jest zapisywany.'


def produced(result):
    """Ile wpisów wyprodukowało zadanie: pole „produced”, a bez niego „note” (jeden wpis). None, gdy zadanie tego nie mówi."""
    if not isinstance(result, dict):
        return None
    value = result.get('produced')
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    if 'note' in result:
        return 1 if result.get('note') else 0
    return None


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
                if phase == 'error':
                    data['consecutive_errors'] = previous.get('consecutive_errors', 0) + 1
                    data['error_since'] = previous.get('error_since') or now
                else:
                    data.update(consecutive_errors=0, error_since=None)
                    if phase == 'ok':
                        data['last_success'] = now
                # Wynik pętli (audyt 5.10, P5): kiedy zadanie ostatnio coś wyprodukowało, nie tylko kiedy ruszyło.
                count = produced(result)
                if count is not None:
                    data['last_produced'] = count
                    if count > 0 and phase == 'ok':
                        data['last_output_at'] = now
                # Retain a classification, never the exception message or a
                # provider response. Generic HTTPError can otherwise hide 402.
                from news.repairer import permanent, transient
                from news.admin_telemetry import safe_error
                error = (str(getattr(getattr(exception, 'response', None), 'status_code', '')) + ' ' + str(exception)
                         if exception else str(result.get('error', '')) if isinstance(result, dict) else '')
                data['repair_error'] = 'permanent' if permanent(error) else 'transient' if transient(error) else 'unknown'
                data['repair_hint'] = safe_error(error) if error.strip() else ''
                # Powód w Raporcie pętli: „błąd (N z rzędu): Klasa: komunikat”; przy częściowym sukcesie (Dyżurny:
                # jedna kontrola padła, reszta działa) puls jest zielony, a powód zostaje w „partial”.
                reason = error_text(exception) if exception else error_text(
                    result.get('error') or result.get('last_error') or '') if isinstance(result, dict) else ''
                data['last_error'] = reason if phase == 'error' else ''
                data['partial'] = (error_text(result.get('partial')) if isinstance(result, dict) and phase != 'error'
                                   and result.get('status') == 'partial' else '')
            cache.set(key, data, TTL)
            from news.daily_schedule import BEAT_PLAN
            if name in BEAT_PLAN:
                from news.models import RepairerState
                # Zachowujemy udany puls także po restarcie cache.
                saved, _ = RepairerState.objects.get_or_create(key='pulse:' + name)
                saved.data = {**saved.data, **data}
                saved.save(update_fields=['data'])
    except Exception:
        logger.warning('Nie udało się zapisać pulsu Celery.', exc_info=False)


@task_prerun.connect(weak=False)
def started(sender=None, task_id=None, args=None, kwargs=None, **extra):
    record(sender, 'running', task_id, args, kwargs)


@task_success.connect(weak=False)
def succeeded(sender=None, result=None, **extra):
    failed_result = isinstance(result, dict) and (result.get('status') in ('error', 'failed', 'too_many_failures') or bool(result.get('error')) or bool(result.get('failed')) or bool(result.get('errors')))
    skipped = isinstance(result, dict) and result.get('status') in (
        'no_free_models', 'closed', 'disabled', 'already_run', 'busy', 'daily_limit', 'locked', 'already_running', 'waiting')
    if getattr(sender, 'name', '') == 'news.tasks.political_poll_task' and isinstance(result, dict):
        skipped = result.get('status') not in ('ok', 'idle')
    if getattr(sender, 'name', '').startswith('scraper.tasks.collect_public_') and isinstance(result, dict):
        # A controlled budget deferral is visible, but is not a failed import.
        skipped = result.get('status') in ('disabled', 'already_running', 'idle', 'deferred')
        failed_result = result.get('status') in ('error', 'blocked_access_review', 'needs_review')
    record(sender, 'error' if failed_result else 'skipped' if skipped else 'ok', result=result)


@task_failure.connect(weak=False)
def failed(sender=None, task_id=None, exception=None, args=None, kwargs=None, **extra):
    record(sender, 'error', task_id, args, kwargs, exception=exception)
