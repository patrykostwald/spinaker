"""Disabled-by-default, metadata-only adapter for the official BZP API.

The endpoint is deliberately configuration-only: the source audit requires the
current UZP integration instruction to be checked before a pilot.  This module
has no scheduler hook and does not create a Source automatically.
"""
from datetime import date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo
import json

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from news.models import ArticleCategory, FetchAttempt, ImportState, Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.utils import fetch_feed, safe_url, upsert_article

SOURCE_URL = 'https://ezamowienia.gov.pl/pl/'
DETAIL_URL = 'https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/'
SEARCH_URL = 'https://ezamowienia.gov.pl/mo-board/api/v1/Board/Search'
STATE_NAME = 'official-backfill:bzp:v1'
MAX_BATCH_SIZE = 25
# The audited operating ceiling is 20 requests/minute.  A setting may make the
# client slower, but cannot weaken that floor without a code review.
MIN_REQUEST_INTERVAL_SECONDS = 3.0


class BZPRateLimited(Exception):
    def __init__(self, retry_after):
        super().__init__('bzp_rate_limited')
        self.retry_after = max(0, int(retry_after))


def _enabled_source():
    if not getattr(settings, 'BZP_API_ENABLED', False):
        return None
    return Source.objects.filter(url=SOURCE_URL, is_active=True, scrape_enabled=True,
        catalog_stage='configured').first()


def _retry_after(response):
    value = response.headers.get('Retry-After', '')
    if str(value).isdigit():
        return int(value)
    try:
        from email.utils import parsedate_to_datetime
        return max(0, round((parsedate_to_datetime(value) - datetime.now(ZoneInfo('UTC'))).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return 60


def reviewed_endpoint(source):
    endpoint = str(getattr(settings, 'BZP_API_SEARCH_URL', SEARCH_URL)).strip()
    if not safe_url(endpoint) or not endpoint.startswith('https://ezamowienia.gov.pl/'):
        raise ValueError('BZP_API_SEARCH_URL must be the reviewed official HTTPS endpoint')
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.API, endpoint)
    if instruction is None:
        return endpoint, None
    return endpoint, instruction


def fetch_page(*, source, instruction, endpoint, date_from, date_to, page, page_size):
    """Read one reviewed search page through the shared audited transport.

    30.09.2026: the public board API answers POST with 405 and expects GET with query parameters,
    returning a plain JSON list (older responses wrapped rows in ``items``/``data``)."""
    from urllib.parse import urlencode
    page_size = min(MAX_BATCH_SIZE, max(1, int(page_size)))
    query = urlencode({'PublicationDateFrom': date_from, 'PublicationDateTo': date_to,
                       'PageNumber': page, 'PageSize': page_size})
    try:
        raw = fetch_feed(f'{endpoint}?{query}', hostname_transport=True, audit_source=source,
            audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.API_RECORD,
            request_headers={'Accept': 'application/json'})
    except requests.HTTPError as exc:
        if getattr(exc.response, 'status_code', None) == 429:
            raise BZPRateLimited(_retry_after(exc.response)) from exc
        raise
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid BZP search response') from exc
    rows = payload if isinstance(payload, list) else payload.get('items', payload.get('data')) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError('Invalid BZP search response')
    return rows


def _field(row, *names):
    for name in names:
        if row.get(name) not in (None, ''):
            return row[name]
    return None


def _metadata(row, window_from, window_to):
    if not isinstance(row, dict):
        raise ValueError('Invalid BZP notice')
    notice_id = str(_field(row, 'noticeId', 'id', 'objectId') or '').strip()
    number = str(_field(row, 'noticeNumber', 'number') or '').strip()
    title = str(_field(row, 'orderObject', 'title', 'noticeTitle') or '').strip()
    if not title and _field(row, 'organizationName'):
        # Plany postępowań i część ogłoszeń nie mają przedmiotu zamówienia — tytuł z typu ogłoszenia i zamawiającego.
        title = f"{_field(row, 'noticeTypeDisplayName', 'noticeType') or 'Ogłoszenie'}: {_field(row, 'organizationName')}".strip()
    published = _field(row, 'publicationDate', 'publicationDateTime', 'publishedAt')
    if not notice_id or not number or not title or not published:
        raise ValueError('Incomplete BZP notice metadata')
    dt = datetime.fromisoformat(str(published).replace('Z', '+00:00'))
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=ZoneInfo('Europe/Warsaw'))
    local_day = timezone.localtime(dt, ZoneInfo('Europe/Warsaw')).date()
    if not window_from <= local_day <= window_to:
        raise ValueError('BZP notice outside requested frozen window')
    url = DETAIL_URL + quote(notice_id, safe='')
    return notice_id, number, title, dt, url


def save_metadata(source, row, window_from, window_to):
    """Idempotently save only public notice metadata as a box."""
    _, number, title, published, url = _metadata(row, window_from, window_to)
    article, created = upsert_article(source=source, title=title, url=url,
        published_date=published, category=ArticleCategory.DOCUMENT,
        description=f'Ogłoszenie BZP {number}', ingestion_method='archive')
    return bool(article and created)


