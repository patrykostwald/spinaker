"""Testy hipotez i backtest strategii. Wyniki: wyniki/analiza.json i blok liczb w RAPORT.md.

    python analiza.py               # prawdziwe dane z dane/lotto.csv
    python analiza.py --symulacja   # gdy danych jeszcze nie ma: uczciwe losowania z komputera
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import sys
from collections import Counter
from math import comb
from pathlib import Path

import dane
import strategie

KATALOG = Path(__file__).resolve().parent
PLIK_JSON = KATALOG / "wyniki" / "analiza.json"
PLIK_RAPORT = KATALOG / "RAPORT.md"
ZNACZNIK_OD = "<!-- WYNIKI-ANALIZY: START (plik generuje analiza.py, nie edytuj ręcznie) -->"
ZNACZNIK_DO = "<!-- WYNIKI-ANALIZY: KONIEC -->"

ZAKLADOW_BACKTEST = 33
WSZYSTKIE = comb(49, 6)  # 13 983 816
# Dzisiejsze zasady (od 18.08.2026) - dane/ZRODLA.md [DP]
CENA = 5.0
NAGRODY_SREDNIE = {3: 35.0, 4: 200.0, 5: 7500.0, 6: 3_000_000.0}
CENA_DAWNIEJ = 3.0
OD_HISTORYCZNYCH = dt.date(2010, 1, 1)   # od kiedy liczymy wynik według historycznych nagród (cena 3 zł) [DP]
ZMIANA_CENY = dt.date(2026, 8, 18)
LICZBA_SYMULOWANYCH = 7300               # przybliżona liczba losowań do 10.2026 [DP]


def p_trafien(k: int) -> float:
    return comb(6, k) * comb(43, 6 - k) / WSZYSTKIE


SREDNIA_TEORIA = 36 / 49  # 0,7347
WARIANCJA_TEORIA = sum(k * k * p_trafien(k) for k in range(7)) - SREDNIA_TEORIA ** 2


def wartosc_oczekiwana(nagrody=NAGRODY_SREDNIE) -> float:
    return sum(p_trafien(k) * nagrody[k] for k in (3, 4, 5, 6))


# ---------- testy ----------

def test_powtorek(losowania) -> dict:
    licz = Counter(l.liczby for l in losowania)
    powtorzone = {"-".join(map(str, z)): c for z, c in licz.items() if c > 1}
    n = len(losowania)
    lam = comb(n, 2) / WSZYSTKIE
    pary = sum(comb(c, 2) for c in licz.values())
    daty = {}
    for l in losowania:
        if licz[l.liczby] > 1:
            daty.setdefault("-".join(map(str, l.liczby)), []).append(f"{l.numer} ({l.data})")
    return {
        "losowan": n,
        "powtorzone_zestawy": powtorzone,
        "gdzie": daty,
        "par_powtorek": pary,
        "oczekiwane_par": round(lam, 3),
        "p_przynajmniej_jednej": round(1 - math.exp(-lam), 3),
    }


def chi2_sf_parzyste(x: float, df: int) -> float:
    """P(X >= x) dla rozkładu chi-kwadrat o parzystej liczbie stopni swobody (wzór zamknięty)."""
    k = df // 2
    pol = x / 2
    wyraz = math.exp(-pol)
    suma = 0.0
    for i in range(k):
        suma += wyraz
        wyraz *= pol / (i + 1)
    return min(1.0, suma)


def test_chi2(losowania) -> dict:
    n = len(losowania)
    licz = Counter(x for l in losowania for x in l.liczby)
    oczek = 6 * n / 49
    x2 = sum((licz[x] - oczek) ** 2 / oczek for x in range(1, 50))
    # Losowanie bez zwracania: suma ma rozkład (43/48)·chi2(48), więc skalujemy przez 48/43.
    x2_kor = x2 * 48 / 43
    return {
        "oczekiwana_czestosc": round(oczek, 1),
        "najczestsza": max(range(1, 50), key=lambda x: licz[x]),
        "najczestsza_ile": licz.most_common(1)[0][1],
        "najrzadsza": min(range(1, 50), key=lambda x: licz[x]),
        "najrzadsza_ile": min(licz[x] for x in range(1, 50)),
        "chi2": round(x2_kor, 2),
        "stopnie_swobody": 48,
        "p": round(chi2_sf_parzyste(x2_kor, 48), 4),
    }


def nagrody_historyczne(l) -> tuple[float, dict] | None:
    if l.data < OD_HISTORYCZNYCH or l.nagrody.get(3) is None:
        return None
    cena = CENA if l.data >= ZMIANA_CENY else CENA_DAWNIEJ
    tabela = {k: (l.nagrody.get(k) or 0.0) for k in (3, 4, 5)}
    tabela[6] = l.nagrody.get(6) or (3_000_000.0 if l.data >= ZMIANA_CENY else 2_000_000.0)
    return cena, tabela


def backtest(losowania, zakladow=ZAKLADOW_BACKTEST, ziarno=7) -> dict:
    """Okno kroczące: przy losowaniu t strategia widzi tylko losowania 0..t-1."""
    rng = random.Random(ziarno)
    historia: list[tuple[int, ...]] = []
    szostki: set[int] = set()
    wyniki = {nazwa: {"zakladow": 0, "suma_trafien": 0, "suma_kw": 0, "rozklad": Counter(),
                      "wygrane": 0.0, "wygrane_bez_6": [], "hist_wydane": 0.0, "hist_wygrane": 0.0,
                      "hist_losowan": 0, "naruszen_limitu": 0, "szostki": []}
              for nazwa in strategie.STRATEGIE}
    for t, l in enumerate(losowania):
        if t >= strategie.OKNO:
            wylos = l.maska
            hist = nagrody_historyczne(l)
            for nazwa, f in strategie.STRATEGIE.items():
                w = wyniki[nazwa]
                zaklady = f(historia, zakladow, rng, frozenset(szostki))
                maski = [strategie.maska(z) for z in zaklady]
                w["naruszen_limitu"] += sum(1 for i in range(len(maski)) for j in range(i)
                                            if (maski[i] & maski[j]).bit_count() > strategie.MAX_WSPOLNYCH)
                wygrana_los = 0.0
                hist_los = 0.0
                for m, z in zip(maski, zaklady):
                    k = (m & wylos).bit_count()
                    w["zakladow"] += 1
                    w["suma_trafien"] += k
                    w["suma_kw"] += k * k
                    w["rozklad"][k] += 1
                    if k >= 3:
                        if k < 6:
                            wygrana_los += NAGRODY_SREDNIE[k]
                        else:
                            w["szostki"].append(f"{l.numer} ({l.data})")
                        if hist:
                            hist_los += hist[1][k]
                w["wygrane"] += wygrana_los
                w["wygrane_bez_6"].append(wygrana_los)
                if hist:
                    w["hist_losowan"] += 1
                    w["hist_wydane"] += hist[0] * zakladow
                    w["hist_wygrane"] += hist_los
        historia.append(l.liczby)
        szostki.add(l.maska)
    return {nazwa: podsumuj(w, zakladow) for nazwa, w in wyniki.items()}


def podsumuj(w: dict, zakladow: int) -> dict:
    n = w["zakladow"]
    srednia = w["suma_trafien"] / n
    wariancja = w["suma_kw"] / n - srednia ** 2
    se = math.sqrt(wariancja / n)
    losowan = len(w["wygrane_bez_6"])
    wydane = losowan * zakladow * CENA
    szostek = len(w["szostki"])
    wygrane = w["wygrane"] + szostek * NAGRODY_SREDNIE[6]
    na_los = [x - zakladow * CENA for x in w["wygrane_bez_6"]]
    sr_los = sum(na_los) / losowan
    se_los = math.sqrt(sum((x - sr_los) ** 2 for x in na_los) / (losowan - 1) / losowan)
    return {
        "losowan": losowan,
        "zakladow": n,
        "srednia_trafien": round(srednia, 4),
        "przedzial95": [round(srednia - 1.96 * se, 4), round(srednia + 1.96 * se, 4)],
        "z_wobec_teorii": round((srednia - SREDNIA_TEORIA) / math.sqrt(WARIANCJA_TEORIA / n), 2),
        "rozklad": {k: w["rozklad"].get(k, 0) for k in range(7)},
        "oczekiwane_3_4_5_6": {k: round(n * p_trafien(k), 1) for k in (3, 4, 5, 6)},
        "wydane_zl": round(wydane),
        "wygrane_zl": round(wygrane),
        "bilans_zl": round(wygrane - wydane),
        "zwrot_proc": round(100 * wygrane / wydane, 1),
        "bilans_na_losowanie_bez_6": round(sr_los, 2),
        "przedzial95_na_losowanie_bez_6": [round(sr_los - 1.96 * se_los, 2), round(sr_los + 1.96 * se_los, 2)],
        "szostki": w["szostki"],
        "historyczne_nagrody": None if not w["hist_losowan"] else {
            "losowan": w["hist_losowan"], "wydane_zl": round(w["hist_wydane"]),
            "wygrane_zl": round(w["hist_wygrane"]),
            "zwrot_proc": round(100 * w["hist_wygrane"] / w["hist_wydane"], 1)},
        "naruszen_limitu_2_wspolnych": w["naruszen_limitu"],
    }


def symulowana_historia(n=LICZBA_SYMULOWANYCH, ziarno=1957) -> list[dane.Losowanie]:
    rng = random.Random(ziarno)
    start = dt.date(1957, 1, 27)
    return [dane.Losowanie(i + 1, start + dt.timedelta(days=3 * i), tuple(sorted(rng.sample(range(1, 50), 6))))
            for i in range(n)]


# ---------- raport ----------

def zl(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " zł"


def blok_raportu(w: dict) -> str:
    t = w["teoria"]
    p, c = w["powtorki"], w["chi2"]
    zrodlo = ("**SYMULACJA** - prawdziwych danych jeszcze nie pobrano (dane/ZRODLA.md); losowania wygenerował komputer, "
              "więc wyniki pokazują metodę i skalę, nie historię Lotto." if w["symulacja"]
              else f"Prawdziwe losowania z dane/lotto.csv ({w['kontrola']['pierwsze']} - {w['kontrola']['ostatnie']}).")
    linie = [ZNACZNIK_OD, "",
             f"Wygenerowano {w['wygenerowano']}. Dane: {zrodlo}", "",
             "**1. Powtórki szóstek.** " +
             (f"Zestawy, które padły więcej niż raz: {', '.join(p['powtorzone_zestawy']) or 'brak'}. "
              f"Przy {p['losowan']} losowaniach rachunek daje średnio {p['oczekiwane_par']:.2f} powtórki "
              f"(szansa, że choć jedna się zdarzy: {100 * p['p_przynajmniej_jednej']:.0f}%)."), "",
             f"**2. Równomierność (chi-kwadrat, 48 st. swobody, poprawka na losowanie bez zwracania).** "
             f"Wynik {c['chi2']}, p = {c['p']}. Najczęstsza liczba {c['najczestsza']} ({c['najczestsza_ile']} razy), "
             f"najrzadsza {c['najrzadsza']} ({c['najrzadsza_ile']}), oczekiwane {c['oczekiwana_czestosc']}. "
             + ("Brak dowodu na nierówność (p > 0,05)." if c["p"] > 0.05 else "p < 0,05: sprawdzić dane i maszyny."), "",
             f"**3. Backtest: {ZAKLADOW_BACKTEST} zakłady na losowanie, okno kroczące, ceny i nagrody według dzisiejszych "
             f"zasad** (zakład {CENA:.0f} zł; 3 = 35 zł, 4 ≈ 200 zł, 5 ≈ 7 500 zł, 6 = 3 mln zł) [DP]. "
             f"Teoria: {t['srednia_trafien']:.4f} trafienia na zakład, zwrot {t['zwrot_proc']:.1f}% stawki.", "",
             "| Strategia | Śr. trafień (95%) | z | 3 / 4 / 5 / 6 trafień | Wydane | Wygrane | Zwrot | Bilans na losowanie bez szóstek (95%) |",
             "|---|---|---|---|---|---|---|---|"]
    for nazwa, s in w["backtest"].items():
        r = s["rozklad"]
        linie.append(
            f"| `{nazwa}` | {s['srednia_trafien']:.4f} ({s['przedzial95'][0]:.4f}-{s['przedzial95'][1]:.4f}) | "
            f"{s['z_wobec_teorii']:+.2f} | {r[3]} / {r[4]} / {r[5]} / {r[6]} | {zl(s['wydane_zl'])} | "
            f"{zl(s['wygrane_zl'])} | {s['zwrot_proc']:.1f}% | {s['bilans_na_losowanie_bez_6']:.2f} zł "
            f"({s['przedzial95_na_losowanie_bez_6'][0]:.2f} do {s['przedzial95_na_losowanie_bez_6'][1]:.2f}) |")
    o = next(iter(w["backtest"].values()))["oczekiwane_3_4_5_6"]
    linie += ["", f"Oczekiwane z rachunku przy tej liczbie zakładów: 3 / 4 / 5 / 6 = {o[3]} / {o[4]} / {o[5]} / {o[6]}. "
              f"Limit najwyżej 2 wspólnych liczb między zakładami: naruszeń "
              f"{sum(s['naruszen_limitu_2_wspolnych'] for s in w['backtest'].values())}. "
              "|z| < 2 oznacza: strategia nie różni się od losu."]
    hist = {n: s["historyczne_nagrody"] for n, s in w["backtest"].items() if s["historyczne_nagrody"]}
    if hist:
        linie += ["", "Według historycznych nagród (od 2010, cena 3 zł, od 18.08.2026 5 zł): " +
                  "; ".join(f"`{n}` zwrot {h['zwrot_proc']}%" for n, h in hist.items()) + "."]
    linie += ["", ZNACZNIK_DO]
    return "\n".join(linie)


def wstaw_do_raportu(blok: str) -> None:
    if not PLIK_RAPORT.exists():
        return
    tekst = PLIK_RAPORT.read_text(encoding="utf-8")
    if ZNACZNIK_OD in tekst and ZNACZNIK_DO in tekst:
        przed = tekst.split(ZNACZNIK_OD)[0]
        po = tekst.split(ZNACZNIK_DO, 1)[1]
        PLIK_RAPORT.write_text(przed + blok + po, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symulacja", action="store_true")
    a = ap.parse_args(argv)
    losowania = dane.wczytaj_csv()
    symulacja = a.symulacja or not losowania
    if symulacja:
        if not a.symulacja:
            print("Brak dane/lotto.csv - liczę na symulacji. Najpierw: python lotto.py pobierz", file=sys.stderr)
        losowania = symulowana_historia()
    wyniki = {
        "wygenerowano": f"{dt.datetime.now():%Y-%m-%d %H:%M}",
        "symulacja": symulacja,
        "kontrola": dane.kontrola(losowania),
        "teoria": {"srednia_trafien": SREDNIA_TEORIA,
                   "p": {k: p_trafien(k) for k in range(7)},
                   "wartosc_oczekiwana_zakladu": wartosc_oczekiwana(),
                   "zwrot_proc": 100 * wartosc_oczekiwana() / CENA},
        "powtorki": test_powtorek(losowania),
        "chi2": test_chi2(losowania),
        "backtest": backtest(losowania),
    }
    PLIK_JSON.parent.mkdir(parents=True, exist_ok=True)
    PLIK_JSON.write_text(json.dumps(wyniki, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    wstaw_do_raportu(blok_raportu(wyniki))
    print(blok_raportu(wyniki))
    return 0


if __name__ == "__main__":
    sys.exit(main())
