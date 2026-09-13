from django.core.management.base import BaseCommand
from scraper.rss_scraper import seed_sources
from news.models import Source


class Command(BaseCommand):
    help = 'Import configured RSS sources without fetching remote content.'

    def handle(self, *args, **options):
        seed_sources()
        self.stdout.write(self.style.SUCCESS(f'Źródła RSS w bazie: {Source.objects.exclude(rss_url="").count()}'))
