from django.core.management.base import BaseCommand
from django.db.models import Count

from news.models import ArchiveJob, ImportState, Source


class Command(BaseCommand):
    help = 'Show local archive backfill state without fetching any URL.'

    def add_arguments(self, parser):
        parser.add_argument('--source-id', action='append', type=int)

    def handle(self, *args, **options):
        source_ids = options.get('source_id')
        sources = Source.objects.filter(pk__in=source_ids) if source_ids else Source.objects.all()
        for source in sources.order_by('pk'):
            state = ImportState.objects.filter(name=f'archive-backfill:{source.pk}').first()
            counts = dict(ArchiveJob.objects.filter(source=source).values('status').annotate(count=Count('id')).values_list('status', 'count'))
            cursor = state.cursor if state else {}
            self.stdout.write(str({'source_id': source.pk, 'name': source.name,
                'active': source.is_active, 'scrape_enabled': source.scrape_enabled,
                'catalog_stage': source.catalog_stage, 'cursor': cursor,
                'jobs': counts}))