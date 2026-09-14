"""Minimal, fail-closed bridge from wordpress_rest_adapter metadata to ArchiveJob.

Scope is intentionally narrow: given the same ``(source, catalog_entry,
endpoint)`` triple already validated by ``wordpress_rest_adapter``, and post
metadata already fetched by ``collect_since_cutoff`` (a ``FetchResult.posts``
list or any iterable of its dicts / plain URL strings), persist one unique
``ArchiveJob(kind='page')`` row per URL. Nothing else is written: no
Article, no ArticleContent, no full text, no excerpt, no HTML snapshot. The
archive worker's own per-page fetch (``scraper.archive.process``) is what
later extracts each page, exactly as it already does for URLs discovered by
``scraper.directory_archive``.

This module is not imported by any scheduler/cron entry point
(``scraper.archive.archive_cycle``/``discovery_cycle``,
``scraper.news_sitemaps.news_sitemap_cycle``) and issues no HTTP requests of
its own. Nothing is activated by adding it: a caller must explicitly hold a
catalog entry with ``archive_verification == {"status": "verified",
"can_backfill": true, "mechanism": "wordpress_rest"}`` plus a current,
reviewed ``SourceAccessInstruction(channel='api')`` for the exact endpoint
before any row is written.  The JSON flag is retained as technical evidence;
it is never an authorization decision.
"""
from django.db import transaction

from news.models import ArchiveJob, Source, SourceAccessInstruction
from scraper.archive import same_host
from scraper.access_gate import require_approved_instruction
from scraper.utils import safe_url
from scraper.wordpress_rest_adapter import ensure_eligible, ensure_same_site


def _post_url(post):
    if isinstance(post, dict):
        return post.get('url')
    return post


def enqueue_page_jobs(source, catalog_entry, endpoint, posts):
    """Persist unique ArchiveJob(kind='page') rows for post metadata URLs.

    ``posts`` items are either plain URL strings or the dicts returned by
    ``wordpress_rest_adapter.post_metadata`` (only ``url`` is used --
    ``title``/``id``/``published_date`` are discovery metadata the adapter
    already hands back to the caller and are not re-persisted here).

    Fail-closed, both gates re-run here immediately before any write, not
    trusted from an earlier ``collect_since_cutoff`` call that may have run
    minutes or checkpoints earlier:
    * ``SourceNotEligible`` unless ``catalog_entry`` is still an explicitly
      approved wordpress_rest source (see ``ensure_eligible``);
    * ``EndpointDomainMismatch`` unless ``endpoint`` still canonically
      matches both ``catalog_entry['url']`` and ``source.url``.
    * ``AccessDenied`` unless the freshly locked Source has a current,
      reviewed API instruction whose endpoint covers ``endpoint``.
    The Source row is re-locked and re-checked (active/enabled/configured,
    and still same-site as ``endpoint``) inside the write transaction, so a
    source disabled or repointed after the caller's own checks still blocks
    the write -- mirroring the Source re-check ``scraper.archive.process``
    already performs for sitemap/listing jobs.

    Each post URL is additionally required to pass ``scraper.utils.safe_url``
    and match the just-locked Source's own host (``scraper.archive.same_host``)
    before being queued -- the WordPress REST response is publisher-supplied
    data, not something this adapter chain controls, so a compromised or
    misconfigured endpoint handing back an off-site ``link`` must not get a
    foreign URL queued into our own archive worker. This mirrors the same
    per-link host restriction ``scraper.directory_archive`` already applies
    to links parsed out of listing HTML.

    Safe to call more than once for the same posts: ``ArchiveJob.url`` is
    globally unique and the insert uses ``ignore_conflicts``, so a retried
    or overlapping call creates no duplicate rows and raises nothing.
    """
    ensure_eligible(catalog_entry)
    ensure_same_site(catalog_entry, endpoint)
    ensure_same_site({'url': source.url}, endpoint)
    candidates, seen = [], set()
    for post in posts:
        url = _post_url(post)
        if isinstance(url, str) and url and len(url) <= 1024 and url not in seen:
            seen.add(url)
            candidates.append(url)
    if not candidates:
        return 0
    with transaction.atomic():
        current = Source.objects.select_for_update().filter(pk=source.pk,
            is_active=True, scrape_enabled=True, catalog_stage='configured').first()
        if current is None:
            raise ValueError('source_unavailable')
        # Re-check host agreement against the just-locked row, not the
        # possibly-stale `source` argument the caller captured earlier.
        ensure_same_site({'url': current.url}, endpoint)
        require_approved_instruction(
            current, SourceAccessInstruction.Channel.API, endpoint)
        urls = [url for url in candidates if safe_url(url) and same_host(url, current.url)]
        if not urls:
            return 0
        ArchiveJob.objects.bulk_create(
            [ArchiveJob(source=current, url=url, kind='page') for url in urls],
            ignore_conflicts=True, batch_size=200)
    return len(urls)
