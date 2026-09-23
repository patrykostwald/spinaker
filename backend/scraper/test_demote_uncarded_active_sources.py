from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceReviewDecision, SourceType


def source(name):
    return Source.objects.create(
        name=name, url=f'https://{name.lower()}.example', source_type=SourceType.INSTITUTION,
        catalog_stage='configured', is_active=True, scrape_enabled=True,
    )


@pytest.mark.django_db
def test_dry_run_does_not_change_sources():
    uncarded = source('Uncarded')
    output = StringIO()
    call_command('demote_uncarded_active_sources', stdout=output)
    uncarded.refresh_from_db()
    assert 'dry_run targets=1' in output.getvalue()
    assert uncarded.is_active and uncarded.scrape_enabled
    assert not SourceReviewDecision.objects.filter(source=uncarded).exists()


@pytest.mark.django_db
def test_apply_demotes_only_sources_without_a_current_card():
    uncarded = source('Uncarded')
    carded = source('Carded')
    SourceAccessInstruction.objects.create(
        source=carded, version=1, status='approved', channel='html', allowed_scope='metadata',
        endpoint=carded.url, terms_url=f'{carded.url}/terms', evidence={'review_note': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', valid_until=timezone.now() + timedelta(days=1),
        daily_request_cap=24,
    )
    output = StringIO()
    call_command('demote_uncarded_active_sources', '--apply', stdout=output)
    uncarded.refresh_from_db()
    carded.refresh_from_db()
    decision = SourceReviewDecision.objects.get(source=uncarded)
    assert 'demoted=1' in output.getvalue()
    assert uncarded.catalog_stage == 'candidate' and not uncarded.is_active and not uncarded.scrape_enabled
    assert decision.decision == SourceReviewDecision.Decision.CONTACT_REQUIRED
    assert carded.catalog_stage == 'configured' and carded.is_active and carded.scrape_enabled
