"""Minimal, fail-closed WordPress REST adapter (metadata only, no persistence).

Scope is intentionally narrow: given a directory/catalog entry (a dict shaped
like an entry in ``scraper/data/verified_local_sources.json``) and an
official ``wp-json/wp/v2/posts`` endpoint, page through posts newest-first
using ``page``/``per_page`` and a ``_fields`` projection, stop at a caller
supplied cutoff date, and hand back a checkpoint the caller can persist.

Fail-closed gate: this module refuses to issue any HTTP request unless the
catalog entry explicitly declares::

    "archive_verification": {"status": "verified", "can_backfill": true,
                              "mechanism": "wordpress_rest"}

No entry in the shipped catalog currently declares ``mechanism ==
"wordpress_rest"``, so nothing is activated by adding this module. There is
no Django/Supabase write here and no full article text is requested or
returned -- callers own persistence of the returned checkpoint and records.
"""
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlencode, urlsplit

DEFAULT_PER_PAGE = 100
MAX_PER_PAGE = 100
# Metadata only. Never request/return post content or excerpt.
FIELDS = 'id,date_gmt,link,title'


class WordPressRestError(ValueError):
    """Base error: the adapter refuses to proceed."""


class SourceNotEligible(WordPressRestError):
    """The catalog entry is not an explicitly approved wordpress_rest source."""


class EndpointDomainMismatch(WordPressRestError):
    """The REST endpoint does not match the source's canonical host."""


class RateLimited(WordPressRestError):
    """The publisher answered 429; callers must back off by ``retry_after``."""

    def __init__(self, retry_after):
        super().__init__(f'wordpress_rest_rate_limited:{retry_after}')
        self.retry_after = retry_after


def is_eligible(catalog_entry):
    """True only for an explicit, fully-approved wordpress_rest entry."""
    verification = catalog_entry.get('archive_verification') if isinstance(catalog_entry, dict) else None
    if not isinstance(verification, dict):
        return False
    return (verification.get('status') == 'verified'
        and verification.get('can_backfill') is True
        and verification.get('mechanism') == 'wordpress_rest')


def ensure_eligible(catalog_entry):
    if not is_eligible(catalog_entry):
        raise SourceNotEligible('wordpress_rest_source_not_verified')
    return catalog_entry


def _canonical_host(url):
    if not isinstance(url, str):
        return ''
    host = (urlsplit(url.strip()).hostname or '').lower()
    return host.removeprefix('www.')


def ensure_same_site(catalog_entry, endpoint):
    """Allow only an exact host match after folding a single ``www.`` prefix.

    Other subdomains remain distinct so publisher ownership is never inferred.
    """
    entry_url = catalog_entry.get('url') if isinstance(catalog_entry, dict) else None
    entry_host = _canonical_host(entry_url)
    endpoint_host = _canonical_host(endpoint)
    if not entry_host or not endpoint_host or entry_host != endpoint_host:
        raise EndpointDomainMismatch('wordpress_rest_endpoint_domain_mismatch')
    return endpoint


def page_url(endpoint, *, page, per_page=DEFAULT_PER_PAGE, fields=FIELDS):
    if not isinstance(page, int) or page < 1:
        raise WordPressRestError('invalid_wordpress_page')
    if not isinstance(per_page, int) or per_page < 1 or per_page > MAX_PER_PAGE:
        raise WordPressRestError('invalid_wordpress_per_page')
    query = urlencode({'page': page, 'per_page': per_page, '_fields': fields,
        'orderby': 'date', 'order': 'desc', 'status': 'publish'})
    return f'{endpoint}?{query}'


def parse_date_gmt(value):
    """``date_gmt`` is explicitly UTC in the WP schema; never substitute another field."""
    if not isinstance(value, str) or 'T' not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is not None and parsed.utcoffset().total_seconds() != 0:
        return None
    return parsed.replace(tzinfo=dt_timezone.utc)


def _retry_after_seconds(headers):
    raw = headers.get('Retry-After') if headers else None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 60


