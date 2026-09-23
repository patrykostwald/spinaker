from unittest.mock import patch

import pytest

from news.models import Source
from scraper.gov_metadata_listing import OFFICIAL_GOV_LISTINGS, named_listing_cycle


@pytest.mark.django_db
@pytest.mark.parametrize("key", ["cyfryzacja", "edukacja", "gdos", "gis", "gios", "infrastruktura", "kis", "klimat", "kowr", "kultura", "map", "mon", "msz", "nauka", "ncbr", "rars", "rolnictwo", "rodzina", "rozwoj", "sprawiedliwosc", "sport", "zdrowie"])
def test_named_gov_cycle_requires_its_configured_source(key):
    assert named_listing_cycle(key) == {"status": "disabled", "queued": 0}


@pytest.mark.django_db
def test_named_gov_cycle_uses_only_whitelisted_map_source():
    item = OFFICIAL_GOV_LISTINGS["map"]
    source = Source.objects.create(name=item["name"], url=item["source_url"], source_type="institution",
        is_active=True, scrape_enabled=True, catalog_stage="configured")
    with patch("scraper.gov_metadata_listing.discover", return_value={"queued": 4, "page": 1, "last_page": 1}) as discover:
        assert named_listing_cycle("map") == {"status": "ok", "source_id": source.pk, "queued": 4, "page": 1, "last_page": 1}
    discover.assert_called_once_with(source.pk)
