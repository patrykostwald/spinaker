"""Persist the non-operational decision implied by completed source audits."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import ImportState, Source, SourceReviewDecision
from scraper.management.commands.source_review_queue import hostname, review_bucket


DECISION_MAP = {
    '00_juz_aktywne_pod_innym_rekordem': (
        SourceReviewDecision.Decision.COVERED,
        'An active configured source already covers this host; do not create a second harvester.'),
    '01_blad_techniczny': (
        SourceReviewDecision.Decision.TECHNICAL_RECHECK,
        'The technical audit failed. Do not ingest until the reported transport, certificate or availability issue is resolved.'),
    '02_instytucja_rss_do_warunkow': (
        SourceReviewDecision.Decision.TERMS_REVIEW,
        'A usable official RSS was found, but no reuse basis has been recorded for this exact channel.'),
    '03_instytucja_bez_potwierdzonego_kanalu': (
        SourceReviewDecision.Decision.CHANNEL_DISCOVERY,
        'No confirmed official machine-readable channel was found in the bounded technical audit. Do not guess an endpoint.'),
    '04_wydawca_lub_organizacja_wymaga_zgody': (
        SourceReviewDecision.Decision.CONTACT_REQUIRED,
        'No published terms or explicit permission for automated metadata reuse are recorded. Keep the source inactive.'),
}


class Command(BaseCommand):
    help = 'Zapisuje decyzje audytowe dla kandydatów; nigdy nie aktywuje źródła ani nie pobiera materiałów.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--reviewed-by', default='automatyczny audyt źródeł')

    def handle(self, *args, **options):
        candidates = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False,
        ).order_by('pk'))
        states = dict(ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in candidates]
        ).values_list('name', 'cursor'))
        active_hosts = {hostname(source.url) for source in Source.objects.filter(
            catalog_stage='configured', is_active=True, scrape_enabled=True,
        ) if hostname(source.url)}
        created = updated = preserved = 0
        now = timezone.now()
        with transaction.atomic():
            for source in candidates:
                result = states.get(f'source-check:{source.pk}', {}) or {}
                bucket = ('00_juz_aktywne_pod_innym_rekordem' if hostname(source.url) in active_hosts
                          else review_bucket(source, result))
                decision, reason = DECISION_MAP[bucket]
                snapshot = {
                    'bucket': bucket, 'audit_status': result.get('audit_status', 'not audited'),
                    'rss': result.get('rss') or {}, 'checked_at': result.get('checked_at'),
                }
                current = getattr(source, 'review_decision', None)
                if current and not current.is_automated:
                    preserved += 1
                    continue
                if current and current.decision == decision and current.audit_snapshot == snapshot:
                    preserved += 1
                    continue
                if not options['apply']:
                    if current:
                        updated += 1
                    else:
                        created += 1
                    continue
                if current:
                    current.decision = decision
                    current.reason = reason
                    current.evidence_urls = []
                    current.audit_snapshot = snapshot
                    current.reviewed_by = options['reviewed_by']
                    current.reviewed_at = now
                    current.is_automated = True
                    current.full_clean()
                    current.save()
                    updated += 1
                else:
                    current = SourceReviewDecision(
                        source=source, decision=decision, reason=reason, evidence_urls=[],
                        audit_snapshot=snapshot, reviewed_by=options['reviewed_by'], reviewed_at=now,
                        is_automated=True,
                    )
                    current.full_clean()
                    current.save()
                    created += 1
        mode = 'ZAPISANO' if options['apply'] else 'PLAN'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: candidates={len(candidates)} created={created} updated={updated} preserved_manual={preserved}.'
        ))
