from datetime import datetime, timezone
from urllib.parse import urlencode

from ..zbieranie import Adapter, BladFormatu
from .wspolne import POLSKA, czysty_tekst, json_dane, punkt, w_obszarze, wpis

URL_USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
ZACHOD, POLUDNIE, WSCHOD, POLNOC = POLSKA
PARAMETRY = urlencode({
    "format": "geojson", "minlongitude": ZACHOD, "minlatitude": POLUDNIE, "maxlongitude": WSCHOD,
    "maxlatitude": POLNOC, "nodata": 204, "orderby": "time",
})


class AdapterUSGS(Adapter):
    def przeprowadz(self, cykl):
        cykl.wykonaj(f"{self.zrodlo.adres}?{PARAMETRY}")

    def parsuj(self, odpowiedz):
        if odpowiedz.status == 204 and not odpowiedz.tresc:
            return []
        try:
            dane = json_dane(odpowiedz)
            if dane["type"] != "FeatureCollection" or not isinstance(dane["features"], list):
                raise ValueError
            wynik = []
            for obiekt in dane["features"]:
                if obiekt["type"] != "Feature" or obiekt["geometry"]["type"] != "Point":
                    raise ValueError
                lon, lat, *_ = obiekt["geometry"]["coordinates"]
                polozenie = punkt(lat, lon)
                if w_obszarze(polozenie, POLSKA):
                    pola = obiekt["properties"]
                    czas = datetime.fromtimestamp(pola["time"] / 1000, tz=timezone.utc)
                    miejsce = czysty_tekst(pola.get("place") or "", 200)
                    wynik.append(wpis(obiekt["id"], pola["title"], pola["url"], czas, miejsce=miejsce, **polozenie))
            return wynik
        except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
            raise BladFormatu("USGS: nieoczekiwany format katalogu GeoJSON.") from exc
