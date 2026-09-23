import pytest

from news.models import SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.management.commands.configure_uokik_sudop_source import ALLOWED_PATHS, ENDPOINT, TERMS_URL, configure
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
    assert card.allowed_path_patterns == ALLOWED_PATHS
    assert card.terms_url == TERMS_URL
    assert card.allowed_scope == SourceAccessInstruction.Scope.METADATA
    assert card.minimum_interval_seconds == 4 and card.daily_request_cap == 120
    assert "training" in card.evidence["excluded"]
    assert approved_instruction(source, "api", API + "/api/przypadki-pomocy?strona=1") == card
    assert approved_instruction(source, "api", API + "/api/kolejka/q-1") == card
    assert approved_instruction(source, "api", API + "/api/wynik/r_1?csv=false") == card
    assert approved_instruction(source, "api", API + "/api/other-endpoint") is None


def test_sudop_configuration_replaces_an_old_too_narrow_card():
    source, old_card = configure("test-redakcja", valid_days=30, daily_cap=120)
    old_card.allowed_path_patterns = ["/sudop-api/api"]
    old_card.save(update_fields=["allowed_path_patterns"])

    _, current_card = configure("test-redakcja", valid_days=30, daily_cap=120)

    assert current_card.pk != old_card.pk
    assert current_card.version == old_card.version + 1
    assert current_card.allowed_path_patterns == ALLOWED_PATHS
