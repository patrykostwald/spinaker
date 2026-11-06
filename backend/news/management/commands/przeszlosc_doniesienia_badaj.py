"""Badanie doniesień medialnych o podmiotach osób publicznych przez Claude API z wyszukiwarką (kolejka przeglądu, limit kosztu).

  python manage.py przeszlosc_doniesienia_badaj --szacuj                  # kogo obejmie i ile to najwyżej kosztuje (bez zapytań)
  python manage.py przeszlosc_doniesienia_badaj --osoba 12 --limit-usd 1  # próba na jednej osobie, BEZ zapisu
  python manage.py przeszlosc_doniesienia_badaj --apply --limit-usd 5     # domyślna lista znanych osób, zapis do kolejki
Wymaga ANTHROPIC_API_KEY (ten sam co przy Klinice). Wszystko trafia jako „do przeglądu”; płatne wywołania tylko bez --szacuj.
"""
from django.core.management.base import BaseCommand

from news import doniesienia_badacz as db


class Command(BaseCommand):
    help = 'Badanie doniesień medialnych (Claude API + wyszukiwarka); wynik do kolejki przeglądu.'

    def add_arguments(self, parser):
        parser.add_argument('--szacuj', action='store_true', help='Tylko lista osób i szacunek kosztu, bez płatnych zapytań.')
        parser.add_argument('--apply', action='store_true', help='Zapisz pozycje do kolejki (bez tego tylko raport).')
        parser.add_argument('--osoba', type=int, action='append', help='Id osoby (można powtórzyć); bez tego lista znanych osób.')
        parser.add_argument('--nazwisko', action='append', help='Imię i nazwisko jak w rejestrze (można powtórzyć), np. --nazwisko "Dariusz Matecki".')
        parser.add_argument('--ponow', action='store_true', help='Zbadaj też osoby zbadane w ostatnich 60 dniach (domyślnie pomijane).')
        parser.add_argument('--limit-usd', type=float, default=5.0, help='Twardy limit kosztu przebiegu w USD (domyślnie 5).')

    def handle(self, *args, **o):
        skip = 0 if o['ponow'] else 60
        figures = db.pick_figures(names=o['nazwisko'], ids=o['osoba'], skip_days=skip)
        if o['szacuj']:
            self.stdout.write(f'Osób do zbadania: {len(figures)} (z {len(o['nazwisko'] or o['osoba'] or db.DEFAULT_NAMES)} na liście)')
            self.stdout.write('; '.join(f'{f.pk}:{f.canonical_name}' for f in figures))
            self.stdout.write(f'Szacunek kosztu najwyżej ok. {len(figures) * db.ESTIMATE_PER_PERSON_USD:.2f} USD (limit przebiegu {o["limit_usd"]:.2f} USD). Nic nie wysłano.')
            return
        result = db.run(names=o['nazwisko'], ids=o['osoba'], apply=o['apply'], budget_usd=o['limit_usd'], write=self.stdout.write, skip_days=skip)
        self.stdout.write(f"{'ZAPISANO' if o['apply'] else 'Raport (bez zapisu)'}: {result}")
