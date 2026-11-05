import json
from django.core.management.base import BaseCommand, CommandError
from news.account_warden import run


class Command(BaseCommand):
    help = 'Strażnik kont polityków: odkrywanie i rotacyjna kontrola. --dry-run bez zapisów i wywołań zewnętrznych.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--only-missing', action='store_true')
        parser.add_argument('--limit', type=int, default=60)

    def handle(self, *args, **options):
        if options['limit'] < 1:
            raise CommandError('--limit musi być dodatni.')
        result = run(dry_run=options['dry_run'], only_missing=options['only_missing'], limit=options['limit'])
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if result['status'] == 'error':
            raise CommandError('Strażnik zakończył przebieg z błędem; szczegóły powyżej i w panelu.')
