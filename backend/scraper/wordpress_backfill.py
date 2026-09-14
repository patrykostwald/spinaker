"""Bounded metadata-only WordPress collection imports with a persistent snapshot."""
from datetime import datetime, timedelta, timezone as dt_timezone
from hashlib import sha256
from html import unescape
import json
import time
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import requests
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from news.models import Article, ArticleContent, ArchiveJob, ImportState, Source, SourceAccessInstruction
from news.signals import invalidate_search
from scraper.archive import SourceDelay, USER_AGENT, host_state, robots
from scraper.html_archive import retry_delay
from scraper.source_probe import public_link
from scraper.utils import fetch_feed, upsert_article
from scraper.access_gate import approved_instruction

# Publisher-disclosed endpoints measured in wordpress-archive-volume-2026-09-09.json.
# GZC remains a disabled candidate. Other WordPress sites were not confirmed.
VERIFIED_ENDPOINTS = {
    'krytykapolityczna.pl': 'https://krytykapolityczna.pl/wp-json/wp/v2/posts',
    'liberte.pl': 'https://liberte.pl/wp-json/wp/v2/posts',
    'wysokienapiecie.pl': 'https://wysokienapiecie.pl/wp-json/wp/v2/posts',
    'niebezpiecznik.pl': 'https://niebezpiecznik.pl/wp-json/wp/v2/posts',
    'jawnylublin.pl': 'https://jawnylublin.pl/wp-json/wp/v2/posts',
}
PAGE_SIZE = 100
FIELDS = ','.join(('id', 'date_gmt', 'link', 'title', 'featured_media', '_links',
    '_embedded.wp:featuredmedia.id', '_embedded.wp:featuredmedia.media_type',
    '_embedded.wp:featuredmedia.source_url',
    '_embedded.wp:featuredmedia.media_details.sizes.medium.source_url',
    '_embedded.wp:featuredmedia.media_details.sizes.thumbnail.source_url'))
# Liberté's API omits nested _fields (live pilot, post 4). This top-level
# metadata projection is the publisher's working shape recorded in the census.
LEGACY_FIELDS = 'id,date_gmt,link,title,featured_media,_links,_embedded'


class WordPressError(ValueError):
    pass


class SourceDisabled(WordPressError):
    pass


class MissingWordPressTitle(WordPressError):
    """The publisher supplied a usable permalink, but no title to archive."""
    pass


def host(url):
    return (urlsplit(url or '').hostname or '').lower().removeprefix('www.')


def endpoint_for(source):
    if source.catalog_stage != 'configured' or not source.is_active or not source.scrape_enabled:
        return None
    endpoint = VERIFIED_ENDPOINTS.get(host(source.url))
    if endpoint is None:
        return None
    if approved_instruction(source, SourceAccessInstruction.Channel.API, endpoint) is None:
        return None
    return endpoint


def ensure_enabled(source_id, endpoint):
    source = Source.objects.get(pk=source_id)
    if endpoint_for(source) != endpoint:
        raise SourceDisabled('source_disabled')
    return source


def collection_url(endpoint, *, offset=0, snapshot=False):
    fields = LEGACY_FIELDS if host(endpoint) == 'liberte.pl' else FIELDS
    return endpoint + '?' + urlencode({'per_page': 1 if snapshot else PAGE_SIZE, 'offset': offset,
        'orderby': 'id', 'order': 'desc' if snapshot else 'asc', 'status': 'publish',
        '_fields': 'id' if snapshot else fields, '_embed': 'wp:featuredmedia', '_envelope': 1})


def fetch_collection(source_id, endpoint, url):
    """Use the same host gate and bounded, DNS-pinned public reader as archives."""
    ensure_enabled(source_id, endpoint)
    if not url.startswith(endpoint + '?') or host(url) != host(endpoint):
        raise WordPressError('unverified_collection_url')
    gate = host_state(urlsplit(endpoint).hostname)
    if not gate['lock'].acquire(blocking=False):
        raise SourceDelay()
    attempted, delay = False, 3
    try:
        if time.monotonic() < gate['next_allowed']:
            raise SourceDelay()
        attempted = True
        policy = robots(url)
        if not policy.can_fetch(USER_AGENT, url):
            raise WordPressError('robots_disallowed')
        rate = policy.request_rate(USER_AGENT)
        delay = max(3, policy.crawl_delay(USER_AGENT) or 0,
            rate.seconds / rate.requests if rate and rate.requests else 0)
        ensure_enabled(source_id, endpoint)
        return fetch_feed(url)
    finally:
        if attempted:
            gate['next_allowed'] = time.monotonic() + delay
        gate['lock'].release()


