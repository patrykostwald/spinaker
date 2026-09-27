"""Kariera sejmowa osób publicznych z oficjalnego API Sejmu: kadencje, daty mandatu i klub (bez danych osobowych)."""
from django.core.management.base import BaseCommand

from news.sejm_career import run


class Command(BaseCommand):
    help = 'Uzupełnia kadencje Sejmu (daty i klub) na profilach osób publicznych.'

    def handle(self, *args, **options):
        self.stdout.write(str(run()))
