"""Tokenizacja i uproszczona fleksja polskich nazw miejsc.

Nie ma tu pełnego analizatora morfologicznego. Nazwy w słowniku są w mianowniku,
a w tekście stoją w dowolnym przypadku („Szczecin”, „Szczecina”, „w Szczecinie”,
„powiatów przemyskiego i lubaczowskiego”). Dopasowanie opiera się na rdzeniach:

* po stronie tekstu każdy wyraz daje zbiór rdzeni kandydujących (wyraz bez odciętej
  końcówki przypadka albo odcięty o jedną z końcówek z `KONCOWKI`);
* po stronie słownika każda nazwa w mianowniku daje zbiór rdzeni (nazwa bez końcówki
  mianownika, z typowymi wymianami głosek: „Ruda” i „Rudzie”, „Sopot” i „Sopocie”,
  „Zgorzelec” i „Zgorzelca”, „Sosnowiec” i „Sosnowca”); rdzeń po wymianie głosek pasuje
  tylko do końcówek -e/-ie/-i, żeby „Sosnowcu” nie było formą wsi „Sosnówka”;
* wyraz pasuje do nazwy, gdy zbiory mają część wspólną.

Wszystko po złożeniu do małych liter bez polskich znaków, więc „Łódź” i „Lodz” są tym samym.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SKLADANIE = str.maketrans({"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"})
_WYRAZ = re.compile(r"[^\W_]+")
# Nazwy kończące się na te litery mogą mieć formy przymiotnikowe („Nowa Ruda” - „Nowej Rudy”).
KONCOWKI_NAZW_PRZYMIOTNIKOWYCH = frozenset("aeiy")

# Od najdłuższych. Końcówki przypadków rzeczowników i przymiotników (bez polskich znaków).
KONCOWKI = (
    "iego", "iemu",
    "ego", "emu", "iej", "ymi", "imi", "ych", "ich", "ami", "ach", "iem", "owi",
    "ia", "ie", "iu", "ej", "ym", "im", "em", "om",
    "a", "e", "i", "o", "u", "y",
)
# Końcówki, które wskazują na przymiotnik. Nazwa rzeczownikowa zakończona spółgłoską lub „o”
# (np. „Gdańsk”, „Głowno”) nie ma takich form, więc „gdańskiego” czy „głównego” to przymiotnik,
# nie miasto.
KONCOWKI_PRZYMIOTNIKA = frozenset({"iego", "iemu", "ego", "emu", "iej", "ej", "ymi", "imi", "ych", "ich", "ym", "im"})
# Końcówki mianownika odcinane po stronie słownika.
_MIANOWNIK = ("ia", "ie", "io", "a", "e", "o", "y", "i")
MIN_RDZEN = 3

# Wymiany głosek przed końcówką -ie/-i: Ruda-Rudzie, Sopot-Sopocie, Góra-Górze, Warta-Warcie.
_WYMIANY = (("ch", "sz"), ("t", "c"), ("d", "dz"), ("r", "rz"), ("k", "c"), ("g", "dz"))


def zloz(tekst: str) -> str:
    """Małe litery bez polskich znaków diakrytycznych."""
    return tekst.lower().translate(_SKLADANIE)


def zloz_pozycyjnie(tekst: str) -> str:
    """Jak `zloz`, ale każdy znak daje dokładnie jeden znak, więc pozycje w wyniku są pozycjami w `tekst`.

    `str.lower()` potrafi zmienić długość (np. „İ” daje dwa znaki), co przesuwałoby pozycje dopasowań.
    """
    znaki = []
    for znak in tekst:
        maly = znak.lower()
        znaki.append((maly if len(maly) == 1 else maly[:1]).translate(_SKLADANIE))
    return "".join(znaki)


_NIEWIDOCZNE = frozenset("­​‌‍﻿")  # miękki łącznik, spacja zerowej szerokości, łączniki zerowej szerokości, BOM


def usun_niewidoczne(tekst: str) -> tuple[str, list[int] | None]:
    """Usuwa znaki niewidoczne („Wroc\\u00adławiu” - miękki łącznik z kopiowanego tekstu) przed tokenizacją.

    Zwraca (czysty tekst, mapa): `mapa[i]` to pozycja i-tego znaku czystego tekstu w oryginale, a ostatni element
    to długość oryginału. Gdy nic nie usunięto, mapa to `None` (pozycje się zgadzają).
    """
    if _NIEWIDOCZNE.isdisjoint(tekst):
        return tekst, None
    znaki: list[str] = []
    mapa: list[int] = []
    for pozycja, znak in enumerate(tekst):
        if znak not in _NIEWIDOCZNE:
            znaki.append(znak)
            mapa.append(pozycja)
    mapa.append(len(tekst))
    return "".join(znaki), mapa


@dataclass(slots=True)
class Token:
    tekst: str
    zlozony: str
    start: int
    koniec: int
    sep: str  # znaki między poprzednim wyrazem a tym (puste na początku tekstu: patrz poczatek_tekstu)
    wielka: bool  # pierwsza litera wielka
    cyfra: bool  # zaczyna się od cyfry
    z_kropka: bool  # bezpośrednio po wyrazie stoi kropka (skrót)
    poczatek_zdania: bool
    _kandydaci: dict[str, str] | None = None

    def kandydaci(self) -> dict[str, str]:
        """Rdzenie kandydujące wyrazu: {rdzeń: odcięta końcówka} (pusta końcówka: wyraz bez zmian)."""
        if self._kandydaci is None:
            self._kandydaci = kandydaci_rdzeni(self.zlozony)
        return self._kandydaci


_SKROTY = frozenset({"woj", "pow", "gm", "ul", "al", "pl", "os", "m", "st", "im", "ks", "dr", "inz", "mgr", "nr", "tel", "godz", "ok", "np", "tzw", "tys", "zm", "ob", "gen"})


def tokenizuj(tekst: str) -> list[Token]:
    wynik: list[Token] = []
    poprzedni_koniec = 0
    for dopasowanie in _WYRAZ.finditer(tekst):
        start, koniec = dopasowanie.span()
        sep = tekst[poprzedni_koniec:start]
        tekst_wyrazu = dopasowanie.group()
        zlozony = zloz(tekst_wyrazu)
        if not wynik:
            poczatek = True
        else:
            poprzedni = wynik[-1]
            koniec_zdania = ("\n" in sep) or any(z in sep for z in ".!?")
            poczatek = koniec_zdania and not (poprzedni.zlozony in _SKROTY and "\n" not in sep and not any(z in sep for z in "!?"))
        wynik.append(Token(
            tekst=tekst_wyrazu, zlozony=zlozony, start=start, koniec=koniec, sep=sep,
            wielka=tekst_wyrazu[0].isupper(), cyfra=tekst_wyrazu[0].isdigit(),
            z_kropka=tekst[koniec:koniec + 1] == ".", poczatek_zdania=poczatek,
        ))
        poprzedni_koniec = koniec
    return wynik


def kandydaci_rdzeni(zlozony: str) -> dict[str, str]:
    """Rdzenie wyrazu z tekstu: sam wyraz oraz wyraz bez jednej z końcówek."""
    wynik = {zlozony: ""}
    for koncowka in KONCOWKI:
        if zlozony.endswith(koncowka) and len(zlozony) - len(koncowka) >= MIN_RDZEN:
            wynik.setdefault(zlozony[: -len(koncowka)], koncowka)
    return wynik


# Dla rdzeni po wymianie głosek dopuszczamy tylko końcówki celownika i miejscownika (Rudzie, Górze, Sopocie).
KONCOWKI_PO_WYMIANIE = frozenset({"e", "ie", "i"})


def rdzenie_mianownika(zlozony: str) -> dict[str, frozenset[str] | None]:
    """Rdzenie nazwy w mianowniku (jeden wyraz, już złożony): {rdzeń: dozwolone końcówki albo None (dowolne)}."""
    wynik: dict[str, frozenset[str] | None] = {}

    def dodaj(rdzen: str, dozwolone: frozenset[str] | None) -> None:
        if len(rdzen) < MIN_RDZEN:
            return
        if rdzen in wynik and wynik[rdzen] is None:
            return
        wynik[rdzen] = None if dozwolone is None else (wynik.get(rdzen) or frozenset()) | dozwolone

    dodaj(zlozony, None)
    for koncowka in _MIANOWNIK:
        if zlozony.endswith(koncowka):
            dodaj(zlozony[: -len(koncowka)], None)
    for rdzen in list(wynik):
        for koniec, zamiana in _WYMIANY:
            if rdzen.endswith(koniec) and not (koniec == "t" and rdzen.endswith(("st", "szt"))):
                dodaj(rdzen[: -len(koniec)] + zamiana, KONCOWKI_PO_WYMIANIE)
        if rdzen.endswith("iec"):  # ruchome „ie”: Sosnowiec-Sosnowca
            dodaj(rdzen[:-3] + "c", None)
        elif rdzen.endswith(("ec", "ek")):  # ruchome „e”: Zgorzelec-Zgorzelca
            dodaj(rdzen[:-2] + rdzen[-1], None)
    return wynik


def wyrazy_nazwy(nazwa: str) -> list[str]:
    """Złożone wyrazy nazwy (łącznik i spacja rozdzielają wyrazy)."""
    return [zloz(w) for w in _WYRAZ.findall(nazwa)]


def wyglada_na_wielkie_litery(tekst: str) -> bool:
    """Czy tekst jest w większości pisany WIELKIMI LITERAMI (wtedy wielka litera nic nie mówi)."""
    litery = [c for c in tekst if c.isalpha()]
    return len(litery) >= 10 and sum(c.isupper() for c in litery) / len(litery) >= 0.7
