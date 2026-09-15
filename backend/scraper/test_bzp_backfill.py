from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings
from django.utils import timezone

from news.models import Article, ArticleContent, ImportState, Source, SourceAccessInstruction
from scraper.bzp_backfill import (DETAIL_URL, MAX_BATCH_SIZE, SEARCH_URL, SOURCE_URL,
    BZPRateLimited, bzp_backfill_cycle, fetch_page)


@pytest.fixture
def source(db):
    source = Source.objects.create(name='Biuletyn Zamówień Publicznych', url=SOURCE_URL,
        source_type='institution')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api', allowed_scope='metadata',
        endpoint=SEARCH_URL, terms_url='https://ezamowienia.gov.pl/', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test')
    return source


def row(identifier, published='2026-09-13T10:15:00+02:00'):
    return {'noticeId': identifier, 'noticeNumber': f'2026/BZP/{identifier}',
        'orderObject': f'Zamówienie {identifier}', 'publicationDate': published,
        'fullText': 'must never be stored'}


def test_disabled_by_default_never_fetches_or_creates_state(source):
    with patch('scraper.bzp_backfill.fetch_page') as fetch:
        assert bzp_backfill_cycle()['status'] == 'disabled'
    fetch.assert_not_called()
    assert not ImportState.objects.exists()


@override_settings(BZP_API_ENABLED=True)
def test_requires_preconfigured_active_source(db):
    with patch('scraper.bzp_backfill.fetch_page') as fetch:
        assert bzp_backfill_cycle()['status'] == 'disabled'
    fetch.assert_not_called()
    assert not Source.objects.exists()


@override_settings(BZP_API_ENABLED=True)
def test_frozen_cutoff_newest_first_bounded_and_idempotent(source):
    now = datetime(2026, 9, 14, 8, tzinfo=dt_timezone.utc)
    rows = [row('abc')]
    with patch('scraper.bzp_backfill.timezone.now', return_value=now), \
            patch('scraper.bzp_backfill.fetch_page', return_value=rows) as fetch:
        first = bzp_backfill_cycle(batch_size=999)
    assert first == {'status': 'ok', 'new_records': 1, 'day': '2026-09-13',
        'page': 1, 'cutoff': '2026-09-13'}
    assert fetch.call_args.kwargs['page_size'] == MAX_BATCH_SIZE
    article = Article.objects.get()
    assert article.source == source and article.url == DETAIL_URL + 'abc'
    assert article.description == 'Ogłoszenie BZP 2026/BZP/abc'
    assert article.ingestion_method == 'archive'
    assert not ArticleContent.objects.exists()
    state = ImportState.objects.get()
    assert state.cursor == {'cutoff': '2026-09-13', 'day': '2026-09-12',
        'page': 1, 'complete': False}
    # Replay of the same persisted day/page can never duplicate a box.
    state.cursor = {'cutoff': '2026-09-13', 'day': '2026-09-13', 'page': 1, 'complete': False}
    state.save(update_fields=['cursor'])
    with patch('scraper.bzp_backfill.fetch_page', return_value=rows):
        assert bzp_backfill_cycle()['new_records'] == 0
    assert Article.objects.count() == 1
    assert 'fullText' not in article.description


@override_settings(BZP_API_ENABLED=True)
def test_429_retry_after_defers_without_moving_cursor_or_writing(source):
    with patch('scraper.bzp_backfill.fetch_page', side_effect=BZPRateLimited(1800)):
        result = bzp_backfill_cycle()
    assert result['status'] == 'deferred' and result['retry_after_seconds'] == 1800
    assert ImportState.objects.get().cursor['page'] == 1
    assert not Article.objects.exists()


@override_settings(BZP_API_SEARCH_URL=SEARCH_URL)
def test_fetch_uses_official_endpoint_and_audited_post_transport(source):
    response = Mock(status_code=429, headers={'Retry-After': '321'})
    instruction = SourceAccessInstruction.objects.get(source=source)
    with patch('scraper.bzp_backfill.fetch_feed', side_effect=requests.HTTPError(response=response)) as fetch:
        with pytest.raises(BZPRateLimited) as raised:
            fetch_page(source=source, instruction=instruction, endpoint=SEARCH_URL,
                date_from='2026-09-13', date_to='2026-09-13', page=1, page_size=100)
    assert raised.value.retry_after == 321
    assert fetch.call_args.kwargs['method'] == 'POST'
    assert fetch.call_args.kwargs['requested_kind'] == 'api_record'
    assert b'"pageSize":25' in fetch.call_args.kwargs['body']


@override_settings(BZP_API_ENABLED=True)
def test_malformed_or_out_of_window_page_does_not_advance(source):
    with patch('scraper.bzp_backfill.timezone.localdate', return_value=date(2026, 9, 14)), \
            patch('scraper.bzp_backfill.fetch_page', return_value=[row('late', '2026-09-14T01:00:00+02:00')]):
        result = bzp_backfill_cycle()
    assert result['status'] == 'error'
    assert ImportState.objects.get().cursor['page'] == 1
    assert not Article.objects.exists()
