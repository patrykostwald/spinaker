import re

from ..models import Wpis
from ..zbieranie import Adapter
from .kanaly import GDACS, GEO, parsuj_kanal
from .wspolne import punkt

URL_GDACS = "https://www.gdacs.org/xml/rss.xml"
KRAJE = {
    alias: kraj
    for kraj, aliasy in (
        ("Polska", "pol/pl/poland/polska"),
        ("Niemcy", "deu/de/germany"),
        ("Czechy", "cze/cz/czech republic/czechia"),
        ("Słowacja", "svk/sk/slovakia"),
        ("Ukraina", "ukr/ua/ukraine"),
        ("Białoruś", "blr/by/belarus"),
        ("Litwa", "ltu/lt/lithuania"),
        ("Rosja", "rus/ru/russia/russian federation"),
    )
    for alias in aliasy.split("/")
}


def obszar(el):
    kraje = el.findall(GDACS + "country")
    dotkniete = el.find(GDACS + "affectedcountries")
    if dotkniete is not None:
        kraje += list(dotkniete)
    if not kraje:
        raise ValueError
    nazwy = {wartosc.strip().casefold() for kraj in kraje for wartosc in
             [kraj.get("iso3", ""), kraj.get("value", ""), *re.split(r"[,;]", kraj.text or "")] if wartosc.strip()}
    kraje_sasiadujace = sorted({KRAJE[nazwa] for nazwa in nazwy if nazwa in KRAJE})
    if not kraje_sasiadujace:
        return None
    miejsce = ", ".join(kraje_sasiadujace)
    wspolrzedne = el.findtext(GEO + "point")
    if wspolrzedne:
        lat, lon = wspolrzedne.split()
        return {"miejsce": miejsce, **punkt(lat, lon)}
    return {"miejsce": miejsce, "dokladnosc": Wpis.Dokladnosc.KRAJ, "pewnosc_lokalizacji": 1}


class AdapterGDACS(Adapter):
    minimalny_odstep = 60

    def parsuj(self, odpowiedz):
        return parsuj_kanal(odpowiedz, "GDACS", wybierz=obszar)
