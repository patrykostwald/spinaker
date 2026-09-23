from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState, Source
from scraper.source_probe import source_signature


@pytest.mark.django_db
def test_next_candidate_audit_selects_only_stale_candidates_and_stays_read_only(tmp_path):
    fresh = Source.objects.create(name='Fresh', url='https://fresh.example', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    stale = Source.objects.create(name='Stale', url='https://stale.example', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    active = Source.objects.create(name='Active', url='https://active.example', catalog_stage='configured',
        is_active=True, scrape_enabled=True)
    ImportState.objects.create(name=f'source-check:{fresh.pk}', last_success=timezone.now(), cursor={
        'probe_version': 1, 'signature': source_signature(fresh), 'audit_status': 'completed',
        'checked_at': timezone.now().isoformat()})
    with patch('scraper.management.commands.audit_next_source_candidates.call_command') as nested:
        call_command('audit_next_source_candidates', '--limit=1', '--output-prefix', str(tmp_path/'audit'))
    nested.assert_called_once()
    args = nested.call_args.args
    assert args[0] == 'audit_sources'
    assert str(stale.pk) in args
    assert str(fresh.pk) not in args and str(active.pk) not in args
    for source in (fresh, stale, active):
        source.refresh_from_db()
    assert fresh.catalog_stage == stale.catalog_stage == 'candidate'
    assert not fresh.is_active and not stale.is_active
