"""Requested URLs use the normal publisher importer and its existing backoff."""
from urllib.parse import urlsplit
from news.models import ArchiveJob
from scraper.utils import safe_url


def enqueue_requested_url(url, source):
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    source_host = (urlsplit(source.url).hostname or '').removeprefix('www.')
    if (not safe_url(url) or len(url) > 1024 or host != source_host
            or not source.is_active or not source.scrape_enabled
            or source.source_type in ('twitter', 'politician', 'editorial')):
        raise ValueError('Not an enabled publisher URL')
    job, _ = ArchiveJob.objects.get_or_create(url=url,
        defaults={'source': source, 'kind': 'page', 'priority': 100})
    # Never reset an active lease, publisher backoff, or completed record.
    ArchiveJob.objects.filter(pk=job.pk, priority__lt=100).update(priority=100)
    return job
