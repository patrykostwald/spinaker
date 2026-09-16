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

    def handle(self, *args, **options):
        latest = SourceAccessInstruction.objects.filter(source=OuterRef('pk')).order_by('-version')
        active = Source.objects.filter(is_active=True, scrape_enabled=True).annotate(
            latest_card_status=Subquery(latest.values('status')[:1]),
            latest_card_valid_until=Subquery(latest.values('valid_until')[:1]),
        )
        blockers = []
        ready = []
        for source in active.order_by('pk'):
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
        self.stdout.write('WYNIK: ' + ('GOTOWE_DO_HARMONOGRAMU' if not blockers else 'NIE_GOTOWE'))
        if blockers:
            raise SystemExit(2)
