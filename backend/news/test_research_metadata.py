import time
from datetime import timedelta
from threading import Event, Lock
from unittest.mock import patch

import pytest
from django.utils import timezone

from news.models import Article, ArchiveJob, Source
from news.research_metadata import (FastNetwork, ProbeError, ResearchMetadataSession,
    _HOSTS, _HOSTS_LOCK, host_state, research_metadata_cycle)

HTML = b'''<html><head><meta property="og:type" content="article">
<meta property="og:title" content="Publisher's real headline">
<meta property="article:published_time" content="2024-01-02T08:00:00+01:00">
<meta property="og:image" content="https://images.example/photo.jpg"></head></html>'''


def publisher(host='example.org', **kwargs):
    return Source.objects.create(name=host, url='https://' + host, **kwargs)


def wait_workers():
    until = time.monotonic() + 3
    while time.monotonic() < until:
        with _HOSTS_LOCK:
            if not _HOSTS:
                return
        time.sleep(0.01)
    raise AssertionError('metadata worker did not release its bounded slot')


@pytest.mark.django_db(transaction=True)
def test_more_than_two_waves_use_at_most_three_distinct_hosts_and_publisher_metadata():
    sources = [publisher(f'publisher{i}.example') for i in range(4)]
    urls = [source.url + f'/story-{i}' for i in range(3) for source in sources]
    lock, active, maxima = Lock(), set(), []
    def fetch(url):
        host = url.split('/')[2]
        with lock:
            assert host not in active
            active.add(host)
            maxima.append(len(active))
        try:
            time.sleep(0.015)
            return HTML, url, []
        finally:
            with lock:
                active.remove(host)
    with patch('news.research_metadata._NETWORK.fetch', side_effect=fetch):
        result = ResearchMetadataSession(sources, allow_fetch=True).enrich(urls)
    assert result['attempted'] == 12
    assert len(result['articles']) == 12
    assert result['pending_urls'] == []
    assert max(maxima) <= 3
    assert ArchiveJob.objects.filter(status='done', priority=100).count() == 12
    assert Article.objects.filter(title="Publisher's real headline", published_date__year=2024).count() == 12
    assert all(article['content_status'] == 'metadata_only' for article in result['articles'])


@pytest.mark.django_db(transaction=True)
def test_deadline_returns_without_waiting_for_http_and_late_response_cannot_write():
    source = publisher()
    release, started = Event(), Event()
    def fetch(url):
        started.set()
        release.wait(2)
        return HTML, url, []
    try:
        with patch('news.research_metadata._NETWORK.fetch', side_effect=fetch):
            before = time.monotonic()
            result = ResearchMetadataSession([source], deadline_seconds=0.08, allow_fetch=True).enrich([source.url + '/slow'])
            assert time.monotonic() - before < 0.5
            assert started.is_set()
            assert result['pending_urls'] == [source.url + '/slow']
            assert not Article.objects.exists()
            release.set()
            wait_workers()
    finally:
        release.set()
        wait_workers()
    assert not Article.objects.exists()
    assert ArchiveJob.objects.get().status == 'pending'


@pytest.mark.django_db(transaction=True)
def test_normal_worker_lease_and_publisher_backoff_are_preserved():
    source = publisher()
    future = timezone.now() + timedelta(hours=4)
    jobs = [ArchiveJob.objects.create(source=source, url=source.url + '/' + status,
        kind='page', status=status, available_at=future, attempts=3) for status in ('running', 'error', 'done')]
    with patch('news.research_metadata._NETWORK.fetch') as fetch:
        result = ResearchMetadataSession([source], allow_fetch=True).enrich([job.url for job in jobs])
        fetch.assert_not_called()
    assert result['attempted'] == 0
    for job in jobs:
        previous = job.status
        job.refresh_from_db()
        assert job.status == previous and job.available_at == future and job.attempts == 3
        assert job.priority == 100


@pytest.mark.django_db(transaction=True)
def test_owner_disabling_source_during_fetch_prevents_article_write():
    source = publisher()
    def fetch(url):
        Source.objects.filter(pk=source.pk).update(is_active=False, scrape_enabled=False)
        return HTML, url, []
    with patch('news.research_metadata._NETWORK.fetch', side_effect=fetch):
        result = ResearchMetadataSession([source], allow_fetch=True).enrich([source.url + '/story'])
    assert result['articles'] == []
    assert not Article.objects.exists()
    assert ArchiveJob.objects.get().status == 'pending'


@pytest.mark.django_db(transaction=True)
def test_foreign_redirect_is_not_saved_under_original_publisher():
    source = publisher()
    with patch('news.research_metadata._NETWORK.fetch', return_value=(HTML, 'https://other.example/story', [])):
        result = ResearchMetadataSession([source], allow_fetch=True).enrich([source.url + '/story'])
    assert result['articles'] == []
    assert not Article.objects.exists()
    assert ArchiveJob.objects.get().last_error == 'publisher_redirect_outside_source'