def history_floor(cursor):
    """Najstarszy dzień przejścia (zasilanie bazy 6.10): pierwsze przejście sięga BZP_BACKFILL_DAYS wstecz
    od dnia odcięcia (domyślnie 365, najwyżej 1095); kolejne przejścia kończą się na poprzednim odcięciu."""
    if cursor.get('floor'):
        return date.fromisoformat(cursor['floor'])
    import os
    days = min(1095, max(1, int(os.environ.get('BZP_BACKFILL_DAYS', '365'))))
    return date.fromisoformat(cursor['cutoff']) - timedelta(days=days)


def _next_pass(cursor, started):
    """Po ukończonym przejściu: nowe, krótkie przejście od wczoraj do poprzedniego odcięcia (nowe ogłoszenia)."""
    yesterday = timezone.localdate(started) - timedelta(days=1)
    previous = date.fromisoformat(cursor['cutoff'])
    if previous >= yesterday:
        return None
    return {'cutoff': yesterday.isoformat(), 'day': yesterday.isoformat(), 'page': 1, 'complete': False,
            'floor': (previous + timedelta(days=1)).isoformat(),
            'history_complete_at': cursor.get('history_complete_at') or started.isoformat()}


def bzp_backfill_cycle(*, batch_size=MAX_BATCH_SIZE):
    """Import at most one page, walking complete days newest-to-oldest."""
    source = _enabled_source()
    if source is None:
        return {'status': 'disabled', 'new_records': 0}
    endpoint, instruction = reviewed_endpoint(source)
    if instruction is None:
        return {'status': 'blocked_access_review', 'new_records': 0}
    batch_size = min(MAX_BATCH_SIZE, max(1, int(batch_size)))
    state, _ = ImportState.objects.get_or_create(name=STATE_NAME)
    started = timezone.now()
    state.last_started = started
    state.save(update_fields=['last_started'])
    cursor = dict(state.cursor)
    if not cursor:
        cutoff = timezone.localdate(started) - timedelta(days=1)
        cursor = {'cutoff': cutoff.isoformat(), 'day': cutoff.isoformat(),
            'page': 1, 'complete': False}
        state.cursor = cursor
        state.save(update_fields=['cursor'])
    if cursor.get('complete'):
        fresh = _next_pass(cursor, started)
        if fresh is None:
            return {'status': 'complete', 'new_records': 0, 'cutoff': cursor['cutoff']}
        cursor = state.cursor = fresh
        state.save(update_fields=['cursor'])
    if cursor.get('cutoff') < cursor.get('day'):
        raise ValueError('Invalid BZP newest-to-oldest cursor')
    day = date.fromisoformat(cursor['day'])
    if day < history_floor(cursor):
        # Okno historii zebrane: koniec przejścia bez zapytania; następne zaczyna się od nowych dni.
        cursor = {**cursor, 'complete': True, 'floor': history_floor(cursor).isoformat(),
                  'history_complete_at': cursor.get('history_complete_at') or started.isoformat()}
        state.cursor = cursor
        state.save(update_fields=['cursor'])
        return {'status': 'complete', 'new_records': 0, 'cutoff': cursor['cutoff']}
    try:
        rows = fetch_page(source=source, instruction=instruction, endpoint=endpoint,
            date_from=day.isoformat(), date_to=day.isoformat(),
            page=int(cursor['page']), page_size=batch_size)
        created = 0
        for row in rows:
            try:
                created += save_metadata(source, row, day, day)
            except ValueError as exc:
                if 'Incomplete BZP notice metadata' not in str(exc):
                    raise  # wpis spoza okna albo zła odpowiedź — kursor nie może się przesunąć
                continue  # jeden niepełny wpis nie zatrzymuje całej strony wyników
        next_cursor = dict(cursor)
        if len(rows) < batch_size:
            next_cursor.update(day=(day - timedelta(days=1)).isoformat(), page=1)
        else:
            next_cursor['page'] = int(cursor['page']) + 1
        with transaction.atomic():
            current = ImportState.objects.select_for_update().get(pk=state.pk)
            if current.cursor != cursor:
                raise ValueError('BZP cursor changed during import')
            current.cursor = next_cursor
            current.last_success, current.last_error = timezone.now(), ''
            current.imported += created
            current.save(update_fields=['cursor', 'last_success', 'last_error', 'imported'])
        return {'status': 'ok', 'new_records': created, 'day': day.isoformat(),
            'page': cursor['page'], 'cutoff': cursor['cutoff']}
    except BZPRateLimited as exc:
        ImportState.objects.filter(pk=state.pk).update(last_error=str(exc))
        return {'status': 'deferred', 'new_records': 0,
            'retry_after_seconds': exc.retry_after, 'cutoff': cursor['cutoff']}
    except Exception as exc:
        ImportState.objects.filter(pk=state.pk).update(last_error=str(exc)[:200])
        return {'status': 'error', 'new_records': 0, 'error': str(exc)[:200]}
