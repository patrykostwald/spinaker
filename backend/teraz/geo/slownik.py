"""Słownik TERYT (województwa, powiaty, gminy) z plików `dane/teryt.json`.

Kody: województwo 2 cyfry, powiat 4 cyfry (pierwsze dwie to województwo), gmina 7 cyfr
(pierwsze cztery to powiat, ostatnia cyfra to rodzaj gminy). Powiaty o numerach od 61
to miasta na prawach powiatu (grodzkie).

Dane wczytują się raz na proces (pamięć modułu).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DANE = Path(__file__).resolve().parent / "dane"

WOJEWODZTWO = "wojewodztwo"
POWIAT = "powiat"
GMINA = "gmina"
DLUGOSC_KODU = {WOJEWODZTWO: 2, POWIAT: 4, GMINA: 7}


@dataclass(frozen=True, slots=True)
class Jednostka:
    kod: str
    nazwa: str  # mianownik bez przedrostka: „lubelskie”, „włodawski”, „Chełm”, „Mogilany”
    poziom: str  # WOJEWODZTWO | POWIAT | GMINA
    rodzaj: str  # powiat: „ziemski”/„grodzki”; gmina: „miejska”/„wiejska”/„miejsko-wiejska”; woj.: ""
    szer: float | None = None  # punkt wewnątrz jednostki (nie środek ciężkości)
    dl: float | None = None

    @property
    def kod_wojewodztwa(self) -> str:
        return self.kod[:2]

    @property
    def kod_powiatu(self) -> str | None:
        return self.kod[:4] if self.poziom != WOJEWODZTWO else None

    @property
    def grodzka(self) -> bool:
        """Miasto na prawach powiatu (powiat grodzki albo jego jedyna gmina)."""
        return self.poziom != WOJEWODZTWO and int(self.kod[2:4]) >= 61

    @property
    def miejska(self) -> bool:
        return self.poziom == GMINA and self.rodzaj in ("miejska", "miejsko-wiejska")


class BladDanych(RuntimeError):
    """Uszkodzony lub niepełny plik danych geokodera (`dane/`). Komunikat mówi, który plik i co jest nie tak."""


_RODZAJE_POWIATU = ("ziemski", "grodzki")
_RODZAJE_GMINY = {"1": "miejska", "2": "wiejska", "3": "miejsko-wiejska"}


class Slownik:
    def __init__(self, surowe: dict):
        try:
            self.stan: str = surowe["stan"]
            self.atrybucja: str = surowe["atrybucja"]
            self.zrodlo: str = surowe["zrodlo"]
            self.jednostki: dict[str, Jednostka] = {}

            def dodaj(jednostka: Jednostka) -> None:
                if jednostka.kod in self.jednostki:  # powtórzony kod po cichu nadpisałby jednostkę
                    raise ValueError(f"powtórzony kod {jednostka.kod!r}")
                self.jednostki[jednostka.kod] = jednostka

            for kod, nazwa in surowe["wojewodztwa"]:
                dodaj(Jednostka(kod, nazwa, WOJEWODZTWO, ""))
            for kod, nazwa, rodzaj, szer, dl in surowe["powiaty"]:
                dodaj(Jednostka(kod, nazwa, POWIAT, rodzaj, szer, dl))
            for kod, nazwa, rodzaj, szer, dl in surowe["gminy"]:
                dodaj(Jednostka(kod, nazwa, GMINA, rodzaj, szer, dl))
        except Exception as blad:  # każdy błąd w treści pliku (zły typ, układ, długość wiersza) to błąd danych
            raise BladDanych(f"teryt.json: zły układ danych ({type(blad).__name__}: {blad})") from blad
        self.wojewodztwa = [j for j in self.jednostki.values() if j.poziom == WOJEWODZTWO]
        self.powiaty = [j for j in self.jednostki.values() if j.poziom == POWIAT]
        self.gminy = [j for j in self.jednostki.values() if j.poziom == GMINA]


def _wczytaj_json(sciezka: Path) -> dict:
    try:
        with sciezka.open(encoding="utf-8") as plik:
            return json.load(plik)
    except FileNotFoundError as blad:
        raise BladDanych(f"Brak pliku danych geokodera: {sciezka.name}") from blad
    except (OSError, UnicodeDecodeError, ValueError) as blad:
        raise BladDanych(f"Uszkodzony plik danych geokodera: {sciezka.name} ({type(blad).__name__}: {blad})") from blad


def wczytaj_slownik(katalog: Path = DANE) -> Slownik:
    """Wczytuje `teryt.json` z katalogu (bez pamięci podręcznej); `BladDanych`, gdy plik jest zły."""
    surowe = _wczytaj_json(katalog / "teryt.json")
    if not isinstance(surowe, dict):
        raise BladDanych("teryt.json: oczekiwano obiektu JSON")
    return Slownik(surowe)


@lru_cache(maxsize=1)
def slownik() -> Slownik:
    return wczytaj_slownik(DANE)


def _jest_liczba(wartosc: object) -> bool:
    return isinstance(wartosc, (int, float)) and not isinstance(wartosc, bool) and wartosc == wartosc  # bez NaN


def _sprawdz_slownik(s: Slownik) -> None:
    kody = set()
    for j in s.jednostki.values():
        dlugosc = DLUGOSC_KODU[j.poziom]
        if not (isinstance(j.kod, str) and len(j.kod) == dlugosc and j.kod.isdigit()):
            raise BladDanych(f"teryt.json: zły kod {j.kod!r} ({j.poziom})")
        if not (isinstance(j.nazwa, str) and j.nazwa.strip()):
            raise BladDanych(f"teryt.json: pusta nazwa jednostki {j.kod}")
        kody.add(j.kod)
        if j.poziom == POWIAT and j.rodzaj != ("grodzki" if int(j.kod[2:]) >= 61 else "ziemski"):
            raise BladDanych(f"teryt.json: powiat {j.kod} ma rodzaj {j.rodzaj!r}, niezgodny z numerem")
        if j.poziom == GMINA and j.rodzaj != _RODZAJE_GMINY.get(j.kod[-1]):
            raise BladDanych(f"teryt.json: gmina {j.kod} ma rodzaj {j.rodzaj!r}, niezgodny z ostatnią cyfrą kodu")
        if j.poziom != WOJEWODZTWO:
            if not _jest_liczba(j.szer) or not _jest_liczba(j.dl):
                raise BladDanych(f"teryt.json: jednostka {j.kod} ma współrzędne, które nie są liczbami ({j.szer!r}, {j.dl!r})")
            if not (48.5 <= j.szer <= 55.5 and 13.5 <= j.dl <= 24.5):
                raise BladDanych(f"teryt.json: jednostka {j.kod} ma współrzędne spoza Polski ({j.szer}, {j.dl})")
            if j.kod[:2] not in s.jednostki or (j.poziom == GMINA and j.kod[:4] not in s.jednostki):
                raise BladDanych(f"teryt.json: jednostka {j.kod} nie ma nadrzędnej jednostki")
    if len(s.wojewodztwa) != 16 or not s.powiaty or not s.gminy:
        raise BladDanych(
            f"teryt.json: oczekiwano 16 województw oraz powiatów i gmin, jest {len(s.wojewodztwa)}/{len(s.powiaty)}/{len(s.gminy)}")
    if not (isinstance(s.atrybucja, str) and s.atrybucja.strip()):
        raise BladDanych("teryt.json: brak atrybucji danych")


def _sprawdz_granice(nazwa_pliku: str, katalog: Path, oczekiwane: set[str]) -> None:
    dane = _wczytaj_json(katalog / nazwa_pliku)
    cechy = dane.get("features") if isinstance(dane, dict) else None
    if not cechy:
        raise BladDanych(f"{nazwa_pliku}: brak obiektów (features)")
    kody = []
    for cecha in cechy:
        try:
            kod, geometria = cecha["properties"]["kod"], cecha["geometry"]
            typ_ok = geometria["type"] in ("Polygon", "MultiPolygon") and bool(geometria["coordinates"])
        except (KeyError, TypeError) as blad:
            raise BladDanych(f"{nazwa_pliku}: obiekt bez kodu lub geometrii ({type(blad).__name__}: {blad})") from blad
        if not typ_ok:
            raise BladDanych(f"{nazwa_pliku}: zła geometria dla kodu {kod}")
        kody.append(kod)
    if len(set(kody)) != len(kody) or set(kody) != oczekiwane:
        brakuje, nadmiar = sorted(oczekiwane - set(kody)), sorted(set(kody) - oczekiwane)
        raise BladDanych(f"{nazwa_pliku}: kody niezgodne ze słownikiem (brakuje: {brakuje[:5]}, nadmiar: {nadmiar[:5]}, powtórzeń: {len(kody) - len(set(kody))})")


def _jako_blad_danych(nazwa_pliku: str, kontrola, *argumenty):
    """Wykonuje kontrolę pliku; każdy błąd w treści danych (też TypeError, np. niehashowalny kod) to `BladDanych`."""
    try:
        return kontrola(*argumenty)
    except BladDanych:
        raise
    except Exception as blad:
        raise BladDanych(f"{nazwa_pliku}: zły układ danych ({type(blad).__name__}: {blad})") from blad


def sprawdz_dane(katalog: Path | None = None) -> Slownik:
    """Sprawdza spójność plików `dane/` (słownik TERYT i granice); `BladDanych` z czytelnym opisem.

    Wywołaj raz przy starcie workera, żeby uszkodzony plik wyszedł od razu, a nie przy pierwszym komunikacie.
    Każdy błąd w treści plików jest zgłaszany jako `BladDanych` (nie surowy TypeError czy KeyError).
    Nie wymaga shapely. Zwraca wczytany słownik.
    """
    katalog = Path(katalog) if katalog is not None else DANE
    s = slownik() if katalog == DANE else wczytaj_slownik(katalog)
    _jako_blad_danych("teryt.json", _sprawdz_slownik, s)
    for plik, kody in (("granice_powiaty.geojson", {j.kod for j in s.powiaty}), ("granice_wojewodztwa.geojson", {j.kod for j in s.wojewodztwa})):
        _jako_blad_danych(plik, _sprawdz_granice, plik, katalog, kody)
    return s


def jednostka(kod: str) -> Jednostka:
    """Jednostka o danym kodzie; `KeyError`, gdy kodu nie ma w słowniku."""
    return slownik().jednostki[kod]


def poziom_kodu(kod: str) -> str:
    for poziom, dlugosc in DLUGOSC_KODU.items():
        if len(kod) == dlugosc:
            return poziom
    raise ValueError(f"Nieprawidłowy kod TERYT: {kod!r}")


def wojewodztwo_powiatu(kod: str) -> str:
    """Kod województwa dla kodu powiatu lub gminy (zwraca też kod województwa dla siebie)."""
    jednostka(kod)
    return kod[:2]


def powiat_gminy(kod: str) -> str:
    """Kod powiatu dla kodu gminy lub powiatu."""
    if len(kod) < 4:
        raise ValueError(f"Województwo nie ma powiatu: {kod!r}")
    jednostka(kod)
    return kod[:4]


def nazwa(kod: str, *, krotka: bool = False, pelna: bool = False) -> str:
    """Nazwa do wyświetlania.

    Domyślnie z rodzajem („województwo lubelskie”, „powiat włodawski”, „miasto Szczecin”,
    „gmina Mogilany”). `krotka=True` daje samą nazwę („lubelskie”, „włodawski”).
    `pelna=True` dopisuje powiat i województwo („gmina Czernichów, powiat żywiecki, woj. śląskie”).
    """
    j = jednostka(kod)
    if krotka:
        return j.nazwa
    if j.poziom == WOJEWODZTWO:
        glowna = f"województwo {j.nazwa}"
    elif j.poziom == POWIAT:
        glowna = f"powiat {j.nazwa}" if j.rodzaj == "ziemski" else f"miasto {j.nazwa} (powiat grodzki)"
    else:
        glowna = f"miasto {j.nazwa}" if j.rodzaj == "miejska" else f"gmina {j.nazwa}"
    if not pelna or j.poziom == WOJEWODZTWO:
        return glowna
    czesci = [glowna]
    if j.poziom == GMINA and not j.grodzka:
        czesci.append(nazwa(kod[:4]))
    czesci.append("woj. " + jednostka(kod[:2]).nazwa)
    return ", ".join(czesci)
