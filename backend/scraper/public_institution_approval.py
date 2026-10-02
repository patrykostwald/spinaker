"""Owner-authorised metadata cards; technical checks never grant content access."""
import json
import re
from urllib.parse import urlsplit

import feedparser
from django.utils.dateparse import parse_datetime

from news.models import FetchAttempt, ImportState
from scraper.source_probe import ProbeError, ProbeNetwork, public_link, source_signature
from scraper.utils import _fetch_fingerprint


# Explicit roots, with DNS-label boundaries (never substring matching).
PUBLIC_DOMAINS = (
    'gov.pl', 'sejm.gov.pl', 'senat.gov.pl', 'prezydent.pl', 'nbp.pl',
    'stat.gov.pl', 'uodo.gov.pl', 'rpo.gov.pl', 'trybunal.gov.pl',
    'sn.pl', 'nik.gov.pl', 'europa.eu',
)
REVIEWED_BY = 'hurtowa decyzja właściciela 3.10.2026'
BLOCKING_STATUSES = {'suspended', 'contact_required', 'rejected'}
SCOPE_NOTE = 'Tytuł, data, link i opis z kanału; bez pełnej treści, HTML artykułów, zdjęć i załączników.'


def official_url(url):
    try:
        parts = urlsplit(url or '')
        host = (parts.hostname or '').lower()
        return bool(public_link(url) and not parts.username and not parts.password
                    and parts.port in (None, 80, 443)
                    and any(host == root or host.endswith('.' + root) for root in PUBLIC_DOMAINS))
    except ValueError:
        return False


def eligibility(source, cards):
    if source.source_type != 'institution':
        return 'Poza zakresem: źródło nie jest instytucją'
    if source.catalog_stage not in ('candidate', 'configured'):
        return 'Źródło wykluczone lub nieznany etap katalogu'
    if not official_url(source.url):
        return 'Domena instytucji poza jawną listą'
    # Preserve the newest decision for every channel/endpoint, including a
    # suspension followed by an unrelated approved card on the same source.
    seen = set()
    for card in cards:
        key = (card.channel, card.endpoint)
        if key not in seen and card.status in BLOCKING_STATUSES:
            return f'Decyzja blokująca: {card.status}'
        seen.add(key)
    return ''


def audit_state(source):
    state = ImportState.objects.filter(name=f'source-check:{source.pk}').first()
    cursor = state.cursor if state and isinstance(state.cursor, dict) else {}
    return cursor if cursor.get('signature') == source_signature(source) else {}


def channel_for(source, cards, audit):
    if source.rss_url:
        return 'rss', source.rss_url
    rss = audit.get('rss') or {}
    if rss.get('url'):
        return 'rss', rss['url']
    discovery = audit.get('legal_channel_discovery') or {}
    if discovery.get('signature') == source_signature(source):
        for item in discovery.get('channels', []):
            if item.get('status') == 'working' and item.get('url'):
                return 'rss', item['url']
    for card in cards:
        if card.channel in ('rss', 'api'):
            return card.channel, card.endpoint
    api = audit.get('official_api') or {}
    if api.get('url'):
        return 'api', api['url']
    # These are documented endpoints already used by the application's preflight.
    from scraper.structured_metadata import SPECS
    for spec in SPECS.values():
        if source.url.rstrip('/') == spec['source_url'].rstrip('/'):
            return 'api', spec['endpoint']
    return '', ''


def error_reason(error):
    if re.search(r'(?<!\d)403(?!\d)', error or ''):
        return '403: szukać innego oficjalnego kanału'
    return 'Kanał niedostępny: ' + (error or 'brak potwierdzonego sukcesu')


def prior_result(source, channel, endpoint, audit):
    """Latest actual check of this endpoint; gate refusals are not HTTP checks."""
    results = []
    attempt = FetchAttempt.objects.filter(source=source, channel=channel,
        url_fingerprint=_fetch_fingerprint(endpoint)).exclude(
            outcome__in=['reserved', 'refused_no_instruction', 'refused_expired',
                         'refused_suspended', 'refused_scope_mismatch',
                         'rate_limit_preemptive', 'daily_limit_preemptive']).first()
    if attempt:
        ok = attempt.outcome == 'ok' and attempt.http_status and 200 <= attempt.http_status < 300
        results.append((attempt.attempted_at, '' if ok else error_reason(
            str(attempt.http_status or attempt.error_code or attempt.outcome)),
            {'fetch_attempt_id': attempt.pk}))
    checked = parse_datetime(audit.get('checked_at') or '')
    item = audit.get('rss' if channel == 'rss' else 'official_api') or {}
    if checked and checked.tzinfo and item.get('url') == endpoint and item.get('status') != 'unknown':
        results.append((checked, '' if item.get('status') == 'working' else error_reason(item.get('error')),
                        {'audit_checked_at': checked.isoformat()}))
    discovery = audit.get('legal_channel_discovery') or {}
    checked = parse_datetime(discovery.get('checked_at') or '')
    if channel == 'rss' and checked and checked.tzinfo and discovery.get('signature') == source_signature(source):
        for item in discovery.get('channels', []):
            if item.get('url') == endpoint:
                results.append((checked, '' if item.get('status') == 'working' else error_reason(item.get('error')),
                                {'channel_discovery_checked_at': checked.isoformat()}))
    # Some legacy importers only stored status text on Source. Never retry a
    # known wall or robots denial merely because there is no FetchAttempt yet.
    if source.last_error and re.search(r'(?<!\d)(403|404|410)(?!\d)|robots', source.last_error, re.I):
        at = source.last_attempted or source.updated_at
        results.append((at, error_reason(source.last_error), {'source_last_attempted': at.isoformat()}))
    state = ImportState.objects.filter(name=f'public-institution-probe:{source.pk}').first()
    saved = state.cursor if state and isinstance(state.cursor, dict) else {}
    if (saved.get('signature') == source_signature(source) and saved.get('endpoint') == endpoint
            and saved.get('channel') == channel and state.last_started):
        results.append((state.last_started, saved['reason'], saved['evidence']))
    if results:
        _, reason, evidence = max(results, key=lambda result: result[0])
        return reason, evidence
    return None


class ApprovalProbeNetwork(ProbeNetwork):
    """Existing audit transport, additionally bounded to official hosts and 8 GETs."""
    def __init__(self):
        super().__init__(delay=3)
        self.requests_left = 8

    def raw(self, address):
        if not official_url(address):
            raise ProbeError('redirect_outside_official_domains')
        if self.requests_left <= 0:
            raise ProbeError('probe_request_limit')
        self.requests_left -= 1
        return super().raw(address)


def probe_channel(channel, endpoint, network):
    try:
        raw, final_url, policies = network.fetch(endpoint)
        if not official_url(final_url):
            raise ProbeError('redirect_outside_official_domains')
        if channel == 'rss':
            if b'<!ENTITY' in raw.upper():
                raise ProbeError('xml_entities_not_allowed')
            parsed = feedparser.parse(raw)
            if not parsed.get('version') or not any(
                    str(entry.get('title', '')).strip() and public_link(entry.get('link', ''))
                    for entry in parsed.get('entries', [])):
                raise ProbeError('not_a_working_feed')
        else:
            payload = json.loads(raw)
            if not isinstance(payload, (dict, list)) or not payload or (
                    isinstance(payload, dict) and ('error' in payload or 'errors' in payload)):
                raise ProbeError('not_a_working_api')
        return '', {'final_url': final_url, 'robots': policies, 'bytes': len(raw)}
    except Exception as exc:
        code = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
        return error_reason(code), {'error': code}
