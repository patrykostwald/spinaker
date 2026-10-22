import json
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from scraper.public_records import SOURCES, collect


class Command(BaseCommand):
    help = 'Jedna ograniczona porcja prywatnych danych; kolejne wywołania wznawiają kolejkę.'

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=tuple(SOURCES), required=True)
        parser.add_argument('--since', type=date.fromisoformat, required=True)
        parser.add_argument('--max-requests', type=int, default=4)

    def handle(self, *args, **options):
        try:
            result = collect(options['source'], since=options['since'], max_requests=options['max_requests'])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False))
        if result['status'] in {'error', 'blocked_access_review', 'disabled', 'needs_review'}:
            raise CommandError('Kolekcja nie została uruchomiona lub wymaga sprawdzenia: ' + result['status'])
