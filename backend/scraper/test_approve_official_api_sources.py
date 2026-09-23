from io import StringIO
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

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
    assert cards.get().allowed_path_patterns == [
        '/sejm/term10/votings/search', '/sejm/term10/votings/{int}', '/sejm/term10/votings/{int}/{int}']


@pytest.mark.django_db
def test_command_issues_a_new_card_when_the_current_card_lacks_search_endpoint():
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm', catalog_stage='configured', is_active=True, scrape_enabled=True)
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API, allowed_scope=SourceAccessInstruction.Scope.CONTENT,
        endpoint='https://api.sejm.gov.pl/sejm/term10/votings',
        allowed_path_patterns=['/sejm/term10/votings/{int}', '/sejm/term10/votings/{int}/{int}'],
        terms_url='https://api.sejm.gov.pl/sejm.html', evidence={'reason': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', valid_until=timezone.now() + timedelta(days=1),
        minimum_interval_seconds=3, daily_request_cap=24,
    )

    call_command('approve_official_api_sources', '--apply',
        '--evidence-url=https://api.sejm.gov.pl/sejm.html', '--reviewed-by=Test redakcyjny', stdout=StringIO())

    assert SourceAccessInstruction.objects.filter(source=source).count() == 2
    assert SourceAccessInstruction.objects.get(source=source, version=2).allowed_path_patterns[0].endswith('/search')


@pytest.mark.django_db
def test_apply_configures_an_existing_official_candidate():
    source = Source.objects.create(name='Sejm Rzeczypospolitej Polskiej',
        url='https://api.sejm.gov.pl/sejm', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)

    call_command('approve_official_api_sources', '--apply',
        '--evidence-url=https://api.sejm.gov.pl/sejm.html', '--reviewed-by=Test redakcyjny', stdout=StringIO())

    source.refresh_from_db()
    assert source.catalog_stage == 'configured'
    assert source.is_active and source.scrape_enabled


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
