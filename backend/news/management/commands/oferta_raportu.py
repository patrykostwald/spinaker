"""python manage.py oferta_raportu --dla "Nazwa organizacji" --plik oferta.pdf

Prywatna oferta PDF raportów spin.clinic. Ten sam cennik dla każdego odbiorcy; ceny tylko w tym pliku, nigdy na stronie."""
from pathlib import Path

from django.core.management.base import BaseCommand

from news.oferta_raportow import render


class Command(BaseCommand):
    help = 'Prywatna oferta PDF raportów (ten sam cennik dla wszystkich). Bez wysyłki.'

    def add_arguments(self, parser):
        parser.add_argument('--dla', default='')
        parser.add_argument('--plik', default='oferta-spin-clinic.pdf')

    def handle(self, *args, **options):
        path = Path(options['plik'])
        path.write_bytes(render(options['dla']))
        self.stdout.write(f'Zapisano {path}')
