"""Shared bounded discovery for individually reviewed gov.pl listings."""

from news.models import Source
from scraper.gov_justice_archive import discover
from scraper.utils import HostRateLimited


def listing_cycle(source_url):
    source = Source.objects.filter(
        url=source_url, is_active=True, scrape_enabled=True, catalog_stage="configured"
    ).first()
    if source is None:
        return {"status": "disabled", "queued": 0}
    try:
        result = discover(source.pk)
    except HostRateLimited as exc:
        return {"status": "deferred", "queued": 0,
                "retry_after_seconds": round(exc.retry_after_seconds, 1)}
    return {"status": "ok", "source_id": source.pk, **result}
