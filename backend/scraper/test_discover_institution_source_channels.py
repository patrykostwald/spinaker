from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_discovers_only_explicit_channels_for_institution_without_working_initial_rss():
    source = Source.objects.create(name='Urząd testowy', url='https://office.example',
        source_type=SourceType.INSTITUTION, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={
        'audit_status': 'completed', 'rss': {'status': 'not_found'},
    })
    discovered = {
        'version': 1, 'status': 'working_channel_requires_editorial_card_review',
        'pages_checked': [{'url': source.url, 'status': 'ok'}],
        'channels': [{'url': 'https://office.example/rss', 'status': 'working', 'usable_entry_count': 2}],
    }
    with patch('scraper.management.commands.discover_institution_source_channels.inspect_explicit_channel',
               return_value=discovered):
        call_command('discover_institution_source_channels', '--apply', '--finalize-contact', stdout=StringIO())
    state = ImportState.objects.get(name=f'source-check:{source.pk}')
    assert state.cursor['legal_channel_discovery']['status'] == 'working_channel_requires_editorial_card_review'
    source.refresh_from_db()
    assert source.is_active is False and source.scrape_enabled is False
    assert source.review_decision.decision == SourceReviewDecision.Decision.CONTACT_REQUIRED


@pytest.mark.django_db
def test_ignores_publishers_even_if_their_first_rss_probe_failed():
    source = Source.objects.create(name='Wydawca', url='https://publisher.example',
        source_type=SourceType.PORTAL, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={
        'audit_status': 'completed', 'rss': {'status': 'not_found'},
    })
    output = StringIO()
    call_command('discover_institution_source_channels', '--apply', stdout=output)
    assert 'pending=0' in output.getvalue()
    assert 'legal_channel_discovery' not in ImportState.objects.get(name=f'source-check:{source.pk}').cursor
