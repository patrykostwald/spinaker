"""Read-only snapshot of approved MVP harvesters and their stored material counts."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from news.models import ImportState, Source, SourceAccessInstruction


class Command(BaseCommand):
    help = 'Pokazuje stan zatwierdzonych harvesterów MVP; nie wykonuje zapytań sieciowych.'

    def handle(self, *args, **options):
        sources = (Source.objects.filter(is_active=True, scrape_enabled=True, catalog_stage='configured')
            .annotate(box_count=Count('articles')).order_by('pk'))
        approved = []
        for source in sources:
            cards = list(SourceAccessInstruction.objects.filter(
                source=source, status=SourceAccessInstruction.Status.APPROVED,
                valid_until__isnull=False).order_by('-version'))
            if not cards:
                continue
            channels = ', '.join(sorted({card.channel for card in cards}))
            approved.append(source)
            self.stdout.write(
                f'ŹRÓDŁO {source.pk}: {source.name} | kanały: {channels} | boxy: {source.box_count} | '
                f'RSS: {source.rss_url or "—"} | ostatnie pobranie: {source.last_scraped or "—"}')
        self.stdout.write(f'ZATWIERDZONE_AKTYWNE: {len(approved)}')
        candidates = Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False
        ).count()
        total_review_queue = len(approved) + candidates
        self.stdout.write(
            f'POSTEP_WERYFIKACJI: {len(approved)}/{total_review_queue} '
            f'(zatwierdzone aktywne / zatwierdzone aktywne + kandydaci)'
        )
        self.stdout.write(f'KANDYDACI_DO_SPRAWDZENIA: {candidates}')
        for name in ('html-archive:kprm:660', 'official:votings', 'official:eli'):
            state = ImportState.objects.filter(name=name).first()
            if state:
                self.stdout.write(
                    f'STAN {name}: zapisano={state.imported}; sukces={state.last_success or "—"}; '
                    f'błąd={state.last_error or "—"}')
