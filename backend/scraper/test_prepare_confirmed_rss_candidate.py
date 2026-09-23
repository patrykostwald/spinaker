from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceType


@pytest.mark.django_db
def test_preparation_accepts_only_one_working_explicit_channel():
    source = Source.objects.create(name='Office', url='https://office.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={'legal_channel_discovery': {
        'status': 'working_channel_requires_editorial_card_review',
        'channels': [{'url': 'https://office.example/rss', 'status': 'working'}],
    }})
    call_command('prepare_confirmed_rss_candidate', '--source-id', str(source.pk), '--apply', stdout=StringIO())
    source.refresh_from_db()
    assert source.rss_url == 'https://office.example/rss'
    assert not source.is_active and not source.scrape_enabled
