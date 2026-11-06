from datetime import date, datetime, timedelta, timezone as dt_timezone
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
        source_type='institution', is_active=True, scrape_enabled=True,
        catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api', allowed_scope='metadata',
        endpoint=SEARCH_URL, terms_url='https://ezamowienia.gov.pl/', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=30), daily_request_cap=1000)
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
def test_fetch_uses_official_endpoint_and_audited_get_transport(source):
    response = Mock(status_code=429, headers={'Retry-After': '321'})
    instruction = SourceAccessInstruction.objects.get(source=source)
    with patch('scraper.bzp_backfill.fetch_feed', side_effect=requests.HTTPError(response=response)) as fetch:
        with pytest.raises(BZPRateLimited) as raised:
            fetch_page(source=source, instruction=instruction, endpoint=SEARCH_URL,
                date_from='2026-09-13', date_to='2026-09-13', page=1, page_size=100)
    assert raised.value.retry_after == 321
    assert 'method' not in fetch.call_args.kwargs and 'body' not in fetch.call_args.kwargs  # API przyjmuje GET (POST → 405)
    assert fetch.call_args.kwargs['requested_kind'] == 'api_record'
    assert fetch.call_args.args[0].startswith(SEARCH_URL + '?') and 'PageSize=25' in fetch.call_args.args[0]


@override_settings(BZP_API_ENABLED=True)
def test_malformed_or_out_of_window_page_does_not_advance(source):
    with patch('scraper.bzp_backfill.timezone.localdate', return_value=date(2026, 9, 14)), \
            patch('scraper.bzp_backfill.fetch_page', return_value=[row('late', '2026-09-16T10:00:00+02:00')]):
        result = bzp_backfill_cycle()
    assert result['status'] == 'error'
    assert ImportState.objects.get().cursor['page'] == 1
    assert not Article.objects.exists()


@override_settings(BZP_API_ENABLED=True)
def test_notice_after_utc_evening_is_accepted_when_api_day_is_utc(source):
    """22:57 UTC 26.07 to 00:57 27.07 w Warszawie: API zwraca je dla 26.07, więc kursor nie może stanąć."""
    now = datetime(2026, 7, 27, 8, tzinfo=dt_timezone.utc)
    rows = [row('niegowa', '2026-07-26T22:57:40.9814811Z'), row('pionki', '2026-07-26T10:46:53.7454917Z')]
    with patch('scraper.bzp_backfill.timezone.now', return_value=now), \
            patch('scraper.bzp_backfill.fetch_page', return_value=rows):
        result = bzp_backfill_cycle()
    assert result['status'] == 'ok' and result['new_records'] == 2
    assert Article.objects.count() == 2
    assert ImportState.objects.get().last_error == ''


def _run(results, **kwargs):
    from scraper.bzp_backfill import bzp_backfill_run
    sleeps, clock = [], {'t': 0.0}
    def fake_sleep(seconds):
        sleeps.append(seconds); clock['t'] += seconds
    with patch('scraper.bzp_backfill.bzp_backfill_cycle', side_effect=results) as cycle:
        out = bzp_backfill_run(sleep=fake_sleep, monotonic=lambda: clock['t'], **kwargs)
    return out, sleeps, cycle


def test_run_fetches_many_pages_spaced_at_most_20_per_minute_and_stops_when_complete(db):
    from django.core.cache import cache
    cache.delete('bzp:pause_until')
    out, sleeps, cycle = _run([{'status': 'ok', 'new_records': 5}] * 3 + [{'status': 'complete', 'new_records': 0}])
    assert out['status'] == 'complete' and out['pages'] == 3 and out['new_records'] == 15 and cycle.call_count == 4
    assert len(sleeps) == 3 and all(s >= 3 for s in sleeps)   # co najmniej 3 s = najwyżej 20/min


def test_run_waits_out_host_gate_then_continues(db):
    from django.core.cache import cache
    cache.delete('bzp:pause_until')
    out, sleeps, _ = _run([{'status': 'error', 'error': 'host_rate_limited:1.500'}, {'status': 'ok', 'new_records': 1},
                           {'status': 'complete', 'new_records': 0}])
    assert out['pages'] == 1 and sleeps[0] == pytest.approx(1.7)


def test_run_stops_on_429_and_pauses_until_retry_after(db):
    from django.core.cache import cache
    cache.delete('bzp:pause_until')
    out, _, cycle = _run([{'status': 'ok', 'new_records': 1}, {'status': 'deferred', 'retry_after_seconds': 600}, {'status': 'ok'}])
    assert out['status'] == 'deferred' and cycle.call_count == 2
    out2, _, cycle2 = _run([{'status': 'ok', 'new_records': 1}])
    assert out2['status'] == 'paused' and cycle2.call_count == 0
    cache.delete('bzp:pause_until')


def test_run_respects_time_budget_and_page_cap(db):
    from django.core.cache import cache
    cache.delete('bzp:pause_until')
    out, _, cycle = _run([{'status': 'ok', 'new_records': 0}] * 500, budget_seconds=10)
    assert 2 <= cycle.call_count <= 4   # ok. 3,2 s na stronę w budżecie 10 s


@override_settings(BZP_API_ENABLED=True)
def test_notice_record_failure_is_logged_not_silent(source, caplog):
    import logging
    from scraper.bzp_backfill import save_notice_record
    with caplog.at_level(logging.WARNING), patch('news.public_records_models.PublicRecord.objects') as manager:
        manager.update_or_create.side_effect = RuntimeError('boom')
        save_notice_record(row('x'), 'x', '2026/BZP/x', 'Tytuł', datetime(2026, 9, 13, 8, tzinfo=dt_timezone.utc), DETAIL_URL + 'x')
    assert 'bzp notice record not saved: RuntimeError: boom' in caplog.text
