import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from news.models import EvidenceLink, OfficialRecord


class Command(BaseCommand):
    help = 'Load sourced editorial topic links; requires the referenced official records.'
    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'data' / 'evidence_links.json'
        count = 0
        for row in json.loads(path.read_text(encoding='utf-8')):
            record = OfficialRecord.objects.filter(provider=row['provider'], external_id=row['external_id']).first()
            if record is None:
                raise CommandError('Import official record first: ' + row['external_id'])
            obj, created = EvidenceLink.objects.update_or_create(article=record.article, phrase=row['phrase'],
                source_url=row['source_url'], defaults={'explanation': row['explanation']})
            count += created
        self.stdout.write(f'New sourced topic links: {count}')
