"""Uproszczone granice powiatów i województw (shapely, indeks STRtree).

Dane: `dane/granice_powiaty.geojson` i `dane/granice_wojewodztwa.geojson`, WGS84,
upraszczane jako jedna pokrywa (sąsiednie powiaty mają wspólną granicę), tolerancja
ok. 0,002° (ok. 150-220 m). Punkt leżący bliżej granicy niż kilkaset metrów może trafić
do sąsiedniego powiatu. Punkt poza wielokątami dostaje najbliższy powiat tylko w promieniu
`TOLERANCJA_M` metrów (liczonym w metrach, nie w stopniach). Granice gmin nie są przechowywane.

Granice: GUGiK, Państwowy Rejestr Granic, stan 10.11.2026.

Kolejność współrzędnych w całym module: szerokość, długość (`lat`, `lon`);
prostokąt `bbox` to (zachód, południe, wschód, północ) = (min_lon, min_lat, max_lon, max_lat),
jak w GeoJSON.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from functools import lru_cache

from .slownik import DANE, BladDanych, _wczytaj_json, jednostka

# Punkt tuż poza uproszczonym wielokątem (błąd uproszczenia do ok. 220 m, a nad Bałtykiem brzeg)
# przypisujemy najbliższemu powiatowi, jeśli leży nie dalej niż tyle metrów od jego granicy.
# Dalej niż to (np. po drugiej stronie granicy państwa) wynik to `None`.
TOLERANCJA_M = 250
_M_NA_STOPIEN = 111_195


class _Warstwa:
    def __init__(self, nazwa_pliku: str):
        from shapely import STRtree, prepare
        from shapely.geometry import shape

        dane = _wczytaj_json(DANE / nazwa_pliku)  # brak lub uszkodzony plik: ten sam czytelny `BladDanych` co w `sprawdz_dane`
        try:
            cechy = dane["features"]
            self.kody: list[str] = [c["properties"]["kod"] for c in cechy]
            self.geometrie = [shape(c["geometry"]) for c in cechy]
            for g in self.geometrie:
                prepare(g)
            self.drzewo = STRtree(self.geometrie)
            self.indeks = {kod: i for i, kod in enumerate(self.kody)}
        except Exception as blad:  # zły układ, zły typ, błąd shapely (GEOSException, ShapelyError): to błąd danych
            raise BladDanych(f"{nazwa_pliku}: zły układ danych ({type(blad).__name__}: {blad})") from blad


@lru_cache(maxsize=None)
def _warstwa(nazwa_pliku: str) -> _Warstwa:
    return _Warstwa(nazwa_pliku)


def _powiaty() -> _Warstwa:
    return _warstwa("granice_powiaty.geojson")


def _wojewodztwa() -> _Warstwa:
    return _warstwa("granice_wojewodztwa.geojson")


def _sprawdz_wspolrzedne(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Współrzędne poza zakresem: lat={lat}, lon={lon}")


def _odleglosc_m(lat: float, lon: float, lat2: float, lon2: float) -> float:
    """Odległość w metrach w lokalnym układzie (długość geograficzna skalowana cosinusem szerokości)."""
    dy = (lat2 - lat) * _M_NA_STOPIEN
    dx = (lon2 - lon) * _M_NA_STOPIEN * math.cos(math.radians((lat + lat2) / 2))
    return math.hypot(dx, dy)


def w_ktorym_powiecie(lat: float, lon: float, tolerancja_m: float = TOLERANCJA_M) -> str | None:
    """Kod powiatu (4 cyfry), w którym leży punkt; `None`, gdy punkt jest poza Polską.

    Punkt na wspólnej granicy dwóch powiatów dostaje powiat o niższym kodzie (wynik jest
    deterministyczny). Punkt tuż poza granicą (nie dalej niż `tolerancja_m` metrów, mierzone
    w lokalnym układzie metrycznym, a nie w stopniach) dostaje najbliższy powiat; dalej: `None`.
    """
    from shapely.geometry import Point, box
    from shapely.ops import nearest_points

    _sprawdz_wspolrzedne(lat, lon)
    warstwa = _powiaty()
    punkt = Point(lon, lat)
    trafione = warstwa.drzewo.query(punkt, predicate="intersects")
    if len(trafione):
        return min(warstwa.kody[i] for i in trafione)
    if tolerancja_m > 0:
        # kandydaci z prostokąta o boku zależnym od szerokości (stopień długości jest krótszy niż szerokości)
        dlat = tolerancja_m / _M_NA_STOPIEN
        dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
        kandydaci = warstwa.drzewo.query(box(lon - dlon, lat - dlat, lon + dlon, lat + dlat))
        najlepszy: tuple[float, str] | None = None
        for i in kandydaci:
            bliski = nearest_points(warstwa.geometrie[int(i)], punkt)[0]
            odleglosc = _odleglosc_m(lat, lon, bliski.y, bliski.x)
            if odleglosc <= tolerancja_m and (najlepszy is None or (odleglosc, warstwa.kody[int(i)]) < najlepszy):
                najlepszy = (odleglosc, warstwa.kody[int(i)])
        if najlepszy:
            return najlepszy[1]
    return None


def w_ktorym_wojewodztwie(lat: float, lon: float, tolerancja_m: float = TOLERANCJA_M) -> str | None:
    """Kod województwa (2 cyfry) dla punktu; `None`, gdy punkt jest poza Polską."""
    powiat = w_ktorym_powiecie(lat, lon, tolerancja_m)
    return powiat[:2] if powiat else None


def geometria(kod: str):
    """Uproszczona geometria shapely dla kodu województwa (2 cyfry) albo powiatu (4 cyfry).

    Dla kodu gminy (7 cyfr) zwraca geometrię jej powiatu: gmin nie przechowujemy.
    """
    jednostka(kod)
    if len(kod) == 2:
        warstwa = _wojewodztwa()
    else:
        warstwa = _powiaty()
        kod = kod[:4]
    return warstwa.geometrie[warstwa.indeks[kod]]


def przecina(teryt: str | Iterable[str], bbox: tuple[float, float, float, float]) -> bool:
    """Czy prostokąt `bbox` (zachód, południe, wschód, północ) przecina jednostkę (lub którąkolwiek z listy).

    Kod województwa i powiatu liczony jest na uproszczonych granicach. Kod gminy jest
    sprawdzany po granicy jej powiatu (zawyża wynik: prawda dla całego powiatu).
    """
    from shapely.geometry import box

    zachod, poludnie, wschod, polnoc = bbox
    if not (zachod <= wschod and poludnie <= polnoc):
        raise ValueError(f"Nieprawidłowy prostokąt (zachód, południe, wschód, północ): {bbox}")
    _sprawdz_wspolrzedne(poludnie, zachod)
    _sprawdz_wspolrzedne(polnoc, wschod)
    prostokat = box(zachod, poludnie, wschod, polnoc)
    kody = [teryt] if isinstance(teryt, str) else list(teryt)
    return any(geometria(kod).intersects(prostokat) for kod in kody)
