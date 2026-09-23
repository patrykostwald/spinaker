from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import DatabaseError
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_preflight_is_read_only_and_reports_missing_source():
    output = StringIO()
    before = Source.objects.count(), SourceAccessInstruction.objects.count()

    call_command('sejm_pilot_preflight', stdout=output)

    assert (Source.objects.count(), SourceAccessInstruction.objects.count()) == before
    assert 'BLOKER: Brak skonfigurowanego źródła API Sejmu.' in output.getvalue()
    assert 'NIE_GOTOWY_DO_PILOTA' in output.getvalue()


@pytest.mark.django_db
def test_preflight_recognises_a_complete_sejm_card(monkeypatch):
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API,
        allowed_scope=SourceAccessInstruction.Scope.CONTENT,
        endpoint='https://api.sejm.gov.pl/sejm/term10/votings',
        terms_url='https://api.sejm.gov.pl/sejm.html', evidence={'url': 'https://api.sejm.gov.pl/sejm.html'},
        reviewed_at=timezone.now(), reviewed_by='Test redakcyjny', valid_until=timezone.now() + timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24)
    monkeypatch.setattr('scraper.management.commands.sejm_pilot_preflight.connection.vendor', 'postgresql')
    output = StringIO()

    call_command('sejm_pilot_preflight', stdout=output)

    assert 'GOTOWY_DO_PILOTA' in output.getvalue()
    assert 'wyszukiwanie, listę posiedzenia i szczegóły głosowania' in output.getvalue()


@pytest.mark.django_db
def test_preflight_reports_an_outdated_database_schema(monkeypatch):
    monkeypatch.setattr(
        'scraper.management.commands.sejm_pilot_preflight.SourceAccessInstruction.objects.filter',
        lambda *args, **kwargs: (_ for _ in ()).throw(DatabaseError('missing column')),
    )
    Source.objects.create(name='Sejm Rzeczypospolitej Polskiej', url='https://api.sejm.gov.pl/sejm')
    output = StringIO()

    call_command('sejm_pilot_preflight', stdout=output)

    assert 'starszy schemat kart dostępu' in output.getvalue()
