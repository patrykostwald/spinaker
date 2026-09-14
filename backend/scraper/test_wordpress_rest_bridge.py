"""Tests for the minimal WordPress REST -> ArchiveJob bridge.

Temporary test database only (see pytest.ini: PYTEST_VERSION forces sqlite).
No network: this module never issues HTTP requests, only writes ArchiveJob
rows from already-fetched metadata.
"""
import pytest

from django.utils import timezone

from news.models import Article, ArchiveJob, ArticleContent, Source, SourceAccessInstruction
from scraper.access_gate import AccessDenied
from scraper.wordpress_rest_adapter import EndpointDomainMismatch, SourceNotEligible
from scraper.wordpress_rest_bridge import enqueue_page_jobs

ENDPOINT = 'https://example.pl/wp-json/wp/v2/posts'


def entry(**overrides):
    verification = {'status': 'verified', 'can_backfill': True, 'mechanism': 'wordpress_rest'}
    verification.update(overrides)
    return {'name': 'Example', 'url': 'https://example.pl', 'archive_verification': verification}


def post(number, *, date='2026-06-01T10:00:00'):
    return {'id': number, 'url': f'https://example.pl/post-{number}/',
        'title': f'Post {number}', 'published_date': date}


def make_source(url='https://example.pl', **overrides):
    defaults = dict(name='Example', url=url, is_active=True, scrape_enabled=True, catalog_stage='configured')
    defaults.update(overrides)
    source = Source.objects.create(**defaults)
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=ENDPOINT, terms_url='https://example.pl/terms',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(),
        reviewed_by='test', minimum_interval_seconds=3)
    return source


# --- fail-closed -----------------------------------------------------------

@pytest.mark.django_db
def test_missing_api_instruction_writes_nothing():
    source = make_source()
    source.access_instructions.all().delete()

    with pytest.raises(AccessDenied, match='no_approved_instruction'):
        enqueue_page_jobs(source, entry(), ENDPOINT, [post(1)])

    assert ArchiveJob.objects.count() == 0

@pytest.mark.django_db
@pytest.mark.parametrize('overrides', [
    {'status': 'needs_review'},
    {'can_backfill': False},
    {'can_backfill': 'true'},
    {'mechanism': 'sitemap_index'},
    {'mechanism': None},
])
def test_ineligible_entry_writes_nothing(overrides):
    source = make_source()
    with pytest.raises(SourceNotEligible):
        enqueue_page_jobs(source, entry(**overrides), ENDPOINT, [post(1)])
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
def test_missing_verification_block_writes_nothing():
    source = make_source()
    bare = {'name': 'Example', 'url': 'https://example.pl'}
    with pytest.raises(SourceNotEligible):
        enqueue_page_jobs(source, bare, ENDPOINT, [post(1)])
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('endpoint', [
    'https://otherdomain.pl/wp-json/wp/v2/posts',
    'https://blog.example.pl/wp-json/wp/v2/posts',
    'https://example.pl.evil.com/wp-json/wp/v2/posts',
])
def test_cross_domain_endpoint_writes_nothing(endpoint):
    source = make_source()
    with pytest.raises(EndpointDomainMismatch):
        enqueue_page_jobs(source, entry(), endpoint, [post(1)])
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
def test_source_url_disagreeing_with_catalog_entry_writes_nothing():
    # catalog_entry/endpoint agree with each other but not with the actual
    # Source row -- must not silently attach jobs to the wrong publisher.
    source = make_source(url='https://mismatched.example')
    with pytest.raises(EndpointDomainMismatch):
        enqueue_page_jobs(source, entry(), ENDPOINT, [post(1)])
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('change', [{'is_active': False}, {'scrape_enabled': False},
    {'catalog_stage': 'excluded', 'is_active': False, 'scrape_enabled': False}])
def test_disabled_source_blocks_write(change):
    source = make_source()
    Source.objects.filter(pk=source.pk).update(**change)
    source.refresh_from_db()
    with pytest.raises(ValueError, match='source_unavailable'):
        enqueue_page_jobs(source, entry(), ENDPOINT, [post(1)])
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
def test_source_repointed_after_caller_check_blocks_write():
    # Simulate the Source having been repointed to a different host after the
    # caller already validated it -- the caller's in-memory `source` object
    # (still example.pl) is stale; only the fresh, locked row inside the
    # write transaction reflects that. The re-check must use the fresh row,
    # not the stale Python object, so the write is still blocked.
    source = make_source()
    Source.objects.filter(pk=source.pk).update(url='https://other.example')
    assert source.url == 'https://example.pl'  # the caller's object is stale on purpose
    with pytest.raises(EndpointDomainMismatch):
        enqueue_page_jobs(source, entry(), ENDPOINT, [post(1)])
    assert ArchiveJob.objects.count() == 0


