from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_command_only_plans_without_apply():
    output = StringIO()

    call_command('approve_official_api_sources', stdout=output)

    assert 'PLAN sejm' in output.getvalue()
    assert not SourceAccessInstruction.objects.exists()


@pytest.mark.django_db
def test_command_creates_two_current_official_api_cards():
    call_command('approve_official_api_sources', '--apply', stdout=StringIO())

    cards = SourceAccessInstruction.objects.filter(channel='api').order_by('endpoint')
    assert cards.count() == 2
    assert all(card.status == SourceAccessInstruction.Status.APPROVED for card in cards)
    assert all(card.allowed_scope == SourceAccessInstruction.Scope.CONTENT for card in cards)


@pytest.mark.django_db
def test_command_never_overrides_a_newer_suspension():
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej', url='https://api.sejm.gov.pl/sejm')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.SUSPENDED,
        channel=SourceAccessInstruction.Channel.API,
        endpoint='https://api.sejm.gov.pl/sejm', evidence={'reason': 'test'},
    )

    call_command('approve_official_api_sources', '--apply', stdout=StringIO())

    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
