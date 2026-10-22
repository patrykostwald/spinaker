"""Dane Lotto: pobieranie z publicznych źródeł, zapis CSV, kontrola kompletności.

Zasady pobierania (START.md): pojedyncze odczyty, przerwa między zapytaniami,
User-Agent z opisem, sprawdzenie robots.txt przed każdym hostem. Bez logowania i kont.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import random
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

KATALOG = Path(__file__).resolve().parent
PLIK_CSV = KATALOG / "dane" / "lotto.csv"
PLIK_LOG = KATALOG / "dane" / "pobrania.log"

USER_AGENT = ("LottoEksperyment/1.0 (prywatny eksperyment statystyczny; pojedyncze odczyty "
              "z przerwami; kontakt przez wlasciciela repozytorium)")
PRZERWA_S = 3.0

# Archiwum publiczne: jeden plik tekstowy z całą historią, wiersz "1. 27.01.1957 8,12,31,39,43,45" [DP].
ZRODLO_ARCHIWUM = "http://www.mbnet.com.pl/dl.txt"
# Strona Totalizatora Sportowego, publiczne odczyty używane przez stronę wyników [DP: adresy do potwierdzenia].
LOTTO_PL_WYNIKI = ("https://www.lotto.pl/api/lotteries/draw-results/by-date-per-game"
                   "?gameType=Lotto&drawDate={data}&index=1&size=10&sort=drawDate&order=DESC")
LOTTO_PL_NAGRODY = "https://www.lotto.pl/api/lotteries/draw-prizes/lotto/{numer}"

POLA = ["numer", "data", "n1", "n2", "n3", "n4", "n5", "n6", "w6", "w5", "w4", "w3"]


@dataclass
class Losowanie:
    numer: int
    data: dt.date
    liczby: tuple[int, ...]
    # Wygrane w zł za jeden zakład w stopniach 6, 5, 4, 3 (None = brak danych).
    nagrody: dict[int, float | None] = field(default_factory=lambda: {6: None, 5: None, 4: None, 3: None})

    @property
    def maska(self) -> int:
        return na_maske(self.liczby)


def na_maske(liczby) -> int:
    m = 0
    for x in liczby:
        m |= 1 << x
    return m


# ---------- pobieranie ----------

_roboty: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_ostatnie: dict[str, float] = {}


def loguj(tekst: str) -> None:
    PLIK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PLIK_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {tekst}\n")


def wolno_pobrac(url: str) -> bool:
    """Sprawdza robots.txt hosta (raz na uruchomienie). Brak robots.txt = brak zakazu."""
    cz = urlsplit(url)
    host = f"{cz.scheme}://{cz.netloc}"
    if host not in _roboty:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.parse(["User-agent: *", "Disallow: /"])
            else:
                rp.parse([])
        except OSError:
            _roboty[host] = None
            return False
        _roboty[host] = rp
    rp = _roboty[host]
    return rp is not None and rp.can_fetch(USER_AGENT, url)


def pobierz_tekst(url: str) -> str | None:
    """Pojedynczy odczyt z przerwą i sprawdzeniem robots.txt; None gdy niedostępne lub zabronione."""
    if not wolno_pobrac(url):
        loguj(f"POMINIETO (robots.txt lub brak dostepu) {url}")
        return None
    host = urlsplit(url).netloc
    czekaj = PRZERWA_S - (time.monotonic() - _ostatnie.get(host, -1e9))
    if czekaj > 0:
        time.sleep(czekaj)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            surowe = r.read()
            kodowanie = r.headers.get_content_charset() or "utf-8"
    except OSError as e:
        loguj(f"BLAD {url}: {e}")
        return None
    finally:
        _ostatnie[host] = time.monotonic()
    loguj(f"OK {url} ({len(surowe)} B)")
    return surowe.decode(kodowanie, "replace")


# ---------- parsowanie ----------

_WIERSZ = re.compile(r"^\s*(\d+)\.\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+([\d,\s]+?)\s*$")


def parsuj_archiwum(tekst: str) -> list[Losowanie]:
    """Format archiwum: 'numer. DD.MM.RRRR a,b,c,d,e,f' (jeden wiersz na losowanie)."""
    wynik = []
    for wiersz in tekst.splitlines():
        m = _WIERSZ.match(wiersz)
        if not m:
            continue
        liczby = tuple(sorted(int(x) for x in m.group(5).replace(" ", "").split(",") if x))
        data = dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        wynik.append(Losowanie(int(m.group(1)), data, liczby))
    return wynik


def _szukaj(obj, warunek):
    """Rekurencyjnie zwraca słowniki JSON spełniające warunek (odporne na drobne zmiany formatu)."""
    if isinstance(obj, dict):
        if warunek(obj):
            yield obj
        for v in obj.values():
            yield from _szukaj(v, warunek)
    elif isinstance(obj, list):
        for v in obj:
            yield from _szukaj(v, warunek)


def parsuj_lotto_pl_wyniki(tekst: str) -> list[tuple[int, dt.date, tuple[int, ...]]]:
    dane = json.loads(tekst)
    out = []
    for d in _szukaj(dane, lambda o: o.get("gameType") == "Lotto" and isinstance(o.get("resultsJson"), list)):
        liczby = tuple(sorted(int(x) for x in d["resultsJson"]))
        if len(liczby) != 6:
            continue
        data = dt.date.fromisoformat(str(d.get("drawDate", ""))[:10])
        out.append((int(d.get("drawSystemId", 0)), data, liczby))
    return out


def parsuj_lotto_pl_nagrody(tekst: str) -> dict[int, float | None]:
    """Stopnie lotto.pl: 1 = szóstka, 2 = piątka, 3 = czwórka, 4 = trójka [DP]."""
    dane = json.loads(tekst)
    stopnie = {1: 6, 2: 5, 3: 4, 4: 3}
    nagrody: dict[int, float | None] = {6: None, 5: None, 4: None, 3: None}
    for d in _szukaj(dane, lambda o: o.get("gameType") == "Lotto" and isinstance(o.get("prizes"), dict)):
        for klucz, p in d["prizes"].items():
            if str(klucz).isdigit() and int(klucz) in stopnie and isinstance(p, dict):
                wartosc = p.get("prizeValue")
                if isinstance(wartosc, (int, float)) and wartosc > 0:
                    nagrody[stopnie[int(klucz)]] = float(wartosc)
    return nagrody


# ---------- CSV ----------

def zapisz_csv(losowania: list[Losowanie], plik: Path = PLIK_CSV) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    with plik.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(POLA)
        for l in losowania:
            w.writerow([l.numer, l.data.isoformat(), *l.liczby,
                        *("" if l.nagrody.get(k) is None else f"{l.nagrody[k]:.2f}" for k in (6, 5, 4, 3))])


def wczytaj_csv(plik: Path = PLIK_CSV) -> list[Losowanie]:
    if not plik.exists():
        return []
    out = []
    with plik.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nagrody = {k: (float(r[f"w{k}"]) if r.get(f"w{k}") else None) for k in (6, 5, 4, 3)}
            out.append(Losowanie(int(r["numer"]), dt.date.fromisoformat(r["data"]),
                                 tuple(int(r[f"n{i}"]) for i in range(1, 7)), nagrody))
    return out


# ---------- kontrola ----------

def kontrola(losowania: list[Losowanie]) -> dict:
    """Kompletność: liczba losowań, luki w numeracji, duplikaty, błędne zestawy, kolejność dat."""
    numery = [l.numer for l in losowania]
    zbior = set(numery)
    luki = [n for n in range(1, max(numery, default=0) + 1) if n not in zbior]
    duplikaty_numerow = sorted({n for n in numery if numery.count(n) > 1}) if len(zbior) != len(numery) else []
    daty = [l.data for l in losowania]
    duplikaty_dat = sorted({d.isoformat() for d in daty if daty.count(d) > 1}) if len(set(daty)) != len(daty) else []
    bledne = [l.numer for l in losowania
              if len(l.liczby) != 6 or len(set(l.liczby)) != 6 or not all(1 <= x <= 49 for x in l.liczby)]
    zla_kolejnosc = [b.numer for a, b in zip(losowania, losowania[1:]) if b.data < a.data]
    return {
        "liczba_losowan": len(losowania),
        "pierwsze": f"{losowania[0].numer} / {losowania[0].data}" if losowania else None,
        "ostatnie": f"{losowania[-1].numer} / {losowania[-1].data}" if losowania else None,
        "luki_w_numeracji": luki,
        "duplikaty_numerow": duplikaty_numerow,
        "duplikaty_dat": duplikaty_dat,
        "bledne_zestawy": bledne,
        "daty_nie_po_kolei": zla_kolejnosc,
        "z_nagrodami": sum(1 for l in losowania if l.nagrody.get(3) is not None),
    }


def porownaj_probke(losowania: list[Losowanie], n: int = 20, ziarno: int = 2026) -> list[dict]:
    """Losowa próbka n losowań porównana z drugim źródłem (lotto.pl, wyszukiwanie po dacie)."""
    probka = random.Random(ziarno).sample(losowania, min(n, len(losowania)))
    wyniki = []
    for l in sorted(probka, key=lambda x: x.data):
        tekst = pobierz_tekst(LOTTO_PL_WYNIKI.format(data=l.data.isoformat()))
        drugie = None
        if tekst:
            try:
                trafione = [z for z in parsuj_lotto_pl_wyniki(tekst) if z[1] == l.data]
                drugie = trafione[0][2] if trafione else None
            except (ValueError, KeyError):
                drugie = None
        wyniki.append({"numer": l.numer, "data": l.data.isoformat(), "archiwum": list(l.liczby),
                       "lotto_pl": list(drugie) if drugie else None,
                       "zgodne": None if drugie is None else drugie == l.liczby})
    return wyniki


def pobierz_nagrody(numer_systemowy: int) -> dict[int, float | None] | None:
    tekst = pobierz_tekst(LOTTO_PL_NAGRODY.format(numer=numer_systemowy))
    if not tekst:
        return None
    try:
        return parsuj_lotto_pl_nagrody(tekst)
    except (ValueError, KeyError):
        return None


def pobierz_wynik_lotto_pl(data: dt.date) -> tuple[int, tuple[int, ...]] | None:
    tekst = pobierz_tekst(LOTTO_PL_WYNIKI.format(data=data.isoformat()))
    if not tekst:
        return None
    try:
        for numer, d, liczby in parsuj_lotto_pl_wyniki(tekst):
            if d == data:
                return numer, liczby
    except (ValueError, KeyError):
        pass
    return None


def odswiez_archiwum() -> list[Losowanie] | None:
    """Pobiera całe archiwum (jeden plik) i scala z nagrodami już zapisanymi w CSV."""
    tekst = pobierz_tekst(ZRODLO_ARCHIWUM)
    if not tekst:
        return None
    nowe = parsuj_archiwum(tekst)
    if not nowe:
        loguj("BLAD archiwum: brak rozpoznanych wierszy")
        return None
    stare = {l.data: l.nagrody for l in wczytaj_csv()}
    for l in nowe:
        if l.data in stare:
            l.nagrody = stare[l.data]
    zapisz_csv(nowe)
    return nowe
