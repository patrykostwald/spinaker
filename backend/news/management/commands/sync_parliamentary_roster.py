"""Stage current official parliamentary rosters without creating X accounts."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.parliamentary_roster import get_rows
from news.political_models import ParliamentaryRosterEntry


class Command(BaseCommand):
    help = 'Pobiera oficjalny roster parlamentarny do wewnętrznego przeglądu; nie dotyka X ani kandydatur kont.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, choices=['sejm', 'senat', 'ep'])
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source = options['source']
        rows = list(get_rows(source))
        if not rows:
            raise CommandError('Źródło nie zwróciło aktywnych pozycji; dla bezpieczeństwa nie oznaczono nic jako nieaktywne.')
        ids = {row.external_id for row in rows}
        if len(ids) != len(rows):
            raise CommandError('Źródło zawiera powielone identyfikatory; import przerwany.')
        existing = {entry.external_id: entry for entry in ParliamentaryRosterEntry.objects.filter(source=source)}
        created = sum(row.external_id not in existing for row in rows)
        updated = len(rows) - created
        absent = ParliamentaryRosterEntry.objects.filter(source=source, active=True).exclude(external_id__in=ids).count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Podgląd {source}: aktywnych w źródle {len(rows)}; nowe {created}; do aktualizacji {updated}; '
                f'do oznaczenia jako nieaktywne {absent}. Bez zapisu.'))
            return
        now = timezone.now()
        with transaction.atomic():
            for row in rows:
                ParliamentaryRosterEntry.objects.update_or_create(source=source, external_id=row.external_id, defaults={
                    'full_name': row.full_name, 'club': row.club, 'district': row.district,
                    'profile_url': row.profile_url, 'source_url': row.source_url, 'active': row.active,
                    'term': row.term,
                    'last_seen_at': now,
                })
            # Only after a non-empty, unique official roster: absent entries are retained but inactive.
            ParliamentaryRosterEntry.objects.filter(source=source, active=True).exclude(external_id__in=ids).update(active=False)
        self.stdout.write(self.style.SUCCESS(
            f'Zaimportowano {len(rows)} aktywnych wpisów {source}; nowe {created}; zaktualizowane {updated}; '
            f'oznaczone nieaktywne {absent}. Nie utworzono kont X ani kandydatur.'
        ))
