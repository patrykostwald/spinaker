from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.configure_nik_rss_source import SOURCE_URL


pytestmark = pytest.mark.django_db


def test_nik_rss_configuration_is_metadata_only_and_recovers_its_candidate():
    source = Source.objects.create(name="NIK", url=SOURCE_URL, rss_url=SOURCE_URL,
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_nik_rss_source", "--reviewed-by=test", "--apply", stdout=StringIO())
    source.refresh_from_db()
    card = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
    assert card.status == "approved"
    assert card.channel == "rss" and card.allowed_scope == "metadata"
    assert card.endpoint == SOURCE_URL and card.allowed_path_patterns == ["/rss"]
    assert source.is_active and source.scrape_enabled and source.catalog_stage == "configured"


def test_nik_rss_configuration_refuses_to_revive_a_suspension():
    source = Source.objects.create(name="NIK", url=SOURCE_URL, rss_url=SOURCE_URL,
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    SourceAccessInstruction.objects.create(source=source, version=1, status="suspended", channel="rss",
        allowed_scope="metadata", endpoint=SOURCE_URL, evidence={"reason": "test"}, daily_request_cap=0)
    with pytest.raises(Exception):
        call_command("configure_nik_rss_source", "--reviewed-by=test", "--apply", stdout=StringIO())
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
