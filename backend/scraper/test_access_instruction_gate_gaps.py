"""Regression targets for access paths not yet covered by the common gate.

They assert that the common policy gate refuses a request before transport or
storage when the source has no approved instruction.
"""

from unittest.mock import Mock

import pytest

from django.utils import timezone
from news.models import Article, Source, SourceAccessInstruction
from scraper.official import import_voting
from scraper.rss_scraper import scrape_rss_source


RSS = (b'<rss version="2.0"><channel><title>Test</title><item>'
       b'<title>News</title><link>https://example.org/1</link>'
       b'</item></channel></rss>')

VOTING = {
    'term': 10, 'sitting': 1, 'votingNumber': 2, 'title': 'Test vote',
    'description': 'Test motion', 'date': '2026-09-15T12:00:00',
    'kind': 'ELECTRONIC', 'yes': 1, 'no': 1,
    'votes': [
        {'MP': 1, 'firstName': 'Jan', 'lastName': 'Testowy', 'club': 'T', 'vote': 'YES'},
        {'MP': 2, 'firstName': 'Anna', 'lastName': 'Przykladowa', 'club': 'P', 'vote': 'NO'},
    ],
}


@pytest.mark.django_db
def test_rss_refuses_transport_without_approved_rss_instruction(monkeypatch):
    source = Source.objects.create(
        name='RSS without instruction', url='https://example.org',
        rss_url='https://example.org/feed',
    )
    fetch = Mock(return_value=RSS)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)

    assert scrape_rss_source(source.pk) == 0
    fetch.assert_not_called()
    assert not Article.objects.exists()


@pytest.mark.django_db
def test_official_api_refuses_transport_without_approved_api_instruction(monkeypatch):
    fetch = Mock(return_value=VOTING)
    monkeypatch.setattr('scraper.official.fetch_json', fetch)

    assert import_voting(10, 1, 2) == 0
    fetch.assert_not_called()
    assert not Article.objects.exists()


@pytest.mark.django_db
def test_newer_suspended_rss_instruction_blocks_older_approval(monkeypatch):
    source = Source.objects.create(
        name='Suspended RSS', url='https://example.org',
        rss_url='https://example.org/feed')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3)
    SourceAccessInstruction.objects.create(
        source=source, version=2, status='suspended', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        evidence={'reason': 'test suspension'}, minimum_interval_seconds=3)
    fetch = Mock(return_value=RSS)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)

    assert scrape_rss_source(source.pk) == 0
    fetch.assert_not_called()


@pytest.mark.django_db
def test_official_task_refuses_before_import_without_instruction(monkeypatch):
    from scraper.tasks import import_official_task

    importer = Mock()
    monkeypatch.setattr('scraper.official.import_eli_changes', importer)

    result = import_official_task('eli')

    assert result['status'] == 'blocked_access_review'
    importer.assert_not_called()


@pytest.mark.django_db
def test_voting_backfill_refuses_before_import_without_instruction(monkeypatch):
    from scraper.official import API
    from scraper.official_backfill import backfill_votings_cycle

    Source.objects.create(name='Sejm without instruction', url=API + '/sejm')
    importer = Mock()
    monkeypatch.setattr('scraper.official_backfill.import_voting_period', importer)

    result = backfill_votings_cycle()

    assert result['status'] == 'blocked_access_review'
    importer.assert_not_called()
