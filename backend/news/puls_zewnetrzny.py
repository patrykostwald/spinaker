"""Puls z zewnątrz (Z3, przegląd architekta 7.10): healthchecks.io budzi właściciela, gdy serwer, beat albo worker padną.

Co 5 minut zadanie puls_zewnetrzny_task: GET <HEALTHCHECK_URL>/start, potem sprawdzenie, czy Dyżurny (duty-15m)
ma świeży bieg bez błędu (ostatnie 15 minut). Świeży -> GET <HEALTHCHECK_URL> (sukces); nieświeży albo błąd bazy ->
POST <HEALTHCHECK_URL>/fail z powodem. Brak pingu przez okres + karencję (15 + 30 min) = serwis zewnętrzny pisze
do właściciela, więc także martwy beat lub worker (który nie wyśle nic) jest widoczny. Bez adresu: disabled."""
import logging
import os
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

FRESH = timedelta(minutes=15)
TIMEOUT = (3, 7)
STATE_KEY = 'puls-zewnetrzny'
DUTY_BEAT = 'duty-15m'


def url():
    return next((os.environ.get(name, '').strip().rstrip('/') for name in ('HEALTHCHECK_URL', 'HEALTHCHECK_PING_URL')
                 if os.environ.get(name, '').strip()), '')


def enabled():
    return bool(url())


def duty_fresh(now):
    """(świeży?, powód) z pulsu Dyżurnego - cache i trwały zapis w bazie (po restarcie cache)."""
    from news.raport_petli import pulse, _stamp
    data = pulse(DUTY_BEAT)
    last = _stamp(data.get('last_event') or data.get('started_at'))
    if not last:
        return False, 'Dyżurny: brak jakiegokolwiek pulsu'
    age = now - last
    if age > FRESH:
        return False, f'Dyżurny: ostatni bieg {round(age.total_seconds() / 60)} min temu'
    if data.get('result') == 'error':
        return False, f"Dyżurny: błąd ({data.get('consecutive_errors') or 1} z rzędu)"
    return True, ''


def ping(suffix='', body=''):
    target = url() + suffix
    try:
        response = requests.post(target, data=body[:1000].encode(), timeout=TIMEOUT) if body else requests.get(target, timeout=TIMEOUT)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _save(**data):
    from news.models import RepairerState
    row, _ = RepairerState.objects.get_or_create(key=STATE_KEY)
    row.data = {**(row.data or {}), **data}
    row.save(update_fields=['data'])


def run(now=None):
    if not enabled():
        return {'status': 'disabled'}
    now = now or timezone.now()
    ping('/start')
    try:
        fresh, reason = duty_fresh(now)
    except Exception as error:  # noqa: BLE001 - baza nie odpowiada: to też powód do alarmu z zewnątrz
        fresh, reason = False, f'Baza: {type(error).__name__}'
    if fresh:
        sent = ping('')
        try:
            _save(last_ping_at=now.isoformat(), last_status='ok' if sent else 'no-answer', reason='')
        except Exception:  # noqa: BLE001
            pass
        return {'status': 'ok', 'produced': 1, 'delivered': sent} if sent else {'status': 'ok', 'produced': 0, 'delivered': False,
                                                                                  'partial': 'healthchecks.io nie odpowiedział'}
    ping('/fail', reason)
    try:
        _save(last_ping_at=now.isoformat(), last_status='fail', reason=reason)
    except Exception:  # noqa: BLE001
        pass
    return {'status': 'error', 'error': reason}


def report_line(now=None):
    from news.models import RepairerState
    from news.raport_petli import _stamp
    if not enabled():
        return 'Puls z zewnątrz: wyłączony (brak HEALTHCHECK_URL) - padnięcia serwera nikt nie zauważy.'
    row = RepairerState.objects.filter(key=STATE_KEY).first()
    data = dict(row.data or {}) if row else {}
    at = _stamp(data.get('last_ping_at'))
    if not at:
        return 'Puls z zewnątrz: włączony, jeszcze bez pingu.'
    local = at.astimezone(timezone.get_current_timezone())
    status = {'ok': 'ok', 'fail': 'FAIL (' + (data.get('reason') or '') + ')', 'no-answer': 'healthchecks.io nie odpowiedział'}.get(data.get('last_status'), '?')
    line = f'Puls z zewnątrz: ostatni ping {local:%H:%M} {status}'
    if now and now - at > timedelta(minutes=20):
        line += ' - UWAGA: od ponad 20 min brak pingu (sprawdź beat i worker)'
    return line
