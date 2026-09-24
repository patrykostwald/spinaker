"""Read-only gate before any scheduled harvesting run.

This command deliberately performs no HTTP requests.  It verifies the local
conditions that must be true before a scheduler may enqueue work; individual
adapters still pass their exact URL through ``approved_instruction``.
"""
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


class Command(BaseCommand):
    help = 'Sprawdza lokalną gotowość aktywnych harvesterów bez żądań sieciowych.'

    def add_arguments(self, parser):
        parser.add_argument('--approved-only', action='store_true',
            help='Raportuje tylko piloty z zatwierdzoną najnowszą kartą; kandydatów pokazuje zbiorczo.')

    def handle(self, *args, **options):
        latest = SourceAccessInstruction.objects.filter(source=OuterRef('pk')).order_by('-version')
        active = Source.objects.filter(is_active=True, scrape_enabled=True).annotate(
            latest_card_status=Subquery(latest.values('status')[:1]),
            latest_card_valid_until=Subquery(latest.values('valid_until')[:1]),
        )
        blockers = []
        ready = []
        skipped_unapproved = 0
        for source in active.order_by('pk'):
            if options['approved_only'] and source.latest_card_status != SourceAccessInstruction.Status.APPROVED:
                skipped_unapproved += 1
                continue
            if source.catalog_stage != 'configured':
                blockers.append((source.pk, source.name, 'nie jest skonfigurowane'))
            elif source.latest_card_status != SourceAccessInstruction.Status.APPROVED:
                blockers.append((source.pk, source.name, 'ostatnia karta nie jest zatwierdzona'))
            elif not source.latest_card_valid_until or source.latest_card_valid_until <= timezone.now():
                blockers.append((source.pk, source.name, 'karta wygasła lub nie ma terminu ważności'))
            else:
                ready.append((source.pk, source.name))

        for pk, name in ready:
            self.stdout.write(self.style.SUCCESS(f'GOTOWE {pk}: {name}'))
        for pk, name, reason in blockers:
            self.stdout.write(self.style.WARNING(f'BLOKER {pk}: {name} — {reason}'))
        if options['approved_only']:
            self.stdout.write(f'KANDYDACI_BEZ_KARTY: {skipped_unapproved}')
        self.stdout.write('WYNIK: ' + ('GOTOWE_DO_HARMONOGRAMU' if not blockers else 'NIE_GOTOWE'))
        if blockers:
            raise SystemExit(2)
