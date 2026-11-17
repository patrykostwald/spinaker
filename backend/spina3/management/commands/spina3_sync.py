"""Zadanie okresowe spina3 (cron co 15 min): import wpisów i diagnoz, dokumenty, usunięte wpisy, cisza wyborcza,
wygaśnięcie 7 dni, wagi i klastry. Bez wywołań sieciowych (importer czyta tabele news)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from spina3 import importer


class Command(BaseCommand):
    help = 'spina3: import boxów Dr. Spina i porządki okresowe (bez sieci).'

    def handle(self, *args, **options):
        result = importer.run_all()
        for key, value in result.items():
            self.stdout.write(f'{key}: {value}')
