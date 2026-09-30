"""Jednorazowo: istniejące syntezy diagnoz przez językoznawcę Konsylium (tylko język; treść diagnozy bez zmian)."""
from django.core.management.base import BaseCommand

from news.clinic import polish_synthesis, published_diagnoses
from news.clinic_scan import synthesis_fingerprint


class Command(BaseCommand):
    help = 'Poprawia polszczyznę zapisanych syntez (x_thread); --dry-run pokazuje zmiany bez zapisu.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        changed = 0
        rows = published_diagnoses().exclude(x_thread=[]).order_by('-diagnosed_at', '-pk')[:options['limit']]
        for row in rows:
            before = list(row.x_thread or [])
            if not before:
                continue
            after = polish_synthesis(before)
            if after == before:
                continue
            changed += 1
            for old, new in zip(before, after):
                if old != new:
                    self.stdout.write(f'#{row.pk}\n  − {old}\n  + {new}')
            if options['dry_run']:
                continue
            # Odcisk syntezy aktualizujemy tylko wtedy, gdy stara synteza była sprawdzona (ta sama reguła co w scan_data).
            trusted = (row.usage or {}).get('scan_synthesis') == synthesis_fingerprint(row)
            row.x_thread = after
            if trusted:
                row.usage = {**(row.usage or {}), 'scan_synthesis': synthesis_fingerprint(row)}
            row.save(update_fields=['x_thread', 'usage'])
        self.stdout.write(f"{'DRY RUN — bez zapisu' if options['dry_run'] else 'Zapis'}: {changed} syntez")
