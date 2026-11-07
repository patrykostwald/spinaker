"""Darmowy raport powiązań z rejestrów urzędowych (bez AI, bez sieci, bez zapisu).

  python manage.py przeszlosc_powiazania_raport
"""
from django.core.management.base import BaseCommand

from news import powiazania_rejestry as pr


class Command(BaseCommand):
    help = 'Tylko odczyt: osoby publiczne z relacją KRS do podmiotu, którego numer (NIP/KRS) jest we wpisie rejestru lobbingu MSWiA.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **o):
        r = pr.lobbying_report(o['limit'])
        self.stdout.write(f"Wpisów rejestru lobbingu w bazie: {r['entries']}; z numerem NIP/KRS: {r['with_ids']}; "
                          f"dopasowanych podmiotów z naszego rejestru (po numerze): {r['matched_orgs']}; osób z relacją KRS: {len(r['rows'])}")
        for row in r['rows']:
            self.stdout.write(f"- {row['figure']} (id {row['figure_id']}) | {row['organisation']} KRS {row['krs']} | "
                              f"{row['role']} {row['organ']} [{row['status']}, {row['verification']}] | wpis lobbingu nr {row['lobby_entry']} | {row['source']}")
        self.stdout.write('Nic nie zapisano. Źródła: rejestr lobbingu MSWiA, KRS.')
