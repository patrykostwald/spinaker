from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import (Article, FetchAttempt, OfficialRecord, Source,
    SourceAccessInstruction)


@pytest.fixture
def existing_vote(db):
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
    article = Article.objects.create(source=source, title='Test',
        url='https://api.sejm.gov.pl/sejm/term10/votings/1/1')
    attempt = FetchAttempt.objects.create(source=source, instruction=card,
        instruction_version=1, channel='api', requested_kind='api_record',
        url_fingerprint='a' * 64, url_host='api.sejm.gov.pl', outcome='ok',
        network_started=True, http_status=200)
    return OfficialRecord.objects.create(article=article, provider='sejm',
        external_id='vote/10/1/1', api_url=article.url, raw_data={'version': 1},
        fetch_attempt=attempt)


@pytest.mark.django_db
def test_revisit_is_read_only_without_apply(monkeypatch, existing_vote):
    monkeypatch.setattr('scraper.management.commands.revisit_sejm_vote.connection.vendor', 'postgresql')
    importer = pytest.importorskip('unittest.mock').Mock()
    monkeypatch.setattr('scraper.management.commands.revisit_sejm_vote.import_voting', importer)

    output = StringIO()
    call_command('revisit_sejm_vote', '--sitting=1', '--vote=1', stdout=output)

    assert 'GOTOWY' in output.getvalue()
    importer.assert_not_called()


@pytest.mark.django_db
def test_revisit_reports_a_new_revision(monkeypatch, existing_vote):
    monkeypatch.setattr('scraper.management.commands.revisit_sejm_vote.connection.vendor', 'postgresql')

    def revise(*args):
        from news.models import OfficialRevision
        OfficialRevision.objects.create(record=existing_vote, raw_data={'version': 1},
            fetched_at=timezone.now())

    monkeypatch.setattr('scraper.management.commands.revisit_sejm_vote.import_voting', revise)
    output = StringIO()
    call_command('revisit_sejm_vote', '--sitting=1', '--vote=1', '--apply', stdout=output)

    assert 'KOREKTA' in output.getvalue()
