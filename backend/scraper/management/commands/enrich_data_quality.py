from django.core.management.base import BaseCommand
from scraper.quality_enrichment import enrich_quality


class Command(BaseCommand):
    help = 'Build deterministic quality profiles and relations without merging or deleting articles.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--after-pk', type=int, default=0)

    def handle(self, *args, **options):
        self.stdout.write(str(enrich_quality(limit=options['limit'], after_pk=options['after_pk'])))
