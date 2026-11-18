import json
import math
import re
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from ..models import Klasa, Wpis
from ..zbieranie import BladFormatu

WARSZAWA = ZoneInfo("Europe/Warsaw")
POLSKA = (14.0, 48.9, 24.2, 55.0)
LIMIT_TRESCI = 16000
POMIJANE = {"script", "style", "template", "iframe", "noscript", "svg"}
PUSTE = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Element:
    def __init__(self, tag="", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.dzieci = []

    def ma_klase(self, nazwa):
        return nazwa in self.attrs.get("class", "").split()

    def znajdz(self, warunek):
        for dziecko in self.dzieci:
            if isinstance(dziecko, Element):
                if warunek(dziecko):
                    yield dziecko
                yield from dziecko.znajdz(warunek)

    def tekst(self, separator=""):
        fragmenty = [
            dziecko if isinstance(dziecko, str) else dziecko.tekst(separator)
            for dziecko in self.dzieci
        ]
        return separator.join(fragmenty)


class DrzewoHTML(HTMLParser):
    def __init__(self, tekst):
        super().__init__(convert_charrefs=True)
        self.korzen = Element()
        self.stos = [self.korzen]
        self.feed(tekst)
        self.close()

    def handle_starttag(self, tag, attrs):
        if len(self.stos) >= 120:
            raise BladFormatu("Zbyt głęboko zagnieżdżony HTML.")
        dziecko = Element(tag, attrs)
        if tag not in POMIJANE and self.stos[-1].tag not in POMIJANE:
            self.stos[-1].dzieci.append(dziecko)
            if tag == "br":
                self.stos[-1].dzieci.append("\n")
        elif self.stos[-1].tag in POMIJANE and tag not in POMIJANE:
            return
        if tag not in PUSTE:
            self.stos.append(dziecko)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for indeks in range(len(self.stos) - 1, 0, -1):
            if self.stos[indeks].tag == tag:
                del self.stos[indeks:]
                break

    def handle_data(self, data):
        if self.stos[-1].tag not in POMIJANE:
            self.stos[-1].dzieci.append(data)


def odczytaj(odpowiedz):
    return odpowiedz.tresc.decode(odpowiedz.kodowanie or "utf-8").lstrip("\ufeff")


def json_dane(odpowiedz):
    return json.loads(odczytaj(odpowiedz))


def uprosc(wartosc, limit=LIMIT_TRESCI):
    return " ".join(wartosc.split())[:limit]


def czysty_tekst(wartosc, limit=LIMIT_TRESCI):
    if not isinstance(wartosc, str):
        raise ValueError
    return uprosc(DrzewoHTML(wartosc).korzen.tekst(), limit)


def data_iso(wartosc, strefa=WARSZAWA):
    czas = datetime.fromisoformat(wartosc)
    return czas if czas.tzinfo else czas.replace(tzinfo=strefa)


def link_http(wartosc):
    adres = urlsplit(wartosc)
    if adres.scheme not in {"https", "http"} or not adres.hostname or adres.username is not None:
        raise ValueError
    return wartosc


def identyfikator(wartosc):
    if not isinstance(wartosc, (str, int)) or not str(wartosc).strip():
        raise ValueError
    wartosc = str(wartosc).strip()
    return wartosc if len(wartosc) <= 255 else sha256(wartosc.encode()).hexdigest()


def wpis(ident, tytul, link, data, *, tresc="", **pola):
    tytul = czysty_tekst(tytul, 500)
    if not tytul:
        raise ValueError
    pola.setdefault("dokladnosc", Wpis.Dokladnosc.BRAK)
    return dict(zewnetrzny_id=identyfikator(ident), tytul=tytul, link=link_http(link),
                opublikowano_at=data, tresc=tresc[:LIMIT_TRESCI], klasa=Klasa.ZWYKLY, **pola)


def punkt(szerokosc, dlugosc):
    lat, lon = float(szerokosc), float(dlugosc)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError
    return dict(szerokosc=lat, dlugosc=lon, dokladnosc=Wpis.Dokladnosc.PUNKT, pewnosc_lokalizacji=1)


def w_obszarze(polozenie, granice):
    zachod, poludnie, wschod, polnoc = granice
    return (poludnie <= polozenie["szerokosc"] <= polnoc
            and zachod <= polozenie["dlugosc"] <= wschod)


def kody_powiatow(dane):
    wartosci = re.split(r"[,;\s]+", dane) if isinstance(dane, str) else dane
    return sorted({str(kod) for kod in (wartosci or []) if re.fullmatch(r"[0-9]{4}", str(kod))})
