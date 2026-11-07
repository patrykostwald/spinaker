"""Rozgrzewanie cache przeszłość.today teraz (zwykle robi to zadanie co godzinę i o 5:35): manage.py przeszlosc_rozgrzej [--zakres all]."""
from django.core.management.base import BaseCommand

from news.przeszlosc_cache import warm


class Command(BaseCommand):
    help = 'Przelicz tematy dnia (i profile posłów przy --zakres all) do cache, żeby czytelnik nie czekał na zimny odczyt.'

    def add_arguments(self, parser):
        parser.add_argument('--zakres', choices=['hot', 'all'], default='hot')
        parser.add_argument('--budzet', type=int, default=20 * 60, help='Budżet czasu w sekundach.')

    def handle(self, *args, **opts):
        stats = warm(opts['zakres'], budget_seconds=opts['budzet'])
        if stats.get('disabled'):
            self.stdout.write('Cache nieaktywny na tej bazie (SQLite); ustaw PRZESZLOSC_CACHE=always, żeby wymusić.')
        self.stdout.write(' '.join(f'{k}={v}' for k, v in stats.items()))
