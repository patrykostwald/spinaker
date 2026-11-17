"""Mechanik od razu: manage.py mechanik (wynik i dziennik ostatnich napraw)."""
from django.core.management.base import BaseCommand

from news import mechanik


class Command(BaseCommand):
    help = 'Naprawa połączeń z modelami Konsylium (lista modeli u dostawcy, próba, zamiennik nazwy).'

    def handle(self, *args, **opts):
        result = mechanik.step()
        self.stdout.write(f"Sprawdzone: {result['checked']}")
        for model, outcome in result['results']:
            self.stdout.write(f'  {model}: {outcome}')
        self.stdout.write('Zamienniki: ' + (', '.join(f'{k} -> {v}' for k, v in mechanik.aliases().items()) or 'brak'))
