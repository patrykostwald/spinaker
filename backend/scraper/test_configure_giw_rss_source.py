from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.configure_giw_rss_source import RSS_URL, SOURCE_URL, TERMS_URL


pytestmark = pytest.mark.django_db


def test_giw_rss_configuration_is_metadata_only_and_idempotent():
    args = ("--reviewed-by", "test", "--apply")
    call_command("configure_giw_rss_source", *args, stdout=StringIO())
    call_command("configure_giw_rss_source", *args, stdout=StringIO())

    source = Source.objects.get(url=SOURCE_URL)
    card = SourceAccessInstruction.objects.get(source=source)
    assert source.is_active and source.scrape_enabled and source.rss_url == RSS_URL
    assert card.channel == "rss" and card.allowed_scope == "metadata"
    assert card.terms_url == TERMS_URL and card.daily_request_cap == 24
    assert "acquisition time" in card.evidence["reuse_conditions"]
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
