"""Powtórka diagnoz wystawionych bez kworum Konsylium (news/council_rerun.py).

  python manage.py konsylium_powtorz --od 2026-10-04 --dry-run   # lista diagnoz do powtórki (bez zapytań do modeli)
  python manage.py konsylium_powtorz --od 2026-10-04             # powtórka w cichych godzinach 2:00-7:00
  python manage.py konsylium_powtorz --od 2026-10-04 --teraz     # od razu (nadal w ramach limitów i kworum)

Idempotentnie: każda diagnoza najwyżej raz; stary wynik zostaje w historii (usage['history']).
"""
import json
from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.council_rerun import WARSAW, run


class Command(BaseCommand):
    help = 'Powtarza diagnozy wystawione bez kworum Konsylium (stary wynik zostaje w historii).'

    def add_arguments(self, parser):
        parser.add_argument('--od', required=True, help='Diagnozy wystawione od dnia (RRRR-MM-DD, czas Warszawy).')
        parser.add_argument('--limit', type=int, default=8)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--teraz', action='store_true', help='Bez czekania na ciche godziny 2:00-7:00.')

    def handle(self, *args, od, limit, dry_run, teraz, **options):
        try:
            since = datetime.combine(datetime.strptime(od, '%Y-%m-%d').date(), time.min, tzinfo=WARSAW)
        except ValueError as error:
            raise CommandError('Data w formacie RRRR-MM-DD.') from error
        result = run(since, limit=max(1, limit), dry_run=dry_run, anytime=teraz, now=timezone.now())
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
