"""Minimal DOM shapes and URL patterns observed on publisher pages 2026-09-09."""
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.core.cache import cache
from django.utils import timezone

from news.models import Article, ArticleContent, ArchiveJob, Source
from scraper.archive import _HOST_STATES, process, run_batch, SourceDelay
from scraper.directory_archive import directory_links, directory_spec


EXAMPLES = [
    ('https://niebezpiecznik.pl/tag/kod/',
     'https://niebezpiecznik.pl/post/czy-jestes-w-stanie-odczytac-ten-kod-wejsciowy/',
     '<div id="main"><div class="post " id="post-24069"><div class="title"><h2><a rel="bookmark" href="{url}">Link</a></h2></div></div>{pager}</div>',
     '<div class="navigation"><div class="left"><a href="/tag/kod/page/2/">Starsze</a></div></div>',
     'https://niebezpiecznik.pl/tag/kod/page/2/'),
    ('https://www.polityka.pl/tematy/andrzej-rzeplinski',
     'https://www.polityka.pl/tygodnikpolityka/kraj/1688366,1,kto-bedzie-bronil-zgodnosci-prawa-z-konstytucja.read',
     '<div id="main_content"><section class="cg_tag_index "><a href="{url}">Link</a>{pager}</section></div>',
     '<div class="cg_pager"><a href="?page=2">2</a><a href="?page=3">3</a><a class="cg_pager_nextpage_link" href="?page=2">Następna</a></div>',
     'https://www.polityka.pl/tematy/andrzej-rzeplinski?page=2'),
    ('https://www.nowiny.pl/ludzie/316-marek-migalski',
     'https://www.nowiny.pl/wiadomosci/244907-marek-migalski-ma-raka-za-kilka-dni-bede-wiedzial-czy-zdazylem-w-ostatnim-momencie.html',
     '<main class="c-page__content"><div id="content-wall" class="c-box m-sv-30-border"><div class="c-news m-complex "><div class="c-news__thumbnail"><a href="{url}"><img src="/test.webp"></a></div><a href="{url}">Link</a><a href="{url}#feedback">Komentarze</a></div>{pager}</div></main>',
     '<a href="/ludzie/316-marek-migalski?p=2" class="c-button m-arrow m-block">Więcej</a>',
     'https://www.nowiny.pl/ludzie/316-marek-migalski?p=2'),
]


@pytest.fixture(autouse=True)
def isolated_host_gates():
    cache.clear()
    _HOST_STATES.clear()
    yield
    cache.clear()
    _HOST_STATES.clear()


def listing_html(example, url=None, pager=True):
    return example[2].format(url=url or example[1], pager=example[3] if pager else '').encode('utf-8')


@pytest.mark.parametrize('example', EXAMPLES)
def test_only_observed_publication_shapes_and_next_page(example):
    publications, pages = directory_links(listing_html(example), example[0])
    assert publications == (example[1],)
    assert pages == (example[4],)
    assert directory_spec(example[4]).page == 2
    assert directory_spec(example[4]).root == directory_spec(example[0]).root


@pytest.mark.parametrize('example', EXAMPLES)
def test_relative_links_work_but_sidebar_and_external_links_do_not(example):
    raw = listing_html(example, url=urlsplit(example[1]).path)
    raw += ('<aside><a href="' + example[1].replace('wejsciowy', 'boczny').replace('1688366', '1688367').replace('244907', '244908') + '">Boczny</a></aside>').encode()
    raw += listing_html(example, url='https://other.example/elsewhere')
    assert directory_links(raw, example[0]) == ((example[1],), (example[4],))


@pytest.mark.parametrize('example', EXAMPLES)
@pytest.mark.parametrize('transform', [
    lambda url: url + '?tracking=1',
    lambda url: url.replace('://', '://evil.example/'),
    lambda url: url.replace(urlsplit(url).hostname, 'sub.' + urlsplit(url).hostname),
    lambda url: url.replace(urlsplit(url).hostname, urlsplit(url).hostname + ':9999'),
    lambda url: 'javascript:alert(1)',
])
def test_unsafe_or_unverified_link_variants_do_not_confirm_catalogue(example, transform):
    with pytest.raises(ValueError, match='^unclassified_page$'):
        directory_links(listing_html(example, url=transform(example[1])), example[0])


