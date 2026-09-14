from types import SimpleNamespace

from scraper.management.commands.backfill_candidates import archive_candidate


def test_short_rss_is_not_an_archive_candidate():
    result = archive_candidate(SimpleNamespace(), {'rss_url': 'https://example.org/feed'})
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