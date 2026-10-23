"""Kontrola: ile osób publicznych ma konto X w news/data/osoby_x.csv, ile nie, i lista braków.

  python manage.py osoby_x_pokrycie           # osoby z bazy; gdy baza pusta — z danych w repo
  python manage.py osoby_x_pokrycie --repo    # osoby z danych w repo
  python manage.py osoby_x_pokrycie --bez-listy
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from news import osoby_x
from news.management.commands.osoby_x_zbierz import people


class Command(BaseCommand):
    help = 'Pokrycie kont X osób publicznych (plik osoby_x.csv; na bazie także konta potwierdzone na stronach).'

    def add_arguments(self, parser):
        parser.add_argument('--repo', action='store_true')
        parser.add_argument('--plik', default=str(osoby_x.CSV_PATH))
        parser.add_argument('--bez-listy', action='store_true', help='Tylko liczby, bez listy braków.')

    def handle(self, *args, **options):
        found, origin = people(options['repo'])
        result = osoby_x.coverage(found, osoby_x.read_rows(Path(options['plik'])))
        self.stdout.write(f"Osoby publiczne ({origin}): {result['osoby']}; z kontem X w osoby_x.csv: {result['z_kontem']}; "
                          f"bez konta: {result['bez_konta']}.")
        if origin == 'baza':
            from news.political_models import PublicFigure
            from news.public_figures import figures_with_verified_x
            shown = len(figures_with_verified_x(PublicFigure.objects.filter(archived=False)))
            self.stdout.write(f'Konto X widoczne na stronach (dowód + potwierdzone konto): {shown}.')
        if not options['bez_listy']:
            self.stdout.write('Braki:')
            for person in result['braki']:
                self.stdout.write(f"- {person.name} · {person.osoba_id} · {'; '.join(person.roles[:2])}")
