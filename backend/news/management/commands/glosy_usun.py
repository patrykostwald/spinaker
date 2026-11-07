from django.core.management.base import BaseCommand, CommandError

from news import council_votes


class Command(BaseCommand):
    help = ('Usuń z dziennika głosów Rady (glosy-*.jsonl i decyzje-*.jsonl) wszystkie linie o podanym wpisie albo diagnozie '
            '(art. 17 i 21 RODO). Pliki są przepisywane pod blokadą dziennika; linie nieparsowalne zostają. Bez AI.')

    def add_arguments(self, parser):
        parser.add_argument('--post-id', type=int, action='append', default=[], help='Numer wpisu (można podać wiele razy).')
        parser.add_argument('--diagnosis-id', type=int, action='append', default=[], help='Numer diagnozy (można podać wiele razy).')
        parser.add_argument('--dry-run', action='store_true', help='Tylko policz, bez zmian w plikach.')

    def handle(self, *args, **options):
        if not options['post_id'] and not options['diagnosis_id']:
            raise CommandError('Podaj co najmniej jedno --post-id albo --diagnosis-id.')
        rows = council_votes.erase(options['post_id'], options['diagnosis_id'], options['dry_run'])
        verb = 'do usunięcia' if options['dry_run'] else 'usunięto'
        for row in rows:
            self.stdout.write(f"{row['file']}: {verb} linii: {row['removed']}, zostaje: {row['kept']}, nieparsowalnych (bez zmian): {row['unparsable']}")
        total = sum(row['removed'] for row in rows)
        self.stdout.write(f"{'Do usunięcia' if options['dry_run'] else 'Usunięto'} linii: {total} w plikach: {len(rows)}. "
                          f'Katalog: {council_votes.log_dir()}.')
