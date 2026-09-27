"""Kariera sejmowa osób publicznych z oficjalnego API Sejmu: kadencje, daty mandatu i klub (bez danych osobowych).

  python manage.py sejm_career            # z API; gdy niedostępne — z pliku news/data/sejm_career.json
  python manage.py sejm_career --export   # zapis mandatów do pliku (uruchamiane tam, gdzie API działa)
"""
from django.core.management.base import BaseCommand

from news.sejm_career import export_bundle, run


class Command(BaseCommand):
    help = 'Uzupełnia kadencje Sejmu (daty i klub) na profilach osób publicznych.'

    def add_arguments(self, parser):
        parser.add_argument('--export', action='store_true')

    def handle(self, *args, export, **options):
        self.stdout.write(f'zapisano {export_bundle()} mandatów' if export else str(run()))
