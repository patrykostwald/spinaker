"""Discover only explicit X links published on official parliamentary pages.

The module never calls api.x.com, never guesses a handle from a name, and does
not create candidates.  It deliberately fails closed for unknown hosts and
non-HTML responses.
"""
from __future__ import annotations

from html import unescape
import re
from urllib.parse import urlparse

import requests
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from news.political_models import SocialHandleEvidence

MAX_RESPONSE_BYTES = 1_000_000
ADMIN_BATCH_LIMIT = 25
ALLOWED_PROFILE_HOSTS = {
    'sejm': {'www.sejm.gov.pl', 'sejm.gov.pl'},
    'senat': {'www.senat.gov.pl', 'senat.gov.pl'},
    'ep': {'data.europarl.europa.eu', 'www.europarl.europa.eu', 'europarl.europa.eu'},
}
_HREF_RE = re.compile(r'''\bhref\s*=\s*["'](?P<href>[^"']+)["']''', re.IGNORECASE)
_EXCLUDED_X_PATHS = {'', 'home', 'search', 'explore', 'i', 'intent', 'share', 'compose', 'messages', 'settings', 'login', 'signup', 'hashtag'}


class SocialDiscoveryError(Exception):
    pass


def _safe_official_url(entry):
    url = (entry.profile_url or entry.source_url or '').strip()
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise SocialDiscoveryError('Profil nie ma bezpiecznego adresu HTTPS.')
    if parsed.hostname.lower() not in ALLOWED_PROFILE_HOSTS.get(entry.source, set()):
        raise SocialDiscoveryError('Host profilu nie jest zatwierdzonym oficjalnym hostem tego rejestru.')
    return url


def extract_x_links(html):
    """Return strict, explicitly linked account URLs; never inspect visible text."""
    if not isinstance(html, str):
        return []
    found = []
    seen = set()
    for match in _HREF_RE.finditer(html):
        raw_url = unescape(match.group('href')).strip()
        parsed = urlparse(raw_url)
        if parsed.scheme != 'https' or parsed.hostname.lower() not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
            continue
        segments = [part for part in parsed.path.split('/') if part]
        if not segments:
            continue
        handle = segments[0]
        if handle.lower() in _EXCLUDED_X_PATHS or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
            continue
        key = handle.lower()
        if key not in seen:
            found.append((handle, raw_url))
            seen.add(key)
    return found


def discover_official_page(evidence_url, *, allowed_hosts, http_get=requests.get):
    """Reusable strict extractor for a known official HTML page.

    A future PublicFigure registry can call this after supplying its own
    reviewed HTTPS host allowlist; no roster-specific inference is involved.
    """
    parsed = urlparse(evidence_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise SocialDiscoveryError('Profil nie ma bezpiecznego adresu HTTPS.')
    if parsed.hostname.lower() not in set(allowed_hosts):
        raise SocialDiscoveryError('Host profilu nie jest zatwierdzonym oficjalnym hostem tego rejestru.')
    try:
        response = http_get(evidence_url, timeout=(5, 20), allow_redirects=False,
            headers={'Accept': 'text/html,application/xhtml+xml'})
    except requests.RequestException as exc:
        raise SocialDiscoveryError('Nie udało się pobrać oficjalnego profilu.') from exc
    if response.status_code != 200:
        raise SocialDiscoveryError(f'Oficjalny profil zwrócił HTTP {response.status_code}.')
    content_type = response.headers.get('Content-Type', '') if hasattr(response, 'headers') else ''
    if 'html' not in content_type.lower():
        raise SocialDiscoveryError('Oficjalny profil nie zwrócił HTML; nie analizowano treści.')
    body = response.content
    if not isinstance(body, (bytes, bytearray)) or len(body) > MAX_RESPONSE_BYTES:
        raise SocialDiscoveryError('Odpowiedź profilu jest pusta lub zbyt duża; nie analizowano treści.')
    html = body.decode(response.encoding or 'utf-8', errors='replace')
    return extract_x_links(html)


def discover_for_entry(entry, *, http_get=requests.get, persist=True):
    """Fetch one approved official page and stage its explicit X links only."""
    evidence_url = _safe_official_url(entry)
    links = discover_official_page(evidence_url,
        allowed_hosts=ALLOWED_PROFILE_HOSTS[entry.source], http_get=http_get)
    if not persist:
        return links
    now = timezone.now()
    evidence = []
    for handle, extracted_url in links:
        item, created = SocialHandleEvidence.objects.get_or_create(
            roster_entry=entry, platform='x', handle__iexact=handle,
            defaults={'handle': handle, 'evidence_url': evidence_url, 'extracted_url': extracted_url, 'observed_at': now},
        )
        if created:
            item.subject_content_type = ContentType.objects.get_for_model(entry, for_concrete_model=False)
            item.subject_object_id = entry.pk
            item.save(update_fields=['subject_content_type', 'subject_object_id'])
        if not created:
            # Keep a human decision intact; only refresh source observations.
            item.evidence_url, item.extracted_url, item.observed_at = evidence_url, extracted_url, now
            item.save(update_fields=['evidence_url', 'extracted_url', 'observed_at'])
        evidence.append(item)
    return evidence
