import pytest
from urllib.parse import urlsplit
from django.utils import timezone
from django.core.cache import cache

@pytest.fixture(autouse=True)
def reset_archive_cache(monkeypatch):
    monkeypatch.setenv('ARCHIVE_STORE_FULL_TEXT', 'true')
    cache.clear()
    from scraper.archive import _HOST_STATES
    _HOST_STATES.clear()
    yield
    cache.clear()
    from scraper.archive import _HOST_STATES
    _HOST_STATES.clear()
from rest_framework.test import APIClient
from news.models import (Article, ArchiveJob, EvidenceSnapshot, FetchAttempt,
    Source, ArticleContent, SourceAccessInstruction)
from scraper.archive import process, run_batch, article_body, SourceDelay


def approve_access(source, channel, endpoint=None, scope='metadata'):
    version = (SourceAccessInstruction.objects.filter(source=source)
        .order_by('-version').values_list('version', flat=True).first() or 0) + 1
    card = SourceAccessInstruction.objects.create(
        source=source, version=version, status='approved', channel=channel,
        allowed_scope=scope, endpoint=endpoint or source.url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3,
        daily_request_cap=24)
    # Production checks robots.txt as a separately authorised request.  Keep
    # fixtures realistic unless a test is explicitly about missing coverage.
    root = urlsplit(endpoint or source.url)
    robots_url = f'{root.scheme}://{root.netloc}/robots.txt'
    if not SourceAccessInstruction.objects.filter(source=source, status='approved',
            channel='sitemap', endpoint=robots_url).exists():
        SourceAccessInstruction.objects.create(
            source=source, version=version + 1, status='approved', channel='sitemap',
            allowed_scope='metadata', endpoint=robots_url,
            allowed_path_patterns=['/robots.txt'], terms_url='https://example.org/terms',
            evidence={'basis': 'test robots'}, reviewed_at=timezone.now(), reviewed_by='test',
            minimum_interval_seconds=3, daily_request_cap=24)
    return card


@pytest.mark.django_db
def test_generic_archive_scheduler_stays_blocked_without_access_instruction(monkeypatch):
    from scraper.archive import archive_cycle
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr('scraper.archive.run_parallel_batch', lambda **_: pytest.fail('scheduler bypassed access gate'))
        assert archive_cycle()['status'] == 'blocked_access_review'


@pytest.mark.django_db
def test_generic_archive_scheduler_accepts_an_explicitly_reviewed_html_job(monkeypatch):
    from scraper.archive import archive_cycle
    source = Source.objects.create(name='Reviewed HTML', url='https://example.org',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    approve_access(source, 'html', 'https://example.org', 'content')
    ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return 1

    monkeypatch.setattr('scraper.archive.run_parallel_batch', run)
    result = archive_cycle()
    assert result['status'] == 'ok'
    assert calls[0]['source_ids'] == [source.pk]
    assert 'source_access_scopes' not in calls[0]


@pytest.mark.django_db
def test_parallel_archive_batch_keeps_one_host_on_one_worker(monkeypatch):
    from scraper.archive import run_parallel_batch
    first = Source.objects.create(name='One', url='https://same.example', is_active=True, scrape_enabled=True)
    second = Source.objects.create(name='Two', url='https://same.example/other', is_active=True, scrape_enabled=True)
    third = Source.objects.create(name='Three', url='https://other.example', is_active=True, scrape_enabled=True)
    for source in (first, second, third):
        ArchiveJob.objects.create(source=source, url=source.url + '/article', kind='page')
    calls = []
    monkeypatch.setattr('scraper.archive.run_batch',
        lambda limit, source_ids, **kwargs: calls.append(set(source_ids)) or 0)
    run_parallel_batch(workers=3, per_worker=3)
    same_host_group = next(group for group in calls if first.pk in group)
    assert second.pk in same_host_group
    assert third.pk not in same_host_group

@pytest.mark.django_db
def test_archive_uses_publication_not_sitemap_lastmod(monkeypatch):
    source = Source.objects.create(name='Test archive', url='https://example.org')
    approve_access(source, 'sitemap', 'https://example.org/map.xml')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/map.xml', kind='sitemap')
    xml = b'<urlset><url><loc>https://example.org/old</loc><lastmod>2026-09-08</lastmod></url><url><loc>https://evil.org/other</loc></url></urlset>'
    html = b'<title>Old article</title><meta property="og:type" content="article"><script type="application/ld+json">{"@type":"NewsArticle","articleBody":"Uniquehistoricalword"}</script>'
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else xml if url.endswith('.xml') else html)
    process(job)
    assert ArchiveJob.objects.count() == 2
    page = ArchiveJob.objects.get(kind='page')
    approve_access(source, 'html', source.url, 'content')
    from scraper.archive import _HOST_STATES
    _HOST_STATES.clear()
    process(page, allowed_scope='content')
    a = Article.objects.get()
    assert a.published_date is None
    assert a.content.text == 'Uniquehistoricalword'
    assert APIClient().get('/api/search/', {'q': 'Uniquehistoricalword'}).json()['total'] == 1
    from scraper.archive import _HOST_STATES
    _HOST_STATES.clear()
    process(page, allowed_scope='content')
    assert Article.objects.count() == 1

    @pytest.mark.django_db
    def test_archive_deduplicates_by_same_host_canonical_url(monkeypatch):
        source = Source.objects.create(name='Canonical source', url='https://example.org')
        first = ArchiveJob.objects.create(source=source, url='https://example.org/alias', kind='page')
        second = ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
        html = (b'<title>Canonical story</title><link rel="canonical" href="/story">'
            b'<meta property="og:type" content="article">')
        monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else html)
        process(first)
        from scraper.archive import _HOST_STATES
        _HOST_STATES.clear()
        process(second)
        assert Article.objects.count() == 1
        article = Article.objects.get()
        assert article.url == 'https://example.org/story'
        assert article.content.source_url == first.url

