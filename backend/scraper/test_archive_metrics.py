from unittest.mock import patch
import pytest
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
