import pytest
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
from news.models import Article, ArchiveJob, Source, ArticleContent
from scraper.archive import process, run_batch, article_body

@pytest.mark.django_db
def test_archive_uses_publication_not_sitemap_lastmod(monkeypatch):
    source = Source.objects.create(name='Test archive', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/map.xml', kind='sitemap')
    xml = b'<urlset><url><loc>https://example.org/old</loc><lastmod>2026-09-08</lastmod></url><url><loc>https://evil.org/other</loc></url></urlset>'
    html = b'<title>Old article</title><meta property="og:type" content="article"><script type="application/ld+json">{"@type":"NewsArticle","articleBody":"Uniquehistoricalword"}</script>'
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else xml if url.endswith('.xml') else html)
    process(job)
    assert ArchiveJob.objects.count() == 2
    page = ArchiveJob.objects.get(kind='page')
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
    job = ArchiveJob.objects.create(source=source, url='https://example.org/metadata-only', kind='page')
    raw = b'<title>Source title</title><meta property="og:type" content="article">' + body_document(
        {'@type': 'NewsArticle', 'url': '/metadata-only', 'articleBody': 'Do not retain this body'})
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else raw)
    process(job, allowed_scope='metadata')
    assert Article.objects.get().content.text == ''


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
def test_archive_preserves_publisher_thumbnail_url(monkeypatch):
    source = Source.objects.create(name='Thumbnail source', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/archive/story')
    html = b'<title>Source title</title><meta property="og:type" content="article"><meta property="og:image" content="/images/photo.jpg">'
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else html)
    process(job)
    assert Article.objects.get().image_url == 'https://example.org/images/photo.jpg'
    from news.metadata import extract_metadata
    assert extract_metadata(b'<title>No photo</title>', job.url)['image_url'] == ''
    assert extract_metadata(b'<meta property="og:image" content="javascript:alert(1)">', job.url)['image_url'] == ''

