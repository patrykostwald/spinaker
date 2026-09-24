"""Unit tests for the minimal WordPress REST adapter. No network, no DB, no Supabase."""
from datetime import datetime, timezone as dt_timezone

import pytest

from scraper.wordpress_rest_adapter import (EndpointDomainMismatch, RateLimited, SourceNotEligible,
    WordPressRestError, collect_since_cutoff, is_eligible)

ENDPOINT = 'https://example.pl/wp-json/wp/v2/posts'
CUTOFF = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)


def entry(**overrides):
    verification = {'status': 'verified', 'can_backfill': True, 'mechanism': 'wordpress_rest'}
    verification.update(overrides)
    return {'name': 'Example', 'url': 'https://example.pl', 'archive_verification': verification}


def post(number, *, date='2026-06-01T10:00:00'):
    return {'id': number, 'date_gmt': date, 'link': f'https://example.pl/post-{number}/',
        'title': {'rendered': f'Post {number}'}}


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    def json(self):
        return self._body


def fetcher_from_pages(pages, calls=None):
    """pages: list of response bodies (lists), indexed by page number (1-based)."""
    def fetcher(url):
        if calls is not None:
            calls.append(url)
        from urllib.parse import parse_qs, urlsplit
        page = int(parse_qs(urlsplit(url).query)['page'][0])
        if page > len(pages):
            return FakeResponse(200, [])
        return FakeResponse(200, pages[page - 1])
    return fetcher


# --- fail-closed -----------------------------------------------------------

@pytest.mark.parametrize('overrides', [
    {'status': 'needs_review'},
    {'can_backfill': False},
    {'can_backfill': 'true'},  # must be a real bool, not a truthy string
    {'mechanism': 'sitemap_index'},
    {'mechanism': None},
])
def test_fail_closed_for_unapproved_entry(overrides):
    assert is_eligible(entry(**overrides)) is False
    calls = []
    with pytest.raises(SourceNotEligible):
        collect_since_cutoff(fetcher_from_pages([[post(1)]], calls), entry(**overrides), ENDPOINT, CUTOFF)
    assert calls == []  # refused before any HTTP call


def test_fail_closed_for_missing_verification_block():
    bare = {'name': 'Example', 'url': 'https://example.pl'}
    assert is_eligible(bare) is False
    with pytest.raises(SourceNotEligible):
        collect_since_cutoff(fetcher_from_pages([[post(1)]]), bare, ENDPOINT, CUTOFF)


def test_approved_entry_is_eligible():
    assert is_eligible(entry()) is True


# --- same-site endpoint gate -------------------------------------------------

@pytest.mark.parametrize('endpoint', [
    'https://example.pl/wp-json/wp/v2/posts',
    'https://www.example.pl/wp-json/wp/v2/posts',
])
def test_same_domain_endpoint_is_accepted(endpoint):
    calls = []
    result = collect_since_cutoff(fetcher_from_pages([[]], calls), entry(), endpoint, CUTOFF)
    assert result.done is True and calls


@pytest.mark.parametrize('endpoint', [
    'https://otherdomain.pl/wp-json/wp/v2/posts',
    'https://blog.example.pl/wp-json/wp/v2/posts',
    'https://example.pl.evil.com/wp-json/wp/v2/posts',
])
def test_cross_domain_endpoint_is_rejected_before_any_fetch(endpoint):
    calls = []
    with pytest.raises(EndpointDomainMismatch):
        collect_since_cutoff(fetcher_from_pages([[post(1)]], calls), entry(), endpoint, CUTOFF)
    assert calls == []


@pytest.mark.parametrize('bad_url', [None, '', 'not a url', '   '])
def test_invalid_catalog_url_is_rejected_before_any_fetch(bad_url):
    calls = []
    broken = entry()
    broken['url'] = bad_url
    with pytest.raises(EndpointDomainMismatch):
        collect_since_cutoff(fetcher_from_pages([[post(1)]], calls), broken, ENDPOINT, CUTOFF)
    assert calls == []


# --- pagination --------------------------------------------------------------

