from django.core.management.base import BaseCommand, CommandError
from news.agents_common import step


class Command(BaseCommand):
    help = 'Jeden darmowy krok; force pomija okno, nigdy limit dzienny ani zakaz płatnych modeli.'

    def add_arguments(self, parser):
        parser.add_argument('--agent', required=True, choices=['strateg', 'pielgrzym'])
        parser.add_argument('--force-window', action='store_true')

    def handle(self, *args, **options):
        try:
            result = step(options['agent'], force=options['force_window'])
        except Exception as error:
            raise CommandError(f'Krok przerwany: {type(error).__name__}') from error
        self.stdout.write(str(result))
