"""Import listy kont w ciszy wyborczej (kandydaci i komitety) z CSV, po przeglądzie radcy (decyzja właściciela 14.10).

Kolumny (nagłówek wymagany): konto, rodzaj, od, do, zrodlo. `rodzaj`: kandydat | komitet. Daty ISO 8601 (np.
2027-10-15T00:00:00+02:00; bez strefy = strefa serwera). Wiersz o tym samym koncie i oknie nie dubluje się.
Lista w repozytorium jest pusta: plik podaje operator. `--dry-run` sprawdza bez zapisu, `--replace` czyści listę przed importem.
"""
from __future__ import annotations

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from spina3.legal import normalize_handle
from spina3.models import SilencedAccount

KINDS = {'kandydat': 'candidate', 'komitet': 'committee', 'candidate': 'candidate', 'committee': 'committee'}
COLUMNS = ('konto', 'rodzaj', 'od', 'do', 'zrodlo')


def _date(value: str, line: int, column: str):
    parsed = parse_datetime((value or '').strip())
    if parsed is None:
        raise CommandError(f'Wiersz {line}: kolumna "{column}" nie jest datą ISO 8601: {value!r}')
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


def parse_rows(handle) -> list[dict]:
    reader = csv.DictReader(handle)
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise CommandError('Brak kolumn: ' + ', '.join(missing) + ' (wymagane: ' + ', '.join(COLUMNS) + ').')
    rows = []
    for line, row in enumerate(reader, start=2):
        account = normalize_handle(row['konto'])
        kind = KINDS.get((row['rodzaj'] or '').strip().lower())
        if not account:
            raise CommandError(f'Wiersz {line}: puste konto.')
        if kind is None:
            raise CommandError(f'Wiersz {line}: rodzaj musi być "kandydat" albo "komitet".')
        starts, ends = _date(row['od'], line, 'od'), _date(row['do'], line, 'do')
        if ends <= starts:
            raise CommandError(f'Wiersz {line}: "do" musi być późniejsze niż "od".')
        source = (row['zrodlo'] or '').strip()
        if not source:
            raise CommandError(f'Wiersz {line}: podaj źródło listy (zrodlo).')
        rows.append({'handle': account, 'kind': kind, 'starts_at': starts, 'ends_at': ends, 'source': source[:300]})
    return rows


class Command(BaseCommand):
    help = 'spina3: import CSV kont w ciszy wyborczej (konto, rodzaj, od, do, zrodlo).'

    def add_arguments(self, parser):
        parser.add_argument('path', help='Ścieżka do pliku CSV (UTF-8).')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--replace', action='store_true', help='Usuń dotychczasową listę przed importem.')

    def handle(self, *args, path, dry_run=False, replace=False, **options):
        with open(path, encoding='utf-8-sig', newline='') as handle:
            rows = parse_rows(handle)
        if dry_run:
            self.stdout.write(f'poprawnych wierszy: {len(rows)} (bez zapisu)')
            return
        created = 0
        with transaction.atomic():
            if replace:
                for row in SilencedAccount.objects.all():
                    row.delete()
            for row in rows:
                _, made = SilencedAccount.objects.get_or_create(
                    handle=row['handle'], starts_at=row['starts_at'], ends_at=row['ends_at'],
                    defaults={'kind': row['kind'], 'source': row['source']})
                created += int(made)
        self.stdout.write(f'zaimportowano: {created}, pominięto (już były): {len(rows) - created}')
