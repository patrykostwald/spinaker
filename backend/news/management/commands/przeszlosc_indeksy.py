"""Indeksy przyspieszające API przeszłość.today (Śledczy R1, P1-9) bez migracji: manage.py przeszlosc_indeksy [--sprawdz].

Dlaczego poza migracjami: indeksy trigramowe (pg_trgm) istnieją tylko w Postgresie, budują się minutami na 525 tys.
artykułów i muszą powstać `CONCURRENTLY` (bez blokowania zapisów zbieraczy), czego migracja w transakcji nie potrafi.
Komenda jest idempotentna (IF NOT EXISTS) i można ją powtarzać. Django nie zna tych indeksów i nie musi: zapytania
`icontains` (UPPER(...) LIKE) i `regex` korzystają z nich automatycznie.
"""
from django.core.management.base import BaseCommand
from django.db import connection

# (nazwa, tabela, wyrażenie) - indeksy B-drzewa działają w SQLite i Postgresie.
BTREE = [
    ('przeszlosc_ballot_mp_voting_idx', 'news_ballot', '(mp_id, voting_id)'),           # _ballots(): głosy posła po id
    ('przeszlosc_recordperson_mp_term_idx', 'news_publicrecordperson', '(mp_id, term)'),  # _records(): dokumenty posła po id
]
# (nazwa, tabela, kolumna) - GIN gin_trgm_ops na UPPER(kolumna): dokładnie tak Django tłumaczy icontains w Postgresie.
TRIGRAM = [
    ('przeszlosc_trgm_article_title', 'news_article', 'title'),
    ('przeszlosc_trgm_article_description', 'news_article', 'description'),
    ('przeszlosc_trgm_publicrecord_title', 'news_publicrecord', 'title'),
    ('przeszlosc_trgm_publicrecord_text', 'news_publicrecord', 'text'),
    ('przeszlosc_trgm_politicalpost_text', 'news_politicalpost', 'text'),
    ('przeszlosc_trgm_voting_motion', 'news_parliamentaryvoting', 'motion'),
    ('przeszlosc_trgm_organisation_name', 'news_registeredorganisation', 'name'),
    ('przeszlosc_trgm_figure_name', 'news_publicfigure', 'canonical_name'),
]


def statements(vendor):
    """SQL do wykonania dla danej bazy; osobna funkcja, żeby test sprawdził treść bez Postgresa."""
    concurrently = 'CONCURRENTLY ' if vendor == 'postgresql' else ''
    out = [f'CREATE INDEX {concurrently}IF NOT EXISTS {name} ON {table} {expr}' for name, table, expr in BTREE]
    if vendor == 'postgresql':
        out.append('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        out += [f'CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} USING gin (upper({column}) gin_trgm_ops)'
                for name, table, column in TRIGRAM]
    return out


def existing(vendor, cursor):
    if vendor == 'postgresql':
        cursor.execute("SELECT indexname FROM pg_indexes WHERE indexname LIKE 'przeszlosc_%'")
    else:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'przeszlosc_%'")
    return sorted(row[0] for row in cursor.fetchall())


class Command(BaseCommand):
    help = 'Załóż indeksy (B-drzewo mp_id; w Postgresie też trigramowe pg_trgm) dla /temat/ i /osoba/. Bezpieczne do powtarzania.'

    def add_arguments(self, parser):
        parser.add_argument('--sprawdz', action='store_true', help='Tylko pokaż, które indeksy już są.')

    def handle(self, *args, **opts):
        vendor = connection.vendor
        with connection.cursor() as cursor:
            if opts['sprawdz']:
                for name in existing(vendor, cursor):
                    self.stdout.write(name)
                return
            if vendor == 'postgresql' and connection.in_atomic_block:
                raise SystemExit('CREATE INDEX CONCURRENTLY nie działa w transakcji - uruchom komendę osobno.')
            for sql in statements(vendor):
                try:
                    cursor.execute(sql)
                    self.stdout.write(f'ok   {sql[:110]}')
                except Exception as error:  # noqa: BLE001 - brak uprawnień do rozszerzenia nie ma zatrzymać B-drzew
                    self.stderr.write(f'błąd {sql[:110]}: {error}')
                    if 'pg_trgm' in sql:
                        self.stderr.write('Rozszerzenie pg_trgm wymaga uprawnień: wykonaj jako superuser `CREATE EXTENSION pg_trgm;` i powtórz.')
                        break
            self.stdout.write('indeksy: ' + ', '.join(existing(vendor, cursor)))
