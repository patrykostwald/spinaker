"""Migawka rankingu (cron co 10 min) i przycięcie starych migawek."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from spina3 import ranking


class Command(BaseCommand):
    help = 'spina3: buduje migawkę rankingu ściany.'

    def handle(self, *args, **options):
        snapshot = ranking.build_snapshot()
        self.stdout.write(f'migawka {snapshot.pk}: {snapshot.box_count} boxów, udział z poziomem {snapshot.rated_share:.2f}')
