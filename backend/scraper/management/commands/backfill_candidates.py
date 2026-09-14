import json
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import Source


CATALOG_PATH = Path(__file__).resolve().parents[2] / 'data' / 'verified_local_sources.json'


def archive_candidate(source, row):
    verification = row.get('archive_verification') or {}
    if verification:
        return {
            'status': verification.get('status', 'needs_review'),
            'archive_type': verification.get('mechanism', 'unknown'),
            'reason': verification.get('reason', ''),
            'urls': verification.get('urls', []),
            'date_range': verification.get('date_range', {}),
            'can_backfill': bool(verification.get('can_backfill')),
        }
    if row.get('sitemap_urls'):
        return {'status': 'verified', 'archive_type': 'verified_sitemap',
            'reason': 'Legacy catalog evidence contains a publisher sitemap; re-audit before benchmark.',
            'urls': row['sitemap_urls'], 'date_range': {}, 'can_backfill': True}
    if row.get('rss_url'):
        return {'status': 'needs_review', 'archive_type': 'rss_only',
            'reason': 'RSS alone does not prove a rewindable archive.', 'urls': [row['rss_url']],
            'date_range': {}, 'can_backfill': False}
    return {'status': 'unsupported', 'archive_type': 'none',
        'reason': 'No verified sitemap, paginated archive, or supported API in the local catalog.',
        'urls': [], 'date_range': {}, 'can_backfill': False}


class Command(BaseCommand):
    help = 'List local, configured sources with verified archive evidence without network access.'

    def add_arguments(self, parser):
        parser.add_argument('--name', help='Case-insensitive substring filter.')

    def handle(self, *args, **options):
        catalog = {row['url'].rstrip('/'): row for row in json.loads(CATALOG_PATH.read_text(encoding='utf-8'))}
        query = Source.objects.filter(is_active=True, scrape_enabled=True, catalog_stage='configured')
        needle = (options.get('name') or '').casefold()
        for source in query.order_by('name'):
            row = catalog.get((source.url or '').rstrip('/'))
            if needle and needle not in source.name.casefold():
                continue
            evidence = archive_candidate(source, row or {})
            self.stdout.write(str({'source_id': source.pk, 'name': source.name,
                'url': source.url, **evidence,
                'verified_on': (row or {}).get('verified_on'),
                'evidence_urls': (row or {}).get('evidence_urls', [])}))