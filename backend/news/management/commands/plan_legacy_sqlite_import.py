"""Dry-run (optionally applied) idempotent import from the legacy standalone
SQLite database into the current Django database.

The legacy SQLite file predates the Postgres/Docker MVP branch and was
populated by a separate, non-containerized local run (``Start-Harvesters.ps1``
with ``USE_SQLITE=true``). Its ``news_article`` rows are mostly raw archive
crawl metadata (``ingestion_method='archive'``), not editorially reviewed
material, and its ``news_articlecontent`` full text was collected only for
local quality experiments -- it is never read or copied by this command and
is not authorised for publication or model training.

This command only ever reads article *metadata* (title, url, published date,
ingestion method, source) from the legacy file. It links an imported row to
an *existing* Source in the target database by exact source URL; it never
creates a new Source, so importing can never silently activate a harvester
for a source that has not been reviewed here.

Dedup is by exact Article.url and by the same canonical-URL normalisation
already used by scraper.quality_enrichment.canonicalize_url, so re-running
this command is idempotent: a second run reports the same rows as
"already present" and writes nothing new for them.

--apply is refused unless the target database name contains "test" (or
--force-non-test-db is passed explicitly), and is always refused against a
Supabase host, so a dry-run mistake cannot reach the working MVP or
production data.
"""
import argparse
import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from news.models import Article, ArticleCategory, Source
from scraper.quality_enrichment import canonicalize_url

# Legacy full-text/derived tables are intentionally never read here.
EXCLUDED_LEGACY_TABLES = ('news_articlecontent',)

LEGACY_ARTICLE_COLUMNS = (
    'id', 'source_id', 'title', 'author', 'description', 'url',
    'published_date', 'ingestion_method', 'category', 'image_url',
    'discovered_at', 'created_at',
)


class Command(BaseCommand):
    help = ('Report (and, on a test database only, apply) an idempotent '
            'metadata-only import from a legacy standalone SQLite export.')

    def add_arguments(self, parser):
        parser.add_argument('--sqlite-path', required=True,
            help='Path to the legacy SQLite file (opened read-only).')
        parser.add_argument('--apply', action='store_true',
            help='Write new Article rows. Default is dry-run/report only.')
        parser.add_argument('--limit', type=int, default=0,
            help='Cap the number of legacy rows scanned (0 = no cap).')
        parser.add_argument('--report', default='',
            help='Optional path to also write the JSON report.')
        parser.add_argument('--force-non-test-db', action='store_true',
            help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        sqlite_path = Path(options['sqlite_path'])
        if not sqlite_path.is_file():
            raise CommandError(f'no such file: {sqlite_path}')

        apply_changes = options['apply']
        if apply_changes:
            self._guard_target_database(options['force_non_test_db'])

        legacy = sqlite3.connect(f'file:{sqlite_path.as_posix()}?mode=ro', uri=True)
        legacy.row_factory = sqlite3.Row
        try:
            report = self._scan(legacy, limit=options['limit'], apply_changes=apply_changes)
        finally:
            legacy.close()

        report['excluded_legacy_tables'] = list(EXCLUDED_LEGACY_TABLES)
        report['mode'] = 'apply' if apply_changes else 'dry_run'
        report['target_database'] = connection.settings_dict.get('NAME')

        rendered = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        self.stdout.write(rendered)
        report_path = options['report']
        if report_path:
            Path(report_path).write_text(rendered, encoding='utf-8')

    def _guard_target_database(self, force_non_test_db):
        name = str(connection.settings_dict.get('NAME') or '')
        host = str(connection.settings_dict.get('HOST') or '')
        if 'supabase' in name.lower() or 'supabase' in host.lower():
            raise CommandError('refusing --apply against a Supabase host')
        if 'test' not in name.lower() and not force_non_test_db:
            raise CommandError(
                f'refusing --apply: target database {name!r} does not look like '
                'a test database. Re-run against a disposable test database, '
                'or pass --force-non-test-db if you have already confirmed it is safe.')

    def _scan(self, legacy, *, limit, apply_changes):
        by_source_url = {source.url: source for source in Source.objects.all() if source.url}
        existing_urls = set(Article.objects.values_list('url', flat=True))
        existing_canonical = {canonicalize_url(url) for url in existing_urls}

        legacy_source_urls = {row['id']: row['url'] for row in
            legacy.execute('SELECT id, url FROM news_source')}

        query = f"SELECT {', '.join(LEGACY_ARTICLE_COLUMNS)} FROM news_article ORDER BY id"
        if limit:
            query += f' LIMIT {int(limit)}'

        by_ingestion_method = {}
        already_present = 0
        missing_source = 0
        imported = 0
        skipped_invalid = 0
        new_candidates_sample = []

        for row in legacy.execute(query):
            by_ingestion_method[row['ingestion_method']] = by_ingestion_method.get(row['ingestion_method'], 0) + 1
            url = (row['url'] or '').strip()
            title = (row['title'] or '').strip()
            if not url or not title or len(url) > 1024:
                skipped_invalid += 1
                continue
            if url in existing_urls or canonicalize_url(url) in existing_canonical:
                already_present += 1
                continue

            source_url = legacy_source_urls.get(row['source_id'])
            target_source = by_source_url.get(source_url) if source_url else None
            if target_source is None:
                missing_source += 1
                continue

            candidate = {
                'legacy_id': row['id'], 'url': url, 'title': title,
                'source_url': source_url, 'ingestion_method': row['ingestion_method'],
                'published_date': row['published_date'],
            }
            if len(new_candidates_sample) < 25:
                new_candidates_sample.append(candidate)

            if apply_changes:
                if self._apply_one(row, target_source, url, title):
                    imported += 1
                    existing_urls.add(url)
                    existing_canonical.add(canonicalize_url(url))

        return {
            'legacy_rows_by_ingestion_method': by_ingestion_method,
            'already_present_in_target': already_present,
            'skipped_invalid_url_or_title': skipped_invalid,
            'skipped_missing_target_source': missing_source,
            'new_candidates_total': len(new_candidates_sample) if not apply_changes else imported,
            'imported': imported if apply_changes else 0,
            'new_candidates_sample': new_candidates_sample,
            'note': ('missing_target_source counts rows whose legacy Source URL has no '
                     'matching Source in the target database; this command never creates '
                     'a Source, so those rows are reported but never imported.'),
        }

    @transaction.atomic
    def _apply_one(self, row, target_source, url, title):
        category = row['category'] if row['category'] in ArticleCategory.values else ArticleCategory.ARTICLE
        _, created = Article.objects.get_or_create(url=url, defaults=dict(
            source=target_source, title=title[:500],
            author=(row['author'] or '')[:200],
            description=(row['description'] or '')[:4000],
            published_date=row['published_date'],
            ingestion_method=row['ingestion_method'] or 'manual',
            category=category,
            image_url=(row['image_url'] or '')[:1024],
            discovered_at=row['discovered_at'],
            evidence_note=f"Zaimportowano z historycznej bazy SQLite (legacy id={row['id']}).",
        ))
        return created