@pytest.mark.django_db(transaction=True)
def test_session_limit_is_shared_between_batches_and_rest_is_durably_queued():
    source = publisher()
    session = ResearchMetadataSession([source], max_urls=100, deadline_seconds=0)
    with patch('news.research_metadata._NETWORK.fetch') as fetch:
        session.enrich([source.url + f'/story-{i}' for i in range(10)])
        result = session.enrich([source.url + f'/story-{i}' for i in range(10, 30)])
        fetch.assert_not_called()
    assert ArchiveJob.objects.filter(status='pending', priority=100).count() == 15
    assert len(result['pending_urls']) == 15


@pytest.mark.django_db(transaction=True)
def test_existing_article_is_returned_without_replacing_editorial_metadata():
    source = publisher()
    article = Article.objects.create(source=source, url=source.url + '/story', title='Existing title',
        category_reviewed=True, image_url='https://images.example/original.jpg', published_date=timezone.now())
    with patch('news.research_metadata._NETWORK.fetch') as fetch:
        result = ResearchMetadataSession([source]).enrich([article.url])
        fetch.assert_not_called()
    assert result['articles'][0]['title'] == 'Existing title'
    assert result['articles'][0]['image_url'] == article.image_url


@pytest.mark.django_db(transaction=True)
def test_web_default_only_enqueues_without_starting_an_independent_crawler():
    source = publisher()
    with patch('news.research_metadata._NETWORK.fetch') as fetch:
        result = ResearchMetadataSession([source]).enrich([source.url + '/new'])
        fetch.assert_not_called()
    assert result['attempted'] == 0
    assert result['pending_urls'] == [source.url + '/new']
    job = ArchiveJob.objects.get()
    assert job.priority == 100 and job.status == 'pending' and job.attempts == 0


@pytest.mark.django_db(transaction=True)
def test_scheduler_cycle_selects_only_due_requested_unstored_active_pages(settings):
    settings.RESEARCH_METADATA_NETWORK_ENABLED = True
    source = publisher()
    disabled = publisher('disabled.example', is_active=False, scrape_enabled=False)
    future = timezone.now() + timedelta(hours=1)
    rows = [
        dict(url=source.url + '/leased', source=source, status='running', available_at=future, priority=100),
        dict(url=source.url + '/backoff', source=source, status='error', available_at=future, priority=100),
        dict(url=source.url + '/historical', source=source, priority=0),
        dict(url=source.url + '/map', source=source, priority=100, kind='sitemap'),
        dict(url=disabled.url + '/off', source=disabled, priority=100),
        dict(url=source.url + '/stored', source=source, priority=100)]
    for row in rows:
        ArchiveJob.objects.create(**{'kind': 'page', **row})
    Article.objects.create(source=source, url=source.url + '/stored', title='Existing')
    wanted = ArchiveJob.objects.create(source=source, url=source.url + '/requested', kind='page', priority=100)
    with patch('news.research_metadata._NETWORK.fetch', side_effect=lambda url: (HTML, url, [])) as fetch:
        result = research_metadata_cycle()
    assert result['requested'] == result['ready'] == result['attempted'] == 1
    assert fetch.call_args.args == (wanted.url,)
    assert ArchiveJob.objects.filter(status='done').count() == 1
    assert Article.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_existing_different_source_record_is_not_misattributed_in_metadata_response():
    first, second = publisher(), publisher('second.example')
    Article.objects.create(source=second, url=first.url + '/story', title='Identity conflict')
    result = ResearchMetadataSession([first, second]).enrich([first.url + '/story'])
    assert result['articles'] == []
    assert result['pending_urls'] == [first.url + '/story']


@pytest.mark.django_db(transaction=True)
def test_registry_retains_institutions_sharing_one_host():
    premier = Source.objects.create(name='KPRM', source_type='institution', url='https://www.gov.pl/web/premier/rss')
    health = Source.objects.create(name='Zdrowie', source_type='institution', url='https://www.gov.pl/web/zdrowie/rss')
    class Registry(dict):
        all_sources = (premier, health)
    result = ResearchMetadataSession(Registry({'www.gov.pl': premier})).enrich(['https://www.gov.pl/web/zdrowie/story'])
    assert result['rejected_urls'] == []
    assert ArchiveJob.objects.get().source_id == health.pk


@pytest.mark.django_db(transaction=True)
def test_unknown_private_and_wrong_institution_urls_never_enter_fast_lane():
    source = Source.objects.create(name='Zdrowie', source_type='institution',
        url='https://www.gov.pl/web/zdrowie/rss')
    with patch('news.research_metadata._NETWORK.fetch') as fetch:
        result = ResearchMetadataSession([source]).enrich(['http://127.0.0.1/private',
            'https://www.gov.pl/web/premier/story', 'https://www.gov.pl.evil.example/story'])
        fetch.assert_not_called()
    assert len(result['rejected_urls']) == 3
    assert not ArchiveJob.objects.exists()


def test_fast_fetch_respects_normal_archive_host_lock():
    network = FastNetwork()
    network.context.deadline = time.monotonic() + 1
    state = host_state('locked.example')
    state['lock'].acquire()
    try:
        with patch('scraper.source_probe.ProbeNetwork.raw') as raw:
            with pytest.raises(ProbeError, match='research_host_busy'):
                network.raw('https://locked.example/story')
            raw.assert_not_called()
    finally:
        state['lock'].release()
