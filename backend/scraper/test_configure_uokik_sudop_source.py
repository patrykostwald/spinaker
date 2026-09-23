import pytest

from news.models import SourceAccessInstruction
from scraper.management.commands.configure_uokik_sudop_source import ENDPOINT, TERMS_URL, configure
from scraper.uokik_sudop import API


pytestmark = pytest.mark.django_db


def test_sudop_card_is_metadata_only_idempotent_and_does_not_enable_the_pilot_flag():
    source, card = configure("test-redakcja", valid_days=30, daily_cap=120)
    again_source, again_card = configure("test-redakcja", valid_days=30, daily_cap=120)

    assert source.pk == again_source.pk
    assert card.pk == again_card.pk
    assert source.url == API and source.is_active and source.scrape_enabled
    assert source.catalog_stage == "configured"
    assert SourceAccessInstruction.objects.filter(source=source).count() == 1
    assert card.endpoint == ENDPOINT
    assert card.terms_url == TERMS_URL
    assert card.allowed_scope == SourceAccessInstruction.Scope.METADATA
    assert card.minimum_interval_seconds == 4 and card.daily_request_cap == 120
    assert "training" in card.evidence["excluded"]