# --- happy path / persistence shape -----------------------------------------

@pytest.mark.django_db
def test_writes_only_unique_page_jobs_no_article_no_content():
    source = make_source()
    created = enqueue_page_jobs(source, entry(), ENDPOINT, [post(1), post(2)])
    assert created == 2
    jobs = list(ArchiveJob.objects.order_by('url'))
    assert [job.url for job in jobs] == ['https://example.pl/post-1/', 'https://example.pl/post-2/']
    assert all(job.kind == 'page' for job in jobs)
    assert all(job.source_id == source.pk for job in jobs)
    assert not Article.objects.exists() and not ArticleContent.objects.exists()


@pytest.mark.django_db
def test_accepts_plain_url_strings_too():
    source = make_source()
    urls = ['https://example.pl/post-1/', 'https://example.pl/post-2/']
    enqueue_page_jobs(source, entry(), ENDPOINT, urls)
    assert set(ArchiveJob.objects.values_list('url', flat=True)) == set(urls)


@pytest.mark.django_db
def test_no_posts_writes_nothing_and_returns_zero():
    source = make_source()
    assert enqueue_page_jobs(source, entry(), ENDPOINT, []) == 0
    assert ArchiveJob.objects.count() == 0


@pytest.mark.django_db
def test_malformed_post_entries_are_skipped_not_fatal():
    source = make_source()
    posts = [post(1), {'id': 2}, {'url': ''}, {'url': 123}, None, 'https://example.pl/post-3/']
    enqueue_page_jobs(source, entry(), ENDPOINT, posts)
    assert set(ArchiveJob.objects.values_list('url', flat=True)) == {
        'https://example.pl/post-1/', 'https://example.pl/post-3/'}


@pytest.mark.django_db
def test_off_site_post_link_from_endpoint_is_dropped_not_queued():
    # The WP REST response is publisher-supplied data; a compromised or
    # misconfigured endpoint handing back a `link` for a different host must
    # not get that foreign URL queued into the archive worker.
    source = make_source()
    posts = [post(1), {'id': 9, 'url': 'https://evil.example/payload'},
        {'id': 10, 'url': 'javascript:alert(1)'}]
    enqueue_page_jobs(source, entry(), ENDPOINT, posts)
    assert set(ArchiveJob.objects.values_list('url', flat=True)) == {'https://example.pl/post-1/'}


@pytest.mark.django_db
def test_all_off_site_links_returns_zero_without_error():
    source = make_source()
    posts = [{'id': 9, 'url': 'https://evil.example/payload'}]
    assert enqueue_page_jobs(source, entry(), ENDPOINT, posts) == 0
    assert ArchiveJob.objects.count() == 0


# --- idempotency / dedup -----------------------------------------------------

@pytest.mark.django_db
def test_duplicate_urls_within_one_call_collapse_to_one_job():
    source = make_source()
    enqueue_page_jobs(source, entry(), ENDPOINT, [post(1), post(1)])
    assert ArchiveJob.objects.count() == 1


@pytest.mark.django_db
def test_retrying_the_same_call_is_safe_and_creates_no_duplicates():
    source = make_source()
    first = enqueue_page_jobs(source, entry(), ENDPOINT, [post(1), post(2)])
    second = enqueue_page_jobs(source, entry(), ENDPOINT, [post(1), post(2), post(3)])
    assert first == 2 and second == 3  # attempted counts, mirroring scraper.archive.process
    assert ArchiveJob.objects.count() == 3


@pytest.mark.django_db
def test_url_already_present_from_a_different_source_or_kind_is_left_untouched():
    # ArchiveJob.url is globally unique; a URL already tracked (e.g. discovered
    # earlier by directory_archive under the same source) must not be
    # clobbered or duplicated by the bridge.
    source = make_source()
    existing = ArchiveJob.objects.create(source=source, url='https://example.pl/post-1/', kind='page',
        status='done', attempts=3)
    enqueue_page_jobs(source, entry(), ENDPOINT, [post(1), post(2)])
    assert ArchiveJob.objects.count() == 2
    existing.refresh_from_db()
    assert existing.status == 'done' and existing.attempts == 3


@pytest.mark.django_db
def test_never_persists_title_or_published_date_fields():
    source = make_source()
    enqueue_page_jobs(source, entry(), ENDPOINT, [post(1)])
    job = ArchiveJob.objects.get()
    fields = {field.name for field in job._meta.get_fields()}
    assert 'title' not in fields and 'excerpt' not in fields and 'text' not in fields and 'snapshot' not in fields
