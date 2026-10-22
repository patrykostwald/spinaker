import json
from django.core.management.base import BaseCommand, CommandError
from news.warden_second_key import run, recheck


class Command(BaseCommand):
    help = 'Drugi klucz Strażnika. --recheck: podgląd napraw z ostatnich 14 dni; --apply zapisuje.'

    def add_arguments(self, parser):
        parser.add_argument('--recheck', action='store_true')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if options['apply'] and not options['recheck']:
            raise CommandError('--apply wymaga --recheck.')
        result = recheck(apply=options['apply']) if options['recheck'] else run()
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
