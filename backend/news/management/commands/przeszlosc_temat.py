"""Podgląd drzewa tematu przeszłość.today na serwerze: manage.py przeszlosc_temat "CPK, lotnisko"."""
from django.core.management.base import BaseCommand

from news.przeszlosc import topic_graph


class Command(BaseCommand):
    help = 'Drzewo powiązań tematu z istniejących danych (bez wywołań AI i sieci).'

    def add_arguments(self, parser):
        parser.add_argument('temat')

    def handle(self, *args, **opts):
        data = topic_graph(opts['temat'])
        names = {'person': 'Osoby', 'organisation': 'KRS', 'record': 'Sejm', 'statement': 'Wpisy', 'diagnosis': 'Diagnozy', 'media': 'Media'}
        self.stdout.write(f"Temat: {data['topic']} · " + ', '.join(f'{names.get(k, k)}: {v}' for k, v in data['counts'].items())
                          + f" · powiązania: {len(data['edges'])}")
        for kind, title in names.items():
            rows = [n for n in data['nodes'] if n['kind'] == kind][:8]
            if rows:
                self.stdout.write(f'\n== {title}')
                for n in rows:
                    self.stdout.write(f"  [{n['links']}] {n.get('date') or '':10} {n['label'][:90]}")
