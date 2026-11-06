"""Zbiera kandydatów doniesień o podmiotach osób z korpusu artykułów (bez sieci); wynik do kolejki przeglądu.

  python manage.py przeszlosc_doniesienia_zbierz                  # sam raport, nic nie zapisuje
  python manage.py przeszlosc_doniesienia_zbierz --apply          # zapis do kolejki „do przeglądu”
  python manage.py przeszlosc_doniesienia_zbierz --osoba 12 --osoba 15   # tylko wybrane osoby
  python manage.py przeszlosc_doniesienia_zbierz --wyczysc-kolejke        # kasuje niepublikowane pozycje zebrane automatycznie
"""
from django.core.management.base import BaseCommand

from news import doniesienia_zbieranie as dz


class Command(BaseCommand):
    help = 'Kandydaci doniesień o podmiotach z korpusu artykułów; pozycje trafiają do kolejki przeglądu.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--na-osobe', type=int, default=5, help='Najwyżej tyle pozycji na osobę (domyślnie 5).')
        parser.add_argument('--razem', type=int, default=2000, help='Najwyżej tyle nowych pozycji w przebiegu.')
        parser.add_argument('--ze-znanymi', action='store_true', help='Także podmioty z potwierdzoną relacją KRS osoby.')
        parser.add_argument('--wyczysc-kolejke', action='store_true', help='Skasuj niepublikowane pozycje zebrane automatycznie (do przeglądu, agent).')
        parser.add_argument('--osoba', type=int, action='append', help='Id osoby (można powtórzyć).')

    def handle(self, *args, **o):
        if o['wyczysc_kolejke']:
            self.stdout.write(f"Skasowano z kolejki (do przeglądu, zebrane automatycznie): {dz.clear_agent_queue()}")
            return
        stats = dz.collect(apply=o['apply'], per_person=o['na_osobe'], total=o['razem'], with_known=o['ze_znanymi'], figure_ids=o['osoba'])
        self.stdout.write(f"{'ZAPISANO' if o['apply'] else 'Raport (bez zapisu)'}: {stats}")
