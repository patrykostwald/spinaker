"""Shared bounded discovery for individually reviewed gov.pl listings."""

from news.models import Source
from scraper.gov_justice_archive import discover
from scraper.utils import HostRateLimited


OFFICIAL_GOV_LISTINGS = {
    "infrastruktura": {
        "name": "Ministerstwo Infrastruktury",
        "source_url": "https://www.gov.pl/web/infrastruktura",
        "listing_url": "https://www.gov.pl/web/infrastruktura/wiadomosci",
    },
    "mon": {
        "name": "Ministerstwo Obrony Narodowej",
        "source_url": "https://www.gov.pl/web/obrona-narodowa",
        "listing_url": "https://www.gov.pl/web/obrona-narodowa/wiadomosci",
    },
    "sprawiedliwosc": {
        "name": "Ministerstwo Sprawiedliwości",
        "source_url": "https://www.gov.pl/web/sprawiedliwosc",
        "listing_url": "https://www.gov.pl/web/sprawiedliwosc/wiadomosci",
    },
    "klimat": {
        "name": "Ministerstwo Klimatu i Środowiska",
        "source_url": "https://www.gov.pl/web/klimat",
        "listing_url": "https://www.gov.pl/web/klimat/wiadomosci",
    },
    "edukacja": {
        "name": "Ministerstwo Edukacji Narodowej",
        "source_url": "https://www.gov.pl/web/edukacja",
        "listing_url": "https://www.gov.pl/web/edukacja/wiadomosci",
    },
    "map": {
        "name": "Ministerstwo Aktywów Państwowych",
        "source_url": "https://www.gov.pl/web/aktywa-panstwowe",
        "listing_url": "https://www.gov.pl/web/aktywa-panstwowe/wiadomosci",
    },
    "msz": {
        "name": "Ministerstwo Spraw Zagranicznych",
        "source_url": "https://www.gov.pl/web/dyplomacja",
        "listing_url": "https://www.gov.pl/web/dyplomacja/aktualnosci",
    },
    "rolnictwo": {
        "name": "Ministerstwo Rolnictwa i Rozwoju Wsi",
        "source_url": "https://www.gov.pl/web/rolnictwo",
        "listing_url": "https://www.gov.pl/web/rolnictwo/wiadomosci",
    },
    "zdrowie": {
        "name": "Ministerstwo Zdrowia",
        "source_url": "https://www.gov.pl/web/zdrowie",
        "listing_url": "https://www.gov.pl/web/zdrowie/wiadomosci",
    },
}


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


def named_listing_cycle(key):
    return listing_cycle(OFFICIAL_GOV_LISTINGS[key]["source_url"])
