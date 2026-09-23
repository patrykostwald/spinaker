from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from scraper.source_probe import PROBE_VERSION, source_signature


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
    candidate = Source.objects.create(
        name='Kandydat', url='https://candidate.example', source_type='institution',
        catalog_stage='candidate', is_active=False, scrape_enabled=False,
    )
    ImportState.objects.create(name=f'source-check:{candidate.pk}', last_success=timezone.now(), cursor={
        'probe_version': PROBE_VERSION, 'signature': source_signature(candidate),
        'audit_status': 'completed', 'checked_at': timezone.now().isoformat(),
    })

    output = StringIO()
    call_command('mvp_harvester_status', stdout=output)

    assert 'POSTEP_WERYFIKACJI: 1/2' in output.getvalue()
    assert 'KANDYDACI_DO_SPRAWDZENIA: 1' in output.getvalue()
    assert 'AUDYT_KANDYDATOW_7D: 1/1' in output.getvalue()
    assert 'PROBY_AUDYTU_7D: 1/1' in output.getvalue()
    assert 'POZOSTALO_DO_AUDYTU: 0/1' in output.getvalue()
