"""Odtwarza pliki danych geokodera Teraz z pobranych granic PRG GUGiK.

Skrypt uruchamia się ręcznie (nie w harmonogramie), gdy GUGiK opublikuje nowy stan
granic. Potrzebuje bibliotek, które NIE należą do zależności działania aplikacji:
`pyshp` (odczyt plików .shp) i, tylko gdy granice są w układzie rzutowanym
(np. EPSG:2180), `pyproj`. Do działania aplikacji wystarcza `shapely`.

Przypięte wersje narzędzi do budowy (instaluj w osobnym środowisku, nie w `requirements.txt`):
`pyshp==3.1.9`, `pyproj==3.7.2`, `shapely>=2.1,<3` (jak w `requirements.txt`).
Uwaga: przy pierwszym zbudowaniu danych (stan 10.11.2026) nie zapisano, jakich wersji pyshp i pyproj
użyto; powyższe to wersje rozwiązane 18.11.2026 i nie były jeszcze sprawdzone na surowych plikach PRG.
Przy następnym budowaniu potwierdź, że skrypt działa na nich, i zapisz wynik tutaj.

Źródło: Państwowy Rejestr Granic (PRG), plik `00_jednostki_administracyjne.zip`
z https://opendata.geoportal.gov.pl (otwarte dane). Pobierz i rozpakuj go ręcznie do
dowolnego katalogu poza repozytorium (albo do `backend/teraz/geo/_zrodla/`, który
jest ignorowany przez git); w środku muszą być pliki
`A01_Granice_wojewodztw`, `A02_Granice_powiatow`, `A03_Granice_gmin` (.shp/.dbf/.prj).
Surowych plików PRG nie dodajemy do repozytorium.

Użycie (z katalogu `backend`):

    python -m teraz.geo.zbuduj_dane KATALOG_Z_SHP [--stan RRRR-MM-DD] [--tolerancja 0.002]

Wynik trafia do `teraz/geo/dane/`:
  - `teryt.json`: słownik województw, powiatów i gmin (kody, nazwy, rodzaje, środki);
  - `granice_powiaty.geojson`, `granice_wojewodztwa.geojson`: uproszczone granice (WGS84).

Granice powiatów upraszczamy jako jedną pokrywę (`shapely.coverage_simplify`), więc
sąsiednie powiaty zachowują wspólną granicę bez szczelin i nakładek. Granice
województw powstają jako suma uproszczonych powiatów, więc są z nimi zgodne.
Atrybucja: „Granice: GUGiK, Państwowy Rejestr Granic, stan 10.11.2026”.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DANE = Path(__file__).resolve().parent / "dane"
ZRODLO = "GUGiK, Państwowy Rejestr Granic (PRG), jednostki administracyjne, otwarte dane"
CYFRY = 4  # liczba miejsc po przecinku we współrzędnych (ok. 11 m)

RODZAJE_GMIN = {"1": "miejska", "2": "wiejska", "3": "miejsko-wiejska"}


def _wczytaj_warstwe(katalog: Path, nazwa: str, kodowanie: str = "utf-8"):
    import shapefile  # pyshp

    czytnik = shapefile.Reader(str(katalog / nazwa), encoding=kodowanie)
    wiersze = []
    for obiekt, rekord in zip(czytnik.shapes(), czytnik.records()):
        pola = rekord.as_dict()
        wiersze.append((pola["JPT_KOD_JE"], pola["JPT_NAZWA_"].strip(), obiekt.__geo_interface__))
    return wiersze


def _przeksztalcenie(katalog: Path, nazwa: str):
    """Zwraca funkcję przeliczającą geometrię na WGS84 albo None, gdy już jest geograficzna."""
    prj = (katalog / f"{nazwa}.prj").read_text(encoding="utf-8", errors="replace")
    if prj.lstrip().upper().startswith("GEOGCS"):
        # ETRS89 (tak jest w PRG) różni się od WGS84 o poniżej metra: pomijamy.
        return None
    from pyproj import Transformer
    from shapely.ops import transform

    t = Transformer.from_crs(prj, "EPSG:4326", always_xy=True)
    return lambda geom: transform(t.transform, geom)


def _geometrie(katalog: Path, nazwa: str):
    from shapely.geometry import shape

    przelicz = _przeksztalcenie(katalog, nazwa)
    wynik = []
    for kod, nazwa_jednostki, geo in _wczytaj_warstwe(katalog, nazwa):
        geom = shape(geo)
        if przelicz:
            geom = przelicz(geom)
        wynik.append((kod, nazwa_jednostki, geom))
    return wynik


def _zaokraglij(wsp: float) -> float:
    return round(wsp, CYFRY)


def _srodek(geom) -> list[float]:
    p = geom.representative_point()
    return [_zaokraglij(p.y), _zaokraglij(p.x)]


def _do_geojson(kod: str, nazwa: str, geom) -> dict:
    from shapely import set_precision
    from shapely.geometry import mapping

    geom = set_precision(geom, 10 ** -CYFRY)
    return {"type": "Feature", "properties": {"kod": kod, "nazwa": nazwa}, "geometry": mapping(geom)}


def _zapisz_geojson(sciezka: Path, cechy: list[dict], opis: str) -> None:
    pelne = {"type": "FeatureCollection", "name": opis, "features": cechy}
    sciezka.write_text(json.dumps(pelne, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def zbuduj(katalog: Path, stan: str, tolerancja: float) -> None:
    import shapely
    from shapely import coverage_is_valid, coverage_simplify, set_precision

    woj = _geometrie(katalog, "A01_Granice_wojewodztw")
    pow_ = _geometrie(katalog, "A02_Granice_powiatow")
    gm = _geometrie(katalog, "A03_Granice_gmin")
    assert (len(woj), len(pow_)) == (16, 380), f"nieoczekiwana liczba jednostek: {len(woj)}, {len(pow_)}"

    kody_woj = {k for k, _, _ in woj}
    kody_pow = {k for k, _, _ in pow_}
    assert all(k[:2] in kody_woj for k in kody_pow), "powiat bez województwa"
    assert all(k[:4] in kody_pow for k, _, _ in gm), "gmina bez powiatu"
    assert len({k for k, _, _ in gm}) == len(gm), "powtórzony kod gminy"
    assert all(k[-1] in RODZAJE_GMIN for k, _, _ in gm), "nieznany rodzaj gminy"

    # --- słownik ---
    slownik = {
        "zrodlo": ZRODLO,
        "stan": stan,
        "atrybucja": f"Granice: GUGiK, Państwowy Rejestr Granic, stan {date.fromisoformat(stan).strftime('%d.%m.%Y')}",
        "uklad": "WGS84 (dane PRG w ETRS89, różnica poniżej 1 m)",
        "opis": "Pola: wojewodztwa [kod, nazwa], powiaty [kod, nazwa, rodzaj, szer, dl], "
                "gminy [kod, nazwa, rodzaj, szer, dl]; szer i dl to punkt wewnątrz jednostki.",
        "wojewodztwa": [],
        "powiaty": [],
        "gminy": [],
    }
    for kod, nazwa, geom in sorted(woj):
        slownik["wojewodztwa"].append([kod, nazwa])
    for kod, nazwa, geom in sorted(pow_):
        grodzki = int(kod[2:]) >= 61
        czysta = re.sub(r"^powiat\s+", "", nazwa)
        slownik["powiaty"].append([kod, czysta, "grodzki" if grodzki else "ziemski", *_srodek(geom)])
    for kod, nazwa, geom in sorted(gm):
        slownik["gminy"].append([kod, nazwa, RODZAJE_GMIN[kod[-1]], *_srodek(geom)])

    # --- granice powiatów: jedna pokrywa, wspólne krawędzie ---
    kody = [k for k, _, _ in pow_]
    surowe = [g.buffer(0) if not g.is_valid else g for _, _, g in pow_]
    uproszczone = list(coverage_simplify(surowe, tolerancja))
    # ten sam rastr współrzędnych co w pliku wynikowym, żeby kontrola dotyczyła tego, co zapisujemy
    uproszczone = [set_precision(g, 10 ** -CYFRY) for g in uproszczone]
    poprawna = coverage_is_valid(uproszczone)
    zle = [kody[i] for i, g in enumerate(uproszczone) if not g.is_valid or g.is_empty]
    if zle:
        raise SystemExit(f"Niepoprawna geometria po uproszczeniu: {zle}")
    nazwy_pow = {k: re.sub(r'^powiat\s+', '', n) for k, n, _ in pow_}
    cechy_pow = [_do_geojson(k, nazwy_pow[k], g) for k, g in zip(kody, uproszczone)]

    # --- granice województw: suma uproszczonych powiatów ---
    cechy_woj = []
    for kod, nazwa, _ in sorted(woj):
        czesci = [g for k, g in zip(kody, uproszczone) if k[:2] == kod]
        suma = shapely.union_all(czesci)
        cechy_woj.append(_do_geojson(kod, nazwa, suma))

    DANE.mkdir(parents=True, exist_ok=True)
    (DANE / "teryt.json").write_text(
        "{\n" + ",\n".join(
            f'"{klucz}": ' + (json.dumps(wartosc, ensure_ascii=False) if not isinstance(wartosc, list)
                              else "[\n" + ",\n".join(json.dumps(w, ensure_ascii=False) for w in wartosc) + "\n]")
            for klucz, wartosc in slownik.items()
        ) + "\n}\n",
        encoding="utf-8",
    )
    _zapisz_geojson(DANE / "granice_powiaty.geojson", cechy_pow, "Granice powiatów (uproszczone), GUGiK PRG")
    _zapisz_geojson(DANE / "granice_wojewodztwa.geojson", cechy_woj, "Granice województw (uproszczone), GUGiK PRG")

    print("Województw:", len(woj), "powiatów:", len(pow_), "gmin:", len(gm))
    print("Rodzaje gmin:", dict(Counter(k[-1] for k, _, _ in gm)))
    print("Pokrywa powiatów poprawna (coverage_is_valid):", poprawna)
    for plik in sorted(DANE.glob("*")):
        print(f"{plik.name}: {plik.stat().st_size / 1024:.0f} KB")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("katalog", type=Path, help="katalog z plikami .shp/.dbf/.prj z PRG")
    parser.add_argument("--stan", default="2026-11-10", help="data stanu PRG (RRRR-MM-DD)")
    parser.add_argument("--tolerancja", type=float, default=0.002, help="tolerancja uproszczenia w stopniach")
    args = parser.parse_args(argv)
    zbuduj(args.katalog, args.stan, args.tolerancja)
    return 0


if __name__ == "__main__":
    sys.exit(main())
