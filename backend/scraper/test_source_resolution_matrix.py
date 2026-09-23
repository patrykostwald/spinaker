from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction, SourceType


@pytest.mark.django_db
def test_matrix_uses_discovery_evidence_without_changing_source(tmp_path):
    active = Source.objects.create(name='Active', url='https://active.example', source_type=SourceType.INSTITUTION,
        catalog_stage='configured', is_active=True, scrape_enabled=True)
    SourceAccessInstruction.objects.create(source=active, channel='api', endpoint='https://active.example/api',
        allowed_scope='metadata', status='approved', terms_url='https://active.example/terms', evidence={'ok': True},
        reviewed_at=timezone.now(), reviewed_by='test', valid_until=timezone.now() + timedelta(days=1), daily_request_cap=10)
    candidate = Source.objects.create(name='Candidate', url='https://candidate.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{candidate.pk}', cursor={
        'legal_terms_discovery': {'checked_at': timezone.now().isoformat()},
        'legal_terms_classification': {'status': 'clear_denial_keep_inactive'},
    })
    output = tmp_path / 'matrix.md'
    call_command('source_resolution_matrix', '--output', str(output), stdout=StringIO())
    text = output.read_text(encoding='utf-8')
    assert 'active_harvester' in text and 'contact_or_keep_inactive' in text
    candidate.refresh_from_db()
    assert not candidate.is_active and candidate.catalog_stage == 'candidate'