def decode_collection(raw):
    payload = json.loads(raw)
    # Envelope exposes WP pagination totals through our existing byte-only reader.
    if not isinstance(payload, dict) or type(payload.get('status')) is not int:
        raise WordPressError('missing_wordpress_envelope')
    headers = payload.get('headers')
    if not isinstance(headers, dict):
        raise WordPressError('missing_wordpress_headers')
    if payload['status'] != 200:
        response = requests.Response()
        response.status_code = payload['status']
        response.headers.update({str(k): str(v) for k, v in headers.items()})
        raise requests.HTTPError(f"wordpress_http_{payload['status']}", response=response)
    values = {key.lower(): value for key, value in headers.items()}
    total = values.get('x-wp-total')
    if isinstance(total, bool) or not str(total).isdigit():
        raise WordPressError('missing_wordpress_total')
    rows = payload.get('body')
    if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
        raise WordPressError('invalid_wordpress_collection')
    ids = [row.get('id') if isinstance(row, dict) else None for row in rows]
    if any(type(item) is not int or item <= 0 for item in ids) or len(set(ids)) != len(ids):
        raise WordPressError('invalid_wordpress_identity')
    return rows, int(total)


def gmt_date(value):
    # date_gmt is explicitly UTC in the WP schema. Do not substitute date or modified.
    if not isinstance(value, str) or 'T' not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is not None and parsed.utcoffset() != timedelta(0):
            return None
        return parsed.replace(tzinfo=dt_timezone.utc)
    except (ValueError, OverflowError):
        return None


def featured_image(row):
    media_id = row.get('featured_media')
    if type(media_id) is not int or media_id <= 0:
        return ''
    embedded = row.get('_embedded')
    images = embedded.get('wp:featuredmedia', []) if isinstance(embedded, dict) else []
    if not isinstance(images, list):
        return ''
    matches = [item for item in images if isinstance(item, dict)
        and type(item.get('id')) is int and item['id'] == media_id and item.get('media_type') == 'image']
    if len(matches) != 1:
        return ''
    image = matches[0]
    sizes = image.get('media_details', {}).get('sizes', {}) if isinstance(image.get('media_details', {}), dict) else {}
    for name in ('medium', 'thumbnail'):
        variant = sizes.get(name) if isinstance(sizes, dict) else None
        address = variant.get('source_url') if isinstance(variant, dict) else None
        if isinstance(address, str) and public_link(address) and len(address) <= 1024:
            return address
    address = image.get('source_url')
    return address if isinstance(address, str) and public_link(address) and len(address) <= 1024 else ''


def post_metadata(row, endpoint):
    link = row.get('link')
    rendered = row.get('title', {}).get('rendered') if isinstance(row.get('title'), dict) else None
    title = unescape(strip_tags(rendered)).strip() if isinstance(rendered, str) else ''
    if (not isinstance(link, str) or not public_link(link) or len(link) > 1024
            or host(link) != host(endpoint)):
        raise WordPressError(f"invalid_wordpress_metadata:{row['id']}")
    if not title:
        raise MissingWordPressTitle(f"wordpress_missing_title:{row['id']}")
    return {'id': row['id'], 'url': link, 'title': title, 'published_date': gmt_date(row.get('date_gmt')),
        'date_raw': str(row.get('date_gmt') or '')[:80], 'image_url': featured_image(row)}


def save_metadata(source, metadata, page_url, digest):
    item, created = upsert_article(source=source, title=metadata['title'], url=metadata['url'],
        published_date=metadata['published_date'], image_url=metadata['image_url'],
        category='article', ingestion_method='archive')
    if item is None or item.source_id != source.pk:
        raise WordPressError('wordpress_source_identity_conflict')
    note = (f"WordPress REST, post ID {metadata['id']}; date_gmt={metadata['date_raw'] or 'brak'}"
        f" ({'UTC' if metadata['published_date'] else 'brak wiarygodnej daty GMT'}); "
        f"API: {page_url}; SHA-256 odpowiedzi: {digest}.")
    updates = {}
    if created:
        updates['evidence_note'] = (item.evidence_note + '\n' + note).strip()
    elif not item.category_reviewed:
        # Preserve all established values; only fill absent, attributable metadata.
        if item.published_date is None and metadata['published_date']:
            updates['published_date'] = metadata['published_date']
            updates['date_precision'] = 'time'
        if not item.image_url and metadata['image_url']:
            updates['image_url'] = metadata['image_url']
        if updates:
            updates['evidence_note'] = (item.evidence_note + '\nUzupełniono brakujące metadane. ' + note).strip()
    if updates:
        Article.objects.filter(pk=item.pk).update(**updates)
        transaction.on_commit(invalidate_search)
    ArticleContent.objects.get_or_create(article=item, defaults={'text': '', 'status': 'metadata_only',
        'method': 'wordpress_rest_metadata_v1', 'response_sha256': digest, 'source_url': page_url})
    return int(created), int(bool(updates) and not created)


