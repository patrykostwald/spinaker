"""Bieżące głosowania Sejmu mają pierwszeństwo przed nadrabianiem archiwum (właściciel 2.10.2026)."""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command

from scraper import official
from scraper.official_backfill import backfill_votings_cycle
from scraper.utils import reserve_daily_fetch_budget

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def test_backfill_waits_while_current_votings_import_runs():
    cache.set('priority:official:votings', True, 60)
    with patch('scraper.official_backfill.Source.objects.filter',
               return_value=SimpleNamespace(first=lambda: SimpleNamespace(pk=1))), \
         patch('scraper.official_backfill._source_enabled', return_value=True), \
         patch('scraper.official_backfill.official_access_allowed', return_value=True), \
         patch('scraper.official_backfill.backfill_budget_left', return_value=True):
        assert backfill_votings_cycle() == {'status': 'current_import_pending', 'new_records': 0}


def test_current_votings_use_full_cap_and_rest_only_backfill_share():
    calls = []
    with patch('scraper.official.official_source', return_value=object()), \
         patch('scraper.official.approved_instruction', return_value=object()), \
         patch('scraper.official.fetch_feed', side_effect=lambda *a, **kw: calls.append(kw['budget_share']) or b'[]'):
        official.fetch_json('/sejm/term10/prints')
        with official.current_voting_budget():
            official.fetch_json('/sejm/term10/votings/search')
        official.fetch_json('/sejm/term10/votings/search')
    assert calls == [official.BACKFILL_SHARE, 1.0, official.BACKFILL_SHARE]


def test_budget_share_lowers_daily_cap():
    from news.models import Source, SourceAccessInstruction
    source = Source.objects.create(name='Sejm API', url='https://api.sejm.gov.pl/', source_type='institution')
    instruction = SourceAccessInstruction.objects.create(source=source, daily_request_cap=10)
    assert sum(reserve_daily_fetch_budget(instruction, share=.6) for _ in range(10)) == 6
    assert sum(reserve_daily_fetch_budget(instruction) for _ in range(10)) == 4


def test_eli_import_stops_after_page_limit_and_reports_partial():
    pages = iter({'items': [{'publisher': 'DU', 'year': 2026, 'pos': n * 100 + i} for i in range(100)], 'totalCount': 500}
                 for n in range(5))
    with patch('scraper.official.official_access_allowed', return_value=True), \
         patch('scraper.official.fetch_json_paced', side_effect=lambda *a, **kw: next(pages)), \
         patch('scraper.official.save_document', return_value=1):
        result = official.import_eli_changes('2026-10-01T00:00:00', offset=0, max_pages=2)
    assert result == {'count': 200, 'complete': False}


def test_sejm_data_status_prints_without_network_errors():
    out = StringIO()
    with patch('news.management.commands.sejm_data_status.fetch_json', side_effect=RuntimeError('secret token')):
        call_command('sejm_data_status', stdout=out)
    text = out.getvalue()
    assert 'Kadencja: 10' in text and 'niedostępne (RuntimeError)' in text and 'secret' not in text
