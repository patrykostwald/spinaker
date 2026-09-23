from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_completion_audit_requires_card_for_active_and_decision_for_candidate(tmp_path):
    active = Source.objects.create(name='Active', url='https://active.example', rss_url='https://active.example/feed',
        source_type=SourceType.INSTITUTION, catalog_stage='configured', is_active=True, scrape_enabled=True)
    candidate = Source.objects.create(name='Candidate', url='https://candidate.example',
        source_type=SourceType.PORTAL, catalog_stage='candidate', is_active=False, scrape_enabled=False)
    output = tmp_path / 'audit.md'
    with pytest.raises(CommandError):
        call_command('source_catalog_completion_audit', '--output', str(output), '--strict', stdout=StringIO())
    SourceAccessInstruction.objects.create(source=active, version=1, status='approved', channel='rss',
        allowed_scope='metadata', endpoint=active.rss_url, terms_url='https://active.example/terms',
        evidence={'review_note': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=1), daily_request_cap=24)
    SourceReviewDecision.objects.create(source=candidate, decision='contact_required', reason='No permission.', reviewed_by='test')
    stream = StringIO()
    call_command('source_catalog_completion_audit', '--output', str(output), '--strict', stdout=stream)
    assert 'complete=true' in stream.getvalue()
    assert 'candidate_decisions=1/1' in stream.getvalue()
