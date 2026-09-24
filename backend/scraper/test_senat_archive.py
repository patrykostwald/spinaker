from unittest.mock import patch

import pytest

from news.models import Source, SourceAccessInstruction
from scraper.senat_archive import ARTICLE_RE, LISTING_URL, SOURCE_URL, discover_senat


@pytest.mark.django_db
def test_senat_discovery_is_disabled_without_a_configured_source():
    assert discover_senat() == {"status": "disabled", "queued": 0}


def test_senat_listing_accepts_only_own_article_urls():
    raw = b'''<a href="https://www.senat.gov.pl/aktualnoscilista/art,12,wlasny-wpis.html">a</a>
    https://www.senat.gov.pl/aktualnoscilista/page,2.html
    https://www.senat.gov.pl/inne/art,13,nie-ten-dzial.html'''
    assert ARTICLE_RE.findall(raw.decode()) == ["https://www.senat.gov.pl/aktualnoscilista/art,12,wlasny-wpis.html"]
