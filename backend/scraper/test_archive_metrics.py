from unittest.mock import patch
from datetime import timedelta
import requests
import pytest
from django.utils import timezone
from news.models import Source, ArchiveJob
from scraper.archive import run_batch, SourceDelay


@pytest.mark.django_db
def test_metrics_count_new_articles_separately_from_maps_and_repeated_pages():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    for name, kind in [('new', 'page'), ('existing', 'page'), ('map', 'sitemap'), ('failed', 'page'), ('deferred', 'page')]:
        ArchiveJob.objects.create(source=source, url=f'https://example.org/{name}', kind=kind)
    def process(job):
        name = job.url.rsplit('/', 1)[1]
        if name == 'failed': raise ValueError('unclassified_page')
        if name == 'deferred': raise SourceDelay()
        return {'new': 1, 'existing': 0, 'map': 10000}[name]
    metrics = {}
    with patch('scraper.archive.process', side_effect=process), patch('scraper.archive.time.sleep'):
        assert run_batch(5, metrics=metrics) == 3
    assert metrics == {'pages_completed': 2, 'sitemaps_completed': 1, 'new_articles': 1,
        'failed_jobs': 1, 'deferred_jobs': 1}
    assert ArchiveJob.objects.get(url='https://example.org/deferred').attempts == 0


@pytest.mark.django_db
def test_parallel_capacity_never_starts_more_workers_than_eligible_sources():
    from scraper.archive import run_parallel_batch
    sources = [Source.objects.create(name=f'Publisher {i}', url=f'https://p{i}.example.org') for i in range(9)]
    for source in sources:
        ArchiveJob.objects.create(source=source, url=source.url + '/article', kind='page')
    handled = []
    def consume(limit, source_ids, metrics):
        handled.extend(source_ids)
        metrics.update(pages_completed=1, new_articles=1)
        return 1
    metrics = {}
    with patch('scraper.archive.run_batch', side_effect=consume):
        assert run_parallel_batch(workers=32, metrics=metrics) == 9
    assert sorted(handled) == sorted(source.pk for source in sources)
    assert metrics == {'active_workers': 9, 'eligible_sources': 9, 'pages_completed': 9, 'new_articles': 9}


@pytest.mark.parametrize('workers', [0, 65])
def test_parallel_capacity_rejects_outside_safety_ceiling(workers):
    from scraper.archive import run_parallel_batch
    with pytest.raises(ValueError):
        run_parallel_batch(workers=workers)


@pytest.mark.django_db
def test_transient_retry_honors_retry_after_without_duplicate_job():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/story', kind='page')
    response = requests.Response(); response.status_code = 429; response.headers['Retry-After'] = '1800'
    error = requests.HTTPError(response=response)
    with patch('scraper.archive.process', side_effect=error), patch('scraper.archive.time.sleep'):
        assert run_batch(1) == 0
    job.refresh_from_db()
    assert job.status == 'error' and job.attempts == 1
    assert job.available_at >= timezone.now() + timedelta(minutes=29)
    assert ArchiveJob.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('error', ['empty_directory', 'non_article_route', 'not_a_sitemap', 'robots_disallowed'])
def test_known_technical_errors_are_terminal(error):
    source = Source.objects.create(name='Publisher', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/technical', kind='page')
    with patch('scraper.archive.process', side_effect=ValueError(error)), patch('scraper.archive.time.sleep'):
        assert run_batch(1) == 0
    job.refresh_from_db()
    assert (job.status, job.last_error, job.attempts) == ('quarantined', error, 1)


@pytest.mark.django_db
@pytest.mark.parametrize('error', ['missing_source_title', 'unclassified_page'])
def test_ambiguous_parser_errors_are_not_immediately_terminal(error):
    source = Source.objects.create(name='Publisher', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/drift', kind='page')
    with patch('scraper.archive.process', side_effect=ValueError(error)), patch('scraper.archive.time.sleep'):
        run_batch(1)
    job.refresh_from_db()
    assert (job.status, job.last_error, job.attempts) == ('error', error, 1)


@pytest.mark.django_db
def test_transient_error_is_quarantined_after_bounded_attempts():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    job = ArchiveJob.objects.create(source=source, url='https://example.org/timeout', kind='page', attempts=4)
    with patch('scraper.archive.process', side_effect=requests.Timeout()), patch('scraper.archive.time.sleep'):
        run_batch(1)
    job.refresh_from_db()
    assert (job.status, job.last_error, job.attempts) == ('quarantined', 'Timeout', 5)


def test_host_circuit_opens_after_three_transient_failures(monkeypatch):
    from types import SimpleNamespace
    from scraper.archive import HOST_CIRCUIT_FAILURES, _HOST_STATES, _record_host_failure, host_state
    _HOST_STATES.clear()
    state = host_state('example.org')
    error = requests.Timeout()
    for _ in range(HOST_CIRCUIT_FAILURES):
        _record_host_failure(state, error)
    assert state['failures'] == HOST_CIRCUIT_FAILURES
    assert state['circuit_until'] > 0
