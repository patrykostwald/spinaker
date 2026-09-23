"""Shared bounded discovery for individually reviewed gov.pl listings."""

from news.models import Source
from scraper.gov_justice_archive import discover
from scraper.utils import HostRateLimited


OFFICIAL_GOV_LISTINGS = {
    "cyfryzacja": {
        "name": "Ministerstwo Cyfryzacji",
        "source_url": "https://www.gov.pl/web/cyfryzacja",
        "listing_url": "https://www.gov.pl/web/cyfryzacja/wiadomosci",
        "terms_url": "https://www.gov.pl/web/cyfryzacja/ponowne-wykorzystywanie",
    },
    "gis": {
        "name": "Główny Inspektorat Sanitarny",
        "source_url": "https://www.gov.pl/web/gis",
        "listing_url": "https://www.gov.pl/web/gis/wiadomosci",
        "terms_url": "https://www.gov.pl/web/gis/ponowne-wykorzystywanie2",
    },
    "gdos": {
        "name": "Generalna Dyrekcja Ochrony Środowiska",
        "source_url": "https://www.gov.pl/web/gdos",
        "listing_url": "https://www.gov.pl/web/gdos/aktualnosci",
        "terms_url": "https://www.gov.pl/web/gdos/ponowne-wykorzytanie-informacji",
    },
    "gios": {
        "name": "Główny Inspektorat Ochrony Środowiska",
        "source_url": "https://www.gov.pl/web/gios",
        "listing_url": "https://www.gov.pl/web/gios/wiadomosci",
        "terms_url": "https://www.gov.pl/web/gios/udostepnienie-informacji-o-srodowisku",
    },
    "gugik": {
        "name": "Główny Urząd Geodezji i Kartografii",
        "source_url": "https://www.gov.pl/web/gugik",
        "listing_url": "https://www.gov.pl/web/gugik/wiadomosci",
        "terms_url": "https://www.gov.pl/web/gugik/ponowne-wykorzystanie-informacji-sektora-publicznego",
    },
    "infrastruktura": {
        "name": "Ministerstwo Infrastruktury",
        "source_url": "https://www.gov.pl/web/infrastruktura",
        "listing_url": "https://www.gov.pl/web/infrastruktura/wiadomosci",
        "terms_url": "https://www.gov.pl/web/infrastruktura/ponowne-wykorzystanie-informacji-sektora-publicznego",
    },
    "kultura": {
        "name": "Ministerstwo Kultury i Dziedzictwa Narodowego",
        "source_url": "https://www.gov.pl/web/kultura",
        "listing_url": "https://www.gov.pl/web/kultura/wiadomosci",
        "terms_url": "https://www.gov.pl/web/kultura/ponowne-wykorzystywanie-informacji-sektora-publicznego",
    },
    "kowr": {
        "name": "Krajowy Ośrodek Wsparcia Rolnictwa",
        "source_url": "https://www.gov.pl/web/kowr",
        "listing_url": "https://www.gov.pl/web/kowr/wiadomosci",
        "terms_url": "https://www.gov.pl/web/kowr/ponowne-wykorzystywanie",
    },
    "kis": {
        "name": "Krajowa Informacja Skarbowa",
        "source_url": "https://www.gov.pl/web/kis",
        "listing_url": "https://www.gov.pl/web/kis/aktualnosci",
        "terms_url": "https://www.gov.pl/web/kis/ponowne-wykorzystanie-informacji-sektora-publicznego",
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
        "terms_url": "https://www.gov.pl/web/sprawiedliwosc/ponowne-wykorzystywanie",
    },
    "nauka": {
        "name": "Ministerstwo Nauki i Szkolnictwa Wyższego",
        "source_url": "https://www.gov.pl/web/nauka",
        "listing_url": "https://www.gov.pl/web/nauka/wiadomosci",
        "terms_url": "https://www.gov.pl/web/nauka/ponowne-wykorzystywanie-informacji-sektora-publicznego",
    },
    "paa": {
        "name": "Państwowa Agencja Atomistyki",
        "source_url": "https://www.gov.pl/web/paa",
        "listing_url": "https://www.gov.pl/web/paa/aktualnosci",
        "terms_url": "https://www.gov.pl/web/paa/ponowne-wykorzystanie-informacji-publicznej",
    },
    "prokuratoria": {
        "name": "Prokuratoria Generalna Rzeczypospolitej Polskiej",
        "source_url": "https://www.gov.pl/web/prokuratoria",
        "listing_url": "https://www.gov.pl/web/prokuratoria/aktualnosci",
        "terms_url": "https://www.gov.pl/web/prokuratoria/ponowne-wykorzystywanie-informacji-publicznych",
    },
    "ncbr": {
        "name": "Narodowe Centrum Badań i Rozwoju",
        "source_url": "https://www.gov.pl/web/ncbr",
        "listing_url": "https://www.gov.pl/web/ncbr/aktualnosci",
        "terms_url": "https://www.gov.pl/web/ncbr/ponowne-wykorzystywanie-informacji-sektora-publicznego",
    },
    "rozwoj": {
        "name": "Ministerstwo Rozwoju i Technologii",
        "source_url": "https://www.gov.pl/web/rozwoj-technologia",
        "listing_url": "https://www.gov.pl/web/rozwoj-technologia/wiadomosci",
        "terms_url": "https://www.gov.pl/web/rozwoj-technologia/uzyskaj-informacje-publiczna-do-ponownego-wykorzystania",
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
    "rodzina": {
        "name": "Ministerstwo Rodziny, Pracy i Polityki Społecznej",
        "source_url": "https://www.gov.pl/web/rodzina",
        "listing_url": "https://www.gov.pl/web/rodzina/wiadomosci",
        "terms_url": "https://www.gov.pl/web/rodzina/bip-zasady-ponownego-wykorzystywania-informacji-sektora-publicznego",
    },
    "rars": {
        "name": "Rządowa Agencja Rezerw Strategicznych",
        "source_url": "https://www.gov.pl/web/rars",
        "listing_url": "https://www.gov.pl/web/rars/wiadomosci",
        "terms_url": "https://www.gov.pl/web/rars/ponowne-wykorzystywanie-informacji-sektora-publicznego",
    },
    "sport": {
        "name": "Ministerstwo Sportu i Turystyki",
        "source_url": "https://www.gov.pl/web/sport",
        "listing_url": "https://www.gov.pl/web/sport/wiadomosci",
        "terms_url": "https://www.gov.pl/web/sport/uzyskaj-informacje-sektora-publicznego-do-ponownego-wykorzystania",
    },
    "zdrowie": {
        "name": "Ministerstwo Zdrowia",
        "source_url": "https://www.gov.pl/web/zdrowie",
        "listing_url": "https://www.gov.pl/web/zdrowie/wiadomosci",
    },
    "wug": {
        "name": "Wyższy Urząd Górniczy",
        "source_url": "https://www.gov.pl/web/wug",
        "listing_url": "https://www.gov.pl/web/wug/informacje-biezace",
        "terms_url": "https://www.gov.pl/web/wug/ponowne-wykorzystywanie-informacji-sektora-publicznego",
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