def save_incomplete_metadata(source, row, page_url, digest):
    """Retain the publisher URL and durable evidence, without inventing an Article.

    Called in the same transaction as the good rows and collection cursor. Existing
    queue state/backoff is never reset. The regular page importer owns the retry.
    """
    job, _ = ArchiveJob.objects.get_or_create(url=row['link'], defaults={
        'source': source, 'kind': 'page', 'status': 'pending', 'last_error': 'wordpress_missing_title'})
    if job.source_id != source.pk:
        raise WordPressError('wordpress_source_identity_conflict')
    evidence = {'post_id': row['id'], 'url': row['link'], 'reason': 'wordpress_missing_title',
        'missing_fields': ['title'], 'date_gmt_raw': str(row.get('date_gmt') or '')[:80],
        'archive_job_id': job.pk, 'api_url': page_url, 'response_sha256': digest,
        'observed_at': timezone.now().isoformat()}
    # This is a historical observation of missing API metadata, not a claim that
    # the normal page fetch is still failing. Its current status lives in ArchiveJob.
    ImportState.objects.get_or_create(name=f'wordpress-gap:{source.pk}:{row["id"]}', defaults={
        'cursor': evidence, 'last_started': timezone.now(), 'last_error': 'wordpress_missing_title'})
    return {key: evidence[key] for key in ('post_id', 'url', 'reason', 'archive_job_id')}


