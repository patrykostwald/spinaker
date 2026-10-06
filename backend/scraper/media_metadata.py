"""Metadane mediów (właściciel 6.10): więcej artykułów w drzewach przeszłość.today, legalnie.

Zasady z news/pracownia_osint.LEGAL: publikacja medialna tylko jako link (1), bez obchodzenia blokad i regulaminów (2),
bez pełnych tekstów (6). Karta „tylko metadane” (tryb MODE) przepuszcza z publicznego kanału RSS wyłącznie tytuł,
datę publikacji, redakcję i adres. Zapisany sygnał odmowy, opt-outu albo paywallu oznacza list o zgodę, nie kartę.
Przy każdym pobraniu sprawdzamy robots.txt hosta i sygnał opt-outu TDM (art. 4 DSM); wynik trzymamy dobę w pamięci podręcznej.
Decyzje zapadają bez sieci: tylko z bazy i katalogu (katalog, rejestr zgód, notatki, ostatnie błędy, audyty).
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from django.core.cache import cache

MODE = 'media_metadata_only'
MEDIA_TYPES = ('portal', 'newspaper', 'rss')
REVIEWED_BY = 'decyzja właściciela 6.10.2026: metadane mediów'
FIELDS = ('title', 'published_date', 'source', 'url')
SCOPE_NOTE = 'Tylko tytuł, data publikacji, redakcja i adres; bez treści, leadu, opisu, autora, tagów i zdjęć.'
LEGAL_BASIS = ['LEGAL 1: publikacje medialne jako link', 'LEGAL 2: bez obchodzenia blokad, paywalli i regulaminów',
               'LEGAL 6: bez pełnych tekstów, tylko metadane', 'art. 4 DSM: robots.txt i sygnał TDM sprawdzane przy pobraniu']
BLOCKING_STATUSES = {'suspended', 'contact_required', 'rejected'}
# Słowa odmowy w notatkach katalogowych i ostatnich błędach: paywall, odmowa, opt-out, zakaz, ściana botów, robots, 403.
REFUSAL = re.compile(r'paywall|płatn\w*\s+mur|odm[oó]w|opt[- ]?out|zakaz|regulamin\s+zabrania|permission_required|bot_protection|'
                     r'robots|tdm|(?<!\d)403(?!\d)', re.I)
BROKEN = re.compile(r'(?<!\d)(404|410)(?!\d)|nieprawidłowy|niedostępny', re.I)
DATA = Path(__file__).parent / 'data'
TDM_TTL = 24 * 60 * 60
CONTENT_SIGNAL = re.compile(r'^\s*content-signal\s*:\s*(.+)$', re.I | re.M)
TDM_RESERVATION = re.compile(r'^\s*tdm-reservation\s*:\s*1\b', re.I | re.M)


def host(url):
    return (urlsplit(url or '').hostname or '').lower().removeprefix('www.')


@lru_cache(maxsize=1)
def registry():
    """Hosty z zapisaną odmową albo ograniczeniem (bez sieci): rejestr zgód wydawców i audyty robots.txt z katalogu."""
    rows = {}
    try:
        for item in json.loads((DATA / 'source_permission_backlog.json').read_text(encoding='utf-8')):
            if item.get('status') == 'permission_required':
                rows[host(item.get('base_url'))] = 'rejestr zgód: ' + (item.get('reason') or 'wymaga zgody wydawcy')
    except (OSError, ValueError):
        pass
    try:
        for item in json.loads((DATA / 'verified_local_sources.json').read_text(encoding='utf-8')):
            bots = item.get('ai_bot_restrictions') or []
            if bots:
                rows.setdefault(host(item.get('url')), 'robots.txt ogranicza agentów AI: ' + ', '.join(map(str, bots)))
    except (OSError, ValueError):
        pass
    rows.pop('', None)
    return rows


def _known(url):
    h = host(url)
    for known, reason in registry().items():
        if h == known or h.endswith('.' + known):
            return reason
    return ''


def eligibility(source):
    if source.source_type not in MEDIA_TYPES:
        return 'Poza zakresem: nie jest medium'
    if source.catalog_stage not in ('candidate', 'configured'):
        return 'Źródło wykluczone z katalogu'
    if not source.rss_url:
        return 'Brak publicznego kanału RSS'
    if source.rss_url.startswith('https://news.google.com/rss/search?'):
        return 'Kanał na żądanie (Google News), nie redakcja'
    from scraper.source_probe import public_link
    if not public_link(source.rss_url) or len(source.rss_url) > 1024:
        return 'Adres kanału nie jest publiczny'
    return ''


def refusal(source, cards):
    """Zapisany sygnał odmowy, opt-outu albo paywallu; pusty napis, gdy go nie ma. Tylko dane, które już mamy."""
    seen = set()
    for card in cards:
        key = (card.channel, card.endpoint)
        if key not in seen and card.status in BLOCKING_STATUSES:
            return f'karta dostępu: {card.status}'
        seen.add(key)
    for url in (source.url, source.rss_url):
        reason = _known(url)
        if reason:
            return reason
    for text, label in ((source.catalog_notes, 'notatka katalogowa'), (source.last_error, 'ostatni błąd')):
        found = REFUSAL.search(text or '')
        if found:
            return f'{label}: {found.group(0)}'
    from scraper.public_institution_approval import audit_state
    for item in audit_state(source).get('evidence', []) or []:
        if isinstance(item, dict) and item.get('kind') == 'robots' and item.get('ai_bot_restrictions'):
            return 'audyt robots.txt: ograniczenia dla agentów AI: ' + ', '.join(map(str, item['ai_bot_restrictions']))
    return ''


def broken(source):
    """Kanał do naprawy adresu (404/410, zły XML): bez karty i bez listu."""
    return bool(source.last_error) and bool(BROKEN.search(source.last_error)) and not REFUSAL.search(source.last_error)


def metadata_only(instruction):
    """Czy karta jest w trybie „tylko metadane mediów” (strażnik w imporcie RSS)."""
    return bool(instruction) and instruction.allowed_scope == 'metadata' and (instruction.evidence or {}).get('mode') == MODE


def build_card(source, cards, now):
    """Niezapisana karta: RSS, metadane, 24 żądania na dobę, 90 dni; dowód z katalogu i zasad LEGAL."""
    from datetime import timedelta
    from news.models import SourceAccessInstruction
    endpoint = source.rss_url
    return SourceAccessInstruction(
        source=source, version=(cards[0].version if cards else 0) + 1,
        status='approved', channel='rss', allowed_scope='metadata', endpoint=endpoint,
        allowed_path_patterns=[urlsplit(endpoint).path or '/'],
        # Adres kanału to dowód decyzji właściciela, nie licencja wydawcy; pełny tekst nigdy nie trafia do bazy.
        terms_url=endpoint,
        evidence={'mode': MODE, 'channel_url': endpoint, 'publisher_url': source.url or '', 'basis': REVIEWED_BY,
                  'fields': list(FIELDS), 'scope': SCOPE_NOTE, 'legal': LEGAL_BASIS,
                  'refusal_check': 'rejestr zgód, notatki, ostatnie błędy, karty i audyty robots.txt bez sygnału odmowy'},
        minimum_interval_seconds=3, daily_request_cap=24, reviewed_at=now, reviewed_by=REVIEWED_BY,
        valid_until=now + timedelta(days=90))


def robots_verdict(feed_url, network):
    """Jedno pobranie robots.txt hosta: Disallow dla naszego agenta, „Content-Signal: search=no” albo
    „tdm-reservation: 1” to opt-out (art. 4 DSM). Brak pliku albo błąd sieci nie jest opt-outem; 4xx na robots.txt
    (poza 404/410) traktujemy jak zamknięte drzwi."""
    from scraper.source_probe import USER_AGENT, origin
    url = origin(feed_url) + '/robots.txt'
    try:
        current = url
        for _ in range(4):
            response = network.raw(current)
            if 'location' in response:
                current = urljoin(current, response['location'])
                continue
            break
        else:
            return {'ok': True, 'reason': '', 'note': 'robots_redirect_limit'}
    except Exception as exc:  # noqa: BLE001 - błąd sieci nie jest decyzją wydawcy
        return {'ok': True, 'reason': '', 'note': f'robots_error:{type(exc).__name__}'}
    status = response.get('status', 0)
    if status in (404, 410):
        return {'ok': True, 'reason': '', 'note': 'robots_absent'}
    if status >= 400:
        return {'ok': False, 'reason': f'robots_http_{status}'}
    text = response.get('raw', b'').decode('utf-8', errors='replace')
    if '<html' in text[:300].lower() or '<!doctype html' in text[:300].lower():
        return {'ok': True, 'reason': '', 'note': 'robots_returned_html'}
    policy = RobotFileParser()
    policy.parse(text.splitlines())
    if not policy.can_fetch(USER_AGENT, feed_url):
        return {'ok': False, 'reason': 'robots_disallowed'}
    for found in CONTENT_SIGNAL.finditer(text):
        signals = dict(part.strip().lower().split('=', 1) for part in found.group(1).split(',') if '=' in part)
        if signals.get('search', '').strip() == 'no':
            return {'ok': False, 'reason': 'tdm_opt_out:search=no'}
    if TDM_RESERVATION.search(text):
        return {'ok': False, 'reason': 'tdm_opt_out:tdm-reservation'}
    return {'ok': True, 'reason': ''}


def tdm_allows(feed_url, network=None):
    """Tanie sprawdzenie przed pobraniem kanału: wynik na host trzymany dobę (jedno żądanie robots.txt na dobę)."""
    key = 'media-tdm:' + host(feed_url)
    verdict = cache.get(key)
    if verdict is None:
        if network is None:
            from scraper.source_probe import ProbeNetwork
            network = ProbeNetwork()
        verdict = robots_verdict(feed_url, network)
        cache.set(key, verdict, TDM_TTL)
    return verdict
