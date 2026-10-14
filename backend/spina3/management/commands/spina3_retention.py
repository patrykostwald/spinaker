"""Retencja danych spina3 (cron raz na dobę): konta do usunięcia po 30 dniach, zgłoszenia i decyzje po 12 miesiącach,
dziennik zdarzeń po SPINA3_EVENT_RETENTION_DAYS (domyślnie 90)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from spina3 import retention


class Command(BaseCommand):
    help = 'spina3: retencja danych (konta do usunięcia, zgłoszenia i decyzje, dziennik zdarzeń).'

    def handle(self, *args, **options):
        for key, value in retention.run().items():
            self.stdout.write(f'{key}: {value}')
