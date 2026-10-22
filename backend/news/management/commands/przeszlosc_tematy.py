"""Automatyczny wybór tematów przeszłość.today teraz (zwykle robi to zadanie o 5:10)."""
from django.core.management.base import BaseCommand

from news.przeszlosc import pick_topics


class Command(BaseCommand):
    help = 'Wybierz najbogatsze tematy z danych (druki Sejmu, skróty z wpisów).'

    def handle(self, *args, **opts):
        for row in pick_topics():
            self.stdout.write(f"{row['score']:>4}  {row['topic']}  {row['counts']}")
