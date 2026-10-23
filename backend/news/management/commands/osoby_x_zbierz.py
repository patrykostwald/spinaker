"""Uzupełnia news/data/osoby_x.csv kontami X z Wikidata (P2002, CC0). Bez skrobania X.com i bez API X.

  python manage.py osoby_x_zbierz             # osoby z bazy (PublicFigure); gdy baza pusta — z danych w repo
  python manage.py osoby_x_zbierz --repo      # osoby z danych w repo (sejm_career.json i lista z 24.09)
  python manage.py osoby_x_zbierz --podglad   # pokaż wynik, nie zapisuj pliku
"""
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

from news import osoby_x


def people(use_repo):
    if not use_repo:
        found = osoby_x.people_from_db()
        if found:
            return found, 'baza'
    return osoby_x.people_from_repo(), 'repo'


class Command(BaseCommand):
    help = 'Zbiera konta X osób publicznych z Wikidata do news/data/osoby_x.csv (wiersze z oficjalnych stron zostają).'

    def add_arguments(self, parser):
        parser.add_argument('--repo', action='store_true', help='Osoby z danych w repo zamiast z bazy.')
        parser.add_argument('--plik', default=str(osoby_x.CSV_PATH))
        parser.add_argument('--podglad', action='store_true', help='Bez zapisu pliku.')

    def handle(self, *args, **options):
        found, origin = people(options['repo'])
        try:
            rows, ambiguous = osoby_x.collect(found)
        except (requests.RequestException, ValueError, KeyError) as error:
            raise CommandError(f'Wikidata nie odpowiedziała ({type(error).__name__}); plik bez zmian.')
        path = Path(options['plik'])
        merged = osoby_x.merge(osoby_x.read_rows(path), rows)
        current = sum(1 for row in rows if row['stan_konta'] == osoby_x.CURRENT)
        for person, qids in ambiguous:
            self.stdout.write(f'[DP] {person.name} ({person.osoba_id}): kilka osób w Wikidata ({", ".join(qids)}) — pominięto')
        if options['podglad']:
            for row in rows:
                self.stdout.write(f"{row['imie_nazwisko']} · @{row['konto']} · {row['stan_konta']} · {row['pewnosc']} · {row['zrodlo']}")
            self.stdout.write(self.style.WARNING(f'PODGLĄD ({origin}): osób {len(found)}; kont z Wikidata {len(rows)} '
                                                 f'(aktualne {current}); niejednoznaczne {len(ambiguous)}. Plik bez zmian.'))
            return
        written = osoby_x.write_rows(merged, path)
        self.stdout.write(self.style.SUCCESS(f'Zapisano {path} ({origin}): wierszy {len(written)}; z Wikidata {len(rows)} '
                                             f'(aktualne {current}); niejednoznaczne {len(ambiguous)}.'))
