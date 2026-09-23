from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction, SourceReviewDecision, SourceType


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


@pytest.mark.django_db
def test_matrix_routes_missing_or_unavailable_terms_to_actionable_outcomes(tmp_path):
    no_terms = Source.objects.create(name='No terms', url='https://no-terms.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    unavailable = Source.objects.create(name='Unavailable', url='https://unavailable.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{no_terms.pk}', cursor={
        'legal_terms_discovery': {'checked_at': timezone.now().isoformat(), 'status': 'no_official_terms_link_found'},
    })
    ImportState.objects.create(name=f'source-check:{unavailable.pk}', cursor={
        'legal_terms_discovery': {'checked_at': timezone.now().isoformat(), 'status': 'unavailable'},
    })
    output = tmp_path / 'matrix.md'
    call_command('source_resolution_matrix', '--output', str(output), stdout=StringIO())
    report = output.read_text(encoding='utf-8')
    assert 'contact_required' in report
    assert 'retry_or_contact_required' in report


@pytest.mark.django_db
def test_matrix_routes_checked_but_unusable_channel_to_contact(tmp_path):
    source = Source.objects.create(name='No feed', url='https://no-feed.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={
        'legal_terms_discovery': {'checked_at': timezone.now().isoformat(),
            'status': 'possible_reuse_basis_requires_editorial_review'},
        'legal_terms_classification': {'status': 'permission_wording_but_no_confirmed_channel'},
        'legal_channel_discovery': {'status': 'no_explicit_channel_found'},
    })
    output = tmp_path / 'matrix.md'
    call_command('source_resolution_matrix', '--output', str(output), stdout=StringIO())
    assert 'contact_required' in output.read_text(encoding='utf-8')


@pytest.mark.django_db
def test_matrix_uses_saved_contact_decision_as_the_final_state(tmp_path):
    source = Source.objects.create(name='Checked institution', url='https://checked.example',
        source_type=SourceType.INSTITUTION, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    ImportState.objects.create(name=f'source-check:{source.pk}', cursor={})
    SourceReviewDecision.objects.create(source=source, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason='No legal collection basis.', reviewed_by='test', is_automated=True)
    output = tmp_path / 'matrix.md'
    call_command('source_resolution_matrix', '--output', str(output), stdout=StringIO())
    assert '| contact_required | 1 |' in output.read_text(encoding='utf-8')
