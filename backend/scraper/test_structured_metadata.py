from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper import structured_metadata


@pytest.mark.django_db
@pytest.mark.parametrize("key,url,endpoint", [
    ("dane_gov", "https://dane.gov.pl", "https://api.dane.gov.pl/1.4/datasets"),
    ("gus_bdl", "https://stat.gov.pl", "https://bdl.stat.gov.pl/api/v1/subjects"),
])
def test_configuration_is_exact_metadata_only(key, url, endpoint):
    source = Source.objects.create(name=key, url=url, is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_structured_metadata_sources", key, "--reviewed-by=test", "--apply", stdout=StringIO())
    source.refresh_from_db()
    card = source.access_instructions.order_by("-version").first()
    assert card.status == "approved" and card.channel == "api"
    assert card.allowed_scope == "metadata" and card.endpoint == endpoint
    assert card.daily_request_cap == 24
    assert source.is_active and source.scrape_enabled and source.catalog_stage == "configured"


@pytest.mark.django_db
def test_preflight_checks_contract_without_persisting_provider_records(monkeypatch):
    source = Source.objects.create(name="dane", url="https://dane.gov.pl", is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_structured_metadata_sources", "dane_gov", "--reviewed-by=test", "--apply", stdout=StringIO())
    monkeypatch.setattr(structured_metadata, "fetch_feed", lambda *args, **kwargs: b'{"data": []}')
    result = structured_metadata.preflight("dane_gov")
    assert result["contract"] == "ok"
    assert source.articles.count() == 0


@pytest.mark.django_db
def test_preflight_rejects_wrong_contract(monkeypatch):
    Source.objects.create(name="dane", url="https://dane.gov.pl", is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_structured_metadata_sources", "dane_gov", "--reviewed-by=test", "--apply", stdout=StringIO())
    monkeypatch.setattr(structured_metadata, "fetch_feed", lambda *args, **kwargs: b'{"unexpected": []}')
    with pytest.raises(structured_metadata.StructuredMetadataPreflightError, match="unexpected_json_contract"):
        structured_metadata.preflight("dane_gov")
