"""Warunki zgody Rządowego Centrum Legislacji na automatyczne pobieranie stron serwisu legislacja.rcl.gov.pl.

Podstawa: pismo RCL.DPK.053.168.2026 z 21.10.2026.  Każdy warunek jest zaszyty tutaj, w kodzie, a nie w ustawieniach,
i działa na najniższej warstwie (scraper.utils._fetch_feed_raw woła guard_request przed każdym połączeniem z hostem RCL),
więc żaden inny moduł nie wyśle zapytania poza warunkami:

1. najwyżej 1 zapytanie na 5 sekund, globalnie (RCL_MIN_INTERVAL_SECONDS; egzekwuje scraper.rcl_client przez HostGate w bazie);
2. tylko 01:00-06:00 czasu polskiego (Europe/Warsaw); zapytanie nie startuje, jeśli mogłoby skończyć się po 06:00;
3. nagłówek User-Agent dokładnie RCL_USER_AGENT;
4. po HTTP 429 lub 503 pobieranie wstrzymane do następnej nocy (halt), bez ponawiania w tej samej nocy;
5. źródło, link i data pobrania przy publikacji (modele news.rcl_models, API news.rcl_api).

Dodatkowo: pobieranie tylko z serwera zgłoszonego do RCL (148.113.242.109) - przełącznik RCL_FETCH_ENABLED, domyślnie wyłączony,
ustawiany wyłącznie na produkcji.  Moduł nie wykonuje żadnego ruchu sieciowego.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta
import os
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import functools

import requests
from django.utils import timezone

RCL_HOST = 'legislacja.rcl.gov.pl'
RCL_BASE_URL = 'https://' + RCL_HOST
RCL_USER_AGENT = 'iapply-legislacja/1.0 (+https://przeszlosc.today; kontakt@iapply.pl)'
# Człon User-Agent dopasowywany do reguł robots.txt (RFC 9309: nazwa produktu bez wersji).
RCL_ROBOTS_TOKEN = 'iapply-legislacja'
RCL_MIN_INTERVAL_SECONDS = 5
RCL_TZ = ZoneInfo('Europe/Warsaw')
WINDOW_START = dtime(1, 0)
WINDOW_END = dtime(6, 0)
# Najdłuższe trwanie jednego zapytania (połączenie 5 s + odczyt 30 s + zapas): zapytanie, które mogłoby się skończyć po 06:00, nie startuje.
REQUEST_ALLOWANCE_SECONDS = 40
HALT_STATE_NAME = 'rcl:halt'
SOURCE_LINE = 'Źródło: Rządowe Centrum Legislacji, legislacja.rcl.gov.pl'
PROCESSING_NOTE = ('Dane ujednolicone i uporządkowane przez iapply sp. z o.o. (operatora spin.clinic i przeszłość.today); '
                   'treść pism i dokumentów należy do RCL i organów wnioskujących.')


class RclRefused(requests.RequestException):
    """Zapytanie do RCL jest niedozwolone w tej chwili; ``reason`` to krótki, stały kod.

    Dziedziczy po RequestException, żeby kod łączący się przez requests traktował odmowę jak zwykłą nieudaną próbę.
    """

    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail
        super().__init__(reason if not detail else f'{reason}: {detail}')


def is_rcl_url(url):
    try:
        return (urlsplit(str(url)).hostname or '').lower() == RCL_HOST
    except ValueError:
        return False


def fetch_enabled():
    """Przełącznik produkcyjny; odczyt przy każdym wywołaniu, nie przy imporcie."""
    return os.environ.get('RCL_FETCH_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def local_now(now=None):
    return (now or timezone.now()).astimezone(RCL_TZ)


def window_open(now=None, *, allowance_seconds=0):
    """Czy ``now`` leży w 01:00-06:00 czasu polskiego, a zapytanie trwające ``allowance_seconds`` skończy się przed 06:00."""
    local = local_now(now)
    start = datetime.combine(local.date(), WINDOW_START, tzinfo=RCL_TZ)
    end = datetime.combine(local.date(), WINDOW_END, tzinfo=RCL_TZ)
    return start <= local and local + timedelta(seconds=allowance_seconds) < end


def next_window_start(now=None):
    """Najbliższe 01:00 czasu polskiego ściśle po ``now``: moment, do którego trwa wstrzymanie po 429/503."""
    local = local_now(now)
    start = datetime.combine(local.date(), WINDOW_START, tzinfo=RCL_TZ)
    if start <= local:
        start += timedelta(days=1)
    return start


def _halt_state():
    from news.models import ImportState
    return ImportState.objects.filter(name=HALT_STATE_NAME).first()


def halted_until(now=None):
    """Do kiedy trwa wstrzymanie (po 429/503/403/odrzuceniu przez zaporę), albo None."""
    state = _halt_state()
    raw = (state.cursor or {}).get('until') if state else None
    if not raw:
        return None
    until = datetime.fromisoformat(raw)
    return until if until > (now or timezone.now()) else None


def halt(reason, *, status=None, url='', retry_after_seconds=0, now=None):
    """Wstrzymuje pobieranie do następnego 01:00 (albo dłużej, jeśli RCL poda Retry-After) i zapisuje zdarzenie."""
    from news.models import ImportState
    from news.rcl_models import RclFetchEvent
    now = now or timezone.now()
    until = next_window_start(now)
    if retry_after_seconds:
        until = max(until, now + timedelta(seconds=min(int(retry_after_seconds), 7 * 86400)))
    state, _ = ImportState.objects.get_or_create(name=HALT_STATE_NAME)
    state.cursor = {'until': until.isoformat(), 'reason': reason, 'status': status, 'at': now.isoformat()}
    state.last_error = f'{reason} {status or ""}'.strip()[:200]
    state.save(update_fields=['cursor', 'last_error'])
    RclFetchEvent.objects.create(kind=reason, http_status=status, url=_safe_path(url),
                                 detail={'halted_until': until.isoformat()})
    return until


def _safe_path(url):
    """W zdarzeniach zapisujemy ścieżkę z zapytaniem, bez schematu i hosta."""
    parts = urlsplit(str(url))
    return (parts.path + ('?' + parts.query if parts.query else ''))[:500]


def guard_request(url, *, now=None):
    """Ostatnia bramka przed połączeniem.  Dla hosta RCL sprawdza wszystkie warunki i zwraca wymagany User-Agent.

    Dla innych hostów zwraca None i niczego nie sprawdza.  Wyjątek ``RclRefused`` oznacza: nie łączyć się.
    """
    if not is_rcl_url(url):
        return None
    if urlsplit(str(url)).scheme != 'https':
        raise RclRefused('not_https')
    if not fetch_enabled():
        raise RclRefused('disabled')
    if not window_open(now, allowance_seconds=REQUEST_ALLOWANCE_SECONDS):
        raise RclRefused('outside_window')
    until = halted_until(now)
    if until is not None:
        raise RclRefused('halted', until.isoformat())
    return RCL_USER_AGENT


def install_requests_guard():
    """Bramka także dla kodu używającego biblioteki requests: host RCL dostaje własny User-Agent i te same warunki.

    Wołane raz z ScraperConfig.ready(); wielokrotne wywołanie nic nie zmienia.
    """
    from requests.adapters import HTTPAdapter
    original = HTTPAdapter.send
    if getattr(original, '_rcl_guarded', False):
        return

    @functools.wraps(original)
    def guarded_send(self, request, *args, **kwargs):
        agent = guard_request(request.url)
        if agent:
            request.headers['User-Agent'] = agent
        return original(self, request, *args, **kwargs)

    guarded_send._rcl_guarded = True
    HTTPAdapter.send = guarded_send
