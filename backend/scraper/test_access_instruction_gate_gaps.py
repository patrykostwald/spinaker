"""Regression targets for access paths not yet covered by the common gate.

They assert that the common policy gate refuses a request before transport or
storage when the source has no approved instruction.
"""

from unittest.mock import Mock

import pytest

from django.utils import timezone
from news.models import Article, FetchAttempt, Source, SourceAccessInstruction
from scraper.official import import_voting
from scraper.rss_scraper import scrape_rss_source
from scraper.archive import process
from scraper.access_gate import AccessDenied
from scraper.access_gate import approved_instruction


RSS = (b'<rss version="2.0"><channel><title>Test</title><item>'
       b'<title>News</title><link>https://example.org/1</link>'
       b'</item></channel></rss>')

RSS_WITH_IMAGE = (b'<rss xmlns:media="http://search.yahoo.com/mrss/" version="2.0"><channel><title>Test</title><item>'
                  b'<title>News with image</title><link>https://example.org/image</link>'
                  b'<media:content url="https://example.org/photo.jpg" type="image/jpeg" />'
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
    refusal = FetchAttempt.objects.get()
    assert refusal.outcome == FetchAttempt.Outcome.REFUSED_NO_INSTRUCTION
    assert refusal.network_started is False


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
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3, daily_request_cap=24)
    SourceAccessInstruction.objects.create(
        source=source, version=2, status='suspended', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        evidence={'reason': 'test suspension'}, minimum_interval_seconds=3)
    fetch = Mock(return_value=RSS)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)

    assert scrape_rss_source(source.pk) == 0
    fetch.assert_not_called()


@pytest.mark.django_db
def test_metadata_rss_never_persists_an_unreviewed_feed_image(monkeypatch):
    source = Source.objects.create(
        name='Approved metadata RSS', url='https://example.org',
        rss_url='https://example.org/feed', is_active=True, scrape_enabled=True,
        catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3,
        daily_request_cap=24)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', Mock(return_value=RSS_WITH_IMAGE))

    assert scrape_rss_source(source.pk) == 1
    assert Article.objects.get().image_url == ''


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


@pytest.mark.django_db
def test_sitemap_instruction_never_authorizes_page_fetch(monkeypatch):
    source = Source.objects.create(name='Sitemap only', url='https://example.org')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='sitemap',
        allowed_scope='content', endpoint='https://example.org/map.xml',
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3, daily_request_cap=24)
    from news.models import ArchiveJob
    job = ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
    fetch = Mock()
    monkeypatch.setattr('scraper.archive.fetch_feed', fetch)

    with pytest.raises(AccessDenied, match='no_approved_instruction'):
        process(job)

    fetch.assert_not_called()


@pytest.mark.django_db
def test_direct_page_process_refuses_without_html_instruction(monkeypatch):
    source = Source.objects.create(name='No HTML instruction', url='https://example.org')
    from news.models import ArchiveJob
    job = ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
    fetch = Mock()
    monkeypatch.setattr('scraper.archive.fetch_feed', fetch)

    with pytest.raises(AccessDenied, match='no_approved_instruction'):
        process(job)

    fetch.assert_not_called()


@pytest.mark.django_db
def test_discovery_refuses_robots_request_without_sitemap_instruction(monkeypatch):
    from scraper.archive import discover

    source = Source.objects.create(name='Discovery without instruction', url='https://example.org')
    robots = Mock()
    monkeypatch.setattr('scraper.archive.robots', robots)

    assert discover(source) == 0
    robots.assert_not_called()


@pytest.mark.django_db
def test_wordpress_backfill_refuses_transport_without_api_instruction(monkeypatch):
    from scraper.wordpress_backfill import VERIFIED_ENDPOINTS, collection_url, fetch_collection, SourceDisabled

    source = Source.objects.create(name='WordPress without instruction', url='https://liberte.pl/feed/')
    fetch = Mock()
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_feed', fetch)

    with pytest.raises(SourceDisabled):
        fetch_collection(source.pk, VERIFIED_ENDPOINTS['liberte.pl'],
            collection_url(VERIFIED_ENDPOINTS['liberte.pl']))

    fetch.assert_not_called()

