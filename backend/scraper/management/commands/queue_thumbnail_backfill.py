"""One pass over absent thumbnails; publisher errors keep their normal backoff."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from news.models import Article, ArchiveJob, ImportState


class Command(BaseCommand):
    help = 'Queue a bounded one-pass batch of automatic records with absent thumbnails. Does not fetch URLs.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 500:
            raise CommandError('limit must be 1..500')
        with transaction.atomic():
            ImportState.objects.get_or_create(name='backfill:thumbnail-v1')
            state = ImportState.objects.select_for_update().get(name='backfill:thumbnail-v1')
            rows = list(Article.objects.filter(pk__gt=int(state.cursor.get('last_pk', 0)),
                image_url='', category_reviewed=False, ingestion_method__in=['rss', 'archive'],
                source__is_active=True, source__scrape_enabled=True).order_by('pk')[:limit])
            queued = 0
            now = timezone.now()
            for article in rows:
                job, created = ArchiveJob.objects.get_or_create(url=article.url,
                    defaults={'source_id': article.source_id, 'kind': 'page', 'priority': 10})
                if created:
                    queued += 1
                elif job.status == 'done':
                    queued += ArchiveJob.objects.filter(pk=job.pk, status='done').update(
                        status='pending', available_at=now, priority=max(10, job.priority))
                # Pending/running/error already have work; don't reset a lease or retry delay.
            state.last_started = now
            state.last_success = now
            state.imported += queued
            state.cursor = {**state.cursor, 'last_pk': rows[-1].pk if rows else state.cursor.get('last_pk', 0),
                'considered': len(rows), 'queued': queued}
            state.save(update_fields=['last_started', 'last_success', 'imported', 'cursor'])
        self.stdout.write(f'Considered {len(rows)} records; queued {queued}. No URLs fetched.')
