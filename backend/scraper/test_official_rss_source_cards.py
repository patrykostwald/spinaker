import pytest

from news.models import SourceAccessInstruction
from scraper.management.commands.configure_giw_rss_source import (
    RSS_URL as GIW_RSS_URL,
    TERMS_URL as GIW_TERMS_URL,
    configure as configure_giw,
)
from scraper.management.commands.configure_ure_rss_source import (
    RSS_URL as URE_RSS_URL,
    TERMS_URL as URE_TERMS_URL,
    configure as configure_ure,
)


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("configure", "rss_url", "terms_url", "name"),
    [
        (configure_ure, URE_RSS_URL, URE_TERMS_URL, "Urząd Regulacji Energetyki"),
        (configure_giw, GIW_RSS_URL, GIW_TERMS_URL, "Główny Inspektorat Weterynarii"),
    ],
)
def test_official_rss_card_is_metadata_only_and_idempotent(configure, rss_url, terms_url, name):
    source, first_card = configure("test-redakcja", valid_days=30, daily_cap=24)
    again_source, again_card = configure("test-redakcja", valid_days=30, daily_cap=24)

    assert source.pk == again_source.pk
    assert first_card.pk == again_card.pk
    assert source.name == name
    assert source.is_active and source.scrape_enabled
    assert source.catalog_stage == "configured"
    assert source.rss_url == rss_url

    cards = SourceAccessInstruction.objects.filter(source=source)
    assert cards.count() == 1
    card = cards.get()
    assert card.status == SourceAccessInstruction.Status.APPROVED
    assert card.channel == SourceAccessInstruction.Channel.RSS
    assert card.allowed_scope == SourceAccessInstruction.Scope.METADATA
    assert card.endpoint == rss_url
    assert card.terms_url == terms_url
    assert card.daily_request_cap == 24
    assert {"article HTML", "images", "video", "full-text snapshots"}.issubset(card.evidence["excluded"])
