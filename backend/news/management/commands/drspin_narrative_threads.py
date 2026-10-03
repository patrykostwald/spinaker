from datetime import date
from django.core.management.base import BaseCommand
from news.narrative_threads import build_narratives


class Command(BaseCommand):
    help = 'Przelicz nitki narracji z zapisanych przekazów (bez sieci, idempotentnie).'

    def add_arguments(self, parser):
        parser.add_argument('--day', type=date.fromisoformat)

    def handle(self, **options):
        self.stdout.write(str(build_narratives(options['day'])))
