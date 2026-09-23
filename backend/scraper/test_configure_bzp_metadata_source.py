from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper.bzp_backfill import SEARCH_URL, SOURCE_URL


pytestmark = pytest.mark.django_db


def test_bzp_configuration_is_explicit_and_idempotent():
    call_command('configure_bzp_metadata_source', stdout=StringIO())
    assert not Source.objects.filter(url=SOURCE_URL).exists()

    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    source = Source.objects.get(url=SOURCE_URL)
    cards = SourceAccessInstruction.objects.filter(source=source, channel='api')
    assert source.is_active and source.scrape_enabled and source.catalog_stage == 'configured'
    assert cards.count() == 1 and cards.get().endpoint == SEARCH_URL
