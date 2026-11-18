"""Geokoder komunikatów: z polskiego tekstu wyciąga kody TERYT województw, powiatów i gmin.

Zasady (plan budowy Teraz, sekcje 3, 5 i 7a oraz opinia prawnika Z0):

* Wynik ma dokładność `gmina`, `powiat`, `wojewodztwo`, `kraj` albo `brak`, razem z pewnością 0..1.
* Nigdy nie zgadujemy: lepiej `brak` albo województwo niż zgadnięta gmina lub powiat. Nazwa wieloznaczna
  (np. kilka gmin „Dąbrowa”, „Czernichów”, „Słubice”) jest rozstrzygana tylko kontekstem z tekstu
  (wymienione województwo lub powiat). Bez kontekstu wynik spada do wspólnego powiatu albo województwa
  kandydatów (z niską pewnością), a gdy kandydaci leżą w różnych województwach, do `brak`.
  Jedyny wyjątek: miasto, gdy jest jedynym takim kandydatem w tym samym województwie (miasto na prawach
  powiatu obok gminy wiejskiej o tej nazwie, np. „Chełm”, albo gmina miejska obok wiejskiej w tym samym
  powiecie, np. „Mielec”), z pewnością 0,65 i uwagami `homonim`, `preferowane-miasto`
  (wyłącza to `PREFERUJ_MIASTO`). „Leszno” i „Olsztyn” mają wiejskiego homonima w innym województwie,
  więc bez kontekstu dają `brak`.
* Skrócone nazwy („w Grodzisku”, „w Ostrowie”, „w Bielsku”, „Tomaszów”) bez pełnej nazwy dają `brak`
  z uwagą `skrot`, chyba że kontekst (województwo, powiat) jednoznacznie wskazuje jedną jednostkę.
* Adresy ulic, osiedla, wsie i dzielnice (także wszystkie dzielnice Warszawy, bez względu na słowo
  „dzielnica”) nie dają gmin; PRG nie zawiera miejscowości. Rzeki (Wisła, Warta, Nysa Kłodzka...) i kluby
  („Wisła Kraków”) nie są gminami o tej nazwie.
* Wielka litera jest warunkiem nazwy gminy i miasta; przymiotniki powiatów („włodawski”) są
  rozpoznawane tylko po słowie „powiat”/„pow.” albo na liście powiatów, a województwa tylko po
  „woj./województwo” albo przed „powiaty:” / „gmina”.
* Zasięg alertu się nie zawęża: województwo i powiat wskazane wprost zostają w `teryt`, także gdy w treści
  padają dokładniejsze miejsca (te trafiają do `dopasowania`). Szerszy kod znika tylko wtedy, gdy węższe
  miejsce jest jego doprecyzowaniem: lista powiatów pod województwem albo zapis adresowy stojący obok
  („woj. lubelskie, powiat chełmski, gmina Chełm”, „Chełm, woj. lubelskie”).

Wejście to czysty tekst (HTML usuwa adapter), obcinany do `MAKS_DLUGOSC` znaków. Współrzędne: patrz `granice.py`.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from . import slownik as sl
from .fleksja import (
    KONCOWKI_PRZYMIOTNIKA,
    KONCOWKI_NAZW_PRZYMIOTNIKOWYCH,
    Token,
    rdzenie_mianownika,
    tokenizuj,
    wyglada_na_wielkie_litery,
    wyrazy_nazwy,
    zloz_pozycyjnie,
)

KRAJ = "kraj"
BRAK = "brak"

# Dłuższy tekst jest obcinany (komunikat ma kilka kilobajtów); chroni przed tekstami, które liczą się długo.
MAKS_DLUGOSC = 20_000

# Miasto wygrywa z wiejskim homonimem, gdy jest jedynym takim kandydatem w tym samym województwie:
# miasto na prawach powiatu (Chełm obok gminy wiejskiej Chełm) albo gmina miejska w tym samym powiecie
# co wiejska (Mielec).
PREFERUJ_MIASTO = True

PEWNOSC_WOJ_ZNACZNIK = 0.95
PEWNOSC_WOJ_ZAKRES = 0.90
PEWNOSC_REGION = 0.75
PEWNOSC_POWIAT = 0.95
PEWNOSC_PO_KONTEKSCIE = 0.90
PEWNOSC_GMINA_ZNACZNIK = 0.90
PEWNOSC_DZIELNICA = 0.90
PEWNOSC_GMINA_SAMODZIELNA = {"grodzka": 0.90, "miejska": 0.85, "miejsko-wiejska": 0.75, "wiejska": 0.60}
PEWNOSC_MIASTO_PREFEROWANE = 0.65
PEWNOSC_SPADEK_DO_POWIATU = 0.70
PEWNOSC_SPADEK_DO_WOJEWODZTWA = 0.60
PEWNOSC_JEDNOSTKA_MAX = 0.80
PEWNOSC_SKROT_MAX = 0.75
PEWNOSC_KRAJ = 0.70
WSPOLCZYNNIK_WIELKICH_LITER = 0.85
WSPOLCZYNNIK_ODRZUCONEJ_NAZWY = 0.90

_WOJ = frozenset({"woj", "wojew"})
_POW = frozenset({"powiat", "powiatu", "powiatem", "powiaty", "powiatow", "powiatach", "powiatom", "powiatami", "powiecie", "pow"})
_GM = frozenset({"gmina", "gminy", "gminie", "gmine", "gmin", "gminach", "gminom", "gminami", "gm"})
_MIASTO = frozenset({"miasto", "miasta", "miastu", "miastem", "miescie", "m"})
_WIES = frozenset({"miejscowosc", "miejscowosci", "miejscowoscia", "wies", "wsi", "wsie", "wsiach", "osiedle", "osiedlu", "osiedla", "solectwo", "solectwie"})
_ULICA = frozenset({"ul", "ulica", "ulicy", "ulice", "ulicach", "al", "aleja", "alei", "aleje", "pl", "plac", "placu", "os", "rondo", "ronda"})
_DZIELNICA = frozenset({"dzielnica", "dzielnicy", "dzielnicie", "dzielnice", "dzielnic", "dzielnicach"})
_SKROTY_Z_KROPKA = frozenset({"gm", "m", "pl", "al", "os"})
_MODYFIKATORY_GMINY = frozenset({"miejska", "miejskiej", "wiejska", "wiejskiej", "miejsko", "wiejsko"})
_LACZNIKI = frozenset({"i", "oraz", "lub", "albo"})

_DZIELNICE_WARSZAWY = (
    "Bemowo", "Białołęka", "Bielany", "Mokotów", "Ochota", "Praga-Południe", "Praga-Północ", "Rembertów",
    "Targówek", "Ursus", "Ursynów", "Wawer", "Wesoła", "Wilanów", "Włochy", "Wola", "Śródmieście", "Żoliborz",
)
KOD_WARSZAWY = "1465011"

# Nieregularne odmiany nazw (rdzeń mianownika nie wystarcza); klucz: nazwa gminy w słowniku.
_NIEREGULARNE = {
    "Białystok": ("Białegostoku", "Białymstoku", "Białemustoku"),
    "Krasnystaw": ("Krasnegostawu", "Krasnymstawie", "Krasnemustawowi", "Krasnymstawem"),
}

# Nazwy regionów równoważne województwu (tylko te jednoznaczne).
_REGIONY = {
    "Mazowsze": "14", "Małopolska": "12", "Wielkopolska": "30", "Podkarpacie": "18",
    "Podlasie": "20", "Lubelszczyzna": "06",
}

# Nazwy gmin, które są też zwykłymi słowami. „Tylko znacznik”: wymagają słowa „gmina/miasto/powiat”
# (np. „Nowy Jork” nie jest gminą Nowe). „Nie na początku zdania”: wystarczy wielka litera w środku zdania.
_TYLKO_ZNACZNIK = frozenset({"nowe", "nowa", "dobra", "dobre", "czarna", "czarne", "biala", "stare"})
_NIE_NA_POCZATKU_ZDANIA = frozenset({"kolo", "kowal", "gniew", "pila", "marki", "klucze", "ploty", "mikolajki", "kozy", "brody", "kamien", "pokoj"})
# Pierwsze wyrazy wielu nazw („Nowy Sącz”, „Stary Sącz”, „Wielka Wieś”): samo takie słowo nie jest skrótem miejsca.
_GENERYCZNE_PIERWSZE = frozenset({
    "nowy", "nowa", "nowe", "stary", "stara", "stare", "wielki", "wielka", "wielkie", "maly", "mala", "male",
    "duzy", "duza", "duze", "dolny", "dolna", "dolne", "gorny", "gorna", "gorne", "czarny", "czarna", "czarne",
    "bialy", "biala", "biale", "zielony", "zielona", "zielone", "swiety", "swieta", "swiete", "kolo", "dobre", "dobra",
})

# Rzeki, które są też nazwami gmin (Wisła, Warta, Nysa, Pilica, Wieprz, Narew, Słupia, Łeba, Oława...) oraz
# większe rzeki bez gminy o tej nazwie (dla porządku listy). Nazwy bez polskich znaków, mianownik.
_RZEKI = frozenset((n,) for n in (
    "wisla", "odra", "warta", "bug", "narew", "san", "pilica", "wieprz", "nysa", "bobr", "dunajec", "notec",
    "wda", "brda", "dreweca", "prosna", "bzura", "ner", "kamienna", "radomka", "biebrza", "sola", "skawa", "raba",
    "wisloka", "wislok", "poprad", "nida", "liwiec", "wkra", "rega", "parseta", "slupia", "lyna", "pasleka", "obra",
    "gwda", "drawa", "ropa", "olza", "kaczawa", "bystrzyca", "widawa", "tanew", "huczwa", "swider", "wiar", "orla",
    "barycz", "sleza", "olawa", "leba", "suprasl", "narewka", "wilga", "gac",
))
# Pierwsze wyrazy nazw klubów sportowych, które są też nazwami gmin („Wisła Kraków”, „Raków Częstochowa”).
_KLUBY = frozenset({("rakow",)})
_PRZED_RZEKA = frozenset({"na", "nad", "wzdluz", "rzeka", "rzeki", "rzece", "rzeke", "rzekach", "dorzecze", "dorzeczu", "dolinie"})
_DRUGI_CZLON_RZEKI = ("klodzk", "luzyck")  # „Nysa Kłodzka”, „Nysa Łużycka”

_PRZYIMKI_MIEJSCA = frozenset({"w", "we", "z", "ze", "do", "od", "na", "nad", "pod", "przy", "kolo", "k", "po", "za", "obok"})
_JEDNOSTKA_PREFIKSY = ("komend", "komisariat", "prokuratur", "urzad", "posterunek", "jednostk")
_JEDNOSTKA_WYRAZY = frozenset({"sad", "sadu", "sadzie", "sadem"})
# Skróty jednostek służb (Policja, PSP): KPP, KMP, KWP, KSP, KP, JRG, PSP (w tym KP PSP, KW PSP).
_JEDNOSTKA_SKROTY = frozenset({"kpp", "kmp", "kwp", "ksp", "kp", "jrg", "psp"})
# Małą literą dopuszczamy w nazwie jednostki tylko te wyrazy (reszta małych liter przerywa przeszukiwanie wstecz).
_JEDNOSTKA_PRZEDROSTKI_MALE = ("wojewodzk", "powiatow", "rejonow", "miejsk", "stoleczn", "okregow")
_JEDNOSTKA_SLOWA_MALE = frozenset({"policji", "policja", "straz", "strazy", "pozarnej", "granicznej", "ratowniczo", "gasnicza", "gasniczej", "gasnicze", "panstwowej"})
_SEP_PROSTY = re.compile(r"[ \t\u00a0\-]+")
_SEP_PIERWSZEGO = re.compile(r"[\s:\-\u2013\u2014(.]{0,6}")
_SEP_ZAKRESU = re.compile(r"[\s\-\u2013\u2014:,(]{0,4}")
_KONIEC_ZDANIA = ".!?;\n"

# Zasięg krajowy: tylko przy słowach o zasięgu („obowiązuje w całym kraju”, „na terenie całego kraju”,
# „dla całej Polski”). „z całej Polski” czy „najwięcej w całym kraju” zasięgiem nie są.
_FRAZA_KRAJU = r"(?:w\s+calej\s+polsce|w\s+calym\s+kraju|calej\s+polski|calego\s+kraju)"
_CZASOWNIK_ZASIEGU = r"(?:obowiazuj\w*|dotyczy\w*|dotycz\w*|ogloszon\w*|ogloszono|wprowadzon\w*|wprowadzono|wysla\w*|wyslan\w*|zasieg\w*)"
_WZORCE_KRAJU = tuple(re.compile(w) for w in (
    r"\bdla\s+(calej\s+polski|calego\s+kraju)\b",
    r"\bdla\s+\w+\s+(w\s+calej\s+polsce|w\s+calym\s+kraju)\b",
    r"\bna\s+(?:terenie|obszarze)\s+(calego\s+kraju|calej\s+polski)\b",
    rf"\b{_CZASOWNIK_ZASIEGU}\b[^.!?\n]{{0,40}}?\b({_FRAZA_KRAJU})\b",
    rf"\b({_FRAZA_KRAJU})\b[^.!?\n]{{0,40}}?\b{_CZASOWNIK_ZASIEGU}\b",
))
# Komunikaty hydrologiczne: nazwa rzeki, która jest też gminą, nie jest wtedy miejscem.
_HYDROLOGIA = re.compile(
    r"hydrolog|wezbran|powodz|wylew|przybor|kulminac|\bstan\w*\s+(?:alarmow|ostrzegawcz|wod)|\bpoziom\w*\s+wod"
    r"|\brzek|\brzece|\bkorytem?\b|\bprzeplyw")


# --------------------------------------------------------------------------- wynik

@dataclass(frozen=True, slots=True)
class Dopasowanie:
    """Jedno rozpoznane miejsce w tekście."""

    fraza: str  # fragment tekstu
    start: int  # pozycje znaków w tekście wejściowym
    koniec: int
    rodzaj: str  # wojewodztwo | powiat | gmina | kraj
    tryb: str  # znacznik | lista | zakres | samodzielne | dzielnica | region | kraj
    teryt: tuple[str, ...]  # przyjęte kody (puste: nie udało się rozstrzygnąć)
    dokladnosc: str  # gmina | powiat | wojewodztwo | kraj | brak
    pewnosc: float
    kandydaci: tuple[str, ...] = ()  # wszystkie kody o tej nazwie, gdy jest wieloznaczna
    uwagi: tuple[str, ...] = ()  # homonim, kontekst, jednostka, skrot, spadek-do-powiatu, spadek-do-wojewodztwa...

    def jako_dict(self) -> dict:
        return {
            "fraza": self.fraza, "start": self.start, "koniec": self.koniec, "rodzaj": self.rodzaj,
            "tryb": self.tryb, "teryt": list(self.teryt), "dokladnosc": self.dokladnosc,
            "pewnosc": self.pewnosc, "kandydaci": list(self.kandydaci), "uwagi": list(self.uwagi),
        }


@dataclass(frozen=True, slots=True)
class Wynik:
    teryt: tuple[str, ...]  # posortowane, bez powtórzeń; zob. zasady zasięgu w opisie modułu
    dokladnosc: str  # gmina | powiat | wojewodztwo | kraj | brak (najgrubsza z przyjętych)
    pewnosc: float  # 0..1; dla `brak` 0.0
    dopasowania: tuple[Dopasowanie, ...] = ()
    uwagi: tuple[str, ...] = ()  # np. „obcieto-tekst”, gdy wejście przekroczyło `MAKS_DLUGOSC`

    def jako_dict(self) -> dict:
        return {
            "teryt": list(self.teryt), "dokladnosc": self.dokladnosc, "pewnosc": self.pewnosc,
            "dopasowania": [d.jako_dict() for d in self.dopasowania], "uwagi": list(self.uwagi),
        }


# --------------------------------------------------------------------------- indeksy nazw

@dataclass(slots=True)
class _Grupa:
    wyrazy: tuple[str, ...]  # złożone wyrazy mianownika
    rdzenie: tuple[dict[str, frozenset[str] | None], ...]
    wielka: bool  # nazwa wymaga wielkiej litery w tekście
    kody: list[str] = field(default_factory=list)


class _Indeks:
    def __init__(self, wielka: bool):
        self.wielka_domyslnie = wielka
        self.grupy: dict[tuple, _Grupa] = {}
        self.po_pierwszym: dict[str, list[_Grupa]] = defaultdict(list)

    def dodaj(self, nazwa: str, kod: str, wielka: bool | None = None) -> None:
        wyrazy = tuple(wyrazy_nazwy(nazwa))
        wielka = self.wielka_domyslnie if wielka is None else wielka
        klucz = (wyrazy, wielka)
        grupa = self.grupy.get(klucz)
        if grupa is None:
            grupa = _Grupa(wyrazy, tuple(rdzenie_mianownika(w) for w in wyrazy), wielka)
            self.grupy[klucz] = grupa
            for rdzen in grupa.rdzenie[0]:
                self.po_pierwszym[rdzen].append(grupa)
        if kod not in grupa.kody:
            grupa.kody.append(kod)


@dataclass(slots=True)
class _Indeksy:
    gminy: _Indeks
    powiaty: _Indeks
    wojewodztwa: _Indeks
    regiony: _Indeks
    dzielnice: _Indeks


@lru_cache(maxsize=1)
def _indeksy() -> _Indeksy:
    s = sl.slownik()
    gminy, powiaty, woj = _Indeks(True), _Indeks(False), _Indeks(False)
    regiony, dzielnice = _Indeks(True), _Indeks(True)
    for j in s.gminy:
        gminy.dodaj(j.nazwa, j.kod)
        for forma in _NIEREGULARNE.get(j.nazwa, ()):
            gminy.dodaj(forma, j.kod)
    for j in s.powiaty:
        powiaty.dodaj(j.nazwa, j.kod, wielka=j.rodzaj == "grodzki")
    for j in s.wojewodztwa:
        woj.dodaj(j.nazwa, j.kod)
    for nazwa, kod in _REGIONY.items():
        regiony.dodaj(nazwa, kod)
    for nazwa in _DZIELNICE_WARSZAWY:
        dzielnice.dodaj(nazwa, KOD_WARSZAWY)
    return _Indeksy(gminy, powiaty, woj, regiony, dzielnice)


def _zgodny_rdzen(token: Token, rdzenie: dict[str, frozenset[str] | None], mianownik: str) -> bool:
    for rdzen, koncowka in token.kandydaci().items():
        if rdzen in rdzenie:
            dozwolone = rdzenie[rdzen]
            if dozwolone is not None and koncowka not in dozwolone:
                continue
            # „gdańskiego” to przymiotnik, a nie forma miasta Gdańsk (nazwa na spółgłoskę lub „o”)
            if koncowka in KONCOWKI_PRZYMIOTNIKA and mianownik[-1] not in KONCOWKI_NAZW_PRZYMIOTNIKOWYCH:
                continue
            return True
    return False


def _zgodna(tokeny: list[Token], i: int, grupa: _Grupa, ile: int) -> bool:
    """Czy pierwsze `ile` wyrazów nazwy pasuje do tokenów od `i`."""
    for k in range(ile):
        tk = tokeny[i + k]
        if grupa.wielka and not tk.wielka:
            return False
        if k and not (tk.sep and _SEP_PROSTY.fullmatch(tk.sep)):
            return False
        if not _zgodny_rdzen(tk, grupa.rdzenie[k], grupa.wyrazy[k]):
            return False
    return True


def _grupy_od(tokeny: list[Token], i: int, indeks: _Indeks) -> list[_Grupa]:
    t = tokeny[i]
    if t.cyfra:
        return []
    kandydaci: dict[int, _Grupa] = {}
    for rdzen in t.kandydaci():
        for grupa in indeks.po_pierwszym.get(rdzen, ()):
            kandydaci[id(grupa)] = grupa
    return list(kandydaci.values())


def _szukaj(tokeny: list[Token], i: int, indeks: _Indeks) -> tuple[int, list[_Grupa]] | None:
    """Najdłuższe dopasowanie nazwy z indeksu od tokenu `i`: (liczba tokenów, grupy o tej długości)."""
    najdluzsza, grupy = 0, []
    for grupa in _grupy_od(tokeny, i, indeks):
        dlugosc = len(grupa.wyrazy)
        if dlugosc < najdluzsza or i + dlugosc > len(tokeny):
            continue
        if not _zgodna(tokeny, i, grupa, dlugosc):
            continue
        if dlugosc > najdluzsza:
            najdluzsza, grupy = dlugosc, []
        grupy.append(grupa)
    return (najdluzsza, grupy) if grupy else None


def _skrocone(tokeny: list[Token], i: int, indeks: _Indeks, ile: int) -> list[_Grupa]:
    """Dłuższe nazwy, których pierwsze `ile` wyrazów pasuje do tokenów od `i` („Grodzisk” - „Grodzisk Mazowiecki”)."""
    if i + ile > len(tokeny):
        return []
    return [g for g in _grupy_od(tokeny, i, indeks) if len(g.wyrazy) > ile and _zgodna(tokeny, i, g, ile)]


def _kody(grupy: list[_Grupa]) -> list[str]:
    wynik: list[str] = []
    for grupa in grupy:
        for kod in grupa.kody:
            if kod not in wynik:
                wynik.append(kod)
    return wynik


# --------------------------------------------------------------------------- znaczniki

def _znacznik(tokeny: list[Token], i: int) -> str | None:
    t = tokeny[i]
    z = t.zlozony
    if z in _SKROTY_Z_KROPKA and (not t.z_kropka or t.sep.endswith((".", "/"))):
        return None
    if z in _WOJ or z.startswith("wojewodztw"):
        return "woj"
    if z in _POW:
        return "pow"
    if z in _GM:
        return "gm"
    if z in _MIASTO:
        return "miasto"
    if z in _WIES:
        return "wies"
    if z in _ULICA:
        return "ulica"
    if z in _DZIELNICA:
        return "dzielnica"
    return None


def _pomin_nazwe(tokeny: list[Token], j: int, maks: int) -> int:
    """Koniec nazwy własnej (ulicy, wsi) zaczynającej się w `j`: kolejne wyrazy wielkie lub liczby."""
    k = j
    while k < len(tokeny) and k - j < maks:
        t = tokeny[k]
        if k > j and any(c in t.sep for c in ".,;:!?\n"):
            break
        if not (t.wielka or t.cyfra):
            break
        k += 1
    return k


# --------------------------------------------------------------------------- trafienia

@dataclass(slots=True)
class _Trafienie:
    start: int  # indeksy tokenów [start, koniec)
    koniec: int
    typ: str  # woj | pow | gmina | region
    tryb: str  # znacznik | lista | zakres | samodzielne | dzielnica | region
    kody: list[str]
    znacznik: str = ""  # gm | miasto (dla gmin)
    lancuch: int = 0
    lancuch_koniec: int = 0
    zakres: set[str] = field(default_factory=set)  # województwa z zakresu (dla powiatów)
    kontekst_wielkich: bool = False  # tekst WIELKIMI LITERAMI: samodzielne trafienie słabsze
    bez_przyimka: bool = False  # nazwa bez przyimka miejsca: tylko miasto (nie wieś ani miasteczko)
    skrot: bool = False  # skrócona nazwa: wymaga kontekstu


def _wczytaj_lancuch(tokeny: list[Token], p: int, indeks: _Indeks) -> list[tuple[int, int, list[str]]]:
    """Lista nazw po znaczniku: „A, B i C”. Zwraca [(start, koniec, kody)] w tokenach."""
    pozycje: list[tuple[int, int, list[str]]] = []
    n = len(tokeny)
    if p >= n or not _SEP_PIERWSZEGO.fullmatch(tokeny[p].sep):
        return pozycje
    while p < n:
        znaleziono = _szukaj(tokeny, p, indeks)
        if not znaleziono:
            break
        dlugosc, grupy = znaleziono
        pozycje.append((p, p + dlugosc, _kody(grupy)))
        p += dlugosc
        if p >= n:
            break
        sep = tokeny[p].sep
        if "\n" in sep or "." in sep or ";" in sep:
            break
        q = p
        if tokeny[q].zlozony in _LACZNIKI and (not sep.strip() or sep.strip() == ","):
            q += 1
        elif tokeny[q].zlozony == "a" and q + 1 < n and tokeny[q + 1].zlozony == "takze":
            q += 2
        elif "," not in sep:
            break
        if q >= n or "\n" in tokeny[q].sep or ("." in tokeny[q].sep):
            break
        p = q
    return pozycje


def _przyimek_przed(tokeny: list[Token], i: int) -> bool:
    return i > 0 and tokeny[i - 1].zlozony in _PRZYIMKI_MIEJSCA


def _slowo_dozwolone(slowo: str, token: Token, wielkie: bool) -> bool:
    if slowo in _TYLKO_ZNACZNIK:
        return False
    if slowo in _NIE_NA_POCZATKU_ZDANIA and (token.poczatek_zdania or wielkie):
        return False
    return True


def _nazwa_dozwolona(grupa: _Grupa, token: Token, wielkie: bool) -> bool:
    if len(grupa.wyrazy) != 1:
        return True
    return _slowo_dozwolone(grupa.wyrazy[0], token, wielkie)


def _jest_miastem(kod: str) -> bool:
    return sl.jednostka(kod).rodzaj in ("miejska", "miejsko-wiejska")


def _blokada_rzeki_lub_klubu(tokeny: list[Token], i: int, dlugosc: int, grupy: list[_Grupa], hydrologia: bool, ind: _Indeksy) -> int:
    """Liczba tokenów do pominięcia, gdy nazwa gminy jest w tekście rzeką albo klubem („na Wiśle”, „Wisła Kraków”).

    Rzeka: po „na/nad/rzeka”, z drugim członem „Kłodzka/Łużycka” albo w tekście o stanie wód (hydrologia).
    Klub: nazwa rzeki lub klubu tuż przed nazwą innego miasta („Wisła Kraków”, „Raków Częstochowa”).
    """
    nazwy = {g.wyrazy for g in grupy}
    rzeka = bool(nazwy & _RZEKI)
    if not rzeka and not (nazwy & _KLUBY):
        return 0
    nastepny = i + dlugosc
    if rzeka:
        if nastepny < len(tokeny) and nazwy == {("nysa",)} and tokeny[nastepny].zlozony.startswith(_DRUGI_CZLON_RZEKI):
            return dlugosc + 1
        if i > 0 and tokeny[i - 1].zlozony in _PRZED_RZEKA:
            return dlugosc
        if hydrologia:
            return dlugosc
    if nastepny < len(tokeny) and tokeny[nastepny].wielka and tokeny[nastepny].sep and _SEP_PROSTY.fullmatch(tokeny[nastepny].sep):
        if _szukaj(tokeny, nastepny, ind.gminy):
            return dlugosc
    return 0


def _szukaj_trafien(tokeny: list[Token], wielkie: bool, hydrologia: bool) -> list[_Trafienie]:
    """Przechodzi po tokenach i zbiera trafienia; ulice, wsie i dzielnice są pomijane."""
    ind = _indeksy()
    n = len(tokeny)
    uzyte = [False] * n
    trafienia: list[_Trafienie] = []
    woj_lancuchy: dict[int, set[str]] = defaultdict(set)  # indeks po pozycji: województwa każdego łańcucha
    ostatnie_woj: _Trafienie | None = None
    numer_lancucha = 0

    def dodaj(h: _Trafienie) -> None:
        nonlocal ostatnie_woj
        trafienia.append(h)
        if h.typ == "woj":
            ostatnie_woj = h
            if h.kody:
                woj_lancuchy[h.lancuch].add(h.kody[0][:2])

    def zakres_przed(start: int) -> set[str]:
        if ostatnie_woj is not None and start - ostatnie_woj.koniec <= 3:
            return set(woj_lancuchy[ostatnie_woj.lancuch])
        return set()

    i = 0
    while i < n:
        if uzyte[i]:
            i += 1
            continue
        znacznik = _znacznik(tokeny, i)
        if znacznik in ("wies", "ulica"):
            koniec = _pomin_nazwe(tokeny, i + 1, 6 if znacznik == "ulica" else 3)
            for k in range(i, koniec):
                uzyte[k] = True
            i = max(koniec, i + 1)
            continue
        if znacznik == "dzielnica":
            znaleziono = _szukaj(tokeny, i + 1, ind.dzielnice) if i + 1 < n else None
            if znaleziono:
                dlugosc, grupy = znaleziono
                dodaj(_Trafienie(i + 1, i + 1 + dlugosc, "gmina", "dzielnica", _kody(grupy)))
                koniec = i + 1 + dlugosc
            else:
                koniec = max(_pomin_nazwe(tokeny, i + 1, 3), i + 1)
            for k in range(i, koniec):
                uzyte[k] = True
            i = koniec
            continue
        if znacznik in ("woj", "pow", "gm", "miasto"):
            p = i + 1
            if znacznik in ("gm", "miasto"):
                while p < n and (tokeny[p].zlozony in _MODYFIKATORY_GMINY or (tokeny[p].zlozony == "st" and znacznik == "miasto")):
                    p += 1
            indeks = {"woj": ind.wojewodztwa, "pow": ind.powiaty, "gm": ind.gminy, "miasto": ind.gminy}[znacznik]
            pozycje = _wczytaj_lancuch(tokeny, p, indeks)
            if pozycje:
                numer_lancucha += 1
                zakres = zakres_przed(i) if znacznik == "pow" else set()
                koniec_lancucha = pozycje[-1][1]
                for start, koniec, kody in pozycje:
                    dodaj(_Trafienie(
                        start, koniec, {"woj": "woj", "pow": "pow"}.get(znacznik, "gmina"),
                        "lista" if znacznik == "pow" else "znacznik", kody, znacznik="" if znacznik in ("woj", "pow") else znacznik, lancuch=numer_lancucha,
                        lancuch_koniec=koniec_lancucha, zakres=set(zakres)))
                    for k in range(start, koniec):
                        uzyte[k] = True
                for k in range(i, p):
                    uzyte[k] = True
                i = koniec_lancucha
                continue
            i += 1
            continue
        # województwo przed „powiaty:” / „gmina”: „lubelskiego - powiaty: ...”
        znaleziono = _szukaj(tokeny, i, ind.wojewodztwa)
        if znaleziono:
            dlugosc, grupy = znaleziono
            j = i + dlugosc
            if j < n and _SEP_ZAKRESU.fullmatch(tokeny[j].sep) and _znacznik(tokeny, j) in ("pow", "gm"):
                numer_lancucha += 1
                dodaj(_Trafienie(i, j, "woj", "zakres", _kody(grupy), lancuch=numer_lancucha, lancuch_koniec=j))
                for k in range(i, j):
                    uzyte[k] = True
                i = j
                continue
        znaleziono = _szukaj(tokeny, i, ind.regiony)
        if znaleziono:
            dlugosc, grupy = znaleziono
            numer_lancucha += 1
            dodaj(_Trafienie(i, i + dlugosc, "region", "region", _kody(grupy), lancuch=numer_lancucha, lancuch_koniec=i + dlugosc))
            for k in range(i, i + dlugosc):
                uzyte[k] = True
            i += dlugosc
            continue
        # samodzielna nazwa gminy lub miasta
        przyimek = _przyimek_przed(tokeny, i)
        znaleziono = _szukaj(tokeny, i, ind.gminy)
        if znaleziono:
            dlugosc, grupy = znaleziono
            grupy = [g for g in grupy if _nazwa_dozwolona(g, tokeny[i], wielkie)]
            if not grupy:
                i += 1
                continue
            # dzielnice Warszawy nie dają gmin („na Bielanach”), chyba że gmina ma dłuższą nazwę („Wola Krzysztoporska”)
            dzielnica = _szukaj(tokeny, i, ind.dzielnice)
            if dzielnica and dzielnica[0] >= dlugosc:
                for k in range(i, i + dzielnica[0]):
                    uzyte[k] = True
                i += dzielnica[0]
                continue
            pominiete = _blokada_rzeki_lub_klubu(tokeny, i, dlugosc, grupy, hydrologia, ind)
            if pominiete:
                for k in range(i, i + pominiete):
                    uzyte[k] = True
                i += pominiete
                continue
            kody = _kody(grupy)
            # homonimię liczymy przed filtrem przyimka; bez przyimka wystarczy, że wśród kandydatów jest miasto
            if not przyimek and not any(sl.jednostka(k).rodzaj == "miejska" for k in kody):
                i += 1
                continue
            skrot = False
            if przyimek and not any(_jest_miastem(k) for k in kody):
                konkurenci = [g for g in _skrocone(tokeny, i, ind.gminy, dlugosc) if _slowo_dozwolone(g.wyrazy[0], tokeny[i], wielkie)]
                if konkurenci:  # „w Grodzisku”: jest gmina Grodzisk, ale też Grodzisk Mazowiecki i Wielkopolski
                    kody = kody + [k for k in _kody(konkurenci) if k not in kody]
                    skrot = True
            dodaj(_Trafienie(i, i + dlugosc, "gmina", "samodzielne", kody, kontekst_wielkich=wielkie, bez_przyimka=not przyimek, skrot=skrot))
            for k in range(i, i + dlugosc):
                uzyte[k] = True
            i += dlugosc
            continue
        # skrót bez gminy o takiej nazwie („w Mińsku” - Mińsk Mazowiecki): brak, ale z uwagą
        if przyimek and tokeny[i].wielka and tokeny[i].zlozony not in _GENERYCZNE_PIERWSZE:
            konkurenci = [g for g in _skrocone(tokeny, i, ind.gminy, 1)
                          if g.wyrazy[0] not in _GENERYCZNE_PIERWSZE and _slowo_dozwolone(g.wyrazy[0], tokeny[i], wielkie)]
            if konkurenci and not (_nazwa_to_rzeka(konkurenci)):
                dodaj(_Trafienie(i, i + 1, "gmina", "samodzielne", _kody(konkurenci), kontekst_wielkich=wielkie, skrot=True))
                uzyte[i] = True
                i += 1
                continue
        i += 1
    return trafienia


def _nazwa_to_rzeka(grupy: list[_Grupa]) -> bool:
    return bool({g.wyrazy[:1] for g in grupy} & _RZEKI)


def _przypisz_zakres_po(trafienia: list[_Trafienie]) -> None:
    """Zakres „po”: powiaty bez województwa przed listą dostają województwo stojące tuż za nią."""
    woje = [w for w in trafienia if w.typ == "woj" and w.kody]
    if not woje:
        return
    starty = [w.start for w in woje]
    lancuchy: dict[int, set[str]] = defaultdict(set)
    for w in woje:
        lancuchy[w.lancuch].add(w.kody[0][:2])
    for h in trafienia:
        if h.typ == "pow" and not h.zakres:
            idx = bisect_left(starty, h.lancuch_koniec)
            if idx < len(woje) and starty[idx] - h.lancuch_koniec <= 3:
                h.zakres = set(lancuchy[woje[idx].lancuch])


# --------------------------------------------------------------------------- rola jednostki organizacyjnej

def _czlon_jednostki(token: Token) -> bool:
    """Czy wyraz może należeć do nazwy jednostki („Komenda”, „Powiatowej”, „KPP”, „komisariatu”, „Policji”)."""
    z = token.zlozony
    return (token.wielka or z.startswith(_JEDNOSTKA_PREFIKSY) or z in _JEDNOSTKA_WYRAZY or z in _JEDNOSTKA_SKROTY
            or z.startswith(_JEDNOSTKA_PRZEDROSTKI_MALE) or z in _JEDNOSTKA_SLOWA_MALE)


def _jednostka_przed(tokeny: list[Token], start: int) -> str | None:
    """Czy nazwa stoi w „Komenda ... Policji w X”: zwraca poziom jednostki (wojewodztwo/powiat/gmina) albo None.

    Przed „w” szukamy wstecz wyłącznie wyrazów nazwy jednostki (wielkie litery, skróty KPP/KMP/KWP/KSP/KP/JRG/PSP,
    „komisariatu” małą literą), więc „... Komendy Wojewódzkiej Policji w Lublinie zatrzymali w Chełmie” nie
    przenosi roli na Chełm.
    """
    if start == 0 or tokeny[start - 1].zlozony not in ("w", "we"):
        return None
    poziom, znaleziono = sl.GMINA, False
    k = start - 2
    while k >= 0 and start - 2 - k < 6 and _czlon_jednostki(tokeny[k]):
        if any(c in tokeny[k + 1].sep for c in _KONIEC_ZDANIA):  # granica zdania
            break
        z = tokeny[k].zlozony
        if z.startswith(_JEDNOSTKA_PREFIKSY) or z in _JEDNOSTKA_WYRAZY or z in _JEDNOSTKA_SKROTY:
            znaleziono = True
        if z.startswith("wojewodzk") or z == "kwp" or (z == "psp" and k > 0 and tokeny[k - 1].zlozony == "kw"):
            poziom = sl.WOJEWODZTWO
        elif poziom != sl.WOJEWODZTWO and (
                z.startswith("powiatow") or z == "kpp" or (z == "kp" and k + 1 < len(tokeny) and tokeny[k + 1].zlozony == "psp")):
            poziom = sl.POWIAT
        k -= 1
    return poziom if znaleziono else None


# --------------------------------------------------------------------------- rozstrzyganie

def _wartosc_kodu_gminy(kod: str) -> float:
    j = sl.jednostka(kod)
    return PEWNOSC_GMINA_SAMODZIELNA["grodzka" if j.grodzka else j.rodzaj]


def _dokladnosc(kod: str) -> str:
    return sl.poziom_kodu(kod)


def _rodzaj(typ: str) -> str:
    return {"woj": sl.WOJEWODZTWO, "region": sl.WOJEWODZTWO, "pow": sl.POWIAT, "gmina": sl.GMINA}[typ]


@dataclass(slots=True)
class _Rozstrzygniecie:
    kody: tuple[str, ...]
    pewnosc: float
    uwagi: tuple[str, ...] = ()
    odrzucone: bool = False  # nazwa wieloznaczna bez rozstrzygnięcia: nic nie przyjęto


def _wspolny_poziom(kody: list[str]) -> tuple[str, int] | None:
    for dlugosc in (4, 2):
        if len({k[:dlugosc] for k in kody}) == 1:
            return kody[0][:dlugosc], dlugosc
    return None


def _spadek(kody: list[str], uwagi: list[str]) -> _Rozstrzygniecie:
    wspolny = _wspolny_poziom(kody)
    uwagi = uwagi + ["homonim"]
    if wspolny and wspolny[1] == 4:
        return _Rozstrzygniecie((wspolny[0],), PEWNOSC_SPADEK_DO_POWIATU, tuple(uwagi + ["spadek-do-powiatu"]))
    if wspolny and wspolny[1] == 2:
        return _Rozstrzygniecie((wspolny[0],), PEWNOSC_SPADEK_DO_WOJEWODZTWA, tuple(uwagi + ["spadek-do-wojewodztwa"]))
    return _Rozstrzygniecie((), 0.0, tuple(uwagi + ["niejednoznaczne"]), odrzucone=True)


def _rozstrzygnij_woj(h: _Trafienie) -> _Rozstrzygniecie:
    pewnosc = {"znacznik": PEWNOSC_WOJ_ZNACZNIK, "zakres": PEWNOSC_WOJ_ZAKRES, "region": PEWNOSC_REGION}[h.tryb]
    return _Rozstrzygniecie(tuple(h.kody[:1]), pewnosc)


def _zawez(kandydaci: list[str], konteksty: list[tuple[set[str], int]]) -> tuple[list[str], bool]:
    """Zawęża kandydatów kontekstem (zbiory kodów województw lub powiatów); zwraca (kandydaci, użyto_kontekstu)."""
    for zbior, dlugosc in konteksty:
        if zbior:
            podzbior = [k for k in kandydaci if k[:dlugosc] in zbior]
            if podzbior and len(podzbior) < len(kandydaci):
                return podzbior, True
            if podzbior:
                return kandydaci, False
    return kandydaci, False


def _zawez_skrot(kandydaci: list[str], konteksty: list[tuple[set[str], int]]) -> tuple[list[str], bool]:
    """Skrócona nazwa przyjmuje tylko kandydatów potwierdzonych kontekstem (nawet jeśli kandydat jest jeden)."""
    for zbior, dlugosc in konteksty:
        if zbior:
            podzbior = [k for k in kandydaci if k[:dlugosc] in zbior]
            if podzbior:
                return podzbior, True
    return kandydaci, False


def _rozstrzygnij_powiat(h: _Trafienie, wszystkie_woj: set[str]) -> _Rozstrzygniecie:
    kandydaci = list(h.kody)
    uwagi: list[str] = []
    if len(kandydaci) > 1:
        kandydaci, uzyto = _zawez(kandydaci, [(h.zakres, 2), (wszystkie_woj, 2)])
        if uzyto:
            uwagi.append("kontekst")
    if len(kandydaci) == 1:
        return _Rozstrzygniecie((kandydaci[0],), PEWNOSC_PO_KONTEKSCIE if uwagi else PEWNOSC_POWIAT, tuple(uwagi))
    if len(h.kody) > 1:
        return _Rozstrzygniecie((), 0.0, ("homonim", "niejednoznaczne"), odrzucone=True)
    return _Rozstrzygniecie((), 0.0, ("brak-kodu",), odrzucone=True)


def _preferowane_miasto(kandydaci: list[str]) -> str | None:
    """Miasto zamiast gminy wiejskiej o tej samej nazwie: tylko gdy wszystkie gminy o tej nazwie są w jednym województwie.

    Miasto na prawach powiatu obok gminy wiejskiej z innego województwa („Leszno”, „Olsztyn”) nie wygrywa:
    bez kontekstu nie wiadomo, o które chodzi. Liczą się gminy o tej samej nazwie; kandydaci o innej nazwie,
    dopasowani tylko fleksją („Siedlcach” pasuje też do gminy Siedlec), nie blokują miasta.
    """
    po_nazwie: dict[str, list[str]] = defaultdict(list)
    for k in kandydaci:
        po_nazwie[sl.jednostka(k).nazwa].append(k)
    wybrane: list[str] = []
    for kody in po_nazwie.values():
        if len({k[:2] for k in kody}) != 1:
            continue
        grodzkie = [k for k in kody if sl.jednostka(k).grodzka]
        if len(grodzkie) == 1:
            wybrane.append(grodzkie[0])
        elif len(kody) > 1 and len({k[:4] for k in kody}) == 1:
            miejskie = [k for k in kody if sl.jednostka(k).rodzaj == "miejska"]
            if len(miejskie) == 1:
                wybrane.append(miejskie[0])
    return wybrane[0] if len(wybrane) == 1 else None


def _rozstrzygnij_gmine(h: _Trafienie, tokeny: list[Token], ctx_pow: set[str], ctx_woj: set[str]) -> _Rozstrzygniecie:
    kandydaci = list(h.kody)
    uwagi: list[str] = []
    jednostki = {k: sl.jednostka(k) for k in kandydaci}
    if h.znacznik == "gm":  # „gmina X” to nie miasto na prawach powiatu, jeśli jest inna
        reszta = [k for k in kandydaci if not jednostki[k].grodzka]
        kandydaci = reszta or kandydaci
    elif h.znacznik == "miasto":  # „miasto X” to nie gmina wiejska, jeśli jest inna
        miejskie = [k for k in kandydaci if jednostki[k].miejska]
        kandydaci = miejskie or kandydaci
    konteksty = [(ctx_pow, 4), (ctx_woj, 2)]
    if h.skrot:
        kandydaci, uzyto = _zawez_skrot(kandydaci, konteksty)
        if not uzyto:
            return _Rozstrzygniecie((), 0.0, ("skrot", "niejednoznaczne"), odrzucone=True)
        uwagi += ["skrot", "kontekst"]
    elif len(kandydaci) > 1:
        kandydaci, uzyto = _zawez(kandydaci, konteksty)
        if uzyto:
            uwagi.append("kontekst")
    if len(kandydaci) == 1:
        kod = kandydaci[0]
        if h.tryb == "dzielnica":
            pewnosc = PEWNOSC_DZIELNICA
        elif h.tryb == "znacznik":
            pewnosc = PEWNOSC_PO_KONTEKSCIE if "kontekst" in uwagi else PEWNOSC_GMINA_ZNACZNIK
        else:
            pewnosc = _wartosc_kodu_gminy(kod)
            if h.kontekst_wielkich:
                pewnosc *= WSPOLCZYNNIK_WIELKICH_LITER
            if "kontekst" in uwagi:
                pewnosc = max(pewnosc, PEWNOSC_PO_KONTEKSCIE)
        if h.skrot:
            pewnosc = min(pewnosc, PEWNOSC_SKROT_MAX)
        wynik = _Rozstrzygniecie((kod,), pewnosc, tuple(uwagi))
    else:
        miasto = _preferowane_miasto(kandydaci) if PREFERUJ_MIASTO and h.znacznik != "gm" else None
        if miasto:
            pewnosc = min(PEWNOSC_MIASTO_PREFEROWANE, PEWNOSC_SKROT_MAX) if h.skrot else PEWNOSC_MIASTO_PREFEROWANE
            wynik = _Rozstrzygniecie((miasto,), pewnosc, tuple(uwagi + ["homonim", "preferowane-miasto"]))
        else:
            wynik = _spadek(kandydaci, uwagi)
    if wynik.kody and h.tryb == "samodzielne" and len(wynik.kody[0]) == 7:
        poziom = _jednostka_przed(tokeny, h.start)
        if poziom:
            kod = wynik.kody[0]
            dlugosc = {sl.WOJEWODZTWO: 2, sl.POWIAT: 4, sl.GMINA: 7}[poziom]
            uwagi_jednostki = ["jednostka"] + ([f"spadek-do-{'wojewodztwa' if dlugosc == 2 else 'powiatu'}"] if dlugosc < 7 else [])
            return _Rozstrzygniecie((kod[:dlugosc],), min(wynik.pewnosc, PEWNOSC_JEDNOSTKA_MAX), wynik.uwagi + tuple(uwagi_jednostki))
    return wynik


def _fraza(tekst: str, tokeny: list[Token], h: _Trafienie) -> tuple[str, int, int]:
    start, koniec = tokeny[h.start].start, tokeny[h.koniec - 1].koniec
    return tekst[start:koniec], start, koniec


# --------------------------------------------------------------------------- zasięg

@dataclass(slots=True)
class _Przyjety:
    kod: str
    pewnosc: float
    h: _Trafienie
    uwagi: tuple[str, ...]

    @property
    def zasieg(self) -> bool:
        """Województwo, region lub powiat wskazane wprost (a nie miejsce jednostki ani spadek homonimu)."""
        return self.h.typ in ("woj", "region", "pow")


def _bez_konca_zdania(tokeny: list[Token], od: int, do: int) -> bool:
    """Czy między tokenami [od, do) nie ma końca zdania ani średnika (spacja przed każdym z nich liczy się)."""
    return not any(c in tokeny[k].sep for k in range(od, do) for c in _KONIEC_ZDANIA)


def _przylegle(tokeny: list[Token], szerszy: _Przyjety, wezszy: _Przyjety) -> bool:
    """Czy węższe miejsce doprecyzowuje szersze w zapisie adresowym („woj. X, powiat Y, gmina Z”, „Z, woj. X”)."""
    s, w = szerszy.h, wezszy.h
    if s.koniec <= w.start:  # szersze stoi przed węższym: węższe musi mieć znacznik (gmina/miasto/powiat)
        if not (w.znacznik or w.typ == "pow"):
            return False
        luka = w.start - s.koniec
        return luka <= 4 and (luka > 0 and _bez_konca_zdania(tokeny, s.koniec, w.start) or luka == 0 and _bez_konca_zdania(tokeny, w.start, w.start + 1))
    if w.koniec <= s.start:  # szersze stoi po węższym
        luka = s.start - w.koniec
        if w.znacznik or w.typ == "pow":
            return luka <= 4 and _bez_konca_zdania(tokeny, w.koniec, s.start)
        # samodzielna nazwa: tylko zapis „Chełm, woj. lubelskie” / „Chełm (woj. lubelskie)”
        if luka > 1 or not _bez_konca_zdania(tokeny, w.koniec, s.start):
            return False
        sep = tokeny[w.koniec].sep
        return "," in sep or "(" in sep
    return False


def _wybierz_kody(tokeny: list[Token], przyjete: list[_Przyjety]) -> list[_Przyjety]:
    """Zostawia przyjęte kody, z pominięciem szerszych, które są tylko doprecyzowane węższym miejscem.

    Szerszy kod (województwo lub powiat wskazane wprost) zostaje, gdy węższe miejsce jest osobną wzmianką
    (zasięg alertu się nie zawęża), także gdy to województwo pomogło rozstrzygnąć homonim w innym zdaniu.
    Znika, gdy jest doprecyzowany: lista powiatów pod województwem albo zapis adresowy stojący obok
    („woj. X, powiat Y, gmina Z”, „Z, woj. X”). Szerszy kod z miejsca jednostki lub ze spadku homonimu
    (nie wskazany wprost) znika zawsze, gdy w tekście jest węższe miejsce w nim zawarte.
    """
    wezsze: dict[str, list[_Przyjety]] = defaultdict(list)
    przypisane: set[str] = set()  # województwa, pod którymi stoi lista powiatów
    for q in przyjete:
        for d in (2, 4):
            if len(q.kod) > d:
                wezsze[q.kod[:d]].append(q)
        if q.h.typ == "pow":
            przypisane.update(z for z in q.h.zakres if q.kod.startswith(z))
    zostaja: list[_Przyjety] = []
    for idx, p in enumerate(przyjete):
        if len(p.kod) == 7 or p.kod not in wezsze:
            zostaja.append(p)
            continue
        if not p.zasieg or p.kod in przypisane:
            continue
        doprecyzowane = False
        for sasiad in range(idx + 1, len(przyjete)):  # sąsiedzi po pozycji: okno kilku tokenów, nie cały tekst
            q = przyjete[sasiad]
            if q.h.start - p.h.koniec > 4:
                break
            if q.kod.startswith(p.kod) and len(q.kod) > len(p.kod) and _przylegle(tokeny, p, q):
                doprecyzowane = True
                break
        if not doprecyzowane:
            for sasiad in range(idx - 1, -1, -1):
                q = przyjete[sasiad]
                if p.h.start - q.h.koniec > 4:
                    break
                if q.kod.startswith(p.kod) and len(q.kod) > len(p.kod) and _przylegle(tokeny, p, q):
                    doprecyzowane = True
                    break
        if not doprecyzowane:
            zostaja.append(p)
    return zostaja


def _znajdz_kraj(zlozony: str) -> tuple[int, int] | None:
    """Pozycje frazy zasięgu krajowego w tekście (pozycje z tekstu złożonego jeden do jednego z oryginałem)."""
    najlepsze: tuple[int, int] | None = None
    for wzorzec in _WZORCE_KRAJU:
        dopasowanie = wzorzec.search(zlozony)
        if dopasowanie:
            pozycje = dopasowanie.span(1)
            if najlepsze is None or pozycje[0] < najlepsze[0]:
                najlepsze = pozycje
    return najlepsze


def _utnij(tekst: str) -> str:
    obciety = tekst[:MAKS_DLUGOSC]
    if tekst[MAKS_DLUGOSC].isalnum() and obciety[-1].isalnum():  # nie tnij wyrazu na pół
        ostatnia = max(obciety.rfind(" "), obciety.rfind("\n"))
        if ostatnia > MAKS_DLUGOSC - 100:
            obciety = obciety[:ostatnia]
    return obciety


def geokoduj(tekst: str | None) -> Wynik:
    """Rozpoznaje w tekście województwa, powiaty i gminy i zwraca ich kody TERYT.

    `teryt` ma kody 2-cyfrowe (województwo), 4-cyfrowe (powiat) i 7-cyfrowe (gmina);
    `dokladnosc` to najgrubszy z przyjętych poziomów (zasięg alertu, nie najmniejsze miejsce).
    Szczegóły każdego miejsca są w `dopasowania`. Tekst dłuższy niż `MAKS_DLUGOSC` jest obcinany (uwaga w wyniku).
    """
    if not tekst or not tekst.strip():
        return Wynik((), BRAK, 0.0, ())
    uwagi_wyniku: tuple[str, ...] = ()
    if len(tekst) > MAKS_DLUGOSC:
        tekst, uwagi_wyniku = _utnij(tekst), ("obcieto-tekst",)
    zlozony = zloz_pozycyjnie(tekst)
    tokeny = tokenizuj(tekst)
    wielkie = wyglada_na_wielkie_litery(tekst)
    trafienia = _szukaj_trafien(tokeny, wielkie, bool(_HYDROLOGIA.search(zlozony)))
    _przypisz_zakres_po(trafienia)

    wyniki: list[tuple[_Trafienie, _Rozstrzygniecie]] = []
    for h in trafienia:
        if h.typ in ("woj", "region"):
            wyniki.append((h, _rozstrzygnij_woj(h)))
    ctx_woj = {r.kody[0] for h, r in wyniki if r.kody}
    for h in trafienia:
        if h.typ == "pow":
            wyniki.append((h, _rozstrzygnij_powiat(h, ctx_woj)))
    ctx_pow = {r.kody[0] for h, r in wyniki if r.kody and len(r.kody[0]) == 4}
    for h in trafienia:
        if h.typ == "gmina":
            wyniki.append((h, _rozstrzygnij_gmine(h, tokeny, ctx_pow, ctx_woj)))
    wyniki.sort(key=lambda para: para[0].start)

    dopasowania: list[Dopasowanie] = []
    przyjete: list[_Przyjety] = []
    odrzucone = 0
    for h, r in wyniki:
        # nazwa bez przyimka: tylko miasto; wieś lub miasteczko („Kotła czarownic”) to nie miejsce zdarzenia
        if h.bez_przyimka and r.kody and len(r.kody[0]) == 7 and sl.jednostka(r.kody[0]).rodzaj != "miejska":
            continue
        fraza, start, koniec = _fraza(tekst, tokeny, h)
        dokladnosc = _dokladnosc(r.kody[0]) if r.kody else BRAK
        dopasowania.append(Dopasowanie(
            fraza=fraza, start=start, koniec=koniec, rodzaj=_rodzaj(h.typ), tryb=h.tryb, teryt=r.kody,
            dokladnosc=dokladnosc, pewnosc=round(r.pewnosc, 2),
            kandydaci=tuple(h.kody) if len(h.kody) > 1 else (), uwagi=r.uwagi))
        if r.kody:
            przyjete.append(_Przyjety(r.kody[0], r.pewnosc, h, r.uwagi))
        else:
            odrzucone += 1

    zasieg_kraju = _znajdz_kraj(zlozony)
    if zasieg_kraju:
        start, koniec = zasieg_kraju
        dopasowania.append(Dopasowanie(
            fraza=tekst[start:koniec], start=start, koniec=koniec, rodzaj=KRAJ, tryb=KRAJ,
            teryt=(), dokladnosc=KRAJ, pewnosc=PEWNOSC_KRAJ))
        dopasowania.sort(key=lambda d: d.start)
    dopasowania_krotka = tuple(dopasowania)

    zostaja = _wybierz_kody(tokeny, przyjete)
    kody = tuple(sorted({p.kod for p in zostaja}))
    if not kody:
        if zasieg_kraju:  # zasięg krajowy bez konkretnych miejsc
            return Wynik((), KRAJ, PEWNOSC_KRAJ, dopasowania_krotka, uwagi_wyniku)
        return Wynik((), BRAK, 0.0, dopasowania_krotka, uwagi_wyniku)
    pewnosc = min(p.pewnosc for p in zostaja)
    if odrzucone:
        pewnosc *= WSPOLCZYNNIK_ODRZUCONEJ_NAZWY
    if zasieg_kraju:  # zasięg krajowy jest najgrubszy, ale nie zeruje konkretnych miejsc
        return Wynik(kody, KRAJ, round(min(pewnosc, PEWNOSC_KRAJ), 2), dopasowania_krotka, uwagi_wyniku)
    dokladnosc = min((_dokladnosc(k) for k in kody), key=lambda p: sl.DLUGOSC_KODU[p])
    return Wynik(kody, dokladnosc, round(pewnosc, 2), dopasowania_krotka, uwagi_wyniku)
