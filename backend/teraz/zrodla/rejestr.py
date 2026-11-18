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
