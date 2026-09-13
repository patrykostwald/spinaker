from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import pytest
from django.core.management import call_command
from django.utils import timezone
from news.models import Article, ArchiveJob, Source, ImportState


@pytest.mark.django_db
def test_backfill_is_bounded_one_pass_and_preserves_retry_delays():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    now = timezone.now()
    records = [Article.objects.create(source=source, title=f'Title {i}', url=f'https://example.org/{i}',
        ingestion_method='rss') for i in range(5)]
    done = ArchiveJob.objects.create(source=source, url=records[0].url, kind='page', status='done')
    error = ArchiveJob.objects.create(source=source, url=records[1].url, kind='page', status='error',
        available_at=now+timedelta(hours=6), attempts=2, last_error='HTTPError')
    running = ArchiveJob.objects.create(source=source, url=records[2].url, kind='page', status='running',
        available_at=now+timedelta(minutes=15), attempts=1)
    with patch('scraper.utils.fetch_feed') as fetch:
        call_command('queue_thumbnail_backfill', limit=3, stdout=StringIO())
        fetch.assert_not_called()
    done.refresh_from_db()
    assert done.status == 'pending' and done.priority == 10
    error.refresh_from_db(); running.refresh_from_db()
    assert error.status == 'error' and error.available_at == now+timedelta(hours=6) and error.attempts == 2
    assert running.status == 'running' and running.available_at == now+timedelta(minutes=15)
    assert not ArchiveJob.objects.filter(url=records[3].url).exists()
    call_command('queue_thumbnail_backfill', limit=3, stdout=StringIO())
    assert ArchiveJob.objects.count() == 5
    # Missing thumbnails don't cause the cursor to wrap into an infinite fetch loop.
    done.status = 'done'; done.save()
    call_command('queue_thumbnail_backfill', limit=3, stdout=StringIO())
    done.refresh_from_db()
    assert done.status == 'done'
    assert ImportState.objects.get(name='backfill:thumbnail-v1').cursor['considered'] == 0


@pytest.mark.django_db
def test_backfill_does_not_schedule_manual_reviewed_or_already_illustrated_records():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    for i, changes in enumerate([{'ingestion_method': 'manual'}, {'category_reviewed': True}, {'image_url': 'https://example.org/photo.jpg'}]):
        Article.objects.create(source=source, title='Title', url=f'https://example.org/{i}', **{'ingestion_method':'rss', **changes})
    call_command('queue_thumbnail_backfill', stdout=StringIO())
    assert not ArchiveJob.objects.exists()
