from django.core.management.base import BaseCommand
from scraper.quality import scan_quality
class Command(BaseCommand):
    help = 'Flag metadata gaps and inconsistencies without changing articles.'
    def add_arguments(self, parser): parser.add_argument('--limit', type=int, default=200)
    def handle(self, *args, **options): self.stdout.write(str(scan_quality(options['limit'])))