@pytest.mark.parametrize('url', [
    'https://niebezpiecznik.pl/post/czy-jestes-w-stanie-odczytac-ten-kod-wejsciowy/',
    'https://niebezpiecznik.pl/tag/kod/feed/',
    'https://niebezpiecznik.pl/tag/kod/?s=anything',
    'https://www.polityka.pl/tygodnikpolityka/kraj',
    'https://www.polityka.pl/tematy/andrzej-rzeplinski/extra',
    'https://www.polityka.pl/tematy/andrzej-rzeplinski?page=2&page=3',
    'https://www.polityka.pl/tematy/andrzej-rzeplinski?page=-1',
    'https://www.nowiny.pl/kontakt',
    'https://www.nowiny.pl/ludzie/316-marek-migalski?p=2&search=1',
    'https://other.example/ludzie/316-marek-migalski',
])
def test_other_routes_are_not_reinterpreted_as_catalogues(url):
    assert directory_links(listing_html(EXAMPLES[0]), url) is None


@pytest.mark.parametrize('example', EXAMPLES)
def test_empty_or_navigation_only_catalogue_remains_error(example):
    for raw in (b'<title>Empty page</title>', example[3].encode(),
                ('<aside><a href="' + example[1] + '">Link</a></aside>').encode()):
        with pytest.raises(ValueError, match='^unclassified_page$'):
            directory_links(raw, example[0])


@pytest.mark.parametrize('example', EXAMPLES)
def test_catalogue_routes_never_become_publication_targets(example):
    with pytest.raises(ValueError, match='^unclassified_page$'):
        directory_links(listing_html(example, url=example[0]), example[0])


def test_pagination_cannot_escape_topic_or_travel_backwards():
    example = EXAMPLES[1]
    raw = example[2].format(url=example[1], pager='''<div class="cg_pager">
        <a href="?page=1">Previous</a><a href="?page=3">Next</a>
        <a href="/tematy/other?page=3">Other</a><a href="?page=40000">Jump</a>
        <a href="?page=3&amp;sort=asc">Sort</a></div>''').encode()
    assert directory_links(raw, example[4])[1] == (example[0] + '?page=3',)


def test_malformed_link_does_not_discard_valid_publications():
    example = EXAMPLES[1]
    raw = listing_html(example)
    for broken in ('https://www.polityka.pl:abc/tygodnikpolityka/kraj/123,1,test.read',
                   'https://[broken/tygodnikpolityka/kraj/123,1,test.read'):
        raw += listing_html(example, url=broken)
    assert directory_links(raw, example[0]) == ((example[1],), (example[4],))


def test_directory_limit_fails_visibly_instead_of_omitting_urls(monkeypatch):
    monkeypatch.setattr('scraper.directory_archive.MAX_DIRECTORY_LINKS', 1)
    raw = listing_html(EXAMPLES[1]) + listing_html(EXAMPLES[1], url=EXAMPLES[1][1].replace('1688366', '1688367'))
    with pytest.raises(ValueError, match='directory_link_limit'):
        directory_links(raw, EXAMPLES[1][0])


def setup_job(monkeypatch, example=EXAMPLES[1], body=None):
    source = Source.objects.create(name='Synthetic publisher', url='https://' + urlsplit(example[0]).hostname)
    job = ArchiveJob.objects.create(source=source, url=example[0], kind='page')
    monkeypatch.setattr('scraper.archive.fetch_feed', lambda url: b'User-agent: *\nAllow: /'
        if url.endswith('/robots.txt') else (body if body is not None else listing_html(example)))
    return source, job


