from datetime import date
from django.core.management.base import BaseCommand
from news.narrative_threads import build_narratives


class Command(BaseCommand):
    help = 'Przelicz spinki narracji z zapisanych przekazów (bez sieci, idempotentnie).'

    def add_arguments(self, parser):
        parser.add_argument('--day', type=date.fromisoformat)

    def handle(self, **options):
        from news.features import threads_enabled, threads_disabled_result
        if not threads_enabled():
            self.stdout.write(str(threads_disabled_result()))
            return
        self.stdout.write(str(build_narratives(options['day'])))
