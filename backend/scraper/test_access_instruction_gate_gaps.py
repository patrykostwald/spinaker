"""Regression targets for access paths not yet covered by the common gate.

They are strict xfails while the known gap exists.  Once the common policy
gate is introduced, remove the markers: the same assertions must pass without
performing a network operation or writing a record.
"""

from unittest.mock import Mock

import pytest

from news.models import Article, Source
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
@pytest.mark.xfail(strict=True, reason='RSS currently bypasses SourceAccessInstruction')
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
@pytest.mark.xfail(strict=True, reason='official API currently bypasses SourceAccessInstruction')
def test_official_api_refuses_transport_without_approved_api_instruction(monkeypatch):
    fetch = Mock(return_value=VOTING)
    monkeypatch.setattr('scraper.official.fetch_json', fetch)

    assert import_voting(10, 1, 2) == 0
    fetch.assert_not_called()
    assert not Article.objects.exists()
