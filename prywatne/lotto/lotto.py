"""Automat Lotto na wirtualnych pieniądzach. Żadnych prawdziwych kuponów, kont ani płatności.

    python lotto.py pobierz [--nagrody N]  # archiwum losowań -> dane/lotto.csv, kontrola, próbka 20 z lotto.pl
    python lotto.py generuj                # kupony wszystkich strategii na najbliższe losowanie
    python lotto.py sprawdz                # wyniki zaległych losowań -> DZIENNIK.csv
    python lotto.py raport                 # wydane, wygrane, bilans dla strategii i łącznie
    python lotto.py strona                 # strona z podglądem -> strona/lotto/ (także po generuj i sprawdz)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import random
import sys
from pathlib import Path

import dane
import strategie

KATALOG = Path(__file__).resolve().parent
KUPONY = KATALOG / "kupony"
DZIENNIK = KATALOG / "DZIENNIK.csv"

BUDZET = 100.0                  # wirtualne zł na każdą strategię na jedno losowanie
CENA = 5.0                      # zł za zakład od 18.08.2026 [DP] - dane/ZRODLA.md
ZAKLADOW = int(BUDZET // CENA)  # 20 zakładów
NAGRODY_SREDNIE = {3: 35.0, 4: 200.0, 5: 7500.0, 6: 3_000_000.0}  # gdy brak prawdziwych kwot [DP]
DNI_LOSOWAN = (1, 3, 5)         # wtorek, czwartek, sobota [DP]
GODZINA_LOSOWANIA = dt.time(22, 0)
KONIEC_SPRZEDAZY = dt.time(21, 30)  # po tej godzinie kupon idzie na następne losowanie (z zapasem) [DP]
WYNIK_PO = dt.time(22, 30)          # od kiedy szukać wyniku

POLA_DZIENNIKA = ["losowanie_data", "strategia", "zakladow", "wydane_zl", "t3", "t4", "t5", "t6",
                  "sr_trafien", "wygrana_zl", "zrodlo_nagrod", "wylosowane", "sprawdzono", "sha256"]


# ---------- terminy ----------

def najblizsze_losowanie(teraz: dt.datetime) -> dt.date:
    d = teraz.date()
    if d.weekday() in DNI_LOSOWAN and teraz.time() < KONIEC_SPRZEDAZY:
        return d
    d += dt.timedelta(days=1)
    while d.weekday() not in DNI_LOSOWAN:
        d += dt.timedelta(days=1)
    return d


def po_losowaniu(data: dt.date, teraz: dt.datetime) -> bool:
    return teraz >= dt.datetime.combine(data, WYNIK_PO)


# ---------- kupony ----------

def suma_kontrolna(kupon: dict) -> str:
    tresc = {k: v for k, v in kupon.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(tresc, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def utworz_kupon(data: dt.date, losowania: list[dane.Losowanie], rng: random.Random,
                 teraz: dt.datetime, zakladow: int = ZAKLADOW) -> dict:
    historia = [l.liczby for l in losowania if l.data < data]
    szostki = frozenset(l.maska for l in losowania if l.data < data)
    kupon = {
        "losowanie_data": data.isoformat(),
        "zapisano": teraz.isoformat(timespec="seconds"),
        "cena_zl": CENA,
        "zakladow_na_strategie": zakladow,
        "dane_do": losowania[-1].data.isoformat() if losowania else None,
        "strategie": {nazwa: [list(z) for z in f(historia, zakladow, rng, szostki)]
                      for nazwa, f in strategie.STRATEGIE.items()},
    }
    kupon["sha256"] = suma_kontrolna(kupon)
    return kupon


def zapisz_kupon(kupon: dict, katalog: Path = KUPONY) -> Path:
    """Blokada: tryb 'x' nie pozwala nadpisać istniejącego pliku (FileExistsError)."""
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / f"{kupon['losowanie_data']}.json"
    with plik.open("x", encoding="utf-8") as f:
        json.dump(kupon, f, ensure_ascii=False, indent=1)
    return plik


def generuj(teraz: dt.datetime | None = None, katalog: Path = KUPONY) -> int:
    teraz = teraz or dt.datetime.now()
    data = najblizsze_losowanie(teraz)
    plik = katalog / f"{data.isoformat()}.json"
    if plik.exists():
        print(f"Kupony na {data} już są ({plik.name}) - nie nadpisuję.")
        return 0
    losowania = dane.wczytaj_csv()
    if not losowania:
        print("Uwaga: brak dane/lotto.csv - strategie `gorace`, `zimne`, `historia` działają bez historii.")
    kupon = utworz_kupon(data, losowania, random.SystemRandom(), teraz)
    try:
        zapisz_kupon(kupon, katalog)
    except FileExistsError:
        print(f"Kupony na {data} już są - nie nadpisuję.")
        return 0
    print(f"Zapisano kupony na {data}: {len(kupon['strategie'])} strategii po {ZAKLADOW} zakładów, "
          f"sha256 {kupon['sha256'][:12]}...")
    return 0


# ---------- sprawdzanie ----------

def policz(zaklady: list[list[int]], wylosowane: tuple[int, ...], nagrody: dict[int, float]) -> dict:
    wyl = set(wylosowane)
    trafienia = [len(wyl & set(z)) for z in zaklady]
    wygrana = sum(nagrody[k] for k in trafienia if k >= 3)
    return {"trafienia": trafienia, "t": {k: trafienia.count(k) for k in (3, 4, 5, 6)}, "wygrana": wygrana}


def sprawdzone(dziennik: Path = DZIENNIK) -> set[str]:
    if not dziennik.exists():
        return set()
    with dziennik.open(encoding="utf-8") as f:
        return {r["losowanie_data"] for r in csv.DictReader(f)}


def dopisz(wiersze: list[dict], dziennik: Path = DZIENNIK) -> None:
    nowy = not dziennik.exists()
    with dziennik.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POLA_DZIENNIKA)
        if nowy:
            w.writeheader()
        w.writerows(wiersze)


class Wyniki:
    """Szuka wyniku losowania: najpierw dane/lotto.csv, potem jedno odświeżenie archiwum, na końcu lotto.pl."""

    def __init__(self):
        self.losowania = {l.data: l for l in dane.wczytaj_csv()}
        self.odswiezone = False

    def __call__(self, data: dt.date) -> tuple[tuple[int, ...], dict[int, float], str] | None:
        if data not in self.losowania and not self.odswiezone:
            self.odswiezone = True
            nowe = dane.odswiez_archiwum()
            if nowe:
                self.losowania = {l.data: l for l in nowe}
        numer = None
        liczby = None
        nagrody_csv: dict = {}
        if data in self.losowania:
            l = self.losowania[data]
            numer, liczby, nagrody_csv = l.numer, l.liczby, l.nagrody
        else:
            z = dane.pobierz_wynik_lotto_pl(data)
            if z:
                numer, liczby = z
        if liczby is None:
            return None
        if all(nagrody_csv.get(k) is not None for k in (3, 4, 5)):
            nagrody, zrodlo = dict(nagrody_csv), "dane/lotto.csv"
        else:
            pobrane = dane.pobierz_nagrody(numer) if numer else None
            if pobrane and all(pobrane.get(k) is not None for k in (3, 4, 5)):
                nagrody, zrodlo = dict(pobrane), "lotto.pl"
            else:
                nagrody, zrodlo = dict(NAGRODY_SREDNIE), "srednie"
        if not nagrody.get(6):
            nagrody[6] = NAGRODY_SREDNIE[6]
        return liczby, nagrody, zrodlo


def sprawdz(teraz: dt.datetime | None = None, katalog: Path = KUPONY, dziennik: Path = DZIENNIK,
            wynik_dla=None) -> int:
    teraz = teraz or dt.datetime.now()
    wynik_dla = wynik_dla or Wyniki()
    gotowe = sprawdzone(dziennik)
    nowych = 0
    for plik in sorted(katalog.glob("*.json")):
        kupon = json.loads(plik.read_text(encoding="utf-8"))
        data_s = kupon["losowanie_data"]
        data = dt.date.fromisoformat(data_s)
        if data_s in gotowe or not po_losowaniu(data, teraz):
            continue
        if suma_kontrolna(kupon) != kupon.get("sha256"):
            print(f"{plik.name}: suma kontrolna się nie zgadza - kupony zmienione po zapisie, pomijam.")
            continue
        wynik = wynik_dla(data)
        if wynik is None:
            print(f"{data}: wyniku jeszcze nie ma - spróbuję przy następnym uruchomieniu.")
            continue
        wylosowane, nagrody, zrodlo = wynik
        wiersze = []
        for nazwa, zaklady in kupon["strategie"].items():
            p = policz(zaklady, wylosowane, nagrody)
            wiersze.append({
                "losowanie_data": data_s, "strategia": nazwa, "zakladow": len(zaklady),
                "wydane_zl": f"{len(zaklady) * kupon['cena_zl']:.2f}",
                "t3": p["t"][3], "t4": p["t"][4], "t5": p["t"][5], "t6": p["t"][6],
                "sr_trafien": f"{sum(p['trafienia']) / len(zaklady):.3f}",
                "wygrana_zl": f"{p['wygrana']:.2f}", "zrodlo_nagrod": zrodlo,
                "wylosowane": " ".join(map(str, wylosowane)),
                "sprawdzono": teraz.isoformat(timespec="seconds"), "sha256": kupon["sha256"],
            })
        dopisz(wiersze, dziennik)
        nowych += 1
        print(f"{data}: wylosowane {' '.join(map(str, wylosowane))}; " +
              ", ".join(f"{w['strategia']} {w['wygrana_zl']} zł" for w in wiersze))
    if not nowych:
        print("Nic nowego do sprawdzenia.")
    return 0


# ---------- raport ----------

def raport(dziennik: Path = DZIENNIK) -> int:
    if not dziennik.exists():
        print("Dziennik jest pusty - najpierw generuj, a po losowaniu sprawdz.")
        return 0
    with dziennik.open(encoding="utf-8") as f:
        wiersze = list(csv.DictReader(f))
    grupy: dict[str, list[dict]] = {}
    for w in wiersze:
        grupy.setdefault(w["strategia"], []).append(w)
    grupy["ŁĄCZNIE"] = wiersze
    print(f"Losowań sprawdzonych: {len({w['losowanie_data'] for w in wiersze})}")
    print(f"{'strategia':<14}{'wydane':>10}{'wygrane':>12}{'bilans':>12}{'śr.traf.':>10}   3/4/5/6")
    for nazwa, g in grupy.items():
        wyd = sum(float(w["wydane_zl"]) for w in g)
        wyg = sum(float(w["wygrana_zl"]) for w in g)
        zakl = sum(int(w["zakladow"]) for w in g)
        sr = sum(float(w["sr_trafien"]) * int(w["zakladow"]) for w in g) / zakl
        t = "/".join(str(sum(int(w[f"t{k}"]) for w in g)) for k in (3, 4, 5, 6))
        print(f"{nazwa:<14}{wyd:>10.2f}{wyg:>12.2f}{wyg - wyd:>12.2f}{sr:>10.3f}   {t}")
    print("Teoria: 0.735 trafienia na zakład; wartość oczekiwana ok. 23% stawki (bez kumulacji).")
    return 0


# ---------- pobieranie ----------

def pobierz(nagrody_ostatnich: int = 0) -> int:
    losowania = dane.odswiez_archiwum()
    if not losowania:
        print("Nie udało się pobrać archiwum (szczegóły: dane/pobrania.log).")
        return 1
    if nagrody_ostatnich:
        # numer w archiwum traktujemy jako numer losowania lotto.pl [DP]
        for l in [l for l in losowania if l.nagrody.get(3) is None][-nagrody_ostatnich:]:
            n = dane.pobierz_nagrody(l.numer)
            if n:
                l.nagrody = n
        dane.zapisz_csv(losowania)
    k = dane.kontrola(losowania)
    k["probka_20"] = dane.porownaj_probke(losowania)
    sprawdzone_ = [p for p in k["probka_20"] if p["zgodne"] is not None]
    k["probka_zgodnych"] = f"{sum(p['zgodne'] for p in sprawdzone_)}/{len(sprawdzone_)} (porównano {len(sprawdzone_)} z 20)"
    k["pobrano"] = dt.datetime.now().isoformat(timespec="seconds")
    (dane.PLIK_CSV.parent / "kontrola.json").write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({x: k[x] for x in k if x != "probka_20"}, ensure_ascii=False, indent=1))
    return 0


def odswiez_strone() -> int:
    """Generuje strona/lotto/ (index.html, dane.json, przeglad.html). Błąd strony nie zatrzymuje automatu."""
    try:
        import strona
        plik = strona.generuj()
    except Exception as ex:  # noqa: BLE001 - automat ma działać dalej, błąd trafia do logu
        dane.loguj(f"strona: błąd {ex!r}")
        print(f"Nie udało się wygenerować strony: {ex}")
        return 1
    print(f"Strona odświeżona: {plik.parent}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Automat Lotto na wirtualnych pieniądzach")
    sub = ap.add_subparsers(dest="polecenie", required=True)
    p = sub.add_parser("pobierz")
    p.add_argument("--nagrody", type=int, default=0, help="pobierz wysokości wygranych dla N ostatnich losowań")
    sub.add_parser("generuj")
    sub.add_parser("sprawdz")
    sub.add_parser("raport")
    sub.add_parser("strona")
    a = ap.parse_args(argv)
    if a.polecenie == "pobierz":
        return pobierz(a.nagrody)
    if a.polecenie == "strona":
        return odswiez_strone()
    kod = {"generuj": generuj, "sprawdz": sprawdz, "raport": raport}[a.polecenie]()
    if a.polecenie in ("generuj", "sprawdz"):
        odswiez_strone()
    return kod


if __name__ == "__main__":
    sys.exit(main())
