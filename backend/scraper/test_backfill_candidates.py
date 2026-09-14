from types import SimpleNamespace

from scraper.management.commands.backfill_candidates import (
    archive_candidate,
    catalog_indexes,
    catalog_row_for,
)


def test_short_rss_is_not_an_archive_candidate():
    result = archive_candidate(SimpleNamespace(), {'rss_url': 'https://example.org/feed'})
    assert result['status'] == 'needs_review'
    assert result['can_backfill'] is False


def test_legacy_sitemap_requires_archive_reaudit():
    result = archive_candidate(SimpleNamespace(), {'sitemap_urls': ['https://example.org/sitemap.xml']})
    assert result['status'] == 'needs_review'
    assert result['can_backfill'] is False


def test_archive_api_and_pagination_are_supported_by_catalog_contract():
    result = archive_candidate(SimpleNamespace(), {'archive_verification': {
        'status': 'verified', 'mechanism': 'paginated_archive',
        'urls': ['https://example.org/archive?page=2'], 'can_backfill': True,
        'date_range': {'oldest': '2020-01-01'}}})
    assert result['archive_type'] == 'paginated_archive'
    assert result['can_backfill'] is True


def test_unverified_catalog_row_is_not_promoted():
    result = archive_candidate(SimpleNamespace(), {'archive_verification': {
        'status': 'needs_review', 'mechanism': 'sitemap', 'can_backfill': False,
        'reason': 'HTTP 429'}})
    assert result['status'] == 'needs_review'
    assert result['reason'] == 'HTTP 429'


def test_rss_source_matches_catalog_by_publisher_host():
    row = {'name': 'Polsat News', 'url': 'https://www.polsatnews.pl'}
    source = SimpleNamespace(name='Polsat News', url='https://www.polsatnews.pl/rss/polska.xml')
    assert catalog_row_for(source, catalog_indexes([row])) is row
