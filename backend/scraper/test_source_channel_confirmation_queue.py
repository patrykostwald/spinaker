from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source


@pytest.mark.django_db
def test_queue_lists_only_permission_without_confirmed_channel(tmp_path):
    source = Source.objects.create(name='Channel review', url='https://channel.example', source_type='institution',
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={
        'legal_terms_discovery': {'checked_at': '2026-09-23T10:00:00+00:00',
            'status': 'possible_reuse_basis_requires_editorial_review',
            'terms_pages': [{'url': 'https://channel.example/terms'}]},
        'legal_terms_classification': {'status': 'permission_wording_but_no_confirmed_channel'},
        'rss': {'status': 'not_found'},
    })
    output = tmp_path / 'channels.md'
    call_command('source_channel_confirmation_queue', '--output', str(output), stdout=StringIO())
    assert 'Źródła do potwierdzenia kanału: **1**.' in output.read_text(encoding='utf-8')
