"""Raport ścieżek: najczęstsze przejścia, wyjścia, klikane elementy i „wściekłe kliknięcia” (coś nie działa)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from news.feedback import clean_path
from news.feedback_models import JourneyStep


class Command(BaseCommand):
    help = 'Zbiorcze ścieżki użytkowników z ostatnich dni (bez danych o osobach).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)
        parser.add_argument('--top', type=int, default=20)

    def handle(self, *args, **opts):
        rows = JourneyStep.objects.filter(hour__gte=timezone.now() - timedelta(days=opts['days']))
        for title, query, fields in [
            ('Przejścia między stronami', rows.filter(action='nav'), ('device', 'source', 'target')),
            ('Skąd ludzie wychodzą', rows.filter(action='exit'), ('device', 'source')),
            ('Klikane elementy', rows.filter(action__startswith='click'), ('device', 'source', 'action')),
            ('Wściekłe kliknięcia (3 w sekundę: pewnie nie działa)', rows.filter(action__startswith='rage'), ('device', 'source', 'action')),
        ]:
            self.stdout.write(f'\n== {title}')
            # starsze wpisy mogły mieć slug osoby lub spółki w adresie: maskujemy je przy odczycie i sumujemy ponownie
            merged = {}
            for row in query.values(*fields).annotate(n=Sum('count')):
                key = tuple(clean_path(row[f]) if f in ('source', 'target') else str(row[f]) for f in fields)
                merged[key] = merged.get(key, 0) + row['n']
            for key, n in sorted(merged.items(), key=lambda item: -item[1])[:opts['top']]:
                self.stdout.write(f'{n:>6}  ' + '  '.join(key))
