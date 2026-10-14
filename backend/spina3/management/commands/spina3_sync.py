"""Zadanie okresowe spina3 (cron co 15 min): import wpisów i diagnoz, dokumenty, usunięte wpisy, cisza wyborcza,
wygaśnięcie 7 dni, wagi i klastry (bez sieci, importer czyta tabele news), a na końcu kontrola wpisów u źródła przez
publiczny oEmbed X (najwyżej 60 wpisów; flaga x_source_check_enabled, opcja --bez-x)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from spina3 import importer, x_source
from spina3.config import flags


class Command(BaseCommand):
    help = 'spina3: import boxów Dr. Spina, porządki okresowe i kontrola wpisów X u źródła.'

    def add_arguments(self, parser):
        parser.add_argument('--bez-x', action='store_true', help='Pomiń kontrolę wpisów przez oEmbed X.')

    def handle(self, *args, **options):
        result = importer.run_all()
        if flags().x_source_check_enabled and not options.get('bez_x'):
            result.update(x_source.check_posts())
        for key, value in result.items():
            self.stdout.write(f'{key}: {value}')