@pytest.mark.django_db
@pytest.mark.parametrize('example', EXAMPLES)
def test_discovery_never_saves_catalogue_as_article_and_is_idempotent(monkeypatch, example):
    # Even a shared publisher template with misleading article metadata must not
    # turn this catalogue (or its link labels) into an Article with an invented date.
    raw = b'<title>Catalogue</title><meta property="og:type" content="article"><meta property="article:published_time" content="2026-01-01T00:00:00Z">' + listing_html(example)
    _, job = setup_job(monkeypatch, example, body=raw)
    assert process(job) == 0
    assert set(ArchiveJob.objects.exclude(pk=job.pk).values_list('url', flat=True)) == {example[1], example[4]}
    existing = ArchiveJob.objects.get(url=example[1])
    existing.status = 'done'; existing.attempts = 3; existing.save()
    _HOST_STATES.clear()
    assert process(job) == 0
    existing.refresh_from_db()
    assert existing.status == 'done' and existing.attempts == 3
    assert ArchiveJob.objects.count() == 3
    assert not Article.objects.exists() and not ArticleContent.objects.exists()


@pytest.mark.django_db
def test_successful_catalogue_counts_page_but_zero_articles(monkeypatch):
    _, job = setup_job(monkeypatch)
    metrics = {}
    assert run_batch(1, metrics=metrics) == 1
    job.refresh_from_db()
    assert job.status == 'done' and job.last_error == ''
    assert metrics['pages_completed'] == 1 and metrics['new_articles'] == 0


@pytest.mark.django_db
def test_empty_catalogue_remains_retriable_error(monkeypatch):
    _, job = setup_job(monkeypatch, body=b'<title>Empty catalogue</title>')
    assert run_batch(1) == 0
    job.refresh_from_db()
    assert job.status == 'error' and job.last_error == 'unclassified_page'
    assert ArchiveJob.objects.count() == 1 and not Article.objects.exists()


@pytest.mark.django_db
def test_robots_disallow_prevents_catalogue_fetch(monkeypatch):
    _, job = setup_job(monkeypatch)
    called = []
    def fetch(url):
        called.append(url)
        return b'User-agent: *\nDisallow: /'
    monkeypatch.setattr('scraper.archive.fetch_feed', fetch)
    assert run_batch(1) == 0
    job.refresh_from_db()
    assert job.last_error == 'robots_disallowed'
    assert called == ['https://www.polityka.pl/robots.txt']
    assert ArchiveJob.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('change', [{'is_active': False}, {'scrape_enabled': False},
    {'catalog_stage': 'excluded'}, {'url': 'https://other.example/'}])
def test_source_change_blocks_discovery_before_fetch_and_before_write(monkeypatch, change):
    source, job = setup_job(monkeypatch)
    Source.objects.filter(pk=source.pk).update(**change)
    def forbidden(url):
        pytest.fail('disabled source must not fetch')
    monkeypatch.setattr('scraper.archive.fetch_feed', forbidden)
    with pytest.raises(ValueError, match='source_unavailable'):
        process(job)
    Source.objects.filter(pk=source.pk).update(is_active=True, scrape_enabled=True, catalog_stage='configured', url='https://www.polityka.pl')
    def disable_during_fetch(url):
        if url.endswith('robots.txt'):
            return b'User-agent: *\nAllow: /'
        Source.objects.filter(pk=source.pk).update(**change)
        return listing_html(EXAMPLES[1])
    monkeypatch.setattr('scraper.archive.fetch_feed', disable_during_fetch)
    with pytest.raises(ValueError, match='source_unavailable'):
        process(job)
    assert ArchiveJob.objects.count() == 1 and not Article.objects.exists()


@pytest.mark.django_db
def test_expired_claim_cannot_enqueue_catalogue_links(monkeypatch):
    _, job = setup_job(monkeypatch)
    job.status = 'running'; job.available_at = timezone.now() + timedelta(minutes=15); job.save()
    ArchiveJob.objects.filter(pk=job.pk).update(available_at=job.available_at + timedelta(minutes=1))
    with pytest.raises(SourceDelay):
        process(job)
    assert ArchiveJob.objects.count() == 1
