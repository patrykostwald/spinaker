from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from scraper.source_probe import PROBE_VERSION, source_signature


pytestmark = pytest.mark.django_db


def test_audited_rss_metadata_card_requires_fresh_working_audit_and_reuses_it():
    source = Source.objects.create(name='Official', url='https://official.example', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', last_success=timezone.now(), cursor={
        'probe_version': PROBE_VERSION, 'signature': source_signature(source), 'audit_status': 'completed',
        'checked_at': timezone.now().isoformat(),
        'rss': {'status': 'working', 'url': 'https://official.example/rss.xml', 'usable_entry_count': 2}})
    args = ('--source-id', str(source.pk), '--terms-url', 'https://official.example/reuse',
        '--evidence-note', 'Official reuse conditions reviewed.', '--reviewed-by', 'test', '--apply')
    call_command('configure_audited_rss_metadata_source', *args, stdout=StringIO())
    call_command('configure_audited_rss_metadata_source', *args, stdout=StringIO())
    source.refresh_from_db()
    assert source.is_active and source.rss_url == 'https://official.example/rss.xml'
    assert SourceAccessInstruction.objects.filter(source=source, channel='rss').count() == 1


def test_audited_rss_metadata_card_refuses_stale_audit():
    source = Source.objects.create(name='Old', url='https://old.example', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', last_success=timezone.now() - timedelta(days=2), cursor={
        'signature': source_signature(source), 'audit_status': 'completed',
        'rss': {'status': 'working', 'url': 'https://old.example/rss.xml', 'usable_entry_count': 1}})
    with pytest.raises(CommandError):
        call_command('configure_audited_rss_metadata_source', '--source-id', str(source.pk),
            '--terms-url', 'https://old.example/reuse', '--evidence-note', 'test', '--apply')
    assert not source.is_active