def fetch_page(fetcher, endpoint, *, page, per_page=DEFAULT_PER_PAGE):
    """Fetch one page. ``fetcher(url)`` must return a requests.Response-like object.

    Raises RateLimited on 429 (carrying Retry-After) and WordPressRestError
    on any other non-200 status or unexpected body shape. The injected
    ``fetcher`` is responsible for enforcing a request timeout.
    """
    url = page_url(endpoint, page=page, per_page=per_page)
    response = fetcher(url)
    if response.status_code == 429:
        raise RateLimited(_retry_after_seconds(getattr(response, 'headers', {})))
    if response.status_code != 200:
        raise WordPressRestError(f'wordpress_rest_http_{response.status_code}')
    try:
        body = response.json()
    except ValueError as error:
        raise WordPressRestError('invalid_wordpress_json') from error
    if not isinstance(body, list):
        raise WordPressRestError('invalid_wordpress_page_shape')
    return body


def post_metadata(row):
    if not isinstance(row, dict):
        raise WordPressRestError('invalid_wordpress_row')
    post_id = row.get('id')
    if not isinstance(post_id, int) or post_id <= 0:
        raise WordPressRestError('invalid_wordpress_post_id')
    link = row.get('link')
    if not isinstance(link, str) or not link:
        raise WordPressRestError(f'invalid_wordpress_link:{post_id}')
    rendered = row.get('title', {}).get('rendered') if isinstance(row.get('title'), dict) else None
    return {'id': post_id, 'url': link, 'title': rendered if isinstance(rendered, str) else '',
        'published_date': parse_date_gmt(row.get('date_gmt'))}


@dataclass
class FetchResult:
    posts: list
    next_checkpoint: dict
    done: bool
    pages_fetched: int = 0


def collect_since_cutoff(fetcher, catalog_entry, endpoint, cutoff, checkpoint=None, *,
        per_page=DEFAULT_PER_PAGE, max_pages=50):
    """Page newest-first from ``endpoint`` until ``cutoff`` (a UTC datetime) is reached.

    Fail-closed: raises SourceNotEligible (no HTTP call at all) unless
    ``catalog_entry`` is an explicitly approved wordpress_rest source. The
    checkpoint returned in ``FetchResult.next_checkpoint`` is the only state
    this function produces; nothing is written to any database. A post ID
    already present in ``checkpoint['seen_ids']`` (e.g. because a prior page
    fetch overlapped this run) is skipped rather than re-collected.
    """
    ensure_eligible(catalog_entry)
    ensure_same_site(catalog_entry, endpoint)
    checkpoint = dict(checkpoint or {})
    seen_ids = set(checkpoint.get('seen_ids', []))
    page = checkpoint.get('next_page', 1)
    collected = []
    reached_cutoff = checkpoint.get('done', False)
    pages_fetched = 0
    if not reached_cutoff:
        for _ in range(max_pages):
            body = fetch_page(fetcher, endpoint, page=page, per_page=per_page)
            pages_fetched += 1
            if not body:
                reached_cutoff = True
                break
            short_page = len(body) < per_page
            for row in body:
                metadata = post_metadata(row)
                if metadata['id'] in seen_ids:
                    continue  # duplicate: already collected in an earlier/overlapping page
                if metadata['published_date'] is not None and metadata['published_date'] < cutoff:
                    reached_cutoff = True
                    break
                seen_ids.add(metadata['id'])
                collected.append(metadata)
            if reached_cutoff or short_page:
                reached_cutoff = reached_cutoff or short_page
                break
            page += 1
    # `page` already holds the next page to fetch: it is only advanced (line
    # above) once a page is fully accepted, so no further +1 belongs here.
    next_checkpoint = {'next_page': 1 if reached_cutoff else page,
        'seen_ids': sorted(seen_ids)[-2000:], 'done': reached_cutoff}
    return FetchResult(posts=collected, next_checkpoint=next_checkpoint,
        done=reached_cutoff, pages_fetched=pages_fetched)
