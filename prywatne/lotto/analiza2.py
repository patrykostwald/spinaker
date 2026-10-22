"""Etap 2: czy da się zwiększyć szansę trafienia? Pięć uczciwych prób znalezienia przewagi.

    python analiza2.py            # pełne liczby (ok. 1-2 minuty), wynik: wyniki/analiza2.json i blok w RAPORT2.md
    python analiza2.py --szybko   # mniej symulacji (do sprawdzenia, że działa)

1. nierówność liczb w epokach (chi-kwadrat, poprawki Bonferroniego i Benjaminiego-Hochberga),
2. pary i trójki liczb częstsze niż z rachunku (dokładny ogon dwumianowy + maksimum z symulacji),
3. zależność od poprzednich losowań (powtórzenia, sumy, parzyste, niskie) wobec symulacji Monte Carlo,
4. test przewidywania: modele widzą tylko przeszłość, sprawdzane na losowaniach od 2010 r.,
5. pokrycie i rzadko grane liczby: co zmienia wypłatę, a czego nie zmienia w szansie.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import sys
from collections import Counter
from itertools import combinations
from math import comb
from pathlib import Path

import analiza
import dane
import strategie

KATALOG = Path(__file__).resolve().parent
PLIK_JSON = KATALOG / "wyniki" / "analiza2.json"
PLIK_RAPORT = KATALOG / "RAPORT2.md"
ZNACZNIK_OD = "<!-- WYNIKI-ANALIZY2: START (plik generuje analiza2.py, nie edytuj ręcznie) -->"
ZNACZNIK_DO = "<!-- WYNIKI-ANALIZY2: KONIEC -->"

ALFA = 0.05
LICZBY = range(1, 50)
# Okresy według częstotliwości losowań w danych (1, 2 i 3 losowania w tygodniu). Daty zmian maszyn
# i zestawów kul nie są publicznie opisane w źródłach, do których mamy dostęp [DP] - te okresy są ich przybliżeniem.
OKRESY = [("1957-1974 (raz w tygodniu)", dt.date(1957, 1, 1), dt.date(1975, 1, 1)),
          ("1975-2006 (2 razy w tygodniu)", dt.date(1975, 1, 1), dt.date(2007, 1, 1)),
          ("2007-2026 (3 razy w tygodniu)", dt.date(2007, 1, 1), dt.date(2100, 1, 1))]
OD_TESTU = dt.date(2010, 1, 1)   # test przewidywania: uczenie na danych do 2009 r., sprawdzanie od 2010 r.


def podzial(losowania, od: dt.date) -> dt.date:
    """Data podziału na uczenie i test; gdy dane nie sięgają `od`, dzielimy w 2/3 historii."""
    if losowania[0].data < od <= losowania[-1].data:
        return od
    return losowania[len(losowania) * 2 // 3].data


# ---------- pomocnicze: rozkłady i poprawki ----------

def chi2_sf(x: float, df: int) -> float:
    """P(X >= x) dla chi-kwadrat o dowolnej liczbie stopni swobody (regularyzowana funkcja gamma)."""
    if x <= 0:
        return 1.0
    a, z = df / 2, x / 2
    if z < a + 1:  # szereg dla dolnej części
        wyraz = suma = 1 / a
        n = a
        for _ in range(1000):
            n += 1
            wyraz *= z / n
            suma += wyraz
            if wyraz < suma * 1e-15:
                break
        return max(0.0, 1 - suma * math.exp(-z + a * math.log(z) - math.lgamma(a)))
    # ułamek łańcuchowy dla górnej części (Lentz)
    b = z + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, math.exp(-z + a * math.log(z) - math.lgamma(a)) * h)


def dwumian_ogon(k: int, n: int, p: float) -> float:
    """P(X >= k) dla X ~ Bin(n, p), dokładnie (sumowanie ogona w logarytmach)."""
    if k <= 0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    suma = 0.0
    for j in range(k, n + 1):
        t = math.exp(math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1) + j * lp + (n - j) * lq)
        suma += t
        if j > n * p and t < suma * 1e-12:
            break
    return min(1.0, suma)


def bonferroni(p: list[float]) -> list[float]:
    return [min(1.0, x * len(p)) for x in p]


def benjamini_hochberg(p: list[float]) -> list[float]:
    """Skorygowane p (q) według Benjaminiego-Hochberga, w tej samej kolejności co wejście."""
    m = len(p)
    kolejnosc = sorted(range(m), key=lambda i: p[i])
    q = [0.0] * m
    najm = 1.0
    for poz in range(m - 1, -1, -1):
        i = kolejnosc[poz]
        najm = min(najm, p[i] * m / (poz + 1))
        q[i] = najm
    return q


def symuluj(n: int, rng: random.Random) -> list[tuple[int, ...]]:
    return [tuple(sorted(rng.sample(LICZBY, 6))) for _ in range(n)]


def p_empiryczne(obserwowana: float, symulowane: list[float]) -> float:
    """Dwustronne p z symulacji: jak często idealny los daje wynik co najmniej tak odległy od średniej."""
    sr = sum(symulowane) / len(symulowane)
    dalej = sum(1 for s in symulowane if abs(s - sr) >= abs(obserwowana - sr) - 1e-12)
    return (dalej + 1) / (len(symulowane) + 1)


# ---------- 1. epoki ----------

def chi2_liczb(zestawy: list[tuple[int, ...]]) -> tuple[float, float, Counter]:
    n = len(zestawy)
    licz = Counter(x for z in zestawy for x in z)
    oczek = 6 * n / 49
    x2 = sum((licz[x] - oczek) ** 2 / oczek for x in LICZBY) * 48 / 43  # poprawka: bez zwracania
    return x2, chi2_sf(x2, 48), licz


def test_epok(losowania: list[dane.Losowanie]) -> dict:
    grupy: list[tuple[str, list]] = []
    for od in range(1950, 2030, 10):
        g = [l.liczby for l in losowania if od <= l.data.year < od + 10]
        if len(g) >= 100:
            grupy.append((f"{max(od, 1957)}-{min(od + 9, 2026)}", g))
    for nazwa, od, do in OKRESY:
        g = [l.liczby for l in losowania if od <= l.data < do]
        if len(g) >= 100:
            grupy.append((nazwa, g))
    wiersze = []
    for nazwa, g in grupy:
        x2, p, licz = chi2_liczb(g)
        oczek = 6 * len(g) / 49
        naj = max(LICZBY, key=lambda x: licz[x])
        rz = min(LICZBY, key=lambda x: licz[x])
        wiersze.append({"okres": nazwa, "losowan": len(g), "chi2": round(x2, 2), "p": p,
                        "najczestsza": f"{naj} ({licz[naj]} wobec {oczek:.0f})",
                        "najrzadsza": f"{rz} ({licz[rz]} wobec {oczek:.0f})"})
    ps = [w["p"] for w in wiersze]
    for w, pb, q in zip(wiersze, bonferroni(ps), benjamini_hochberg(ps)):
        w["p"] = round(w["p"], 4)
        w["p_bonferroni"] = round(pb, 4)
        w["q_bh"] = round(q, 4)
    return {"testow": len(wiersze), "okresy": wiersze,
            "istotnych_po_poprawce": sum(1 for w in wiersze if w["q_bh"] < ALFA)}


# ---------- 2. pary i trójki ----------

def _klucz(kombinacja) -> int:
    k = 0
    for x in kombinacja:
        k = k * 50 + x
    return k


def _odklucz(k: int, r: int) -> tuple[int, ...]:
    out = []
    for _ in range(r):
        k, x = divmod(k, 50)
        out.append(x)
    return tuple(reversed(out))


def zlicz_grupy(zestawy, r: int) -> Counter:
    return Counter(_klucz(c) for z in zestawy for c in combinations(z, r))


def test_par_trojek(losowania: list[dane.Losowanie], symulacji: int, rng: random.Random) -> dict:
    zestawy = [l.liczby for l in losowania]
    n = len(zestawy)
    out = {}
    for r, nazwa in ((2, "pary"), (3, "trojki")):
        p1 = comb(49 - r, 6 - r) / comb(49, 6)  # szansa, że dana para (trójka) padnie w jednym losowaniu
        wszystkich = comb(49, r)
        licz = zlicz_grupy(zestawy, r)
        oczek = n * p1
        # p dla każdej możliwej pary/trójki (także tych, które nie padły ani razu: p = 1)
        top = licz.most_common(10)
        ogon_cache: dict[int, float] = {}
        def ogon(k):
            if k not in ogon_cache:
                ogon_cache[k] = dwumian_ogon(k, n, p1)
            return ogon_cache[k]
        ps_wszystkie = [ogon(c) for c in licz.values()] + [1.0] * (wszystkich - len(licz))
        q = benjamini_hochberg(ps_wszystkie)
        najm_p = min(ps_wszystkie)
        # maksimum z symulacji: jak duży „rekord” daje idealny los przy tej samej liczbie losowań
        maks_sym = [max(zlicz_grupy(symuluj(n, rng), r).values()) for _ in range(symulacji)]
        maks = top[0][1]
        out[nazwa] = {
            "wszystkich": wszystkich, "oczekiwane_na_jedna": round(oczek, 2),
            "najczestsze": [{"liczby": "-".join(map(str, _odklucz(k, r))), "razy": c,
                             "p": round(ogon(c), 6)} for k, c in top],
            "najmniejsze_p": najm_p,
            "p_bonferroni": round(min(1.0, najm_p * wszystkich), 4),
            "istotnych_bh": sum(1 for x in q if x < ALFA),
            "rekord": maks,
            "rekord_symulacje_sr": round(sum(maks_sym) / len(maks_sym), 1),
            "rekord_symulacje_zakres": [min(maks_sym), max(maks_sym)],
            "p_rekordu": round((sum(1 for m in maks_sym if m >= maks) + 1) / (len(maks_sym) + 1), 3),
            "symulacji": symulacji,
        }
    return out


# ---------- 3. zależność od poprzednich losowań ----------

def _autokorelacja(x: list[float], lag: int) -> float:
    n = len(x)
    sr = sum(x) / n
    mian = sum((v - sr) ** 2 for v in x)
    return sum((x[i] - sr) * (x[i + lag] - sr) for i in range(n - lag)) / mian


def miary_zaleznosci(zestawy: list[tuple[int, ...]]) -> dict[str, float]:
    sumy = [sum(z) for z in zestawy]
    parz = [sum(1 for v in z if v % 2 == 0) for z in zestawy]
    niskie = [sum(1 for v in z if v <= 24) for z in zestawy]
    maski = [strategie.maska(z) for z in zestawy]
    m = {}
    for lag in (1, 2, 3):
        m[f"powtorzen_z_losowania_{lag}_wstecz"] = (
            sum((maski[i] & maski[i - lag]).bit_count() for i in range(lag, len(maski))) / (len(maski) - lag))
    for lag in (1, 2):
        m[f"autokorelacja_sumy_lag{lag}"] = _autokorelacja(sumy, lag)
    m["autokorelacja_parzystych_lag1"] = _autokorelacja(parz, 1)
    m["autokorelacja_niskich_lag1"] = _autokorelacja(niskie, 1)
    m["srednia_suma"] = sum(sumy) / len(sumy)
    m["wariancja_sumy"] = sum((s - m["srednia_suma"]) ** 2 for s in sumy) / (len(sumy) - 1)
    m["srednio_parzystych"] = sum(parz) / len(parz)
    m["srednio_niskich_1_24"] = sum(niskie) / len(niskie)
    return m


OPIS_MIAR = {
    "powtorzen_z_losowania_1_wstecz": "ile liczb powtarza się z poprzedniego losowania",
    "powtorzen_z_losowania_2_wstecz": "ile liczb powtarza się sprzed 2 losowań",
    "powtorzen_z_losowania_3_wstecz": "ile liczb powtarza się sprzed 3 losowań",
    "autokorelacja_sumy_lag1": "czy duża suma pociąga dużą sumę w następnym",
    "autokorelacja_sumy_lag2": "to samo co 2 losowania dalej",
    "autokorelacja_parzystych_lag1": "czy liczba parzystych przechodzi na następne",
    "autokorelacja_niskich_lag1": "czy liczba niskich (1-24) przechodzi na następne",
    "srednia_suma": "średnia suma 6 liczb",
    "wariancja_sumy": "rozrzut sumy",
    "srednio_parzystych": "średnio parzystych w losowaniu",
    "srednio_niskich_1_24": "średnio niskich (1-24) w losowaniu",
}


def test_zaleznosci(losowania: list[dane.Losowanie], symulacji: int, rng: random.Random) -> dict:
    zestawy = [l.liczby for l in losowania]
    obs = miary_zaleznosci(zestawy)
    sym = [miary_zaleznosci(symuluj(len(zestawy), rng)) for _ in range(symulacji)]
    wiersze = []
    for k, v in obs.items():
        s = [x[k] for x in sym]
        sr = sum(s) / len(s)
        sd = math.sqrt(sum((x - sr) ** 2 for x in s) / (len(s) - 1))
        wiersze.append({"miara": k, "opis": OPIS_MIAR[k], "dane": round(v, 4), "los_srednio": round(sr, 4),
                        "los_odchylenie": round(sd, 4), "p": p_empiryczne(v, s)})
    ps = [w["p"] for w in wiersze]
    for w, pb, q in zip(wiersze, bonferroni(ps), benjamini_hochberg(ps)):
        w["p"] = round(w["p"], 4)
        w["p_bonferroni"] = round(pb, 4)
        w["q_bh"] = round(q, 4)
    return {"symulacji": symulacji, "miary": wiersze,
            "istotnych_po_poprawce": sum(1 for w in wiersze if w["q_bh"] < ALFA)}


# ---------- 4. test przewidywania ----------

def _top6(wynik: dict[int, float], rng: random.Random) -> set[int]:
    return set(sorted(LICZBY, key=lambda x: (-wynik[x], rng.random()))[:6])


def test_przewidywania(losowania: list[dane.Losowanie], od: dt.date = OD_TESTU, ziarno: int = 11) -> dict:
    """Każdy model przed losowaniem t widzi tylko losowania < t. Model `markow` uczy się raz, na danych do `od`."""
    rng = random.Random(ziarno)
    od = podzial(losowania, od)
    uczace = [l.liczby for l in losowania if l.data < od]
    testowe_idx = [i for i, l in enumerate(losowania) if l.data >= od and i >= 50]
    # Markow: P(liczba padnie | padła w poprzednim) i P(padnie | nie padła), osobno dla każdej liczby.
    po_obecnej = Counter()
    obecnej = Counter()
    po_nieobecnej = Counter()
    nieobecnej = Counter()
    for a, b in zip(uczace, uczace[1:]):
        sa, sb = set(a), set(b)
        for x in LICZBY:
            if x in sa:
                obecnej[x] += 1
                po_obecnej[x] += x in sb
            else:
                nieobecnej[x] += 1
                po_nieobecnej[x] += x in sb
    p_obecna = {x: (po_obecnej[x] + 1) / (obecnej[x] + 2) for x in LICZBY}
    p_nieobecna = {x: (po_nieobecnej[x] + 1) / (nieobecnej[x] + 2) for x in LICZBY}

    zestawy = [l.liczby for l in losowania]
    licz_calosc = Counter(x for z in zestawy[:testowe_idx[0]] for x in z)
    ostatnio = {}
    for i, z in enumerate(zestawy[:testowe_idx[0]]):
        for x in z:
            ostatnio[x] = i
    modele = {
        "czeste_od_1957": "6 liczb najczęstszych w całej dotychczasowej historii",
        "czeste_ostatnie_50": "6 liczb najczęstszych w ostatnich 50 losowaniach",
        "rzadkie_ostatnie_50": "6 liczb najrzadszych w ostatnich 50 losowaniach",
        "najdluzej_nie_bylo": "6 liczb, które najdłużej nie padły („należą się”)",
        "markow": "liczby z najwyższą szansą po tym, co padło ostatnio (uczony tylko na danych sprzed testu)",
        "los": "6 losowych liczb (punkt odniesienia)",
    }
    trafienia = {m: [] for m in modele}
    for i in testowe_idx:
        okno = Counter(x for z in zestawy[i - 50:i] for x in z)
        poprz = set(zestawy[i - 1])
        typy = {
            "czeste_od_1957": _top6({x: licz_calosc[x] for x in LICZBY}, rng),
            "czeste_ostatnie_50": _top6({x: okno[x] for x in LICZBY}, rng),
            "rzadkie_ostatnie_50": _top6({x: -okno[x] for x in LICZBY}, rng),
            "najdluzej_nie_bylo": _top6({x: i - ostatnio.get(x, -1) for x in LICZBY}, rng),
            "markow": _top6({x: (p_obecna if x in poprz else p_nieobecna)[x] for x in LICZBY}, rng),
            "los": set(rng.sample(LICZBY, 6)),
        }
        wyl = set(zestawy[i])
        for m, typ in typy.items():
            trafienia[m].append(len(typ & wyl))
        for x in zestawy[i]:
            licz_calosc[x] += 1
            ostatnio[x] = i
    n = len(testowe_idx)
    sr_teoria = analiza.SREDNIA_TEORIA
    sd_teoria = math.sqrt(analiza.WARIANCJA_TEORIA)
    wiersze = []
    for m, opis in modele.items():
        t = trafienia[m]
        sr = sum(t) / n
        z = (sr - sr_teoria) / (sd_teoria / math.sqrt(n))
        p = math.erfc(abs(z) / math.sqrt(2))
        wiersze.append({"model": m, "opis": opis, "srednio_trafien": round(sr, 4), "z": round(z, 2), "p": p,
                        "trojek_i_wiecej": sum(1 for k in t if k >= 3),
                        "oczekiwane_trojek_i_wiecej": round(n * sum(analiza.p_trafien(k) for k in (3, 4, 5, 6)), 1)})
    ps = [w["p"] for w in wiersze]
    for w, pb in zip(wiersze, bonferroni(ps)):
        w["p"] = round(w["p"], 4)
        w["p_bonferroni"] = round(pb, 4)
    return {"uczenie_do": od.isoformat(), "losowan_testowych": n, "teoria_srednio": round(sr_teoria, 4),
            "modele": wiersze, "istotnych_po_poprawce": sum(1 for w in wiersze if w["p_bonferroni"] < ALFA)}


# ---------- 5. pokrycie i rzadko grane ----------

def test_pokrycia(zestawow: int, rng: random.Random, zakladow: int = 20, losowan_na_zestaw: int = 100) -> dict:
    """20 zakładów: zupełnie losowe (mogą się dublować) wobec rozpisanych (najwyżej 2 wspólne liczby)."""
    wyniki = {}
    for nazwa, generator in (
            ("losowe_bez_ograniczen", lambda: [tuple(sorted(rng.sample(LICZBY, 6))) for _ in range(zakladow)]),
            ("rozpisane_max_2_wspolne", lambda: strategie.los([], zakladow, rng))):
        trafien = 0
        zakladow_lacznie = 0
        z_wygrana = 0
        rozklad_wygranych = Counter()
        for _ in range(zestawow):
            maski = [strategie.maska(z) for z in generator()]
            for _ in range(losowan_na_zestaw):
                w = strategie.maska(rng.sample(LICZBY, 6))
                k = [(m & w).bit_count() for m in maski]
                trafien += sum(k)
                zakladow_lacznie += len(k)
                wygranych = sum(1 for x in k if x >= 3)
                z_wygrana += wygranych > 0
                rozklad_wygranych[min(wygranych, 3)] += 1
        prob = zestawow * losowan_na_zestaw
        wyniki[nazwa] = {
            "srednio_trafien_na_zaklad": round(trafien / zakladow_lacznie, 4),
            "szansa_choc_jednej_wygranej_proc": round(100 * z_wygrana / prob, 2),
            "rozklad_liczby_wygranych_proc": {str(k) if k < 3 else "3+": round(100 * v / prob, 2)
                                              for k, v in sorted(rozklad_wygranych.items())},
            "prob": prob,
        }
    p3 = sum(analiza.p_trafien(k) for k in (3, 4, 5, 6))
    wyniki["teoria_niezalezne_proc"] = round(100 * (1 - (1 - p3) ** zakladow), 2)
    return wyniki


def kontrola_wysokich(losowania: list[dane.Losowanie]) -> dict:
    """`rzadko_grane` miało z = -2,67 w backteście. Czy liczby 32-49 padały rzadziej? Test jednej proporcji."""
    n = len(losowania)
    wysokie = sum(1 for l in losowania for x in l.liczby if x >= 32)
    oczek = n * 6 * 18 / 49
    # liczba wysokich w jednym losowaniu: rozkład hipergeometryczny (18 z 49, ciągniemy 6)
    var = n * 6 * (18 / 49) * (31 / 49) * (43 / 48)
    z = (wysokie - oczek) / math.sqrt(var)
    return {"wysokich_32_49": wysokie, "oczekiwane": round(oczek, 1), "z": round(z, 2),
            "p": round(math.erfc(abs(z) / math.sqrt(2)), 4)}


ZAKRESY = [(1, 9), (10, 19), (20, 29), (30, 39), (40, 49), (1, 24), (25, 49), (1, 31), (32, 49)]


def _z_zakresu(losowania, od: int, do: int) -> tuple[int, float, float]:
    n = len(losowania)
    k = do - od + 1
    ile = sum(1 for l in losowania for x in l.liczby if od <= x <= do)
    oczek = n * 6 * k / 49
    var = n * 6 * (k / 49) * (1 - k / 49) * (43 / 48)
    return ile, oczek, (ile - oczek) / math.sqrt(var)


def hipoteza_z_uczenia(losowania: list[dane.Losowanie], od: dt.date = OD_TESTU) -> dict:
    """Uczciwe sprawdzenie „wykrytej” nierówności: hipotezę wybieramy na danych do `od`
    (najbardziej odstający zakres liczb), a sprawdzamy ją jednym testem jednostronnym na danych od `od`."""
    od = podzial(losowania, od)
    uczace = [l for l in losowania if l.data < od]
    testowe = [l for l in losowania if l.data >= od]
    kandydaci = []
    for a, b in ZAKRESY:
        ile, oczek, z = _z_zakresu(uczace, a, b)
        kandydaci.append({"zakres": f"{a}-{b}", "ile": ile, "oczekiwane": round(oczek, 1), "z": round(z, 2)})
    naj = max(kandydaci, key=lambda k: abs(k["z"]))
    a, b = map(int, naj["zakres"].split("-"))
    p_ucz = min(1.0, math.erfc(abs(naj["z"]) / math.sqrt(2)) * len(ZAKRESY))
    ile, oczek, z = _z_zakresu(testowe, a, b)
    kierunek = 1 if naj["z"] > 0 else -1
    p_test = 0.5 * math.erfc(kierunek * z / math.sqrt(2))  # jednostronnie, w kierunku z uczenia
    return {"uczenie": f"{uczace[0].data.year}-{uczace[-1].data.year}", "test": f"{od.year}-{testowe[-1].data.year}",
            "kandydaci": kandydaci, "wybrany": naj["zakres"], "kierunek": "częściej" if kierunek > 0 else "rzadziej",
            "z_uczenie": naj["z"], "p_uczenie_bonferroni": round(p_ucz, 4),
            "test_ile": ile, "test_oczekiwane": round(oczek, 1), "z_test": round(z, 2), "p_test": round(p_test, 4),
            "potwierdzona": p_test < ALFA}


# ---------- całość ----------

def policz_wszystko(losowania: list[dane.Losowanie], szybko: bool = False, ziarno: int = 2026) -> dict:
    rng = random.Random(ziarno)
    return {
        "wygenerowano": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "losowan": len(losowania),
        "zakres": f"{losowania[0].data} - {losowania[-1].data}",
        "epoki": test_epok(losowania),
        "pary_trojki": test_par_trojek(losowania, 20 if szybko else 200, rng),
        "zaleznosc": test_zaleznosci(losowania, 50 if szybko else 1000, rng),
        "przewidywanie": test_przewidywania(losowania),
        "hipoteza": hipoteza_z_uczenia(losowania),
        "pokrycie": test_pokrycia(20 if szybko else 400, rng),
        "wysokie_liczby": kontrola_wysokich(losowania),
    }


def werdykt(w: dict) -> dict:
    """Czy którykolwiek test po poprawce na wielokrotne testy pokazał nierówność, którą da się wykorzystać."""
    pt = w["pary_trojki"]
    sygnaly = {
        "epoki": w["epoki"]["istotnych_po_poprawce"] > 0,
        "pary": pt["pary"]["istotnych_bh"] > 0 or pt["pary"]["p_rekordu"] < ALFA,
        "trojki": pt["trojki"]["istotnych_bh"] > 0 or pt["trojki"]["p_rekordu"] < ALFA,
        "zaleznosc": w["zaleznosc"]["istotnych_po_poprawce"] > 0,
        "przewidywanie": any(m["p_bonferroni"] < ALFA and m["z"] > 0 for m in w["przewidywanie"]["modele"]),
        "hipoteza_z_uczenia": w["hipoteza"]["potwierdzona"],
    }
    return {"sygnaly": sygnaly, "cokolwiek_istotne": any(sygnaly.values())}


def _p(x: float) -> str:
    return "< 0,0001" if x < 0.0001 else f"{x:.4f}".replace(".", ",")


def _l(x: float, n: int = 3) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def blok_raportu(w: dict) -> str:
    e, pt, z, pr, po, wy = (w["epoki"], w["pary_trojki"], w["zaleznosc"], w["przewidywanie"], w["pokrycie"],
                            w["wysokie_liczby"])
    wer = werdykt(w)
    out = [f"Wygenerowano {w['wygenerowano']}. Dane: {w['losowan']} losowań ({w['zakres']}). "
           f"Poziom istotności 0,05 po poprawce na wielokrotne testy.", ""]
    out += ["### 1. Nierówność liczb w okresach (chi-kwadrat, 48 st. swobody)", "",
            "| Okres | Losowań | Chi-kwadrat | p | p po Bonferronim | q (BH) | Najczęstsza | Najrzadsza |",
            "|---|---|---|---|---|---|---|---|"]
    for r in e["okresy"]:
        out.append(f"| {r['okres']} | {r['losowan']} | {_l(r['chi2'], 1)} | {_p(r['p'])} | {_p(r['p_bonferroni'])} "
                   f"| {_p(r['q_bh'])} | {r['najczestsza']} | {r['najrzadsza']} |")
    out += ["", f"Istotnych po poprawce: **{e['istotnych_po_poprawce']} z {e['testow']}**.", ""]
    out += ["### 2. Pary i trójki liczb", ""]
    for nazwa, opis in (("pary", "Pary"), ("trojki", "Trójki")):
        d = pt[nazwa]
        naj = ", ".join(f"{x['liczby']} ({x['razy']}×)" for x in d["najczestsze"][:5])
        out.append(f"- **{opis}** ({d['wszystkich']} możliwych, każda powinna paść średnio {_l(d['oczekiwane_na_jedna'], 1)} razy). "
                   f"Najczęstsze: {naj}. Najmniejsze p {_p(d['najmniejsze_p'])}, po Bonferronim {_p(d['p_bonferroni'])}; "
                   f"istotnych według BH: {d['istotnych_bh']}. Rekord {d['rekord']}× wobec rekordów w {d['symulacji']} "
                   f"symulacjach idealnego losu: średnio {_l(d['rekord_symulacje_sr'], 1)}, od {d['rekord_symulacje_zakres'][0]} "
                   f"do {d['rekord_symulacje_zakres'][1]} (p = {_p(d['p_rekordu'])}).")
    out += ["", f"### 3. Zależność od poprzednich losowań ({z['symulacji']} symulacji idealnego losu)", "",
            "| Co sprawdzamy | Dane | Idealny los (średnio ± odchylenie) | p | q (BH) |", "|---|---|---|---|---|"]
    for r in z["miary"]:
        out.append(f"| {r['opis']} | {_l(r['dane'], 4)} | {_l(r['los_srednio'], 4)} ± {_l(r['los_odchylenie'], 4)} "
                   f"| {_p(r['p'])} | {_p(r['q_bh'])} |")
    out += ["", f"Istotnych po poprawce: **{z['istotnych_po_poprawce']} z {len(z['miary'])}**.", ""]
    out += [f"### 4. Test przewidywania (uczenie na danych sprzed {pr['uczenie_do']}, sprawdzenie na "
            f"{pr['losowan_testowych']} losowaniach od tej daty)", "",
            f"Każdy model typuje 6 liczb przed losowaniem, znając tylko przeszłość. Los daje średnio {_l(pr['teoria_srednio'], 4)} trafienia.", "",
            "| Model | Śr. trafień | z | p po Bonferronim | 3+ trafień (oczekiwane) |", "|---|---|---|---|---|"]
    for r in pr["modele"]:
        out.append(f"| `{r['model']}`: {r['opis']} | {_l(r['srednio_trafien'], 4)} | {_l(r['z'], 2)} | {_p(r['p_bonferroni'])} "
                   f"| {r['trojek_i_wiecej']} ({_l(r['oczekiwane_trojek_i_wiecej'], 1)}) |")
    out += ["", f"Modeli lepszych od losu po poprawce: **{pr['istotnych_po_poprawce']}**.", ""]
    h = w["hipoteza"]
    out += [f"**4b. Hipoteza z danych {h['uczenie']}, sprawdzona na {h['test']}.** Spośród {len(h['kandydaci'])} zakresów "
            f"(1-9, 10-19, ..., 1-24, 32-49) najbardziej odstawał zakres {h['wybrany']}: padał {h['kierunek']} "
            f"(z = {_l(h['z_uczenie'], 2)}, p po Bonferronim {_p(h['p_uczenie_bonferroni'])}). "
            f"Na nowych danych: {h['test_ile']} wobec {_l(h['test_oczekiwane'], 1)} oczekiwanych, z = {_l(h['z_test'], 2)}, "
            f"p jednostronne {_p(h['p_test'])} - {'POTWIERDZONA' if h['potwierdzona'] else 'nie potwierdziła się'}.", ""]
    a, b = po["losowe_bez_ograniczen"], po["rozpisane_max_2_wspolne"]
    out += [f"### 5. Pokrycie: 20 zakładów losowych wobec rozpisanych ({a['prob']} prób)", "",
            "| | Śr. trafień na zakład | Szansa na choć jedną wygraną (3+) | Rozkład liczby wygranych 0 / 1 / 2 / 3+ |",
            "|---|---|---|---|"]
    for nazwa, d in (("Losowe (mogą się dublować)", a), ("Rozpisane (najwyżej 2 wspólne)", b)):
        r = d["rozklad_liczby_wygranych_proc"]
        out.append(f"| {nazwa} | {_l(d['srednio_trafien_na_zaklad'], 4)} | {_l(d['szansa_choc_jednej_wygranej_proc'], 2)}% "
                   f"| {' / '.join(_l(r.get(k, 0), 2) + '%' for k in ('0', '1', '2', '3+'))} |")
    out += ["", f"Teoria dla 20 niezależnych zakładów: {_l(po['teoria_niezalezne_proc'], 2)}% na choć jedną wygraną.", "",
            f"**Kontrola `rzadko_grane`:** liczby 32-49 padły {wy['wysokich_32_49']} razy wobec {_l(wy['oczekiwane'], 1)} "
            f"oczekiwanych (z = {_l(wy['z'], 2)}, p = {_p(wy['p'])}).", "",
            f"**Werdykt automatu:** {'ZNALEZIONO sygnał: ' + ', '.join(k for k, v in wer['sygnaly'].items() if v) if wer['cokolwiek_istotne'] else 'żaden test po poprawce nie pokazał nierówności, którą da się wykorzystać'}."]
    return "\n".join(out)


def wstaw_do_raportu(blok: str, plik: Path = PLIK_RAPORT) -> None:
    tekst = plik.read_text(encoding="utf-8") if plik.exists() else f"{ZNACZNIK_OD}\n{ZNACZNIK_DO}\n"
    przed, reszta = tekst.split(ZNACZNIK_OD, 1)
    _, po = reszta.split(ZNACZNIK_DO, 1)
    plik.write_text(f"{przed}{ZNACZNIK_OD}\n\n{blok}\n\n{ZNACZNIK_DO}{po}", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lotto: szukanie przewagi (etap 2)")
    ap.add_argument("--szybko", action="store_true", help="mniej symulacji")
    a = ap.parse_args(argv)
    losowania = dane.wczytaj_csv()
    if not losowania:
        print("Brak dane/lotto.csv - najpierw: python lotto.py pobierz")
        return 1
    w = policz_wszystko(losowania, a.szybko)
    w["werdykt"] = werdykt(w)
    PLIK_JSON.parent.mkdir(parents=True, exist_ok=True)
    PLIK_JSON.write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    wstaw_do_raportu(blok_raportu(w))
    print(json.dumps(w["werdykt"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
