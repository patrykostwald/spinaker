from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from news.models import ArchiveJob, Source
from scraper.queue import enqueue_requested_url
from scraper.archive import run_batch


@pytest.mark.django_db
def test_request_does_not_override_running_lease_or_failure_backoff():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    future = timezone.now() + timedelta(hours=5)
    for status in ['running', 'error', 'done']:
        job = ArchiveJob.objects.create(source=source, url=f'https://example.org/{status}',
            kind='page', status=status, available_at=future, attempts=3)
        enqueue_requested_url(job.url, source)
        enqueue_requested_url(job.url, source)
        job.refresh_from_db()
        assert job.status == status and job.available_at == future
        assert job.attempts == 3 and job.priority == 100
    assert ArchiveJob.objects.count() == 3


@pytest.mark.django_db
def test_requested_urls_preserve_archive_slots():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    old = timezone.now() - timedelta(days=1)
    historical = [ArchiveJob.objects.create(source=source, url=f'https://example.org/old-{i}', kind='page', available_at=old) for i in range(5)]
    urgent = [enqueue_requested_url(f'https://example.org/requested-{i}', source) for i in range(5)]
    handled = []
    with patch('scraper.archive.process', side_effect=lambda job: handled.append(job.pk)), patch('scraper.archive.time.sleep'):
        assert run_batch(4) == 4
    assert handled == [urgent[0].pk] + [job.pk for job in historical[:3]]


@pytest.mark.django_db
def test_small_new_source_gets_a_turn_alongside_large_old_queue():
    big = Source.objects.create(name='Big', url='https://big.example.org')
    small = Source.objects.create(name='Small', url='https://small.example.org')
    old = timezone.now() - timedelta(days=1)
    for i in range(8):
        ArchiveJob.objects.create(source=big, url=f'https://big.example.org/{i}', kind='page', available_at=old)
    new = ArchiveJob.objects.create(source=small, url='https://small.example.org/new', kind='page')
    handled = []
    with patch('scraper.archive.process', side_effect=lambda job: handled.append(job.pk)), patch('scraper.archive.time.sleep'):
        assert run_batch(2, source_ids=[big.pk, small.pk]) == 2
    assert new.pk in handled


@pytest.mark.django_db
def test_queue_rejects_foreign_and_disabled_sources():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    with pytest.raises(ValueError):
        enqueue_requested_url('https://example.org.evil.test/story', source)
    source.scrape_enabled = False
    with pytest.raises(ValueError):
        enqueue_requested_url('https://example.org/story', source)
    assert not ArchiveJob.objects.exists()
