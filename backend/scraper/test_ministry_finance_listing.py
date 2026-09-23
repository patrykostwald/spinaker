from unittest.mock import patch

import pytest

from news.models import Source
from scraper.ministry_finance_listing import SOURCE_URL, ministry_finance_listing_cycle


@pytest.mark.django_db
def test_finance_cycle_requires_a_configured_source():
    assert ministry_finance_listing_cycle() == {"status": "disabled", "queued": 0}


@pytest.mark.django_db
def test_finance_cycle_uses_only_the_configured_source():
    source = Source.objects.create(name="MF", url=SOURCE_URL, source_type="institution",
        is_active=True, scrape_enabled=True, catalog_stage="configured")
    with patch("scraper.gov_metadata_listing.discover", return_value={"queued": 3, "page": 1, "last_page": 1}) as discover:
        assert ministry_finance_listing_cycle() == {"status": "ok", "source_id": source.pk, "queued": 3, "page": 1, "last_page": 1}
    discover.assert_called_once_with(source.pk)
