from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_pilot_command_is_read_only_without_apply(monkeypatch):
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm', is_active=True,
        scrape_enabled=True, catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='content', endpoint='https://api.sejm.gov.pl/sejm/term10/votings',
        allowed_path_patterns=['/sejm/term10/votings/{int}', '/sejm/term10/votings/{int}/{int}'],
        terms_url='https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )
    monkeypatch.setattr('scraper.management.commands.run_sejm_vote_pilot.connection.vendor', 'postgresql')
    importer = pytest.importorskip('unittest.mock').Mock()
    monkeypatch.setattr('scraper.management.commands.run_sejm_vote_pilot.import_voting', importer)
    output = StringIO()

    call_command('run_sejm_vote_pilot', '--sitting=1', '--vote=1', stdout=output)

    assert 'GOTOWY' in output.getvalue()
    importer.assert_not_called()


@pytest.mark.django_db
def test_pilot_command_verifies_list_before_detail(monkeypatch):
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm', is_active=True,
        scrape_enabled=True, catalog_stage='configured')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='content', endpoint='https://api.sejm.gov.pl/sejm/term10/votings',
        allowed_path_patterns=['/sejm/term10/votings/{int}', '/sejm/term10/votings/{int}/{int}'],
        terms_url='https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright',
        evidence={'basis': 'test'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + __import__('datetime').timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )
    monkeypatch.setattr('scraper.management.commands.run_sejm_vote_pilot.connection.vendor', 'postgresql')
    fetch = pytest.importorskip('unittest.mock').Mock(return_value=[
        {'term': 10, 'sitting': 1, 'votingNumber': 2},
    ])
    importer = pytest.importorskip('unittest.mock').Mock(return_value=True)
    monkeypatch.setattr('scraper.management.commands.run_sejm_vote_pilot.fetch_json', fetch)
    monkeypatch.setattr('scraper.management.commands.run_sejm_vote_pilot.import_voting', importer)

    call_command('run_sejm_vote_pilot', '--sitting=1', '--vote=2', '--apply', stdout=StringIO())

    fetch.assert_called_once_with('/sejm/term10/votings/1')
    importer.assert_called_once_with(10, 1, 2)
