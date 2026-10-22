"""Metryki tygodniowe z agregatów (bez śledzenia) i alarmy do raportu."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from spina3 import metrics


class Command(BaseCommand):
    help = 'spina3: metryki 4.1-4.10 i alarmy (JSON).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(metrics.compute(days=options['days']), ensure_ascii=False, indent=2, default=str))