@pytest.mark.django_db
def test_failed_archive_is_retained_without_article(monkeypatch):
    source = Source.objects.create(name='Test', url='https://example.org')
    approve_access(source, 'html')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/old', kind='page')
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nDisallow: /')
    assert run_batch(1) == 0
    job.refresh_from_db()
    assert job.last_error == 'robots_disallowed' and job.status == 'quarantined'
    assert job.available_at > timezone.now()
    assert Article.objects.count() == 0

def test_body_extraction_ignores_unrelated_json():
    assert article_body(b'<script type="application/ld+json">{"@type":"Product","articleBody":"not article"}</script>') == ''


def test_jsonld_uses_article_date_not_claim_date():
    from news.metadata import extract_metadata
    raw = b'<title>Article</title><script type="application/ld+json">[{"@type":"ClaimReview","datePublished":"2016-12-03T00:00:00Z"},{"@type":"NewsArticle","url":"https://example.org/a","datePublished":"2016-12-06T11:33:48Z"}]</script>'
    result = extract_metadata(raw, 'https://example.org/a')
    assert result['published_date'].startswith('2016-12-06T11:33:48')
    assert result['date_source'] == 'jsonld:Article.datePublished'
    assert extract_metadata(raw, 'https://example.org/different')['published_date'] is None


def body_document(nodes):
    import json
    return ('<script type="application/ld+json">' + json.dumps(nodes, ensure_ascii=False) + '</script>').encode('utf-8')


def test_reader_does_not_attribute_longer_related_article_to_source():
    nodes = [
        {'@type': 'NewsArticle', 'url': 'https://example.org/target', 'articleBody': 'Exact source text'},
        {'@type': 'NewsArticle', 'url': 'https://example.org/related', 'articleBody': 'Unrelated long text ' * 50},
    ]
    assert article_body(body_document(nodes), 'https://example.org/target') == 'Exact source text'
    assert article_body(body_document(nodes), 'https://example.org/missing') == ''


@pytest.mark.parametrize('nodes', [
    [{'@type': 'NewsArticle', 'articleBody': 'One'}, {'@type': 'NewsArticle', 'articleBody': 'Two'}],
    [{'@type': 'NewsArticle', 'url': '/target', 'articleBody': 'One'}, {'@type': 'NewsArticle', 'url': '/target', 'articleBody': 'Two'}],
    [{'@type': 'NewsArticle', 'url': '/target', 'mainEntityOfPage': {'@id': '/other'}, 'articleBody': 'Conflicting identity'}],
    [{'@type': 'NewsArticle', 'articleBody': 'Unknown'}, {'@type': 'NewsArticle', 'url': '/other', 'articleBody': 'Other'}],
    [{'@type': 'NewsArticle', 'url': '/target?id=2', 'articleBody': 'Different query'}],
    [{'@type': 42, 'articleBody': 'Invalid schema'}],
])
def test_reader_leaves_ambiguous_text_empty(nodes):
    assert article_body(body_document(nodes), 'https://example.org/target') == ''


def test_reader_accepts_relative_identity_and_keeps_source_characters():
    nodes = {'@graph': [{'@type': 'NewsArticle', 'mainEntityOfPage': {'@id': '/target#article'}, 'articleBody': '  Źródło — pełna treść.  '}]}
    assert article_body(body_document(nodes), 'https://example.org/target') == '  Źródło — pełna treść.  '


def test_reader_honors_declared_encoding():
    raw = ('<meta charset="windows-1250"><script type="application/ld+json">'
           '{"@type":"NewsArticle","articleBody":"Zażółć gęślą jaźń"}</script>').encode('cp1250')
    assert article_body(raw, 'https://example.org/target') == 'Zażółć gęślą jaźń'


@pytest.mark.django_db
def test_unrelated_body_is_not_saved_or_searchable(monkeypatch):
    source = Source.objects.create(name='Test publisher', url='https://example.org')
    approve_access(source, 'html')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/target', kind='page')
    raw = b'<title>Source title</title><meta property="og:type" content="article">' + body_document(
        {'@type': 'NewsArticle', 'url': '/other', 'articleBody': 'Foreignuniquesearchterm'})
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else raw)
    process(job)
    article = Article.objects.get()
    assert article.url == job.url
    assert article.content.text == '' and article.content.status == 'metadata_only'
    assert APIClient().get('/api/search/', {'q': 'Foreignuniquesearchterm'}).json()['total'] == 0


