from django.core.management.base import BaseCommand

from news.clinic import fill_x_threads


class Command(BaseCommand):
    help = 'Uzupełnia syntezy diagnoz do wątków na X (darmowy model) dla opublikowanych diagnoz bez syntezy.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        self.stdout.write(f'Uzupełniono syntez: {fill_x_threads(limit=options["limit"])}')
