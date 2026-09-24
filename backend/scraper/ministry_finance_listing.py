"""Bounded metadata-only discovery for the official Ministry of Finance listing."""

from scraper.gov_metadata_listing import listing_cycle


SOURCE_URL = "https://www.gov.pl/web/finanse"


def ministry_finance_listing_cycle():
    return listing_cycle(SOURCE_URL)
