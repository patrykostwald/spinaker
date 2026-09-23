"""Read-only snapshot of approved MVP harvesters and their stored material counts."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from news.models import ImportState, Source, SourceAccessInstruction
from scraper.management.commands.audit_sources import is_fresh, is_recent_attempt


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
        candidates = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False
        ).order_by('pk'))
        candidate_states = dict(ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in candidates]
        ).values_list('name', 'cursor'))
        audited = [source for source in candidates if is_fresh(
            source, candidate_states.get(f'source-check:{source.pk}', {}), 168)]
        attempted = [source for source in candidates if is_recent_attempt(
            source, candidate_states.get(f'source-check:{source.pk}', {}), 168)]
        failed = [source for source in candidates if candidate_states.get(
            f'source-check:{source.pk}', {}).get('audit_status') == 'failed']
        candidate_count = len(candidates)
        total_review_queue = len(approved) + candidate_count
        self.stdout.write(
            f'POSTEP_WERYFIKACJI: {len(approved)}/{total_review_queue} '
            f'(zatwierdzone aktywne / zatwierdzone aktywne + kandydaci)'
        )
        self.stdout.write(f'KANDYDACI_DO_SPRAWDZENIA: {candidate_count}')
        self.stdout.write(
            f'AUDYT_KANDYDATOW_7D: {len(audited)}/{candidate_count} '
            f'(zakonczone bez bledu; bledy techniczne: {len(failed)})'
        )
        self.stdout.write(
            f'PROBY_AUDYTU_7D: {len(attempted)}/{candidate_count} '
            f'(zakonczone lub zarejestrowany blad; nie sa ponawiane automatycznie przez 7 dni)'
        )
        for name in ('html-archive:kprm:660', 'official:votings', 'official:eli'):
            state = ImportState.objects.filter(name=name).first()
            if state:
                self.stdout.write(
                    f'STAN {name}: zapisano={state.imported}; sukces={state.last_success or "—"}; '
                    f'błąd={state.last_error or "—"}')
