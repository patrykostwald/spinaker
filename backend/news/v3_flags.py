"""Flagi v3 w jednym miejscu (recenzja Fable 13.10): ustawienia z `config/settings.py` (env) jako wartość domyślna,
nadpisywane w bazie (SiteFlag, przełącznik w adminie bez restartu, z dziennikiem i oknem czasowym od-do).

Używane przez: causal_chain, position_pairs, przeszlosc_v3, zmiana_zdania (stary blok), cache /api/clinic/.
"""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone

KNOWN = (
    'CAUSAL_CHAIN_ENABLED', 'PRZEKAZ_SPIN_STRENGTH_ENABLED', 'ELECTION_SILENCE', 'POSITION_PAIRS_ENABLED',
    'POSITION_CHANGES_LEGACY_ENABLED', 'PRZESZLOSC_VOTES_LIST_ENABLED', 'PRZESZLOSC_NETWORK_ENABLED',
    'PRZESZLOSC_PRIVACY_NOTICE_ENABLED', 'ASSETS_DECLARATIONS_ENABLED',
)
CACHE_KEY = 'v3-site-flags'
CACHE_SECONDS = 30  # przełącznik w adminie działa najpóźniej po 30 s (zapis czyści cache od razu)


def _rows() -> dict:
    """{klucz: (wartość, od, do)} z bazy, z krótkim cache; pusty słownik, gdy tabeli jeszcze nie ma (przed migracją)."""
    from django.core.cache import cache
    rows = cache.get(CACHE_KEY)
    if rows is None:
        try:
            from news.clinic_models import SiteFlag
            rows = {r.key: (r.value, r.active_from, r.active_until) for r in SiteFlag.objects.all()}
        except Exception:  # noqa: BLE001 - brak tabeli albo bazy nie może wyłączyć serwisu
            rows = {}
        cache.set(CACHE_KEY, rows, CACHE_SECONDS)
    return rows


def clear_cache():
    from django.core.cache import cache
    cache.delete(CACHE_KEY)


def _window_ok(start, end, now) -> bool:
    return (start is None or now >= start) and (end is None or now < end)


def flag(name: str, now=None) -> bool:
    """Wartość flagi: wiersz SiteFlag (jeśli jest i obowiązuje w swoim oknie) wygrywa z ustawieniem z env."""
    now = now or timezone.now()
    row = _rows().get(name)
    if row is not None:
        value, start, end = row
        if _window_ok(start, end, now):
            return bool(value)
        # poza oknem: wiersz nie obowiązuje, decyduje ustawienie z env
    return bool(getattr(settings, name, False))


def silence(now=None) -> bool:
    """Cisza wyborcza: SiteFlag ELECTION_SILENCE (z oknem od-do), ustawienie ELECTION_SILENCE albo okno dat
    ELECTION_SILENCE_FROM / ELECTION_SILENCE_UNTIL z env (ISO 8601)."""
    now = now or timezone.now()
    if flag('ELECTION_SILENCE', now):
        return True
    start, end = getattr(settings, 'ELECTION_SILENCE_FROM', None), getattr(settings, 'ELECTION_SILENCE_UNTIL', None)
    return bool(start or end) and _window_ok(start, end, now)
