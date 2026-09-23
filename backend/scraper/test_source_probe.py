import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command

from news.models import ImportState, Source
from scraper.source_probe import (ProbeError, ProbeNetwork, SourceProbe, audit_source,
    parse_sitemap, public_link)


def source(**changes):
    values = dict(pk=1, name='Test', url='https://example.com/', rss_url='https://example.com/rss',
        catalog_stage='configured', source_type='portal')
    values.update(changes)
    return SimpleNamespace(**values)


def test_sitemap_counts_pages_not_images_and_never_calls_lastmod_publication_date():
    raw = b'''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
        <url><loc>https://example.com/story</loc><lastmod>2025-12-01</lastmod>
        <image:image><image:loc>https://example.com/photo.jpg</image:loc></image:image></url></urlset>'''
    kind, entries = parse_sitemap(raw, 'https://example.com/map.xml')
    assert kind == 'urlset'
    assert entries == [{'url': 'https://example.com/story', 'news_publication_date': None}]
    with pytest.raises(ProbeError):
        parse_sitemap(b'<!DOCTYPE x><urlset/>', 'https://example.com/map.xml')
    with pytest.raises(ProbeError):
        parse_sitemap(b'<html/>', 'https://example.com/map.xml')


def test_dns_pin_rejects_any_private_resolution_and_robots_blocks_page():
    network = ProbeNetwork(delay=0)
    with patch('scraper.source_probe.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
        with pytest.raises(ProbeError, match='non_public_address'):
            network.raw('https://example.com/')
    with patch.object(network, 'raw', return_value={'status': 200, 'raw': b'User-agent: *\nDisallow: /'}) as raw:
        with pytest.raises(ProbeError, match='robots_disallowed'):
            network.fetch('https://blocked.example/article')
        assert raw.call_count == 1
    assert public_link('http://127.0.0.1/') == ''


def test_excluded_and_missing_url_make_no_network_requests():
    with patch.object(ProbeNetwork, 'fetch') as fetch:
        for item in (source(catalog_stage='excluded'), source(url='', rss_url='')):
            result = SourceProbe(item, ProbeNetwork()).run()
            assert result['audit_status'] == 'skipped'
        fetch.assert_not_called()


def test_empty_http_response_is_not_a_feed_and_does_not_abort_archive_check():
    class EmptyNetwork:
        def fetch(self, url):
            return b'', url, []
    result = SourceProbe(source(), EmptyNetwork()).run()
    assert result['audit_status'] == 'completed'
    assert result['rss']['status'] == 'unavailable'
    assert result['rss']['error'] == 'not_a_feed'
    assert result['archive']['status'] == 'unavailable'


def test_shared_government_home_is_not_institution_evidence_without_disclosed_link():
    class GovernmentNetwork:
        def fetch(self, url):
            return b'<html><a href="/web/gov/ministerstwa">Ministerstwa</a></html>', 'https://www.gov.pl/', []
    result = SourceProbe(source(url='https://www.gov.pl/web/old-ministry/rss',
        rss_url='', source_type='institution'), GovernmentNetwork()).run()
    assert result['archive']['status'] == 'unavailable'
    assert result['archive']['listing_urls'] == []
    assert any(e['error'] == 'institution_redirected_to_shared_home' for e in result['errors'])


def test_explicit_external_rss_is_checked_without_guessing_feed_host():
    class HostedFeedNetwork:
        def fetch(self, url):
            if url == 'https://feeds.example/actual-channel':
                return b'<rss version="2.0"><channel><item><title>Story</title><link>https://example.com/story</link></item></channel></rss>', url, []
            return b'<html><link rel="alternate" type="application/rss+xml" href="https://feeds.example/actual-channel"></html>', url, []
    result = SourceProbe(source(rss_url=''), HostedFeedNetwork()).run()
    assert result['rss']['status'] == 'working'
    assert result['rss']['url'] == 'https://feeds.example/actual-channel'


def test_working_feed_also_checks_archive_and_counts_failed_root_as_incomplete():
    feed = b'<rss version="2.0"><channel><title>Test</title><link>https://example.com/</link><item><title>Story</title><link>https://example.com/story</link></item></channel></rss>'
    pages = {
        'https://example.com/rss': feed,
        'https://example.com/': b'<html><head><link rel="https://api.w.org/" href="https://example.com/wp-json/" /></head></html>',
        'https://example.com/map.xml': b'<urlset><url><loc>https://example.com/story</loc></url></urlset>',
        'https://example.com/story': b'<html><head><title>Story</title></head></html>'}
    class FakeNetwork:
        def fetch(self, url):
            if url not in pages:
                raise ProbeError('http_404')
            return pages[url], url, [{'kind': 'robots', 'url': 'https://example.com/robots.txt', 'status': 'ok',
                'sitemap_urls': ['https://example.com/map.xml', 'https://example.com/broken.xml']}]
    result = SourceProbe(source(), FakeNetwork()).run()
    assert result['rss']['status'] == 'working'
    assert result['archive']['status'] == 'sitemap'
    assert result['archive']['page_urls_observed'] == 1
    assert result['archive']['volume_estimate']['status'] == 'sample_only'
    assert any(e['kind'] == 'publisher_api_link' for e in result['evidence'])
    assert result['rss']['sample']['published_date'] is None


@pytest.mark.django_db(transaction=True)
def test_checkpoint_command_resumes_without_rechecking_or_changing_source(tmp_path):
    item = Source.objects.create(name='No URL', url=None, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    result = audit_source(item)
    assert result['audit_status'] == 'skipped'
    state = ImportState.objects.get(name=f'source-check:{item.pk}')
    assert state.last_success is not None
    with patch('scraper.management.commands.audit_sources.probe_source') as probe:
        call_command('audit_sources', source_id=[item.pk], output_prefix=str(tmp_path / 'audit'))
        probe.assert_not_called()
    report = json.loads((tmp_path / 'audit.json').read_text(encoding='utf-8'))
    assert report['summary']['total'] == 1
    assert report['sources'][0]['audit_status'] == 'skipped'
    item.refresh_from_db()
    assert not item.is_active and not item.scrape_enabled


@pytest.mark.django_db(transaction=True)
def test_fatal_probe_error_is_saved_with_a_bounded_diagnostic_and_does_not_activate_source():
    item = Source.objects.create(name='TLS failure', url='https://publisher.example/',
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    with patch('scraper.source_probe.probe_source', side_effect=ProbeError('certificate_hostname_mismatch')):
        result = audit_source(item)
    assert result['audit_status'] == 'failed'
    assert result['fatal_error'] == 'ProbeError'
    assert result['fatal_error_detail'] == 'certificate_hostname_mismatch'
    assert result['errors'][-1]['kind'] == 'fatal_probe'
    state = ImportState.objects.get(name=f'source-check:{item.pk}')
    assert state.last_success is None
    assert state.last_error == 'ProbeError'
    item.refresh_from_db()
    assert not item.is_active and not item.scrape_enabled
