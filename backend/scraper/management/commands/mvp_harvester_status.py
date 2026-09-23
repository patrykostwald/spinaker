"""Read-only snapshot of approved MVP harvesters and their stored material counts."""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.harvester_coverage import schedule_label
from scraper.management.commands.audit_sources import is_fresh, is_recent_attempt
from scraper.management.commands.source_review_queue import hostname, review_bucket


class Command(BaseCommand):
    help = 'Pokazuje stan zatwierdzonych harvesterów MVP; nie wykonuje zapytań sieciowych.'

    def handle(self, *args, **options):
        sources = (Source.objects.filter(is_active=True, scrape_enabled=True, catalog_stage='configured')
            .annotate(box_count=Count('articles')).order_by('pk'))
        approved = []
        coverage = {'scheduled': [], 'needs_schedule_mapping': []}
        for source in sources:
            cards = list(SourceAccessInstruction.objects.filter(
                source=source, status=SourceAccessInstruction.Status.APPROVED,
                valid_until__gt=timezone.now(), daily_request_cap__gte=1,
                reviewed_at__isnull=False).exclude(terms_url='').exclude(reviewed_by='').exclude(evidence={}).order_by('-version'))
            if not cards:
                continue
            channels = ', '.join(sorted({card.channel for card in cards}))
            schedule, schedule_status = schedule_label(source, cards)
            coverage[schedule_status].append(source)
            approved.append(source)
            self.stdout.write(
                f'ŹRÓDŁO {source.pk}: {source.name} | kanały: {channels} | boxy: {source.box_count} | '
                f'RSS: {source.rss_url or "—"} | harmonogram: {schedule} | '
                f'ostatnie pobranie: {source.last_scraped or "—"}')
        self.stdout.write(f'ZATWIERDZONE_AKTYWNE: {len(approved)}')
        self.stdout.write(
            f'AKTYWNE_Z_HARMONOGRAMEM: {len(coverage["scheduled"])}/{len(approved)}')
        self.stdout.write(
            f'AKTYWNE_BEZ_MAPOWANIA_HARMONOGRAMU: {len(coverage["needs_schedule_mapping"])}/{len(approved)}')
        for source in coverage['needs_schedule_mapping']:
            self.stdout.write(f'BRAK_MAPOWANIA {source.pk}: {source.name}')
        candidates = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False
        ).order_by('pk'))
        candidate_states = dict(ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in candidates]
        ).values_list('name', 'cursor'))
        active_hosts = {hostname(source.url) for source in approved if hostname(source.url)}
        review_counts = {
            '00_juz_aktywne_pod_innym_rekordem': 0,
            '01_blad_techniczny': 0,
            '02_instytucja_rss_do_warunkow': 0,
            '03_instytucja_bez_potwierdzonego_kanalu': 0,
            '04_wydawca_lub_organizacja_wymaga_zgody': 0,
        }
        for candidate in candidates:
            result = candidate_states.get(f'source-check:{candidate.pk}', {}) or {}
            bucket = ('00_juz_aktywne_pod_innym_rekordem'
                      if hostname(candidate.url) in active_hosts else review_bucket(candidate, result))
            review_counts[bucket] += 1
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
        total_sources = Source.objects.count()
        self.stdout.write(f'AKTYWNE_POBIERANIE: {len(approved)}/{total_sources}')
        self.stdout.write(
            f'NIEUKONCZONE_ZRODLA: {candidate_count}/{total_sources} '
            '(znalezione technicznie, ale bez decyzji o uruchomieniu)'
        )
        self.stdout.write(
            'POTENCJALNIE_DO_KONTAKTU_PO_DECYZJI: '
            f'{review_counts["04_wydawca_lub_organizacja_wymaga_zgody"]}/{total_sources} '
            '(tylko lista; nic nie jest wysyłane)'
        )
        self.stdout.write(
            'JAWNE_WARUNKI_DO_ODSZUKANIA: '
            f'{review_counts["02_instytucja_rss_do_warunkow"]}/{total_sources} '
            '(głównie instytucje publiczne z działającym kanałem)'
        )
        self.stdout.write(
            'NIEJASNY_LUB_BRAKUJACY_KANAL: '
            f'{review_counts["03_instytucja_bez_potwierdzonego_kanalu"]}/{total_sources}'
        )
        self.stdout.write(
            'BLEDY_TECHNICZNE: '
            f'{review_counts["01_blad_techniczny"]}/{total_sources}'
        )
        self.stdout.write(
            'DUPLIKATY_JUZ_AKTYWNYCH: '
            f'{review_counts["00_juz_aktywne_pod_innym_rekordem"]}/{total_sources}'
        )
        self.stdout.write(
            f'AUDYT_KANDYDATOW_7D: {len(audited)}/{candidate_count} '
            f'(zakonczone bez bledu; bledy techniczne: {len(failed)})'
        )
        self.stdout.write(
            f'PROBY_AUDYTU_7D: {len(attempted)}/{candidate_count} '
            f'(zakonczone lub zarejestrowany blad; nie sa ponawiane automatycznie przez 7 dni)'
        )
        self.stdout.write(
            f'POZOSTALO_DO_AUDYTU: {max(candidate_count - len(attempted), 0)}/{candidate_count}'
        )
        for name in ('html-archive:kprm:660', 'official:votings', 'official:eli'):
            state = ImportState.objects.filter(name=name).first()
            if state:
                self.stdout.write(
                    f'OSTATNI_PRZEBIEG {name}: zapisano={state.imported}; sukces={state.last_success or "—"}; '
                    f'błąd={state.last_error or "—"}')
        gates = {
            'official:votings': ('https://api.sejm.gov.pl/sejm',
                                 'https://api.sejm.gov.pl/sejm/term10/votings/search'),
            'official:eli': ('https://api.sejm.gov.pl/eli',
                             'https://api.sejm.gov.pl/eli/changes/acts'),
        }
        for name, (source_url, request_url) in gates.items():
            source = Source.objects.filter(url=source_url).first()
            ready = approved_instruction(source, SourceAccessInstruction.Channel.API, request_url) is not None
            self.stdout.write(f'BRAMKA {name}: {"GOTOWA" if ready else "BLOKADA"}')
