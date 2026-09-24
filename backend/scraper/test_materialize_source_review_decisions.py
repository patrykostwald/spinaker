from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_materializes_decisions_and_preserves_manual_reviews():
    official = Source.objects.create(
        name='Official', url='https://official.example', source_type=SourceType.INSTITUTION,
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    )
    publisher = Source.objects.create(
        name='Publisher', url='https://publisher.example', source_type=SourceType.PORTAL,
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    )
    ImportState.objects.create(name=f'source-check:{official.pk}', cursor={
        'audit_status': 'completed', 'rss': {'status': 'working', 'url': 'https://official.example/feed'},
    })
    SourceReviewDecision.objects.create(
        source=publisher, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason='Manual decision.', reviewed_by='editor', is_automated=False,
    )
    stream = StringIO()
    call_command('materialize_source_review_decisions', '--apply', stdout=stream)
    official.refresh_from_db()
    publisher.refresh_from_db()
    assert official.review_decision.decision == SourceReviewDecision.Decision.TERMS_REVIEW
    assert official.review_decision.is_automated
    assert publisher.review_decision.reason == 'Manual decision.'
    assert 'created=1' in stream.getvalue()
    assert 'preserved_manual=1' in stream.getvalue()
