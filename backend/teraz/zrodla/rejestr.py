from ..zbieranie import AdapterTestowy
from . import cert_pl, emsc, firms, gdacs, gios, imgw_hydro, imgw_meteo, pse_osp, rcb, usgs

ADAPTERY = {
    "teraz-testowy": AdapterTestowy,
    "rcb": rcb.AdapterRCB,
    "imgw_meteo": imgw_meteo.AdapterIMGWMeteo,
    "imgw_hydro": imgw_hydro.AdapterIMGWHydro,
    "gios": gios.AdapterGIOS,
    "firms": firms.AdapterFIRMS,
    "emsc": emsc.AdapterEMSC,
    "usgs": usgs.AdapterUSGS,
    "gdacs": gdacs.AdapterGDACS,
    "cert_pl": cert_pl.AdapterCERT,
    "pse_osp": pse_osp.AdapterPSE,
}

# Rodzaj łącza zaimplementowanych adapterów (pole Zrodlo.rodzaj_lacza). Migracja 0006 zapisuje te same wartości,
# a test_historia_zrodel pilnuje zgodności obu list.
RODZAJ_LACZA = {
    "teraz-testowy": "reczne",
    "rcb": "scraping",
    "imgw_meteo": "api",
    "imgw_hydro": "api",
    "gios": "api",
    "firms": "api",
    "emsc": "websocket",
    "usgs": "api",
    "gdacs": "rss",
    "cert_pl": "rss",
    "pse_osp": "rss",
}
