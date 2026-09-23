"""Bounded metadata-only discovery for the official MSWiA news listing."""

from scraper.gov_metadata_listing import listing_cycle


SOURCE_URL = "https://www.gov.pl/web/mswia"


def mswia_listing_cycle():
    """Queue current MSWiA items; article processing remains in archive_batch."""
    return listing_cycle(SOURCE_URL)
