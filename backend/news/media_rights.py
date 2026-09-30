"""Kiedy pokazujemy zdjęcie i opis (lead) materiału — a kiedy tylko tytuł, datę, autora i link.

Decyzja właściciela 28.09.2026: materiały mediów bez zgody redakcji pokazujemy wyłącznie jako tytuł, datę, autora
i link (prawo wydawców prasowych; tak też obiecujemy w prośbach o zgodę). Zdjęcie i opis zostają przy:
- źródłach urzędowych — dokumenty i materiały urzędowe nie są chronione prawem autorskim (art. 4 ustawy),
- materiałach z oficjalnych API z linkiem do oryginału (YouTube, X),
- materiałach autorów nitek (redakcja/dziennikarz dodaje własny materiał),
- redakcjach, które dały zgodę: zatwierdzona SourceUsageDecision z użyciem „public_card”.
Dane w bazie zostają — zmienia się tylko to, co widzi czytelnik. Zgoda redakcji przywraca zdjęcia i leady od razu.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from django.core.cache import cache
from django.utils import timezone

OFFICIAL_SUFFIXES = ('.gov.pl', '.gov', '.europa.eu', 'sejm.gov.pl', 'senat.gov.pl', 'prezydent.pl', 'trybunal.gov.pl',
                     'nbp.pl', 'rpo.gov.pl', 'nik.gov.pl', 'sn.pl', 'nsa.gov.pl')
API_HOSTS = ('youtube.com', 'youtu.be', 'x.com', 'twitter.com')
API_TYPES = ('twitter', 'politician', 'editorial', 'institution')


def _host(source) -> str:
    return (urlsplit(getattr(source, 'url', '') or '').hostname or '').lower().removeprefix('www.')


def is_official_host(host: str) -> bool:
    return bool(host) and (host.startswith('bip.') or '.bip.' in host
                           or any(host == suffix.lstrip('.') or host.endswith(suffix) for suffix in OFFICIAL_SUFFIXES))


def _consented(source) -> bool:
    """Zatwierdzona, aktualna decyzja o użyciu z „kartą publiczną” (najwyższa wersja rozstrzyga)."""
    from news.models import SourceUsageDecision
    decision = SourceUsageDecision.objects.filter(source=source).order_by('-version').first()
    if decision is None or decision.status != SourceUsageDecision.Status.APPROVED:
        return False
    if decision.valid_until and decision.valid_until < timezone.now():
        return False
    return SourceUsageDecision.Use.PUBLIC_CARD in (decision.allowed_uses or [])


def media_allowed(source) -> bool:
    """Czy przy materiałach tego źródła wolno pokazać zdjęcie i opis."""
    if source is None:
        return False
    host = _host(source)
    if source.source_type in API_TYPES or is_official_host(host) or any(host == h or host.endswith('.' + h) for h in API_HOSTS):
        return True
    key = f'media-allowed-{source.pk}'
    cached = cache.get(key)
    if cached is None:
        cached = _consented(source)
        cache.set(key, cached, 600)
    return bool(cached)


def article_media_allowed(article) -> bool:
    # Rekordy z oficjalnych API (Sejm, ELI, dziennik ustaw) — zawsze urzędowe.
    if getattr(article, 'official_record', None) is not None:
        return True
    return media_allowed(getattr(article, 'source', None))
