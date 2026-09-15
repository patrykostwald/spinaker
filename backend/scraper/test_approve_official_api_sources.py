from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_command_only_plans_without_apply():
    output = StringIO()

    call_command('approve_official_api_sources', stdout=output)

    assert 'PLAN sejm' in output.getvalue()
    assert not Source.objects.exists()
    assert not SourceAccessInstruction.objects.exists()


@pytest.mark.django_db
def test_command_creates_one_current_official_voting_card():
    call_command('approve_official_api_sources', '--apply',
        '--evidence-url=https://api.sejm.gov.pl/sejm.html', '--reviewed-by=Test redakcyjny', stdout=StringIO())

    cards = SourceAccessInstruction.objects.filter(channel='api').order_by('endpoint')
    assert cards.count() == 1
    assert all(card.status == SourceAccessInstruction.Status.APPROVED for card in cards)
    assert all(card.allowed_scope == SourceAccessInstruction.Scope.CONTENT for card in cards)


@pytest.mark.django_db
def test_command_never_overrides_a_newer_suspension():
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej', url='https://api.sejm.gov.pl/sejm')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.SUSPENDED,
        channel=SourceAccessInstruction.Channel.API,
        endpoint='https://api.sejm.gov.pl/sejm/term10/votings', evidence={'reason': 'test'},
    )

    call_command('approve_official_api_sources', '--apply',
        '--evidence-url=https://api.sejm.gov.pl/sejm.html', '--reviewed-by=Test redakcyjny', stdout=StringIO())

    assert SourceAccessInstruction.objects.filter(source=source).count() == 1


@pytest.mark.django_db
def test_apply_refuses_to_invent_review_evidence():
    with pytest.raises(ValueError, match='evidence-url'):
        call_command('approve_official_api_sources', '--apply', stdout=StringIO())
