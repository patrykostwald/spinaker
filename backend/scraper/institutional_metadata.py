"""Disabled-by-default, bounded metadata pilots for audited institutions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
import os
import time
from urllib.parse import urlsplit
from uuid import uuid4
from xml.etree import ElementTree

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from news.models import Article, ArticleContent, ImportState, Source
from news.signals import invalidate_search
from scraper.archive import SourceDelay, USER_AGENT, host_state, robots
from scraper.html_archive import retry_delay
from scraper.source_probe import public_link
from scraper.utils import fetch_feed, upsert_article

MAX_RECORDS = 25
MIN_HOST_INTERVAL_SECONDS = 3

@dataclass(frozen=True)
class Pilot:
    key: str
    source_host: str
    endpoint: str
    kind: str
    path_markers: tuple[str, ...] = ()

PILOTS = {
    'knf': Pilot('knf', 'knf.gov.pl', 'https://www.knf.gov.pl/sitemap.xml', 'sitemap',
        ('/komunikacja/komunikaty', '/dla_konsumenta/ostrzezenia_publiczne',
         '/wyniki_kontroli/', '/publikacje_i_opracowania/')),
    'nik': Pilot('nik', 'nik.gov.pl', 'https://www.nik.gov.pl/rss/id,1.html', 'rss'),
}

class MetadataPilotError(ValueError): pass

def enabled():
    return os.getenv('INSTITUTIONAL_METADATA_PILOT_ENABLED', '').lower() in ('1', 'true', 'yes')

def _host(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')

def _publisher_url(value, pilot):
    return (isinstance(value, str) and len(value) <= 1024 and public_link(value)
        and _host(value) == pilot.source_host)

def _eligible(source, pilot):
    return (enabled() and source.is_active and source.scrape_enabled
        and source.catalog_stage == 'configured' and _host(source.url or '') == pilot.source_host)

def parse_feed(raw, pilot):
    """Return at most MAX_RECORDS independent publisher publication units."""
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper(): raise MetadataPilotError('invalid_xml')
    try: root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc: raise MetadataPilotError('invalid_xml') from exc
    rows = []
    if pilot.kind == 'rss':
        for item in root.findall('.//item')[:MAX_RECORDS]:
            link = (item.findtext('link') or '').strip()
            title = unescape(strip_tags(item.findtext('title') or '')).strip()
            raw_date = (item.findtext('pubDate') or '').strip()
            try:
                published = parsedate_to_datetime(raw_date) if raw_date else None
                if published and published.tzinfo is None: published = None
            except (TypeError, ValueError, OverflowError): published = None
            if _publisher_url(link, pilot) and title:
                rows.append({'url': link, 'title': title[:500], 'published_date': published,
                    'date_raw': raw_date[:100]})
    else:
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        nodes = root.findall('s:url', ns) if root.tag.endswith('urlset') else []
        if not nodes and root.tag.endswith('urlset'): nodes = root.findall('url')
        for node in nodes:
            link = (node.findtext('s:loc', namespaces=ns) or node.findtext('loc') or '').strip()
            if (_publisher_url(link, pilot)
                    and any(marker.lower() in urlsplit(link).path.lower() for marker in pilot.path_markers)):
                # Sitemap lastmod is not a publisher publication date.
                rows.append({'url': link, 'title': '', 'published_date': None, 'date_raw': ''})
                if len(rows) == MAX_RECORDS: break
    return rows

def fetch_bounded(source_id, pilot):
    source = Source.objects.get(pk=source_id)
    if not _eligible(source, pilot):
        raise MetadataPilotError('source_disabled')
    gate = host_state(pilot.source_host)
    if not gate['lock'].acquire(blocking=False): raise SourceDelay()
    attempted, delay = False, MIN_HOST_INTERVAL_SECONDS
    try:
        if time.monotonic() < gate['next_allowed']: raise SourceDelay()
        attempted = True
        policy = robots(pilot.endpoint)
        if not policy.can_fetch(USER_AGENT, pilot.endpoint): raise MetadataPilotError('robots_disallowed')
        rate = policy.request_rate(USER_AGENT)
        delay = max(MIN_HOST_INTERVAL_SECONDS, policy.crawl_delay(USER_AGENT) or 0,
            rate.seconds / rate.requests if rate and rate.requests else 0)
        return fetch_feed(pilot.endpoint)
    finally:
        if attempted: gate['next_allowed'] = time.monotonic() + delay
        gate['lock'].release()

def _save(source, row, pilot, digest, retrieved_at):
    article, created = upsert_article(source=source, title=row['title'], url=row['url'],
        published_date=row['published_date'], category='statement', ingestion_method='archive')
    if article is None or article.source_id != source.pk: raise MetadataPilotError('source_identity_conflict')
    if created:
        Article.objects.filter(pk=article.pk).update(evidence_note=(
            f"Źródło: {row['url']}; data wydawcy: {row['date_raw'] or 'brak'}; "
            f"pozyskano: {retrieved_at.isoformat()}; przetworzenie: normalizacja metadanych."))
        transaction.on_commit(invalidate_search)
    ArticleContent.objects.get_or_create(article=article, defaults={'text': '', 'status': 'metadata_only',
        'method': f'{pilot.key}_{pilot.kind}_metadata_v1', 'response_sha256': digest,
        'source_url': pilot.endpoint})
    return int(created)

def run_pilot(source_id, key, *, cutoff):
    """One request and one bounded atomic page; cutoff is frozen on first call."""
    pilot, source = PILOTS[key], Source.objects.get(pk=source_id)
    if not enabled() or not source.is_active or not source.scrape_enabled:
        return {'status': 'disabled', 'new_records': 0}
    if cutoff.tzinfo is None: raise MetadataPilotError('cutoff_requires_timezone')
    now, token = timezone.now(), uuid4().hex
    name = f'institutional-metadata:{key}:{source_id}'
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=name)
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        cursor, frozen = dict(state.cursor), cutoff.isoformat()
        if cursor.get('cutoff') and cursor['cutoff'] != frozen: raise MetadataPilotError('cutoff_mismatch')
        if cursor.get('complete'): return {'status': 'complete', 'new_records': 0}
        if cursor.get('available_at', '') > now.isoformat(): return {'status': 'deferred', 'new_records': 0}
        cursor.update(cutoff=frozen, lease=token, available_at=(now + timedelta(minutes=10)).isoformat())
        state.cursor = cursor; state.last_started = now
        state.save(update_fields=['cursor', 'last_started'])
    try:
        raw = fetch_bounded(source_id, pilot)
        rows, digest = parse_feed(raw, pilot), sha256(raw).hexdigest()
        # KNF remains discovery-only: the audited sitemap does not supply titles or publication dates.
        savable = rows if pilot.kind == 'rss' else []
        with transaction.atomic():
            source = Source.objects.select_for_update().get(pk=source_id)
            state = ImportState.objects.select_for_update().get(name=name)
            if state.cursor.get('lease') != token: return {'status': 'superseded', 'new_records': 0}
            if not _eligible(source, pilot):
                state.cursor = {**state.cursor, 'lease': None, 'available_at': timezone.now().isoformat()}
                state.save(update_fields=['cursor'])
                return {'status': 'disabled', 'new_records': 0}
            created = sum(_save(source, row, pilot, digest, now) for row in savable
                if row['published_date'] is None or row['published_date'] <= cutoff)
            state.cursor = {'cutoff': frozen, 'complete': True, 'lease': None,
                'records_examined': len(rows), 'response_sha256': digest,
                'available_at': (timezone.now() + timedelta(seconds=MIN_HOST_INTERVAL_SECONDS)).isoformat()}
            state.imported += created; state.last_success = timezone.now(); state.last_error = ''
            state.save(update_fields=['cursor', 'imported', 'last_success', 'last_error'])
        return {'status': 'complete', 'new_records': created, 'examined': len(rows)}
    except Exception as exc:
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name=name)
            if state.cursor.get('lease') == token:
                failures = state.cursor.get('failures', 0) + (0 if isinstance(exc, SourceDelay) else 1)
                delay = MIN_HOST_INTERVAL_SECONDS if isinstance(exc, SourceDelay) else retry_delay(exc, failures)
                state.cursor = {**state.cursor, 'lease': None, 'failures': failures,
                    'available_at': (timezone.now() + timedelta(seconds=delay)).isoformat()}
                state.last_error = '' if isinstance(exc, SourceDelay) else str(exc)[:200]
                state.save(update_fields=['cursor', 'last_error'])
        return {'status': 'deferred' if isinstance(exc, SourceDelay) else 'error', 'new_records': 0,
            'error': '' if isinstance(exc, SourceDelay) else str(exc)[:200]}
