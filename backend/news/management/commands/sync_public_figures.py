"""Import reviewable public figures from explicit official rosters only."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.government_roster import cabinet_rows
from news.political_models import PublicFigure


class Command(BaseCommand):
    help = 'Importuje aktualny skład Rady Ministrów z KPRM; nie dotyka X ani kandydatur kont.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, choices=['cabinet'])
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if options['source'] != 'cabinet':
            raise CommandError('Dostępne źródło: cabinet.')
        rows = list(cabinet_rows())
        if not rows:
            raise CommandError('Źródło nie zwróciło członków rządu; dla bezpieczeństwa nie oznaczono nic jako archiwalne.')
        keys = {row.import_key for row in rows}
        if len(keys) != len(rows):
            raise CommandError('Źródło zawiera powielone klucze importu; import przerwany.')
        existing = {item.import_key: item for item in PublicFigure.objects.filter(import_key__startswith='kprm-cabinet:')}
        created = sum(row.import_key not in existing for row in rows)
        updated = len(rows) - created
        absent = PublicFigure.objects.filter(import_key__startswith='kprm-cabinet:', archived=False, status='current').exclude(import_key__in=keys).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd cabinet: aktualnych w źródle {len(rows)}; nowe {created}; do aktualizacji {updated}; '
                f'do oznaczenia jako byli członkowie rządu {absent}. Bez zapisu i bez działań w X.'
            ))
            return
        now = timezone.now()
        with transaction.atomic():
            for row in rows:
                PublicFigure.objects.update_or_create(import_key=row.import_key, defaults={
                    'canonical_name': row.canonical_name,
                    'role_category': 'government',
                    'role_title': row.role_title,
                    'organisation': 'Rada Ministrów',
                    'status': 'current',
                    'official_profile_url': '',
                    'evidence_url': row.source_url,
                    'evidence_note': 'Aktualny skład Rady Ministrów wskazany przez KPRM.',
                    'source_checked_at': now,
                    'archived': False,
                })
            PublicFigure.objects.filter(import_key__startswith='kprm-cabinet:', archived=False, status='current').exclude(import_key__in=keys).update(
                status='former', source_checked_at=now
            )
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(rows)} aktualnych członków rządu; nowe {created}; zaktualizowane {updated}; '
            f'oznaczone jako byli członkowie rządu {absent}. Nie utworzono kont X ani kandydatur.'
        ))
