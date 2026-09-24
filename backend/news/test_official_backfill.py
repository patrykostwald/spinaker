from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from news.models import ImportState, Source
from scraper.official_backfill import LOCK, backfill_votings_cycle


@pytest.fixture(autouse=True)
def allow_official_api_for_backfill_unit_tests(monkeypatch):
    """These tests exercise the persisted cursor, not the access gate."""
    monkeypatch.setattr('scraper.official_backfill.official_access_allowed', lambda provider, path: True)
    monkeypatch.setattr('scraper.official.official_access_allowed', lambda provider, path: True)


@pytest.fixture
def source(db):
    cache.clear()
    return Source.objects.create(name='Test Sejm', url='https://api.sejm.gov.pl/sejm')


@override_settings(SEJM_TERM=10)
def test_first_window_and_resume_keep_frozen_cutoff(source):
    first_now = datetime(2023, 11, 25, 12, tzinfo=dt_timezone.utc)
    with patch('scraper.official_backfill.timezone.now', return_value=first_now), \
            patch('scraper.official_backfill.import_voting_period', return_value=8) as importer:
        first = backfill_votings_cycle()
    assert first['from_date'] == '2023-11-13' and first['to_date'] == '2023-11-19'
    assert first['status'] == 'ok'
    assert importer.call_args.args == (10, '2023-11-13', '2023-11-19')
    assert callable(importer.call_args.kwargs['guard'])
    with patch('scraper.official_backfill.import_voting_period', return_value=3) as importer:
        second = backfill_votings_cycle()
        third = backfill_votings_cycle()
    assert second['from_date'] == '2023-11-20' and second['to_date'] == '2023-11-25'
    assert second['cutoff'] == '2023-11-25' and second['status'] == third['status'] == 'complete'
    assert importer.call_count == 1
    state = ImportState.objects.get()
    assert state.imported == 11 and state.cursor['periods_completed'] == 2


@override_settings(SEJM_TERM=10)
def test_failure_keeps_cursor_and_success_stamp_then_replays_same_window(source):
    cursor = {'term': 10, 'next_from': '2023-11-20', 'cutoff': '2023-12-31', 'complete': False, 'periods_completed': 1}
    stamp = datetime(2023, 11, 19, 12, tzinfo=dt_timezone.utc)
    state = ImportState.objects.create(name='official-backfill:votings:10', cursor=cursor, last_success=stamp, imported=8)
    with patch('scraper.official_backfill.import_voting_period', side_effect=TimeoutError('test failure')):
        assert backfill_votings_cycle()['status'] == 'error'
    state.refresh_from_db()
    assert state.cursor == cursor and state.last_success == stamp and state.imported == 8
    assert not cache.get(LOCK)
    with patch('scraper.official_backfill.import_voting_period', return_value=2) as importer:
        assert backfill_votings_cycle()['status'] == 'ok'
    assert importer.call_args.args == (10, '2023-11-20', '2023-11-26')


@pytest.mark.parametrize('field,value', [('scrape_enabled', False), ('is_active', False), ('catalog_stage', 'excluded'), ('catalog_stage', 'candidate')])
def test_disabled_source_never_starts_import_or_creates_state(source, field, value):
    Source.objects.filter(pk=source.pk).update(**{field: value})
    with patch('scraper.official_backfill.import_voting_period') as importer:
        assert backfill_votings_cycle()['status'] == 'disabled'
    importer.assert_not_called()
    assert not ImportState.objects.exists()


def test_current_voting_import_lock_prevents_parallel_backfill(source):
    cache.add(LOCK, True, 3600)
    with patch('scraper.official_backfill.import_voting_period') as importer:
        assert backfill_votings_cycle()['status'] == 'already_running'
    importer.assert_not_called()
    assert cache.get(LOCK) is True


@override_settings(SEJM_TERM=10)
def test_source_disabled_during_window_stops_next_item_and_keeps_cursor(source):
    def importing(*args, guard):
        Source.objects.filter(pk=source.pk).update(scrape_enabled=False)
        guard()
        pytest.fail('Guard should prevent the next request')

    with patch('scraper.official_backfill.import_voting_period', side_effect=importing):
        result = backfill_votings_cycle()
    assert result['status'] == 'deferred' and result['error'] == 'source_disabled'
    state = ImportState.objects.get()
    assert state.cursor['next_from'] == '2023-11-13' and state.last_success is None


@override_settings(SEJM_TERM=10)
def test_source_disabled_while_detail_is_fetched_prevents_persisting_it(source):
    def fetch(path, *, return_receipt=False, **params):
        if path.endswith('/search'):
            result = [{'term': 10, 'sitting': 1, 'votingNumber': 1}]
        else:
            Source.objects.filter(pk=source.pk).update(scrape_enabled=False)
            result = {'not': 'used because the source was disabled'}
        return (result, None) if return_receipt else result

    with patch('scraper.official.fetch_json', side_effect=fetch), \
            patch('scraper.official.save_voting') as save:
        result = backfill_votings_cycle()
    save.assert_not_called()
    assert result['status'] == 'deferred' and result['error'] == 'source_disabled'
    assert ImportState.objects.get().cursor['next_from'] == '2023-11-13'


@pytest.mark.django_db
def test_missing_source_is_not_automatically_created():
    assert backfill_votings_cycle()['status'] == 'disabled'
    assert not Source.objects.exists()
