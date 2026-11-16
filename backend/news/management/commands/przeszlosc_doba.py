"""Samorozwój przeszłość.today: raport doby, kolejka rozwoju i samonaprawa kolejek zbieraczy (news/przeszlosc_samorozwoj.py).

Przykłady:
  python manage.py przeszlosc_doba              # raport doby na żywo (bez zapisu, bez sieci)
  python manage.py przeszlosc_doba --kolejka    # stan każdej pozycji listy rozwoju
  python manage.py przeszlosc_doba --uruchom    # to samo co zadanie 6:35: odłożenie trwale błędnych zadań, zapis raportu i kolejki
"""
import json

from django.core.management.base import BaseCommand

from news import przeszlosc_samorozwoj as s


class Command(BaseCommand):
    help = 'Raport doby przeszłość.today, lista rozwoju i (z --uruchom) samonaprawa kolejek zbieraczy.'

    def add_arguments(self, parser):
        parser.add_argument('--kolejka', action='store_true', help='Pokaż stan każdej pozycji listy rozwoju.')
        parser.add_argument('--uruchom', action='store_true', help='Wykonaj krok dnia (jak zadanie Celery o 6:35).')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        if options['uruchom']:
            self.stdout.write(f'Krok dnia: {s.run()}')
        if options['kolejka']:
            data = s.kolejka()
            if options['json']:
                self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
                return
            for r in data['pozycje']:
                self.stdout.write(f"{r['key']:<12} {r['stan']:<20} na: {r['na_kogo'] or '-'}  ({r['title']})")
            return
        data = s.doba()
        if options['json']:
            self.stdout.write(json.dumps({k: v for k, v in data.items() if k != 'liczniki'}, ensure_ascii=False, indent=2,
                                         default=str))
            return
        for line in s.lines(data, saved=True):
            self.stdout.write(line)
