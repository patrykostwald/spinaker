"""Bounded metadata-only discovery for the official MSWiA news listing."""

from news.models import Source
from scraper.gov_justice_archive import discover
from scraper.utils import HostRateLimited


SOURCE_URL = "https://www.gov.pl/web/mswia"


def mswia_listing_cycle():
    """Queue current MSWiA items; article processing remains in archive_batch."""
    source = Source.objects.filter(
        url=SOURCE_URL, is_active=True, scrape_enabled=True, catalog_stage="configured"
    ).first()
    if source is None:
        return {"status": "disabled", "queued": 0}
    try:
        result = discover(source.pk)
    except HostRateLimited as exc:
        return {"status": "deferred", "queued": 0,
                "retry_after_seconds": round(exc.retry_after_seconds, 1)}
    return {"status": "ok", "source_id": source.pk, **result}
