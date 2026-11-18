import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from ..zbieranie import BladFormatu
from .wspolne import data_iso, odczytaj, wpis

ATOM = "{http://www.w3.org/2005/Atom}"
GDACS = "{http://www.gdacs.org}"
GEO = "{http://www.georss.org/georss}"


def drzewo(odpowiedz, tag):
    tekst = odczytaj(odpowiedz)
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", tekst, re.I) or "\x00" in tekst:
        raise ValueError
    xml = ElementTree.fromstring(tekst)
    if xml.tag != tag:
        raise ValueError
    return xml


def data_rss(data):
    czas = parsedate_to_datetime(data)
    return czas if czas.tzinfo else czas.replace(tzinfo=timezone.utc)


def parsuj_kanal(odpowiedz, nazwa, *, atom=False, wybierz=None):
    try:
        if atom:
            feed = drzewo(odpowiedz, ATOM + "feed")
            rekordy = feed.findall(ATOM + "entry")
        else:
            korzen = drzewo(odpowiedz, "rss")
            feed = korzen.find("channel")
            if feed is None:
                raise ValueError
            rekordy = feed.findall("item")
        if not feed.findtext(ATOM + "title" if atom else "title"):
            raise ValueError
        if not rekordy and any(el.tag.split("}")[-1] in {"item", "entry"} for el in feed.iter()):
            raise ValueError
        wynik = []
        for el in rekordy:
            pola = wybierz(el) if wybierz else {}
            if pola is None:
                continue
            if atom:
                link = next(a.attrib["href"] for a in el.findall(ATOM + "link")
                            if a.get("rel", "alternate") == "alternate")
                data = data_iso(el.findtext(ATOM + "published") or el.findtext(ATOM + "updated"), timezone.utc)
                tytul = el.findtext(ATOM + "title")
                ident = el.findtext(ATOM + "id") or link
            else:
                link = el.findtext("link")
                data = data_rss(el.findtext("pubDate"))
                tytul = el.findtext("title")
                ident = el.findtext("guid") or link
            wynik.append(wpis(ident, tytul, link, data, **pola))
        return wynik
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration, ElementTree.ParseError) as exc:
        raise BladFormatu(f"{nazwa}: nieoczekiwany format kanału lub brak wymaganych pól wpisu.") from exc
