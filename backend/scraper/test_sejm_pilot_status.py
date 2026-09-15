from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import (Article, FetchAttempt, OfficialRecord, Source,
    SourceAccessInstruction, SourceDailyFetchBudget)


@pytest.mark.django_db
def test_status_reports_budget_audit_and_record_without_network():
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm')
    card = SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='content', endpoint='https://api.sejm.gov.pl/sejm/term10/votings',
        terms_url='https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )
    SourceDailyFetchBudget.objects.create(instruction=card, day=timezone.localdate(), used=2)
    attempt = FetchAttempt.objects.create(
        source=source, instruction=card, instruction_version=1, channel='api',
        requested_kind='api_record', url_fingerprint='a' * 64, url_host='api.sejm.gov.pl',
        outcome='ok', network_started=True, http_status=200,
    )
    article = Article.objects.create(source=source, title='Test vote',
        url='https://api.sejm.gov.pl/sejm/term10/votings/1/1')
    OfficialRecord.objects.create(article=article, provider='sejm', external_id='vote/10/1/1',
        api_url='https://api.sejm.gov.pl/sejm/term10/votings/1/1', raw_data={}, fetch_attempt=attempt)
    output = StringIO()

    call_command('sejm_pilot_status', stdout=output)

    text = output.getvalue()
    assert '2/24' in text
    assert 'REKORDY: 1' in text
    assert 'ok=1' in text