@pytest.mark.django_db
def test_expired_instruction_blocks_before_transport(monkeypatch):
    from datetime import timedelta

    source = Source.objects.create(
        name='Expired RSS instruction', url='https://example.org',
        rss_url='https://example.org/feed')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() - timedelta(seconds=1),
        minimum_interval_seconds=3)
    fetch = Mock(return_value=RSS)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)

    assert scrape_rss_source(source.pk) == 0
    fetch.assert_not_called()


@pytest.mark.django_db
def test_an_endpoint_specific_suspension_does_not_disable_another_api_endpoint():
    source = Source.objects.create(name='Two API endpoints', url='https://example.org')
    common = dict(source=source, status='approved', channel='api', allowed_scope='metadata',
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3, daily_request_cap=24)
    SourceAccessInstruction.objects.create(version=1, endpoint='https://example.org/api/votes', **common)
    SourceAccessInstruction.objects.create(version=2, status='suspended', channel='api',
        endpoint='https://example.org/api/prints', evidence={'reason': 'test'},
        minimum_interval_seconds=3, source=source)

    assert approved_instruction(source, 'api', 'https://example.org/api/votes/1') is not None
    assert approved_instruction(source, 'api', 'https://example.org/api/prints/1') is None


@pytest.mark.django_db
def test_access_card_can_allow_only_integer_voting_paths():
    source = Source.objects.create(name='Sejm-like API', url='https://example.org',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='content', endpoint='https://example.org/sejm/term10/votings',
        allowed_path_patterns=[
            '/sejm/term10/votings/{int}',
            '/sejm/term10/votings/{int}/{int}',
        ],
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )

    assert approved_instruction(source, 'api', 'https://example.org/sejm/term10/votings/4')
    assert approved_instruction(source, 'api', 'https://example.org/sejm/term10/votings/4/1')
    assert approved_instruction(source, 'api', 'https://example.org/sejm/term10/votings/4/1/pdf') is None


@pytest.mark.django_db
def test_access_card_token_never_matches_a_path_separator_or_punctuation():
    source = Source.objects.create(name='Token API', url='https://example.org',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='metadata', endpoint='https://example.org/api',
        allowed_path_patterns=['/api/jobs/{token}'],
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )

    assert approved_instruction(source, 'api', 'https://example.org/api/jobs/a_2-b')
    assert approved_instruction(source, 'api', 'https://example.org/api/jobs/a.b') is None
    assert approved_instruction(source, 'api', 'https://example.org/api/jobs/a/other') is None


@pytest.mark.django_db
def test_daily_cap_blocks_before_a_second_network_request(monkeypatch):
    """The reviewed cap is durable and fails closed before transport."""
    from scraper.utils import HostRateLimited, SourceHTTPResponse, fetch_response_once

    source = Source.objects.create(name='Daily limited API', url='https://example.org',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    instruction = SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='content', endpoint='https://example.org/api',
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=1,
    )
    raw = Mock(return_value=SourceHTTPResponse(200, {}, b'{}'))
    monkeypatch.setattr('scraper.utils._fetch_feed_raw', raw)

    fetch_response_once('https://example.org/api/1', audit_source=source,
        audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.API_RECORD,
        hostname_transport=True)
    with pytest.raises(HostRateLimited):
        fetch_response_once('https://example.org/api/2', audit_source=source,
            audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.API_RECORD,
            hostname_transport=True)

    assert raw.call_count == 1
    assert FetchAttempt.objects.filter(
        outcome=FetchAttempt.Outcome.DAILY_LIMIT_PREEMPTIVE,
        network_started=False,
    ).count() == 1
