"""Kolejka weryfikacji adresów spoza bazy (etap F) z blokadą SSRF i zasadami przeciw doxxingowi przez URL.

Bez sieci, dopóki `flags().url_fetch_enabled` jest False: kontrole automatyczne (schemat, host, adres prywatny,
dane osobowe w adresie, skracacze, listy blokad) działają bez połączenia; pobranie strony wymaga osobnego procesu
z `fetcher` (interfejs niżej) i decyzji człowieka. Nic nie jest publicznie widoczne przed decyzją człowieka
(PETLA 2.2 wiersz 7): karta linku ma stan "oczekuje", a box z linku czytelnika jest oznaczony i noindex.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.db import transaction
from django.utils import timezone

from .config import config, flags
from .models import Box, Pin, UrlCheck
from .text import normalize

TRACKING_PREFIXES = ('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'igshid', 'ref', 'ref_src', 'si')
SHORTENERS = {'bit.ly', 't.co', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly', 'cutt.ly', 'lnkd.in', 'rb.gy', 'shorturl.at'}
# Serwisy wyszukiwania ludzi, wklejarki i hosty plików: dane osób prywatnych, kopie cudzych treści (GS Media).
BLOCKED_DOMAINS = {'pastebin.com', 'paste.ee', 'ghostbin.com', 'controlc.com', 'justpaste.it', 'anonfiles.com',
                   'mega.nz', 'archive.ph', 'archive.today', 'archive.is', 'web.archive.org', 'telegra.ph',
                   'docs.google.com', 'drive.google.com', 'dropbox.com', '4chan.org', 'kiwifarms.net'}
PRIVATE_PROFILE_PATTERNS = (
    re.compile(r'^(www\.)?facebook\.com/(profile\.php|people/)', re.I),
    re.compile(r'^(www\.)?instagram\.com/[^/]+/?$', re.I),
    re.compile(r'^(www\.)?tiktok\.com/@[^/]+/?$', re.I),
    re.compile(r'^(www\.)?linkedin\.com/in/', re.I),
)
PESEL_IN_URL = re.compile(r'(?<!\d)\d{11}(?!\d)')
PHONE_IN_URL = re.compile(r'(?<!\d)(?:48)?\d{9}(?!\d)')
EMAIL_IN_URL = re.compile(r'[\w.+-]+(?:@|%40)[\w-]+\.[\w.-]+', re.I)
ALLOWED_CONTENT = ('text/html', 'application/xhtml+xml', 'application/json', 'application/pdf')
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT = 10


def normalize_url(raw: str) -> str:
    """https, bez www, bez utm_* i fragmentu, bez końcowego ukośnika; AMP do wersji kanonicznej ('/amp' na końcu)."""
    raw = (raw or '').strip()
    if not raw:
        return ''
    if not re.match(r'^https?://', raw, re.I):
        raw = 'https://' + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ''
    host = (parts.hostname or '').lower().removeprefix('www.')
    if not host or '.' not in host and host != 'localhost':
        return ''
    if parts.username or parts.password:
        return ''
    scheme = 'https' if parts.scheme.lower() in ('http', 'https') else ''
    if not scheme:
        return ''
    path = re.sub(r'/+', '/', parts.path or '/')
    path = re.sub(r'/amp/?$', '/', path, flags=re.I)
    if path != '/' and path.endswith('/'):
        path = path[:-1]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(TRACKING_PREFIXES) and k.lower() not in ('amp',)]
    query.sort()
    port = ''
    if parts.port and parts.port not in (80, 443):
        port = f':{parts.port}'
    return urlunsplit((scheme, host + port, path, urlencode(query), ''))


def is_private_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def host_is_safe(host: str, resolver: Callable[[str], list[str]] | None = None) -> tuple[bool, str]:
    """Blokada adresów prywatnych i localhost PO rozwiązaniu DNS (SSRF, PETLA 2.2 wiersz 10)."""
    host = (host or '').lower()
    if not host or host == 'localhost' or host.endswith('.local') or host.endswith('.internal'):
        return False, 'host lokalny'
    try:
        ipaddress.ip_address(host)
        return (not is_private_ip(host)), 'adres IP zamiast domeny'
    except ValueError:
        pass
    if resolver is None:
        return True, 'bez rozwiązania DNS (sprawdzane przy pobraniu)'
    try:
        addresses = resolver(host)
    except (socket.gaierror, OSError):
        return False, 'domena nie rozwiązuje się'
    if not addresses:
        return False, 'domena nie rozwiązuje się'
    for address in addresses:
        if is_private_ip(address):
            return False, 'domena wskazuje adres prywatny'
    return True, ''


def dns_resolver(host: str) -> list[str]:
    return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})


def automatic_checks(normalized: str) -> dict:
    """Kontrole bez sieci. Wynik: {'verdict': 'rejected'|'needs_review'|'queued', 'reason': ..., ...}."""
    parts = urlsplit(normalized)
    host = (parts.hostname or '').lower()
    out = {'host': host, 'verdict': 'queued', 'reason': ''}
    safe, why = host_is_safe(host)
    if not safe:
        return {**out, 'verdict': 'rejected', 'reason': f'Adres odrzucony: {why}.'}
    if host in BLOCKED_DOMAINS or any(host.endswith('.' + d) for d in BLOCKED_DOMAINS):
        return {**out, 'verdict': 'rejected', 'reason': 'Ten serwis jest na liście blokad (kopie treści, pliki, dane osób).'}
    path_query = parts.path + '?' + parts.query
    if EMAIL_IN_URL.search(path_query) or PESEL_IN_URL.search(path_query) or PHONE_IN_URL.search(parts.query):
        return {**out, 'verdict': 'rejected', 'reason': 'Adres zawiera dane osobowe (e-mail, numer); nie publikujemy takich linków.'}
    if host in SHORTENERS:
        return {**out, 'verdict': 'needs_review', 'reason': 'Skracacz: adres trzeba rozwiązać do celu.', 'shortener': True}
    for pattern in PRIVATE_PROFILE_PATTERNS:
        if pattern.match(host + parts.path):
            return {**out, 'verdict': 'needs_review', 'reason': 'Profil osoby w serwisie społecznościowym: wymaga sprawdzenia, czy to osoba publiczna.'}
    if known_publisher(host):
        out['publisher'] = True
    else:
        out['verdict'], out['reason'] = 'needs_review', 'Domena spoza katalogu wydawców i instytucji: decyzja człowieka.'
    return out


def known_publisher(host: str) -> bool:
    """Domena wydawcy pierwotnego: katalog źródeł `news.Source` (aktywne) albo host urzędowy (news.media_rights)."""
    from news.media_rights import is_official_host
    from news.models import Source
    if is_official_host(host):
        return True
    for source_url in Source.objects.filter(is_active=True).exclude(url__isnull=True).values_list('url', flat=True):
        source_host = (urlsplit(source_url).hostname or '').lower().removeprefix('www.')
        if source_host and (host == source_host or host.endswith('.' + source_host)):
            return True
    return False


def domain_submissions_today(domain: str, now=None) -> int:
    now = now or timezone.now()
    return UrlCheck.objects.filter(domain=domain, created_at__gte=now - timedelta(days=1)).count()


@transaction.atomic
def enqueue(normalized: str, actor: str = '', now=None) -> UrlCheck:
    now = now or timezone.now()
    check, created = UrlCheck.objects.get_or_create(url_normalized=normalized, defaults={
        'url_input': normalized, 'domain': urlsplit(normalized).hostname or '', 'submitted_by': actor, 'created_at': now})
    if created:
        result = automatic_checks(normalized)
        check.checks = result
        if result['verdict'] == 'rejected':
            check.status, check.reason, check.checked_at = 'rejected', result['reason'], now
        elif result['verdict'] == 'needs_review':
            check.status, check.reason = 'needs_review', result['reason']
        check.save()
    return check


@dataclass
class FetchResult:
    status: int = 0
    final_url: str = ''
    content_type: str = ''
    body: str = ''
    redirects: list = field(default_factory=list)
    error: str = ''


def requests_fetcher(url: str, resolver=dns_resolver) -> FetchResult:
    """Pobranie krok po kroku: każde przekierowanie sprawdzone pod kątem adresu prywatnego, maks. 3, 10 s, 2 MB, tylko HTML.
    Używać wyłącznie w osobnym procesie bez dostępu do sieci wewnętrznej; w testach zastępowane atrapą."""
    import requests
    result = FetchResult()
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        host = urlsplit(current).hostname or ''
        safe, why = host_is_safe(host, resolver)
        if not safe:
            result.error = f'SSRF: {why}'
            return result
        try:
            response = requests.get(current, timeout=TIMEOUT, allow_redirects=False, stream=True,
                                    headers={'User-Agent': 'spina3 link check (kontakt@iapply.pl)'})
        except requests.RequestException as exc:
            result.error = f'błąd pobierania: {exc.__class__.__name__}'
            return result
        if response.is_redirect and response.headers.get('Location'):
            result.redirects.append(current)
            current = requests.compat.urljoin(current, response.headers['Location'])
            continue
        result.status, result.final_url = response.status_code, current
        result.content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if result.content_type not in ALLOWED_CONTENT:
            result.error = f'typ treści {result.content_type or "nieznany"} nie jest dozwolony'
            return result
        body = b''
        for chunk in response.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES:
                result.error = 'strona większa niż 2 MB'
                return result
        result.body = body.decode(response.encoding or 'utf-8', errors='replace') if result.content_type != 'application/pdf' else ''
        return result
    result.error = 'za dużo przekierowań'
    return result


TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I)
OG_TITLE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.I)


def process(check: UrlCheck, fetcher: Callable[[str], FetchResult] | None = None, now=None) -> UrlCheck:
    """Jeden krok kolejki: pobiera metadane (jeśli jest fetcher) i przekazuje do decyzji człowieka; nigdy nie publikuje sam."""
    now = now or timezone.now()
    if check.status in ('accepted', 'rejected', 'duplicate'):
        return check
    if fetcher is None:
        if not flags().url_fetch_enabled:
            check.status = 'needs_review' if check.status == 'queued' else check.status
            check.reason = check.reason or 'Bez pobierania (url_fetch_enabled=false): decyzja człowieka na podstawie adresu.'
            check.save(update_fields=['status', 'reason'])
            return check
        fetcher = requests_fetcher
    check.attempts += 1
    result = fetcher(check.url_normalized)
    check.checked_at = now
    if result.error or result.status != 200:
        check.fetched = {'error': result.error or f'HTTP {result.status}', 'redirects': result.redirects}
        check.status, check.reason = 'needs_review', f'Pobranie nieudane: {check.fetched["error"]}.'
        check.save()
        return check
    title = (OG_TITLE.search(result.body) or TITLE.search(result.body))
    canonical = CANONICAL.search(result.body)
    canonical_url = normalize_url(canonical.group(1)) if canonical else normalize_url(result.final_url)
    check.fetched = {'title': re.sub(r'\s+', ' ', title.group(1)).strip()[:300] if title else '',
                     'canonical': canonical_url, 'content_type': result.content_type, 'redirects': result.redirects}
    if canonical_url and canonical_url != check.url_normalized:
        existing = Box.objects.filter(url=canonical_url).first()
        if existing is not None:
            check.status, check.box, check.reason = 'duplicate', existing, 'Adres kanoniczny jest już w bazie.'
            check.save()
            _attach_box(check, existing, now)
            return check
    check.status, check.reason = 'needs_review', 'Metadane pobrane; czeka na decyzję człowieka.'
    check.save()
    return check


@transaction.atomic
def decide(check: UrlCheck, staff, decision: str, reason: str = '', *, title: str = '', kind: str = 'article', now=None) -> UrlCheck:
    """Decyzja człowieka: accept tworzy box z linku czytelnika (oznaczony, noindex, bez miniatury i cytatu) albo publikuje
    oczekujący box użytkownika (kotwica), reject oznacza cel odrzucony (przypięcia: 7 dni na wymianę; box kotwica ukryty)."""
    now = now or timezone.now()
    if decision not in ('accept', 'reject'):
        raise ValueError('decision')
    check.decided_by, check.decided_at = staff, now
    from .spinka import recompute
    if decision == 'reject':
        check.status, check.reason = 'rejected', reason or 'Odrzucony przez zespół.'
        check.save()
        for pin in Pin.objects.filter(url_check=check).exclude(status='removed'):
            pin.target_status, pin.unavailable_since = 'rejected', now
            pin.replace_deadline = now + timedelta(days=config().replace_days)
            pin.save(update_fields=['target_status', 'unavailable_since', 'replace_deadline', 'updated_at'])
            recompute(pin.box, now)
        # box użytkownika z tego adresu (kotwica): ukryty z powodem
        for box in Box.objects.filter(url=check.url_normalized, added_by='user', status__in=('pending', 'published')):
            box.status, box.hidden_reason = 'hidden', (reason or 'Adres odrzucony przez zespół.')[:240]
            box.save(update_fields=['status', 'hidden_reason', 'updated_at'])
            from .legal import REGULAMIN_SEKCJA_ZRODLA, record_decision
            record_decision(user=box.added_by_user, target_type='box', restriction='hide', facts=box.hidden_reason,
                            basis=REGULAMIN_SEKCJA_ZRODLA, staff=staff, box=box, now=now)
            recompute(box, now)
        return check
    box = Box.objects.filter(url=check.url_normalized).first()
    if box is not None and box.status == 'pending':
        box.status = 'published'
        if title:
            box.title = title[:500]
        box.save(update_fields=['status', 'title', 'updated_at'])
        recompute(box, now)
    if box is None:
        domain = check.domain
        box = Box.objects.create(
            kind=kind, title=(title or check.fetched.get('title') or check.url_normalized)[:500], url=check.url_normalized,
            source_name=domain, source_domain=domain, added_by='user', reader_link=True, noindex=True,
            show_title=True, show_quote=False, show_thumbnail=False, show_avatar=False,
            published_at=(Pin.objects.filter(url_check=check).order_by('created_at', 'pk')
                          .values_list('created_at', flat=True).first() or check.created_at),
            search_text=normalize(title or check.fetched.get('title') or domain), status='published')
    check.status, check.box, check.reason = 'accepted', box, reason or 'Zaakceptowany przez zespół.'
    check.next_recheck_at = now + timedelta(days=config().url_recheck_days)
    check.save()
    _attach_box(check, box, now)
    return check


def _attach_box(check: UrlCheck, box: Box, now):
    from .spinka import recompute
    for pin in Pin.objects.filter(url_check=check).exclude(status='removed'):
        pin.pinned_box, pin.target_status, pin.unavailable_since, pin.replace_deadline = box, 'ok', None, None
        if pin.box_id == box.pk:
            pin.target_status = 'rejected'  # ten sam box co kotwica: przypięcie do samego siebie
        pin.save(update_fields=['pinned_box', 'target_status', 'unavailable_since', 'replace_deadline', 'updated_at'])
        recompute(pin.box, now)


def process_batch(limit: int = 20, fetcher=None, now=None) -> int:
    count = 0
    for check in UrlCheck.objects.filter(status='queued').order_by('created_at')[:limit]:
        process(check, fetcher, now)
        count += 1
    return count
