"""Apply only a recently verified feed, preserving owner exclusions and frequency."""
import json
from datetime import timedelta
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from news.models import Source, ImportState, SourceAccessInstruction
from scraper.source_probe import source_signature
from scraper.access_gate import reviewed_instruction_for_endpoint


class Command(BaseCommand):
    help = 'Apply explicit source IDs whose current access audit proves a working RSS.'

    def add_arguments(self, parser):
        parser.add_argument('--source-id', action='append', type=int, required=True)
        parser.add_argument('--report', required=True)

    def handle(self, *args, **options):
        changes, skipped = [], []
        for pk in options['source_id']:
            with transaction.atomic():
                source = Source.objects.select_for_update().get(pk=pk)
                state = ImportState.objects.filter(name=f'source-check:{pk}').first()
                result = state.cursor if state else {}
                rss = result.get('rss', {})
                if (source.catalog_stage == 'excluded' or not state or not state.last_success
                        or state.last_success < timezone.now() - timedelta(days=1)
                        or result.get('signature') != source_signature(source)
                        or result.get('audit_status') != 'completed' or rss.get('status') != 'working'
                        or not rss.get('url') or not rss.get('usable_entry_count')):
                    skipped.append({'id': pk, 'reason': 'audit_not_current_or_feed_unusable'})
                    continue
                if reviewed_instruction_for_endpoint(source, SourceAccessInstruction.Channel.RSS, rss['url']) is None:
                    skipped.append({'id': pk, 'reason': 'missing_approved_access_card'})
                    continue
                fields = ('rss_url', 'catalog_stage', 'is_active', 'scrape_enabled', 'scrape_frequency_minutes')
                before = {field: getattr(source, field) for field in fields}
                source.rss_url = rss['url']
                if source.catalog_stage == 'candidate':
                    source.catalog_stage = 'configured'
                    source.is_active = source.scrape_enabled = True
                source.full_clean()
                source.save(update_fields=['rss_url','catalog_stage','is_active','scrape_enabled','updated_at'])
                after = {field: getattr(source, field) for field in fields}
                # The applied endpoint is the exact feed already fetched in this
                # audit. Preserve its original config and proof time explicitly.
                state.cursor = {**result, 'configuration_before_apply': before,
                    'configuration_applied_at': timezone.now().isoformat(),
                    'configured_rss_url': source.rss_url, 'catalog_stage': source.catalog_stage,
                    'signature': source_signature(source)}
                state.save(update_fields=['cursor'])
                if before != after:
                    changes.append({'id':pk,'name':source.name,'before':before,'after':after,
                                    'evidence_checked_at':result['checked_at']})
        report = {'applied_at':timezone.now().isoformat(),'changes':changes,'skipped':skipped}
        Path(options['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.stdout.write(json.dumps({'changed':len(changes),'skipped':skipped}))
