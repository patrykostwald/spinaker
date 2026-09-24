"""Fail closed for configured sources that no longer have a valid access card."""
from django.db import transaction
from django.core.management.base import BaseCommand

from news.models import Source, SourceReviewDecision
from scraper.access_gate import has_current_approved_instruction


class Command(BaseCommand):
    help = ('Moves active sources without a current reviewed card back to inactive candidates. '
            'It never contacts a publisher or downloads content.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the fail-closed changes.')
        parser.add_argument('--reviewed-by', default='catalog safety gate')

    def handle(self, *args, **options):
        active = list(Source.objects.filter(
            catalog_stage='configured', is_active=True, scrape_enabled=True,
        ).order_by('pk'))
        targets = [source for source in active if not has_current_approved_instruction(source)]
        if not options['apply']:
            self.stdout.write(
                f'SOURCE_SAFETY_DEMOTION: dry_run targets={len(targets)} active_total={len(active)}; no changes.'
            )
            for source in targets:
                self.stdout.write(f'WOULD_DEMOTE {source.pk}: {source.name}')
            return

        created = updated = preserved_manual = 0
        with transaction.atomic():
            for source in targets:
                source.catalog_stage = 'candidate'
                source.is_active = False
                source.scrape_enabled = False
                source.save(update_fields=('catalog_stage', 'is_active', 'scrape_enabled', 'updated_at'))
                existing = SourceReviewDecision.objects.filter(source=source).first()
                if existing and not existing.is_automated:
                    preserved_manual += 1
                    continue
                defaults = {
                    'decision': SourceReviewDecision.Decision.CONTACT_REQUIRED,
                    'reason': ('No current reviewed SourceAccessInstruction exists for this active source. '
                               'It remains inactive until published terms or explicit permission are recorded.'),
                    'evidence_urls': [url for url in (source.rss_url, source.url) if url],
                    'audit_snapshot': {'reason': 'no_current_approved_access_card'},
                    'reviewed_by': options['reviewed_by'],
                    'is_automated': True,
                }
                _, was_created = SourceReviewDecision.objects.update_or_create(source=source, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'SOURCE_SAFETY_DEMOTION: demoted={len(targets)} created={created} updated={updated} '
            f'preserved_manual={preserved_manual}; no contact or import was performed.'
        ))
