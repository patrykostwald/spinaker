from django.core.management.base import BaseCommand, CommandError

from news import council_votes


class Command(BaseCommand):
    help = ('Usuń stare pliki miesięczne głosów Rady (glosy-RRRR-MM.jsonl) i decyzji człowieka (decyzje-RRRR-MM.jsonl). '
            'Bez AI i bez harmonogramu: uruchamia właściciel po opinii Prawnika.')

    def add_arguments(self, parser):
        parser.add_argument('--keep-days', type=int, default=None,
                            help='Ile dni trzymać głosy (domyślnie COUNCIL_VOTES_RETENTION_DAYS, a bez niej 730).')
        parser.add_argument('--keep-decisions-days', type=int, default=None,
                            help='Ile dni trzymać decyzje człowieka (domyślnie COUNCIL_DECISIONS_RETENTION_DAYS, a bez niej 1095).')
        parser.add_argument('--dry-run', action='store_true', help='Tylko pokaż, co zostałoby usunięte.')

    def handle(self, *args, **options):
        for name in ('keep_days', 'keep_decisions_days'):
            if options[name] is not None and options[name] < 0:
                raise CommandError('Liczba dni nie może być ujemna.')
        rows = council_votes.cleanup(options['keep_days'], options['keep_decisions_days'], options['dry_run'])
        for row in rows:
            self.stdout.write(f"{'do usunięcia' if options['dry_run'] else 'usunięto'}: {row['file']} ({row['kind']})")
        verb = 'Do usunięcia' if options['dry_run'] else 'Usunięto'
        self.stdout.write(f'{verb} plików: {len(rows)}. Katalog: {council_votes.log_dir()}.')
