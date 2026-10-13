from decimal import InvalidOperation
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import requests
from django.core.management.base import BaseCommand, CommandError

from news import niw_dotacje as niw


class Command(BaseCommand):
    help = ('Import listy dotacji NIW-CRSO (umowy z numerem KRS); --dry-run bez zapisu; --plik zamiast pobierania; '
            '--archiwum katalog kopii pliku (domyślnie NIW_ARCHIWUM_DIR albo backend/reports/niw).')

    def add_arguments(self, parser):
        parser.add_argument('--plik', help='Lokalny XLSX z oryginalną datą w nazwie (DD-MM-RRRR).')
        parser.add_argument('--dry-run', action='store_true', help='Parsuj i policz, bez zapisu do bazy.')
        parser.add_argument('--archiwum', help='Katalog archiwum pobranych plików (poza repo).')
        parser.add_argument('--bez-usuwania', action='store_true',
                            help='Nie usuwaj z bazy umów, których nie ma w nowym pliku.')

    def handle(self, *args, **options):
        try:
            if options['plik']:
                path = Path(options['plik'])
                with path.open('rb') as stream:
                    raw = stream.read(niw.MAX_BYTES + 1)
                name, response_url = path.name, ''
            else:
                html, _ = niw.download(niw.PAGE_URL)
                raw, response_url = niw.download(niw.latest_file(html.decode('utf-8-sig', errors='replace')))
                name = response_url
            if len(raw) > niw.MAX_BYTES:
                raise ValueError('Plik przekracza limit 20 MB.')
            records, stats = niw.parse_xlsx(raw, name)
            archived = niw.archive_file(raw, name, options['archiwum'])
        except (OSError, ValueError, KeyError, IndexError, OverflowError, BadZipFile, ParseError,
                InvalidOperation, requests.RequestException) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Stan pliku: {niw.file_date(name)}; umowy z KRS: {len(records)}; '
                          f"pominięte bez KRS: {stats['bez_krs']} (w tym osoby fizyczne wg rejestru: {stats['osoby_fizyczne']}); "
                          f"błędne (kwota lub data): {stats['bledne']}; duplikaty w pliku: {stats['duplikaty']}")
        self.stdout.write(f'Archiwum: {archived}')
        if options['dry_run']:
            self.stdout.write('Dry-run: bez zapisu do bazy.')
            return
        counts = niw.save_records(records, response_url, remove_stale=not options['bez_usuwania'])
        self.stdout.write(f"Utworzone: {counts['created']}; zaktualizowane: {counts['updated']}; "
                          f"bez zmian: {counts['unchanged']}; usunięte (brak w nowym pliku): {counts['removed']}")
