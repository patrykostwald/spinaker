"""Import all reviewed candidate catalogs as inactive configuration, never as publications."""
import csv
import json
import unicodedata
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from news.models import Source
from news.source_catalog import domain_key, public_catalog_url


def normalized_name(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def media_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    if rows and not {'nazwa', 'adres'}.issubset(rows[0]):
        raise CommandError('CSV musi zawierać kolumny nazwa i adres, oddzielone średnikiem.')
    for row in rows:
        notes = '\n'.join(f'{key}: {value.strip()}' for key, value in row.items() if value and key not in ('nazwa', 'adres'))
        yield {'name': row['nazwa'].strip(), 'url': row.get('adres', '').strip(),
               'identity': '', 'source_type': 'portal', 'notes': notes}


def official_rows(path):
    rows = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(rows, list):
        raise CommandError('Oficjalny katalog JSON musi być listą obiektów.')
    for row in rows:
        notes = '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value}'
                          for key, value in row.items() if value and key not in ('name', 'publisher_url', 'source_identity_url'))
        yield {'name': row['name'].strip(), 'url': row.get('publisher_url', '').strip(),
               'identity': row.get('source_identity_url', ''), 'source_type': 'institution', 'notes': notes}


class Command(BaseCommand):
    help = 'Wczytaj pełne katalogi kandydatów do panelu źródeł, bez aktywowania importu i bez usuwania danych.'

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument('--media-csv', default=str(root / 'reports' / 'rozszerzenie-mediow-2026-09-09.csv'))
        parser.add_argument('--official-json', default=str(root / 'reports' / 'kandydaci-importery-oficjalne-2026-09-09.json'))

    def handle(self, *args, **options):
        try:
            rows = list(media_rows(Path(options['media_csv']))) + list(official_rows(Path(options['official_json'])))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f'Nie odczytano katalogów: {exc}')
        prepared = []
        for row in rows:
            if not row['name'] or len(row['name']) > 255:
                raise CommandError('Każdy kandydat musi mieć nazwę do 255 znaków.')
            try:
                row['url'] = public_catalog_url(row['url'], resolve=False)
            except ValidationError as exc:
                # Preserve a bad supplied address as evidence, never turn it into an active endpoint.
                row['notes'] += f"\nAdres do wyjaśnienia: {row['url']}\nWalidacja: {exc.detail}"
                row['url'] = ''
            prepared.append(row)
        created = linked = annotated = 0
        with transaction.atomic():
            existing = list(Source.objects.select_for_update().order_by('pk'))
            by_url = {source.url: source for source in existing if source.url}
            by_seed = {source.catalog_seed_key: source for source in existing if source.catalog_seed_key}
            by_name = {normalized_name(source.name): source for source in existing}
            by_domain = {}
            for source in existing:
                if source.url:
                    by_domain.setdefault(domain_key(source.url), source)
            for row in prepared:
                key = normalized_name(row['name'])
                source = (by_seed.get(sha256(row['identity'].encode('utf-8')).hexdigest())
                          or by_seed.get(sha256(row['url'].encode('utf-8')).hexdigest())
                          or by_url.get(row['identity']) or by_url.get(row['url']) or by_name.get(key)
                          or (by_domain.get(domain_key(row['url'])) if row['url'] and row['source_type'] != 'institution' else None))
                block = f"[Kandydatura: {row['name']}]\nAdres zgłoszony: {row['url'] or 'nie ustalono'}\n{row['notes']}".strip()
                if source is None:
                    source = Source.objects.create(name=row['name'], url=row['url'] or None,
                        source_type=row['source_type'], rss_url='', is_active=False, scrape_enabled=False,
                        catalog_stage='candidate', catalog_notes=block, scrape_frequency_minutes=60)
                    existing.append(source)
                    created += 1
                    if source.url:
                        by_url[source.url] = source
                        by_seed[source.catalog_seed_key] = source
                        by_domain.setdefault(domain_key(source.url), source)
                else:
                    linked += 1
                    if block not in source.catalog_notes:
                        source.catalog_notes = (source.catalog_notes.rstrip() + '\n\n' + block).strip()
                        source.save(update_fields=['catalog_notes'])
                        annotated += 1
                by_name[key] = source
        self.stdout.write(self.style.SUCCESS(
            f'Przeczytano {len(prepared)} pozycji; nowych nieaktywnych kandydatów: {created}; '
            f'powiązano z katalogiem: {linked}; uzupełniono notatki: {annotated}. Nie uruchomiono pobierania.'))
