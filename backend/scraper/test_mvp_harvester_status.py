from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_status_reports_review_progress():
    source = Source.objects.create(
        name='Zatwierdzone', url='https://approved.example', source_type='institution',
        catalog_stage='configured', is_active=True, scrape_enabled=True,
    )
    SourceAccessInstruction.objects.create(
        source=source, channel='html', endpoint='https://approved.example',
        allowed_scope='metadata', status='approved', valid_until=timezone.now() + timedelta(days=1),
    )
    Source.objects.create(
        name='Kandydat', url='https://candidate.example', source_type='institution',
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    )

    output = StringIO()
    call_command('mvp_harvester_status', stdout=output)

    assert 'POSTEP_WERYFIKACJI: 1/2' in output.getvalue()
    assert 'KANDYDACI_DO_SPRAWDZENIA: 1' in output.getvalue()
