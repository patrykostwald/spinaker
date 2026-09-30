"""Rekruter Konsylium ręcznie.

  python manage.py council_recruiter --dry-run   # zwiad i sito: kto byłby kandydatem (bez zapytań do modeli)
  python manage.py council_recruiter             # pełny przebieg: zdrowie składu + egzamin i posiedzenie
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Kontrola zdrowia Konsylium i rekrutacja jednego kandydata (albo podgląd z --dry-run).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, dry_run=False, **options):
        from news.council_recruiter import run
        self.stdout.write(json.dumps(run(dry_run=dry_run), ensure_ascii=False, indent=2, default=str))
