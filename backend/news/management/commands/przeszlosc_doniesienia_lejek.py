"""Lejek doniesień medialnych (tani: korpus + GDELT -> lektura artykułów -> Haiku na fragmentach -> weryfikacja cytatu -> KRS -> kolejka).

  python manage.py przeszlosc_doniesienia_lejek --nazwisko "Marcin Romanowski"            # próba bez zapisu
  python manage.py przeszlosc_doniesienia_lejek --wszyscy --max-osob 50 --limit-usd 1 --apply
Pozycje trafiają wyłącznie do kolejki przeglądu. Bez --apply tylko raport (zapytania do modelu i tak się odbywają, ale kosztują grosze).
"""
from django.core.management.base import BaseCommand

from news import doniesienia_lejek as lejek


class Command(BaseCommand):
    help = 'Tani lejek doniesień medialnych o podmiotach osób publicznych.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--osoba', type=int, action='append')
        parser.add_argument('--nazwisko', action='append')
        parser.add_argument('--wszyscy', action='store_true')
        parser.add_argument('--max-osob', type=int)
        parser.add_argument('--ponow', action='store_true')
        parser.add_argument('--limit-usd', type=float, default=2.0)
        parser.add_argument('--szukaj-krs', action='store_true', help='Druga runda z wyszukiwarką (drogi Sonnet) dla podmiotów bez numeru KRS.')
        parser.add_argument('--bez-gdelt', action='store_true')
        parser.add_argument('--diagnoza', action='store_true', help='Wypisz, co znaleziono i pobrano przy każdej osobie (korpus, GDELT, długość tekstu).')

    def handle(self, *args, **o):
        result = lejek.run(names=o['nazwisko'], ids=o['osoba'], apply=o['apply'], budget_usd=o['limit_usd'], write=self.stdout.write,
                           skip_days=0 if o['ponow'] else 60, everyone=o['wszyscy'], limit=o['max_osob'], allow_search=o['szukaj_krs'],
                           use_gdelt=not o['bez_gdelt'], verbose=o['diagnoza'])
        self.stdout.write(f"{'ZAPISANO' if o['apply'] else 'Raport (bez zapisu)'}: {result}")