def run_wordpress_source(source_id):
    source = Source.objects.get(pk=source_id)
    endpoint = endpoint_for(source)
    if not endpoint:
        return {'status': 'disabled', 'new_records': 0, 'source_id': source_id}
    now, token = timezone.now(), uuid4().hex
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=f'wordpress-archive:{source_id}')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        previous = dict(state.cursor)
        if previous.get('available_at', '') > now.isoformat():
            return {'status': 'deferred', 'new_records': 0, 'source_id': source_id}
        if previous.get('complete') and state.last_success and now - state.last_success < timedelta(days=1):
            return {'status': 'complete', 'new_records': 0, 'source_id': source_id}
        cursor = {} if previous.get('complete') else previous.copy()
        if cursor.get('endpoint', endpoint) != endpoint:
            return {'status': 'error', 'new_records': 0, 'source_id': source_id, 'error': 'wordpress_endpoint_changed'}
        cursor.update(endpoint=endpoint, lease=token, available_at=(now + timedelta(minutes=10)).isoformat())
        state.cursor, state.last_started = cursor, now
        state.save(update_fields=['cursor', 'last_started'])
    try:
        snapshot = 'cutoff_id' not in cursor
        offset = max(cursor.get('offset', 0) - 1, 0)
        page_url = collection_url(endpoint, offset=offset, snapshot=snapshot)
        raw = fetch_collection(source_id, endpoint, page_url)
        rows, total = decode_collection(raw)
        digest = sha256(raw).hexdigest()
        incomplete = []
        if snapshot:
            if len(rows) > 1 or (not rows and total):
                raise WordPressError('invalid_wordpress_snapshot')
            next_cursor = {'endpoint': endpoint, 'cutoff_id': rows[0]['id'] if rows else 0,
                'snapshot_at': now.isoformat(), 'snapshot_total': total,
                'offset': 0, 'last_id': None, 'processed': 0, 'pages_completed': 0, 'complete': not rows,
                'incomplete_records_seen': previous.get('incomplete_records_seen', 0),
                'recent_incomplete': previous.get('recent_incomplete', [])}
            records = []
        else:
            ids = [row['id'] for row in rows]
            if ids != sorted(ids):
                raise WordPressError('wordpress_ordering_not_honored')
            if not rows and total > offset:
                raise WordPressError('wordpress_empty_page_before_end')
            if cursor['offset'] and (not ids or ids[0] != cursor['last_id']):
                # Deletion/unpublishing can shift offset pagination. Replay the
                # snapshot, retaining its fixed ID boundary and already saved URLs.
                next_cursor = {**cursor, 'offset': 0, 'last_id': None, 'processed': 0,
                    'rewinds': cursor.get('rewinds', 0) + 1, 'pagination_shift': True}
                records = []
            else:
                remaining = rows[1:] if cursor['offset'] else rows
                accepted = [row for row in remaining if row['id'] <= cursor['cutoff_id']]
                records = []
                for row in accepted:
                    try:
                        records.append(post_metadata(row, endpoint))
                    except MissingWordPressTitle:
                        incomplete.append(row)
                if len({row['link'] for row in accepted}) != len(accepted):
                    raise WordPressError('wordpress_duplicate_permalink')
                complete = (bool(ids and ids[-1] >= cursor['cutoff_id']) or offset + len(rows) >= total)
                if not remaining and not complete:
                    raise WordPressError('wordpress_page_did_not_advance')
                next_cursor = {**cursor, 'offset': cursor['offset'] + len(accepted),
                    'last_id': accepted[-1]['id'] if accepted else cursor['last_id'],
                    'processed': cursor['processed'] + len(accepted),
                    'pages_completed': cursor['pages_completed'] + 1, 'complete': complete,
                    'observed_total': total, 'pagination_shift': False}
        with transaction.atomic():
            current = ImportState.objects.select_for_update().get(pk=state.pk)
            if current.cursor.get('lease') != token:
                return {'status': 'superseded', 'new_records': 0, 'source_id': source_id}
            source = ensure_enabled(source_id, endpoint)
            created = filled = 0
            for metadata in records:
                added, enriched = save_metadata(source, metadata, page_url, digest)
                created += added
                filled += enriched
            gaps = [save_incomplete_metadata(source, row, page_url, digest) for row in incomplete]
            if gaps:
                next_cursor['incomplete_records_seen'] = ImportState.objects.filter(
                    name__startswith=f'wordpress-gap:{source.pk}:').count()
                by_id = {item['post_id']: item for item in next_cursor.get('recent_incomplete', []) + gaps}
                next_cursor['recent_incomplete'] = list(by_id.values())[-20:]
            next_cursor['last_page_incomplete'] = len(gaps)
            shifted = next_cursor.get('pagination_shift', False)
            next_cursor.update(lease=None, failures=0, last_page_sha256=digest,
                available_at=(timezone.now() + timedelta(seconds=60 if shifted else 3)).isoformat())
            current.cursor = next_cursor
            current.imported += created
            current.last_error = ('wordpress_pagination_shift_rewound' if shifted
                else 'wordpress_missing_titles_queued' if gaps else '')
            if not shifted:
                current.last_success = timezone.now()
            current.save(update_fields=['cursor', 'imported', 'last_error', 'last_success'])
        return {'status': 'partial' if shifted or incomplete else 'ok', 'source_id': source_id,
            'phase': 'snapshot' if snapshot else 'rewound' if shifted else 'page',
            'new_records': created, 'metadata_filled': filled, 'processed': len(records),
            'incomplete_records': len(incomplete),
            'missing_dates': sum(item['published_date'] is None for item in records),
            'missing_images': sum(not item['image_url'] for item in records),
            'complete': next_cursor['complete'], 'cutoff_id': next_cursor['cutoff_id']}
    except Exception as exc:
        with transaction.atomic():
            current = ImportState.objects.select_for_update().get(pk=state.pk)
            if current.cursor.get('lease') == token:
                deferred = isinstance(exc, (SourceDelay, SourceDisabled))
                failures = previous.get('failures', 0) + (0 if deferred else 1)
                wait = 60 if deferred else retry_delay(exc, failures)
                current.cursor = {**previous, 'lease': None, 'failures': failures,
                    'available_at': (timezone.now() + timedelta(seconds=wait)).isoformat()}
                current.last_error = '' if deferred else str(exc)[:200] if isinstance(exc, WordPressError) else type(exc).__name__
                current.save(update_fields=['cursor', 'last_error'])
        return {'status': 'disabled' if isinstance(exc, SourceDisabled) else 'deferred' if isinstance(exc, SourceDelay) else 'error',
            'source_id': source_id, 'new_records': 0,
            'error': str(exc)[:200] if isinstance(exc, WordPressError) else type(exc).__name__}


def wordpress_cycle():
    """One request per confirmed source, sequentially, in the shared scheduler process."""
    sources = [source for source in Source.objects.filter(is_active=True, scrape_enabled=True,
        catalog_stage='configured').order_by('pk') if endpoint_for(source)]
    results = [run_wordpress_source(source.pk) for source in sources]
    status = ('partial' if any(row['status'] in ('error', 'partial') for row in results)
        else 'ok' if any(row['status'] == 'ok' for row in results) else 'idle')
    return {'status': status, 'new_records': sum(row['new_records'] for row in results), 'sources': results}
