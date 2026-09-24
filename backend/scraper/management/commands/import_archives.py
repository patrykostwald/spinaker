from django.core.management.base import BaseCommand, CommandError
from news.models import Source
from scraper.archive import discover, run_batch

class Command(BaseCommand):
    help = 'Discover publisher-declared sitemaps and process a resumable bounded archive batch.'
    def add_arguments(self, parser):
        parser.add_argument('--source-id', type=int)
        parser.add_argument('--limit', type=int, default=10)
    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 100: raise CommandError('limit must be 1..100')
        if options['source_id']:
            source = Source.objects.get(pk=options['source_id'], is_active=True)
            self.stdout.write(f'Discovered sitemap jobs: {discover(source)}')
        self.stdout.write(f'Completed jobs: {run_batch(options["limit"])}')
