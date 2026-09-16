from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_eli_configuration_is_narrow_metadata_api_only():
    source = Source.objects.create(name="ELI", url="https://api.sejm.gov.pl/eli",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_eli_metadata_source", "--reviewed-by=test", "--apply", stdout=StringIO())
    source.refresh_from_db()
    card = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
    assert card.status == "approved"
    assert card.channel == "api" and card.allowed_scope == "metadata"
    assert card.endpoint.endswith("/eli/changes/acts")
    assert source.is_active and source.scrape_enabled and source.catalog_stage == "configured"


@pytest.mark.django_db
def test_eli_configuration_never_overrides_a_suspension():
    source = Source.objects.create(name="ELI", url="https://api.sejm.gov.pl/eli",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    SourceAccessInstruction.objects.create(source=source, version=1, status="suspended",
        channel="api", allowed_scope="metadata", endpoint="https://api.sejm.gov.pl/eli/changes/acts",
        evidence={"reason": "test"}, daily_request_cap=0)
    with pytest.raises(Exception):
        call_command("configure_eli_metadata_source", "--reviewed-by=test", "--apply", stdout=StringIO())
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
