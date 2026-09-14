import json
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import Source


CATALOG_PATH = Path(__file__).resolve().parents[2] / 'data' / 'verified_local_sources.json'


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
            if not row or not row.get('sitemap_urls'):
                continue
            if needle and needle not in source.name.casefold():
                continue
            self.stdout.write(str({'source_id': source.pk, 'name': source.name,
                'url': source.url, 'archive_type': 'verified_sitemap',
                'sitemap_urls': row['sitemap_urls'], 'verified_on': row.get('verified_on'),
                'evidence_urls': row.get('evidence_urls', [])}))