@pytest.mark.django_db
def test_metadata_scope_never_stores_article_body_even_when_full_text_mode_is_on(monkeypatch):
    source = Source.objects.create(name='Metadata only', url='https://example.org')
    approve_access(source, 'html', scope='metadata')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/metadata-only', kind='page')
    raw = b'<title>Source title</title><meta property="og:type" content="article">' + body_document(
        {'@type': 'NewsArticle', 'url': '/metadata-only', 'articleBody': 'Do not retain this body'})
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else raw)
    process(job, allowed_scope='metadata')
    assert Article.objects.get().content.text == ''


@pytest.mark.django_db
def test_snapshot_scope_preserves_raw_html_privately_after_a_successful_fetch(monkeypatch, settings, tmp_path):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    settings.EVIDENCE_SNAPSHOT_STORAGE_ROOT = str(tmp_path / 'private-snapshots')
    source = Source.objects.create(name='Snapshot publisher', url='https://example.org')
    card = approve_access(source, 'html', scope='snapshot')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/snapshot-story', kind='page')
    html = b'<title>Snapshot title</title><meta property="og:type" content="article">'
    receipt = FetchAttempt.objects.create(
        source=source, instruction=card, instruction_version=card.version,
        channel='html', requested_kind='page', url_fingerprint='a' * 64,
        url_host='example.org', outcome='ok', network_started=True, http_status=200,
    )

    def fetch(url, **kwargs):
        if url.endswith('robots.txt'):
            return b'User-agent: *\nAllow: /'
        return (html, receipt) if kwargs.get('return_receipt') else html

    monkeypatch.setattr('scraper.archive.fetch_feed', fetch)
    process(job, allowed_scope='snapshot')

    snapshot = EvidenceSnapshot.objects.get()
    assert snapshot.article == Article.objects.get()
    assert snapshot.fetch_attempt == receipt
    assert snapshot.allowed_uses == []
    assert snapshot.consent_status == 'allowed'


@pytest.mark.django_db
def test_reviewed_archive_job_uses_hostname_transport(monkeypatch):
    source = Source.objects.create(name='Reviewed', url='https://example.org')
    approve_access(source, 'html')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/reviewed', kind='page')
    calls = []
    html = b'<title>Reviewed source</title><meta property="og:type" content="article">'
    def fetch(url, **kwargs):
        calls.append(kwargs.get('hostname_transport'))
        return b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else html
    monkeypatch.setattr('scraper.archive.fetch_feed', fetch)
    process(job, allowed_scope='metadata')
    assert calls == [True, True]


def test_archive_host_gate_covers_robots_and_fetch(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    from scraper.archive import SourceDelay
    from urllib.robotparser import RobotFileParser
    entered, release = Event(), Event()
    policy = RobotFileParser(); policy.parse(['User-agent: *', 'Allow: /', 'Crawl-delay: 10'])
    def robot(url, **_):
        entered.set()
        assert release.wait(3)
        return policy
    monkeypatch.setattr('scraper.archive.robots', robot)
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: (_ for _ in ()).throw(RuntimeError('network failed')))
    job = SimpleNamespace(url='https://example.org/a')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(process, job)
        assert entered.wait(3)
        with pytest.raises(SourceDelay): process(job)
        release.set()
        with pytest.raises(RuntimeError): first.result()
    # Even after cache eviction, error cleanup retains publisher cooldown.
    cache.clear()
    with pytest.raises(SourceDelay): process(job)


@pytest.mark.django_db
def test_archive_rate_limit_is_deferred_not_failed(monkeypatch):
    from scraper.utils import HostRateLimited
    from urllib.robotparser import RobotFileParser

    source = Source.objects.create(name='Rate limited archive', url='https://example.org')
    approve_access(source, 'html')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
    policy = RobotFileParser()
    policy.parse(['User-agent: *', 'Allow: /'])
    monkeypatch.setattr('scraper.archive.robots', lambda *args, **kwargs: policy)
    monkeypatch.setattr('scraper.archive.fetch_feed',
        lambda *args, **kwargs: (_ for _ in ()).throw(HostRateLimited(3)))

    with pytest.raises(SourceDelay) as deferred:
        process(job, allowed_scope='metadata')

    assert deferred.value.retry_after_seconds == 3

@pytest.mark.django_db
def test_archive_preserves_publisher_thumbnail_url(monkeypatch):
    source = Source.objects.create(name='Thumbnail source', url='https://example.org')
    approve_access(source, 'html')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/archive/story')
    html = b'<title>Source title</title><meta property="og:type" content="article"><meta property="og:image" content="/images/photo.jpg">'
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else html)
    process(job)
    assert Article.objects.get().image_url == 'https://example.org/images/photo.jpg'
    from news.metadata import extract_metadata
    assert extract_metadata(b'<title>No photo</title>', job.url)['image_url'] == ''
    assert extract_metadata(b'<meta property="og:image" content="javascript:alert(1)">', job.url)['image_url'] == ''