def test_pagination_walks_pages_until_short_page_and_uses_fields_and_per_page():
    calls = []
    page1 = [post(n) for n in range(100, 0, -1)]  # full page, id 100..1 desc
    page2 = [post(101)]  # short page ends pagination
    fetcher = fetcher_from_pages([page1, page2], calls)
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, per_page=100)
    assert [item['id'] for item in result.posts] == list(range(100, 0, -1)) + [101]
    assert result.done is True and result.pages_fetched == 2
    from urllib.parse import parse_qs, urlsplit
    first = parse_qs(urlsplit(calls[0]).query)
    assert first['page'] == ['1'] and first['per_page'] == ['100']
    assert first['_fields'] == ['id,date_gmt,link,title']
    assert parse_qs(urlsplit(calls[1]).query)['page'] == ['2']


def test_checkpoint_resumes_from_next_page_without_refetching_earlier_pages():
    # max_pages=1 bounds each call to a single request, mirroring one backfill
    # cycle; the checkpoint is what lets a second cycle resume from page 2.
    calls = []
    fetcher = fetcher_from_pages([[post(2)], [post(1)]], calls)
    first = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, per_page=1, max_pages=1)
    assert [item['id'] for item in first.posts] == [2]
    assert first.done is False and first.next_checkpoint['next_page'] == 2
    second = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF,
        checkpoint=first.next_checkpoint, per_page=1, max_pages=1)
    assert [item['id'] for item in second.posts] == [1]
    assert len(calls) == 2  # never re-fetched page 1


def test_done_checkpoint_short_circuits_without_any_fetch():
    calls = []
    fetcher = fetcher_from_pages([[post(1)]], calls)
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, checkpoint={'done': True, 'next_page': 1})
    assert result.posts == [] and result.done is True and calls == []


# --- 429 / Retry-After ---------------------------------------------------

def test_rate_limit_raises_with_retry_after_seconds():
    def fetcher(url):
        return FakeResponse(429, headers={'Retry-After': '120'})
    with pytest.raises(RateLimited) as error:
        collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF)
    assert error.value.retry_after == 120


def test_rate_limit_without_retry_after_header_defaults_safely():
    def fetcher(url):
        return FakeResponse(429, headers={})
    with pytest.raises(RateLimited) as error:
        collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF)
    assert error.value.retry_after == 60


def test_non_429_error_status_raises_plain_wordpress_error():
    def fetcher(url):
        return FakeResponse(500)
    with pytest.raises(WordPressRestError, match='wordpress_rest_http_500'):
        collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF)


def test_invalid_json_body_raises_wordpress_error_not_a_raw_value_error():
    class BrokenJsonResponse(FakeResponse):
        def json(self):
            raise ValueError('invalid json')

    def fetcher(url):
        return BrokenJsonResponse(200)

    with pytest.raises(WordPressRestError, match='invalid_wordpress_json'):
        collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF)


# --- cutoff ------------------------------------------------------------------

def test_cutoff_stops_collection_and_excludes_older_posts():
    calls = []
    rows = [post(3, date='2026-06-01T00:00:00'), post(2, date='2025-06-01T00:00:00'),
        post(1, date='2024-01-01T00:00:00')]
    fetcher = fetcher_from_pages([rows], calls)
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, per_page=100)
    assert [item['id'] for item in result.posts] == [3]
    assert result.done is True
    assert len(calls) == 1  # stopped mid-page; did not request a further page


def test_cutoff_exactly_at_boundary_is_kept_not_dropped():
    rows = [post(1, date='2026-01-01T00:00:00')]  # equal to CUTOFF
    fetcher = fetcher_from_pages([rows, []])
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, per_page=100)
    assert [item['id'] for item in result.posts] == [1]


# --- duplicates ----------------------------------------------------------

def test_duplicate_post_id_across_overlapping_pages_is_collected_once():
    # Publisher pagination overlap: id 2 reappears on page 2.
    fetcher = fetcher_from_pages([[post(2), post(1)]])
    checkpoint = {'next_page': 1, 'seen_ids': [2]}
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, checkpoint=checkpoint, per_page=100)
    assert [item['id'] for item in result.posts] == [1]
    assert result.next_checkpoint['seen_ids'] == [1, 2]


def test_duplicate_post_id_within_a_single_page_is_collected_once():
    fetcher = fetcher_from_pages([[post(1), post(1)], []])
    result = collect_since_cutoff(fetcher, entry(), ENDPOINT, CUTOFF, per_page=100)
    assert [item['id'] for item in result.posts] == [1]
