"""Linki do kanałów YouTube i kont X znalezione na stronach głównych źródeł z katalogu.

Stronę główną czytamy raz, tym samym mechanizmem co audyt źródeł (robots.txt, co najmniej 3 s między
żądaniami do hosta, tylko publiczne adresy, bez omijania blokad). Link na stronie źródła jest dowodem, że
kanał lub konto należy do tego źródła. Samo przypisanie niczego nie pobiera: kanały YouTube trafiają do
przeglądu (``OfficialVideoChannel`` pending_review), a konta X — do zapisu dowodu przy źródle.
"""
import re
from urllib.parse import urljoin, urlsplit

from django.utils import timezone

from news.models import ImportState, Source

YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com'}
X_HOSTS = {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com'}
YOUTUBE_SKIP = {'watch', 'embed', 'playlist', 'shorts', 'results', 'feed', 'redirect', 'live', 'vi', 'account', 'premium'}
X_SKIP = {'share', 'intent', 'home', 'i', 'search', 'hashtag', 'login', 'privacy', 'tos', 'explore', 'settings', 'messages'}
HANDLE = re.compile(r'^[A-Za-z0-9_]{1,15}$')
STATE = 'source-social:{}'


def youtube_link(href: str) -> str:
    parts = urlsplit(href)
    if (parts.hostname or '').lower() not in YOUTUBE_HOSTS:
        return ''
    segments = [segment for segment in parts.path.split('/') if segment]
    if not segments or segments[0].lower() in YOUTUBE_SKIP:
        return ''
    if segments[0] in ('channel', 'user', 'c') and len(segments) > 1:
        return f'https://www.youtube.com/{segments[0]}/{segments[1]}'
    return f'https://www.youtube.com/{segments[0]}'


def x_handle(href: str) -> str:
    parts = urlsplit(href)
    if (parts.hostname or '').lower() not in X_HOSTS:
        return ''
    segments = [segment for segment in parts.path.split('/') if segment]
    if not segments or segments[0].lower() in X_SKIP or not HANDLE.match(segments[0]):
        return ''
    return segments[0]


def links_on_page(raw: bytes, base: str) -> dict:
    from scraper.source_probe import PublisherLinks
    parser = PublisherLinks()
    parser.feed(raw.decode('utf-8', errors='replace'))
    youtube, x = [], []
    for link in parser.links:
        href = urljoin(base, link['href'].strip())
        channel, handle = youtube_link(href), x_handle(href)
        if channel and channel not in youtube:
            youtube.append(channel)
        if handle and handle.lower() not in {h.lower() for h in x}:
            x.append(handle)
    return {'youtube': youtube[:3], 'x': x[:3]}


def discover(source: Source, network) -> dict:
    """Czyta stronę główną źródła i zapisuje znalezione linki jako dowód (ImportState)."""
    from scraper.source_probe import ProbeError
    result = {'checked_at': timezone.now().isoformat(), 'evidence_url': source.url, 'youtube': [], 'x': []}
    try:
        raw, final_url, _ = network.fetch(source.url)
        result.update(links_on_page(raw, final_url), evidence_url=final_url, status='ok')
    except ProbeError as error:
        result.update(status='error', error=str(error)[:120])
    except Exception as error:  # sieć, dekodowanie — źródło zostaje bez zmian
        result.update(status='error', error=type(error).__name__)
    state, _ = ImportState.objects.get_or_create(name=STATE.format(source.pk))
    state.cursor = result
    state.save(update_fields=['cursor'])
    return result


def stored(source: Source) -> dict:
    state = ImportState.objects.filter(name=STATE.format(source.pk)).first()
    return dict(state.cursor) if state else {}
