from unittest.mock import patch

import pytest

from news.models import Source
from scraper.mswia_listing import SOURCE_URL, mswia_listing_cycle


@pytest.mark.django_db
def test_mswia_cycle_requires_a_configured_source():
    assert mswia_listing_cycle() == {"status": "disabled", "queued": 0}


@pytest.mark.django_db
def test_mswia_cycle_uses_only_the_configured_source():
    source = Source.objects.create(name="MSWiA", url=SOURCE_URL, source_type="institution",
        is_active=True, scrape_enabled=True, catalog_stage="configured")
    with patch("scraper.mswia_listing.discover", return_value={"queued": 5, "page": 1, "last_page": 1}) as discover:
        assert mswia_listing_cycle() == {"status": "ok", "source_id": source.pk, "queued": 5, "page": 1, "last_page": 1}
    discover.assert_called_once_with(source.pk)
