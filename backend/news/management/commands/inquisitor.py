import json
from django.core.management.base import BaseCommand
from news.inquisitor import run


class Command(BaseCommand):
    help = 'Oszczędna niezależna kontrola diagnoz; --limit nie podnosi limitu dziennego.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int)

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(run(dry_run=options['dry_run'], limit=options['limit']), ensure_ascii=False))
