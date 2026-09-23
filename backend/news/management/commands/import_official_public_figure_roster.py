"""Import a manually reviewed roster published by a public institution."""
import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.political_models import PUBLIC_FIGURE_ROLE_CATEGORIES, PublicFigure


REQUIRED_HEADERS = {
    'source_key', 'canonical_name', 'role_category', 'role_title', 'organisation',
    'official_profile_url', 'evidence_url',
}
FORBIDDEN_HEADERS = {'pesel', 'date_of_birth', 'birth_date', 'data_urodzenia', 'address'}
SOURCE_KEY_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,100}$')
ROLE_CATEGORIES = {key for key, _ in PUBLIC_FIGURE_ROLE_CATEGORIES}


def value(row, key):
    return (row.get(key) or '').strip()


def is_https_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and bool(parsed.netloc)


class Command(BaseCommand):
    help = ('Wczytuje ręcznie sprawdzony roster z oficjalnych stron instytucji. '
            'Wymaga bezpośrednich URL-i dowodowych, nie dopasowuje nazwisk i nie dotyka X ani KRS.')

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--scope', required=True,
            help='Stały zakres, np. regional-marshals albo city-executives.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        scope = options['scope'].strip()
        if not SOURCE_KEY_RE.fullmatch(scope):
            raise CommandError('scope może mieć małe litery, cyfry i pojedyncze myślniki.')
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError(f'Nie znaleziono pliku: {path}')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            forbidden = FORBIDDEN_HEADERS & headers
            if forbidden:
                raise CommandError('Plik zawiera niedozwolone dane: ' + ', '.join(sorted(forbidden)))
            missing = REQUIRED_HEADERS - headers
            if missing:
                raise CommandError('Brakuje kolumn: ' + ', '.join(sorted(missing)))
            rows = list(reader)
        if not rows:
            raise CommandError('Pusty roster nie może oznaczać wpisów jako byłe; import przerwany dla bezpieczeństwa.')

        prepared, errors, source_keys = [], [], set()
        for number, row in enumerate(rows, start=2):
            missing = [key for key in REQUIRED_HEADERS if not value(row, key)]
            source_key = value(row, 'source_key')
            if missing:
                errors.append(f'Wiersz {number}: brak wartości: {", ".join(sorted(missing))}')
                continue
            if not SOURCE_KEY_RE.fullmatch(source_key):
                errors.append(f'Wiersz {number}: nieprawidłowy source_key')
                continue
            if source_key in source_keys:
                errors.append(f'Wiersz {number}: powtórzony source_key')
                continue
            source_keys.add(source_key)
            if value(row, 'role_category') not in ROLE_CATEGORIES:
                errors.append(f'Wiersz {number}: nieznana role_category')
                continue
            if not is_https_url(value(row, 'official_profile_url')) or not is_https_url(value(row, 'evidence_url')):
                errors.append(f'Wiersz {number}: official_profile_url i evidence_url muszą być bezpośrednimi adresami https')
                continue
            prepared.append(row)
        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError(f'Nie zapisano rosteru; błędnych wierszy: {len(errors)}.')

        prefix = f'official-roster:{scope}:'
        keys = {f'{prefix}{value(row, "source_key")}' for row in prepared}
        existing = set(PublicFigure.objects.filter(import_key__in=keys).values_list('import_key', flat=True))
        created = len(keys - existing)
        updated = len(keys & existing)
        former = PublicFigure.objects.filter(import_key__startswith=prefix, archived=False, status='current').exclude(import_key__in=keys).count()
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd {scope}: {len(prepared)} wpisów; nowe {created}; do aktualizacji {updated}; do oznaczenia jako byłe {former}. Bez zapisu.'
            ))
            return

        now = timezone.now()
        with transaction.atomic():
            for row in prepared:
                PublicFigure.objects.update_or_create(
                    import_key=f'{prefix}{value(row, "source_key")}',
                    defaults={
                        'canonical_name': value(row, 'canonical_name'),
                        'role_category': value(row, 'role_category'),
                        'role_title': value(row, 'role_title'),
                        'organisation': value(row, 'organisation'),
                        'status': 'current',
                        'official_profile_url': value(row, 'official_profile_url'),
                        'evidence_url': value(row, 'evidence_url'),
                        'evidence_note': value(row, 'evidence_note'),
                        'source_checked_at': now,
                        'parliamentary_roster_entry': None,
                        'archived': False,
                    },
                )
            PublicFigure.objects.filter(import_key__startswith=prefix, archived=False, status='current').exclude(import_key__in=keys).update(
                status='former', source_checked_at=now)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(prepared)} wpisów z rosteru {scope}; nowe {created}; zaktualizowane {updated}; oznaczone jako byłe {former}. Nie utworzono kont X ani kandydatur.'
        ))
