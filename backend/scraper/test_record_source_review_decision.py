from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_records_manual_decision_without_enabling_source():
    source = Source.objects.create(
        name='Official', url='https://www.official.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    )
    call_command('record_source_review_decision', '--source-host', 'official.example',
        '--decision', 'contact_required', '--reason', 'No exact channel terms.',
        '--evidence-url', 'https://official.example/terms', '--apply', stdout=StringIO())
    source.refresh_from_db()
    assert not source.is_active
    assert source.review_decision.decision == SourceReviewDecision.Decision.CONTACT_REQUIRED
    assert not source.review_decision.is_automated
