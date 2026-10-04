from django.core.management.base import BaseCommand

from news import ekspert_ai
from news.agents_common import WindowClosed


class Command(BaseCommand):
    help = 'Ekspert AI: stan wiedzy o AI ze znalezisk Pielgrzyma (darmowe modele, każde twierdzenie ze źródłem).'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Bez czekania na tydzień i na wolne okno limitów.')

    def handle(self, **options):
        try:
            note = ekspert_ai.step(force=options['force'])
        except WindowClosed as error:
            self.stdout.write(f'Okno zamknięte: {error}')
            return
        self.stdout.write(f'{note.title} [{note.status}]\n\n{note.body}')
