"""Pokrycie KRS przeszłość.today: raport, zasilenie kolejki i uzupełnianie z oficjalnych rejestrów.

Przykłady:
  python manage.py przeszlosc_krs_pokrycie                      # sam raport (bez sieci)
  python manage.py przeszlosc_krs_pokrycie --json               # raport jako JSON
  python manage.py przeszlosc_krs_pokrycie --zasil              # dopisz braki do kolejki (bez sieci)
  python manage.py przeszlosc_krs_pokrycie --uzupelnij --limit 50   # partia: Biała lista MF -> KRS, odpisy z api-krs
"""
import json

from django.core.management.base import BaseCommand

from news import krs_pokrycie


class Command(BaseCommand):
    help = 'Raport pokrycia KRS osób i podmiotów; --zasil i --uzupelnij prowadzą kolejkę uzupełnień.'

    def add_arguments(self, parser):
        parser.add_argument('--zasil', action='store_true', help='Dopisz do kolejki podmioty bez odpisu i NIP-y z rekordów pieniędzy.')
        parser.add_argument('--uzupelnij', action='store_true', help='Jedna partia kolejki (sieć: Biała lista MF i api-krs).')
        parser.add_argument('--limit', type=int, help='Najwyżej tyle odpisów KRS w partii (domyślnie KRS_POKRYCIE_LIMIT albo 200).')
        parser.add_argument('--zapytan-bialej-listy', type=int, help='Najwyżej tyle zapytań do Białej listy (po 30 NIP).')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        if options['zasil']:
            self.stdout.write(f"Zasilono kolejkę: {krs_pokrycie.zasil() or 'nic nowego'}")
        if options['uzupelnij']:
            self.stdout.write(f"Uzupełniono: {krs_pokrycie.uzupelnij(options['limit'], options['zapytan_bialej_listy'])}")
        data = krs_pokrycie.raport()
        self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) if options['json'] else krs_pokrycie.raport_tekst(data))
