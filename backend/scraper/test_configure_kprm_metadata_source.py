from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.configure_kprm_metadata_source import SOURCE_URL, TERMS_URL


pytestmark = pytest.mark.django_db


def test_kprm_pilot_is_metadata_only_and_recovers_catalog_candidate():
    source = Source.objects.create(name='KPRM', url=SOURCE_URL, catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    call_command('configure_kprm_metadata_source', '--reviewed-by=test', '--apply', stdout=StringIO())
    source.refresh_from_db()
    card = SourceAccessInstruction.objects.get(source=source)
    assert card.channel == 'html' and card.allowed_scope == 'metadata'
    assert card.endpoint == 'https://www.gov.pl/web/premier'
    assert card.terms_url == TERMS_URL and card.daily_request_cap == 24
    assert source.is_active and source.scrape_enabled and source.catalog_stage == 'configured'


def test_kprm_pilot_refuses_to_override_suspended_card():
    source = Source.objects.create(name='KPRM', url=SOURCE_URL, catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    SourceAccessInstruction.objects.create(source=source, version=1, status='suspended', channel='html',
        allowed_scope='metadata', endpoint='https://www.gov.pl/web/premier', evidence={'reason': 'test'})
    with pytest.raises(Exception):
        call_command('configure_kprm_metadata_source', '--apply', stdout=StringIO())
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
