"""Lotto, etap 3: wielka symulacja technik „przewidywania” (walk-forward, bez podglądania przyszłości).

Uruchom w folderze prywatne/lotto/etap3:
    python symulacja.py            # pełna symulacja (ok. 20-40 min na 4 rdzeniach)
    python symulacja.py --szybko   # próba na 1500 losowaniach (ok. 1 min)

Każda technika dostaje tylko losowania DO dnia t (widok tylko do odczytu `X[:t]`) i zwraca ocenę 49 liczb;
im wyższa ocena, tym wyżej liczba w rankingu. Połączenia technik powstają z rankingów, które też widziały tylko przeszłość.
Wyniki: wyniki/symulacja.json i tabele w ../RAPORT3.md (między znacznikami).
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import sys
import time
import warnings
import zlib
from math import comb
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", message=".*Maximum iterations.*")

KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG.parent))

import dane  # noqa: E402

PLIK_JSON = KATALOG / "wyniki" / "symulacja.json"
PLIK_RAPORT = KATALOG / "RAPORT3.md"
ZNACZNIK_OD = "<!-- WYNIKI-SYMULACJI: START (plik generuje symulacja.py, nie edytuj ręcznie) -->"
ZNACZNIK_DO = "<!-- WYNIKI-SYMULACJI: KONIEC -->"

ROZGRZEWKA = 500
K = (6, 12, 18, 24)
SYSTEMY = range(7, 13)
OD_TESTU = dt.date(2010, 1, 1)          # wybór połączeń na latach do 2009, ocena na 2010-2026
EPOKI = (dt.date(1975, 1, 1), dt.date(2007, 1, 1))  # zmiany liczby losowań w tygodniu (analiza2.OKRESY)
CENA = 5.0
NAGRODY = {3: 35.0, 4: 200.0, 5: 7500.0, 6: 3_000_000.0}   # jak w RAPORT.md / lotto.NAGRODY_SREDNIE [DP]
ALFA = 0.05


# ---------- dane ----------

def macierz(losowania) -> np.ndarray:
    """Losowania -> macierz N x 49 (1 = liczba padła), tylko do odczytu."""
    X = np.zeros((len(losowania), 49), dtype=np.int8)
    for i, l in enumerate(losowania):
        X[i, [x - 1 for x in l.liczby]] = 1
    X.flags.writeable = False
    return X


def losowa_historia(n: int, ziarno: int = 0) -> np.ndarray:
    rng = np.random.default_rng(ziarno)
    X = np.zeros((n, 49), dtype=np.int8)
    for i in range(n):
        X[i, rng.choice(49, 6, replace=False)] = 1
    X.flags.writeable = False
    return X


def _ziarno(nazwa: str) -> int:
    return zlib.crc32(nazwa.encode())


# ---------- techniki ----------

class Technika:
    """Baza: `wynik(przeszlosc)` zwraca ocenę 49 liczb. Stan jest douczany przyrostowo wyłącznie z wierszy
    przekazanej przeszłości; krótsza przeszłość niż ostatnio (np. w teście) zeruje stan."""
    nazwa = ""
    opis = ""

    def __init__(self):
        self.rng = np.random.default_rng(_ziarno(self.nazwa))
        self.reset()

    def reset(self):
        self.n = 0

    def wynik(self, przeszlosc: np.ndarray) -> np.ndarray:
        if len(przeszlosc) < self.n:
            self.rng = np.random.default_rng(_ziarno(self.nazwa))
            self.reset()
        for i in range(self.n, len(przeszlosc)):
            self.ucz(przeszlosc, i)
        self.n = len(przeszlosc)
        return np.asarray(self.ocena(przeszlosc), dtype=float)

    def ucz(self, p, i):          # wiersz i (oraz wcześniejsze) jest już przeszłością
        pass

    def ocena(self, p):
        raise NotImplementedError


class Los(Technika):
    nazwa, opis = "los", "losowy ranking (punkt odniesienia)"

    def ocena(self, p):
        return self.rng.random(49)


class Czeste(Technika):
    nazwa, opis = "czeste", "najczęstsze w całej historii"

    def reset(self):
        super().reset()
        self.c = np.zeros(49)

    def ucz(self, p, i):
        self.c += p[i]

    def ocena(self, p):
        return self.c


class CzesteEpoka(Technika):
    nazwa, opis = "czeste_epoka", "najczęstsze od początku bieżącej epoki maszyn"

    def __init__(self, poczatki: tuple[int, ...] = ()):
        self.poczatki = tuple(poczatki)
        super().__init__()

    def ocena(self, p):
        od = max([0] + [s for s in self.poczatki if s <= len(p) - 100])  # min. 100 losowań w epoce
        return p[od:].sum(0)


class Okno(Technika):
    okno, znak = 50, 1

    def ocena(self, p):
        return self.znak * p[-self.okno:].sum(0)


class Gorace(Okno):
    nazwa, opis = "gorace", "najczęstsze w ostatnich 50"


class Zimne(Okno):
    nazwa, opis, znak = "zimne", "najrzadsze w ostatnich 50", -1


class Anomalia(Okno):
    nazwa, opis, okno = "anomalia", "największe odchylenie w górę w ostatnich 300", 300


class Zalegle(Technika):
    nazwa, opis = "zalegle", "najdłużej nieobecne („należy się”)"

    def reset(self):
        super().reset()
        self.ostatnio = np.full(49, -1)

    def ucz(self, p, i):
        self.ostatnio[p[i] == 1] = i

    def ocena(self, p):
        return len(p) - self.ostatnio


class Ewma(Technika):
    nazwa, opis, polowa = "ewma", "częstość z zapominaniem (połowa wagi po 100 losowaniach)", 100

    def reset(self):
        super().reset()
        self.e = np.zeros(49)
        self.lam = 0.5 ** (1 / self.polowa)

    def ucz(self, p, i):
        self.e = self.e * self.lam + p[i]

    def ocena(self, p):
        return self.e


class Bayes(Ewma):
    # Średnia a posteriori rozkładu Dirichleta: (alfa + c_i) / (49 alfa + 6n). Przy równym założeniu dla wszystkich
    # liczb ranking zależy tylko od c_i, więc bayes to częstość z wolnym zapominaniem; założenie równe 300 losowaniom
    # wpływa na ocenę w zł (ułamki), nie na kolejność.
    nazwa, opis, polowa = "bayes", "Dirichlet z zapominaniem (połowa po 500), założenie: wszystkie równe", 500

    def ocena(self, p):
        alfa = 300 * 6 / 49
        return (alfa + self.e) / (49 * alfa + self.e.sum())


class Powtorki(Technika):
    nazwa, opis = "powtorki", "liczby z ostatnich losowań (ostatnie najwyżej)"

    def ocena(self, p):
        w = 0.5 ** np.arange(1, min(10, len(p)) + 1)
        return w @ p[::-1][:len(w)]


class Sasiedzi(Technika):
    nazwa, opis = "sasiedzi", "sąsiedzi (±1) liczb z ostatniego losowania"

    def ocena(self, p):
        o = p[-1].astype(float)
        s = np.zeros(49)
        s[1:] += o[:-1]
        s[:-1] += o[1:]
        return s


class Pary(Technika):
    nazwa, opis = "pary", "najczęstsi partnerzy liczb z ostatniego losowania"

    def reset(self):
        super().reset()
        self.C = np.zeros((49, 49))

    def ucz(self, p, i):
        r = p[i].astype(float)
        self.C += np.outer(r, r)

    def ocena(self, p):
        C = self.C.copy()
        np.fill_diagonal(C, 0)
        return p[-1] @ C


class Markow(Technika):
    nazwa, opis = "markow", "łańcuch Markowa: co pada po liczbach z ostatniego losowania"

    def reset(self):
        super().reset()
        self.T = np.ones((49, 49))
        self.c = np.full(49, 49.0)

    def ucz(self, p, i):
        if i > 0:
            a = p[i - 1].astype(float)
            self.T += np.outer(a, p[i])
            self.c += a * 6

    def ocena(self, p):
        return p[-1] @ (self.T / self.c[:, None])


class HazardPrzerw(Technika):
    nazwa, opis = "hazard_przerw", "empiryczna szansa powrotu po przerwie obecnej długości"
    MAX = 120

    def reset(self):
        super().reset()
        self.przerwa = np.zeros(49, dtype=int)
        self.doszlo = np.ones(self.MAX + 1)
        self.wrocilo = np.full(self.MAX + 1, 6 / 49)

    def ucz(self, p, i):
        g = np.minimum(self.przerwa, self.MAX)
        np.add.at(self.doszlo, g, 1)
        np.add.at(self.wrocilo, g, p[i])
        self.przerwa = np.where(p[i] == 1, 0, self.przerwa + 1)

    def ocena(self, p):
        g = np.minimum(self.przerwa, self.MAX)
        return self.wrocilo[g] / self.doszlo[g]


# --- filtry zestawów (systemy graczy działające na całych zestawach) ---

class Filtr(Technika):
    """Losowa pula 30 000 zestawów (niezależna od danych); kryterium z przeszłości wybiera „typowe” zestawy;
    ocena liczby = jak często występuje w wybranych zestawach. Kryterium odświeżane co 250 losowań."""
    CO = 250
    PULA = 30_000

    def __init__(self):
        rng = np.random.default_rng(49)
        self.pula = np.sort(np.argsort(rng.random((self.PULA, 49)), axis=1)[:, :6], axis=1) + 1
        super().__init__()

    def reset(self):
        super().reset()
        self.zestawy: list[np.ndarray] = []
        self.wazne_od = None
        self.s = None

    def ucz(self, p, i):
        self.zestawy.append(np.flatnonzero(p[i]) + 1)

    def ocena(self, p):
        if self.s is None or len(p) - self.wazne_od >= self.CO:
            hist = np.array(self.zestawy)
            ok = self.wybierz(hist, self.pula)
            self.s = np.bincount(self.pula[ok].ravel() - 1, minlength=49).astype(float)
            self.wazne_od = len(p)
        return self.s

    @staticmethod
    def _typowe_klasy(hist_klucz, pula_klucz, pokrycie=0.5):
        wart, ile = np.unique(hist_klucz, return_counts=True)
        kolej = np.argsort(-ile)
        suma = np.cumsum(ile[kolej]) / ile.sum()
        wybrane = wart[kolej[:np.searchsorted(suma, pokrycie) + 1]]
        return np.isin(pula_klucz, wybrane)

    def wybierz(self, hist, pula):
        raise NotImplementedError


class Suma(Filtr):
    nazwa, opis = "suma", "zestawy o sumie w środkowych 50% dawnych sum"

    def wybierz(self, hist, pula):
        a, b = np.percentile(hist.sum(1), [25, 75])
        s = pula.sum(1)
        return (s >= a) & (s <= b)


class Delta(Filtr):
    nazwa, opis = "delta", "system delta: różnice w typowych (10-90%) przedziałach"

    def wybierz(self, hist, pula):
        dh, dp = np.diff(hist, axis=1), np.diff(pula, axis=1)
        a, b = np.percentile(dh, [10, 90], axis=0)
        return ((dp >= a) & (dp <= b)).all(1)


class Pozycje(Filtr):
    nazwa, opis = "pozycje", "każda pozycja (1.-6. liczba) w typowym przedziale (25-75%)"

    def wybierz(self, hist, pula):
        a, b = np.percentile(hist, [25, 75], axis=0)
        return ((pula >= a) & (pula <= b)).all(1)


class ParzysteNiskie(Filtr):
    nazwa, opis = "parzyste_niskie", "najczęstsze proporcje parzyste/nieparzyste i niskie/wysokie"

    def wybierz(self, hist, pula):
        def klucz(z):
            return (z % 2 == 0).sum(1) * 10 + (z <= 24).sum(1)
        return self._typowe_klasy(klucz(hist), klucz(pula))


class Szablony(Filtr):
    nazwa, opis = "szablony", "szablony Gianelli: najczęstsze układy dziesiątek"

    def wybierz(self, hist, pula):
        def klucz(z):
            d = z // 10
            return sum((d == j).sum(1) * 7 ** j for j in range(5))
        return self._typowe_klasy(klucz(hist), klucz(pula))


# --- uczenie maszynowe ---

class Cechy:
    """Cechy każdej liczby przed losowaniem i: częstość w 10/50/200/całości, przerwa, była w ostatnim, EWMA."""
    NAZWY = ("f10", "f50", "f200", "fcala", "przerwa", "ostatnie", "ewma")

    def __init__(self):
        self.c = np.zeros(49)
        self.ostatnio = np.full(49, -1.0)
        self.e = np.zeros(49)
        self.lam = 0.5 ** (1 / 100)

    def przed(self, p, i) -> np.ndarray:
        """Cechy z wierszy p[:i] (stan zawiera dokładnie wiersze < i)."""
        n = max(i, 1)
        return np.column_stack([
            p[max(0, i - 10):i].sum(0) / 10, p[max(0, i - 50):i].sum(0) / 50, p[max(0, i - 200):i].sum(0) / 200,
            self.c / n, np.minimum(i - self.ostatnio, 200) / 200,
            p[i - 1] if i > 0 else np.zeros(49), self.e * (1 - self.lam),
        ]) * np.array([49 / 6] * 4 + [1, 1, 49 / 6])

    def dodaj(self, p, i):
        self.c += p[i]
        self.ostatnio[p[i] == 1] = i
        self.e = self.e * self.lam + p[i]


class ML(Technika):
    """Model uczony na parach (cechy przed losowaniem i, wynik losowania i) dla i < chwila douczenia."""
    CO = 250
    OD = 200

    def reset(self):
        super().reset()
        self.cechy = Cechy()
        self.F: list[np.ndarray] = []
        self.Y: list[np.ndarray] = []
        self.model = None
        self.uczono = 0

    def ucz(self, p, i):
        if i >= self.OD:
            self.F.append(self.wejscie(p, i))
            self.Y.append(np.asarray(p[i]))
        self.cechy.dodaj(p, i)

    def wejscie(self, p, i):
        return self.cechy.przed(p, i)

    def ocena(self, p):
        if self.model is None or len(p) - self.uczono >= self.CO:
            self.model = self.dopasuj(np.array(self.F), np.array(self.Y))
            self.uczono = len(p)
        return self.przewiduj(self.model, self.wejscie(p, len(p)))

    def dopasuj(self, F, Y):
        Xf = F.reshape(-1, F.shape[-1])
        y = Y.reshape(-1)
        return self.klasyfikator().fit(Xf, y)

    def przewiduj(self, model, f):
        return model.predict_proba(f)[:, 1]

    def klasyfikator(self):
        raise NotImplementedError


class Logistyczna(ML):
    nazwa, opis = "logistyczna", "regresja logistyczna na 7 cechach"

    def klasyfikator(self):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=300))


class Las(ML):
    nazwa, opis, CO = "las", "las losowy (60 drzew, głębokość 6)", 500

    def klasyfikator(self):
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=60, max_depth=6, max_samples=60_000, min_samples_leaf=50,
                                      n_jobs=-1, random_state=1)


class Boosting(ML):
    nazwa, opis, CO = "boosting", "gradient boosting (100 iteracji)", 500

    def klasyfikator(self):
        from sklearn.ensemble import HistGradientBoostingClassifier
        return HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, max_depth=4, random_state=1)


class Siec(ML):
    """Zamiennik LSTM: sieć widzi okno 10 ostatnich losowań (490 wejść) i przewiduje 49 wyjść naraz."""
    nazwa, opis, CO, OKNO = "siec", "sieć neuronowa na oknie 10 losowań (zamiast LSTM)", 500, 10

    def wejscie(self, p, i):
        okno = np.zeros((self.OKNO, 49))
        kawalek = p[max(0, i - self.OKNO):i]
        okno[self.OKNO - len(kawalek):] = kawalek
        return okno.ravel()

    def dopasuj(self, F, Y):
        from sklearn.neural_network import MLPClassifier
        return MLPClassifier(hidden_layer_sizes=(64,), alpha=1e-3, max_iter=40, random_state=1).fit(F, Y)

    def przewiduj(self, model, f):
        return model.predict_proba(f[None, :])[0]


class Genetyczny(ML):
    """Algorytm genetyczny dobiera wagi 7 cech tak, by na ostatnich 1500 losowaniach przeszłości
    maksymalizować trafienia w top-12."""
    nazwa, opis, CO = "genetyczny", "algorytm genetyczny dobiera wagi cech", 500

    def dopasuj(self, F, Y):
        F, Y = F[-1500:], Y[-1500:]
        Z = (F - F.mean(1, keepdims=True)) / (F.std(1, keepdims=True) + 1e-9)
        rng = np.random.default_rng(7 + len(F))
        pop = rng.normal(size=(40, Z.shape[2]))

        def przystosowanie(w):
            s = Z @ w
            top = np.argpartition(-s, 12, axis=1)[:, :12]
            return np.take_along_axis(Y, top, 1).sum(1).mean()

        for _ in range(25):
            fit = np.array([przystosowanie(w) for w in pop])
            elita = pop[np.argsort(-fit)[:8]]
            rodzice = elita[rng.integers(0, 8, size=(32, 2))]
            maska_ = rng.random((32, Z.shape[2])) < 0.5
            dzieci = np.where(maska_, rodzice[:, 0], rodzice[:, 1]) + rng.normal(0, 0.3, (32, Z.shape[2]))
            pop = np.vstack([elita, dzieci])
        fit = np.array([przystosowanie(w) for w in pop])
        return pop[int(np.argmax(fit))]

    def przewiduj(self, w, f):
        z = (f - f.mean(0)) / (f.std(0) + 1e-9)
        return z @ w


class Klastry(Technika):
    nazwa, opis, CO = "klastry", "k-średnich (8 grup) + przejścia między grupami", 500

    def reset(self):
        super().reset()
        self.km = None
        self.uczono = 0

    def ocena(self, p):
        if self.km is None or len(p) - self.uczono >= self.CO:
            from sklearn.cluster import KMeans
            self.km = KMeans(n_clusters=8, n_init=3, random_state=1).fit(p.astype(float))
            et = self.km.labels_
            self.P = np.ones((8, 8))
            np.add.at(self.P, (et[:-1], et[1:]), 1)
            self.P /= self.P.sum(1, keepdims=True)
            self.uczono = len(p)
        g = self.km.predict(p[-1:].astype(float))[0]
        return self.P[g] @ self.km.cluster_centers_


class Analogi(Technika):
    nazwa, opis = "analogi", "co padało po 50 losowaniach najbardziej podobnych do ostatniego"

    def ocena(self, p):
        if len(p) < 60:
            return np.zeros(49)
        wsp = p[:-1].astype(np.int16) @ p[-1].astype(np.int16)
        klucz = wsp.astype(np.int64) * 100_000 + np.arange(len(wsp))      # remisy: nowsze pierwsze
        idx = np.argpartition(-klucz, 50)[:50]
        return p[idx + 1].sum(0)


class Bandyta(Technika):
    nazwa, opis = "bandyta", "uczenie ze wzmocnieniem: próbkowanie Thompsona z zapominaniem"

    def reset(self):
        super().reset()
        self.a = np.ones(49)
        self.b = np.ones(49)

    def ucz(self, p, i):
        self.a = 0.995 * self.a + p[i]
        self.b = 0.995 * self.b + (1 - p[i])

    def ocena(self, p):
        return self.rng.beta(self.a + 1, self.b + 1)


def wszystkie_techniki(daty: list[dt.date] | None = None) -> list[Technika]:
    poczatki = tuple(next((i for i, d in enumerate(daty) if d >= e), len(daty)) for e in EPOKI) if daty else ()
    return [Los(), Czeste(), CzesteEpoka(poczatki), Gorace(), Zimne(), Zalegle(), Ewma(), Bayes(), Anomalia(),
            Powtorki(), Sasiedzi(), Pary(), Markow(), HazardPrzerw(), Suma(), Delta(), Pozycje(), ParzysteNiskie(),
            Szablony(), Logistyczna(), Las(), Boosting(), Siec(), Genetyczny(), Klastry(), Analogi(), Bandyta()]


# ---------- silnik ----------

def na_rangi(oceny: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Oceny (..., 49) -> rangi (0 = najlepsza); remisy łamane losowo."""
    szum = rng.random(oceny.shape)
    kolej = np.lexsort((szum, -oceny), axis=-1)
    rangi = np.empty_like(kolej)
    np.put_along_axis(rangi, kolej, np.arange(49), axis=-1)
    return rangi.astype(np.int8)


def symuluj(X: np.ndarray, techniki: list[Technika], rozgrzewka: int = ROZGRZEWKA, postep: bool = True) -> dict:
    """Walk-forward: dla t = rozgrzewka..N-1 każda technika widzi tylko X[:t]. Zwraca oceny i rangi (N - rozgrzewka, 49)."""
    X = np.array(X, dtype=np.int8)
    X.flags.writeable = False
    N = len(X)
    oceny = {t.nazwa: np.zeros((N - rozgrzewka, 49), dtype=np.float32) for t in techniki}
    czas = {t.nazwa: 0.0 for t in techniki}
    start = time.time()
    for t in range(rozgrzewka, N):
        przeszlosc = X[:t]
        for tech in techniki:
            t0 = time.time()
            oceny[tech.nazwa][t - rozgrzewka] = tech.wynik(przeszlosc)
            czas[tech.nazwa] += time.time() - t0
        if postep and (t - rozgrzewka) % 500 == 0:
            print(f"  losowanie {t}/{N}, {time.time() - start:.0f} s", flush=True)
    rangi = {n: na_rangi(o, np.random.default_rng(_ziarno(n) + 1)) for n, o in oceny.items()}
    return {"oceny": oceny, "rangi": rangi, "czas_s": czas}


def pozycje_trafien(rangi: np.ndarray, Xp: np.ndarray) -> np.ndarray:
    """Rangi 6 wylosowanych liczb w każdym losowaniu: (n, 6)."""
    return np.sort(rangi[Xp.astype(bool)].reshape(len(Xp), 6), axis=1)


# ---------- połączenia ----------

def borda(rangi_lista: list[np.ndarray], ziarno: int = 0) -> np.ndarray:
    suma = np.sum([r.astype(np.int32) for r in rangi_lista], axis=0)
    return na_rangi(-suma.astype(float), np.random.default_rng(ziarno))


def srednia(oceny_lista: list[np.ndarray], ziarno: int = 0) -> np.ndarray:
    z = [(o - o.mean(1, keepdims=True)) / (o.std(1, keepdims=True) + 1e-9) for o in oceny_lista]
    return na_rangi(np.mean(z, axis=0), np.random.default_rng(ziarno))


def stacking(rangi_lista: list[np.ndarray], Xp: np.ndarray, co: int = 500, minimum: int = 500) -> np.ndarray:
    """Regresja logistyczna na rangach technik; model dla wiersza t uczony tylko na wierszach < punkt douczenia <= t.
    Dopóki brak `minimum` wierszy przeszłości, używa Bordy."""
    from sklearn.linear_model import LogisticRegression
    n = len(Xp)
    cech = np.stack([1 - r.astype(np.float32) / 48 for r in rangi_lista], axis=-1)   # (n, 49, m)
    wynik = borda(rangi_lista, 3).astype(float) * -1
    for r in range(minimum, n, co):
        model = LogisticRegression(max_iter=300).fit(cech[:r].reshape(-1, cech.shape[-1]), Xp[:r].reshape(-1))
        do = min(n, r + co)
        wynik[r:do] = model.predict_proba(cech[r:do].reshape(-1, cech.shape[-1]))[:, 1].reshape(do - r, 49)
    return na_rangi(wynik, np.random.default_rng(4))


def trafienia12(rangi: np.ndarray, Xp: np.ndarray) -> float:
    return float(((rangi < 12) & (Xp == 1)).sum(1).mean())


def najlepsze_polaczenie(rangi: dict[str, np.ndarray], Xp: np.ndarray, uczenie: np.ndarray, r: int) -> tuple[str, ...]:
    """Najlepsza para / trójka (Borda) według trafień w top-12 tylko na wierszach `uczenie` (lata do 2009)."""
    nazwy = [n for n in rangi if n != "los"]
    najl, wynik = None, -1.0
    for kombinacja in itertools.combinations(nazwy, r):
        w = trafienia12(borda([rangi[n][uczenie] for n in kombinacja]), Xp[uczenie])
        if w > wynik:
            najl, wynik = kombinacja, w
    return najl


# ---------- miary i istotność ----------

def hiper(N: int, K_: int, n: int, k: int) -> float:
    """P(k sukcesów w n losowaniach bez zwracania z N, w tym K_ sukcesów)."""
    if k < 0 or k > n or k > K_ or n - k > N - K_:
        return 0.0
    return comb(K_, k) * comb(N - K_, n - k) / comb(N, n)


def ev_zakladu_z_puli(h: int, pula: int = 12) -> float:
    """Średnia wygrana zakładu losowanego z top-`pula`, gdy pula zawiera h wylosowanych liczb."""
    return sum(hiper(pula, h, 6, j) * NAGRODY[j] for j in (3, 4, 5, 6))


def wygrana_systemu(h: int, n: int) -> float:
    """Wygrana zakładu systemowego n liczb (C(n,6) zakładów), gdy h z nich zostało wylosowanych."""
    return sum(comb(h, j) * comb(n - h, 6 - j) * NAGRODY[j] for j in (3, 4, 5, 6))


EV_ZAKLADU = sum(hiper(49, 6, 6, j) * NAGRODY[j] for j in (3, 4, 5, 6))   # los: średnia wygrana zakładu


def holm(p: list[float]) -> list[float]:
    m = len(p)
    kolej = sorted(range(m), key=lambda i: p[i])
    out = [0.0] * m
    najw = 0.0
    for poz, i in enumerate(kolej):
        najw = max(najw, min(1.0, (m - poz) * p[i]))
        out[i] = najw
    return out


_NULL: dict = {}


def rozklad_losu(L: int, k: int, symulacji: int, ziarno: int = 2026) -> np.ndarray:
    """Średnie trafienia w top-k dla `symulacji` losowych rankingów na L losowaniach (Monte Carlo)."""
    klucz = (L, k, symulacji)
    if klucz not in _NULL:
        rng = np.random.default_rng(ziarno + k)
        out = []
        for i in range(0, symulacji, 500):
            m = min(500, symulacji - i)
            out.append(rng.hypergeometric(6, 43, k, size=(m, L)).mean(1))
        _NULL[klucz] = np.concatenate(out)
    return _NULL[klucz]


def przedzial(roznice: np.ndarray, rng: np.random.Generator, blok: int = 50, powtorzen: int = 1000) -> tuple[float, float]:
    """95% przedział średniej metodą bootstrap blokowy (bloki po 50 losowań)."""
    L = len(roznice)
    nb = max(1, L // blok)
    starty = rng.integers(0, max(1, L - blok + 1), size=(powtorzen, nb))
    idx = (starty[:, :, None] + np.arange(blok)).reshape(powtorzen, -1)
    sr = roznice[np.minimum(idx, L - 1)].mean(1)
    return float(np.percentile(sr, 2.5)), float(np.percentile(sr, 97.5))


def ocen(poz: np.ndarray, symulacji: int, rng: np.random.Generator) -> dict:
    """Miary dla jednej metody na jednym okresie; `poz` = rangi wylosowanych liczb (L, 6)."""
    L = len(poz)
    w: dict = {"losowan": L, "k": {}}
    for k in K:
        h = (poz < k).sum(1)
        sr = float(h.mean())
        oczek = 6 * k / 49
        null = rozklad_losu(L, k, symulacji)
        p = float((1 + (null >= sr - 1e-12).sum()) / (1 + len(null)))
        a, b = przedzial(h - oczek, rng)
        w["k"][k] = {"srednia": sr, "los": oczek, "roznica": sr - oczek, "ci": [a, b], "p": p}
    h12 = (poz < 12).sum(1)
    h6 = (poz < 6).sum(1)
    ev12 = np.array([ev_zakladu_z_puli(h) for h in range(7)])
    w["zl_20_z_top12"] = float((20 * ev12[h12]).mean() - 100)
    w["zl_20_los"] = 20 * EV_ZAKLADU - 100
    w["top6_rozklad"] = np.bincount(h6, minlength=7).tolist()
    syst = {}
    for n in SYSTEMY:
        hn = (poz < n).sum(1)
        koszt = comb(n, 6) * CENA
        wyg = np.array([wygrana_systemu(h, n) for h in range(7)])[hn]
        syst[n] = {
            "koszt_zl": koszt,
            "zwrot_na_zl": float(wyg.mean() / koszt),
            "zwrot_na_zl_los": EV_ZAKLADU / CENA,
            "co_najmniej": {j: {"czestosc": float((hn >= j).mean()),
                                "los": sum(hiper(49, 6, n, i) for i in range(j, 7)),
                                "razy": int((hn >= j).sum())} for j in (3, 4, 5, 6)},
        }
    w["systemy"] = syst
    # wariant 100 zł: system 7 z rang 0-6 + system 7 z rang 7-13 + 6 zakładów z top-12
    hA = (poz < 7).sum(1)
    hB = ((poz >= 7) & (poz < 14)).sum(1)
    s7 = np.array([wygrana_systemu(h, 7) for h in range(7)])
    w["zl_2x7_plus_6"] = float((s7[hA] + s7[hB] + 6 * ev12[h12]).mean() - 100)
    return w


# ---------- całość ----------

def policz_wszystko(losowania, szybko: bool = False, symulacji: int = 20_000, postep: bool = True) -> dict:
    if szybko:
        losowania = losowania[-1500:] if len(losowania) > 1500 else losowania
        symulacji = 2000
    X = macierz(losowania)
    daty = [l.data for l in losowania]
    t0 = time.time()
    sym = symuluj(X, wszystkie_techniki(daty), postep=postep)
    Xp = X[ROZGRZEWKA:]
    daty_p = np.array(daty[ROZGRZEWKA:])
    uczenie = daty_p < OD_TESTU
    if uczenie.all() or not uczenie.any():   # dane bez roku 2010 (np. próba): podział w 2/3
        uczenie = np.arange(len(Xp)) < len(Xp) * 2 // 3
    test = ~uczenie
    rangi = dict(sym["rangi"])
    pojedyncze = [n for n in rangi if n != "los"]
    para = najlepsze_polaczenie(rangi, Xp, uczenie, 2)
    trojka = najlepsze_polaczenie(rangi, Xp, uczenie, 3)
    rangi["borda"] = borda([sym["rangi"][n] for n in pojedyncze], 1)
    rangi["srednia"] = srednia([sym["oceny"][n] for n in pojedyncze], 2)
    rangi["stacking"] = stacking([sym["rangi"][n] for n in pojedyncze], Xp)
    rangi["para"] = borda([rangi[n] for n in para], 5)
    rangi["trojka"] = borda([rangi[n] for n in trojka], 6)
    opisy = {t.nazwa: t.opis for t in wszystkie_techniki(daty)}
    opisy.update({"borda": "głosowanie rang wszystkich technik", "srednia": "średnia ocen wszystkich technik",
                  "stacking": "regresja logistyczna na rangach (uczona na przeszłości)",
                  "para": "najlepsza para z lat do 2009: " + " + ".join(para),
                  "trojka": "najlepsza trójka z lat do 2009: " + " + ".join(trojka)})
    rng = np.random.default_rng(11)
    wyniki = {}
    for nazwa, r in rangi.items():
        poz = pozycje_trafien(r, Xp)
        wyniki[nazwa] = {"opis": opisy[nazwa], "cale": ocen(poz, symulacji, rng),
                         "uczenie": ocen(poz[uczenie], symulacji, rng), "test": ocen(poz[test], symulacji, rng)}
    for okres in ("cale", "uczenie", "test"):
        klucze = [(n, k) for n in wyniki for k in K]
        ph = holm([wyniki[n][okres]["k"][k]["p"] for n, k in klucze])
        for (n, k), p in zip(klucze, ph):
            wyniki[n][okres]["k"][k]["p_holm"] = p
    for n, w in wyniki.items():
        w["przechodzi"] = any(w["test"]["k"][k]["p_holm"] < ALFA and w["uczenie"]["k"][k]["roznica"] > 0 for k in K)
    return {
        "policzono": dt.datetime.now().isoformat(timespec="seconds"),
        "losowan": len(losowania), "od": daty[0].isoformat(), "do": daty[-1].isoformat(),
        "rozgrzewka": ROZGRZEWKA, "ocenianych": int(len(Xp)),
        "uczenie_do": str(daty_p[uczenie][-1]), "test_od": str(daty_p[test][0]),
        "losowan_uczenie": int(uczenie.sum()), "losowan_test": int(test.sum()),
        "symulacji_losu": symulacji, "czas_s": round(time.time() - t0, 1),
        "czas_technik_s": {k: round(v, 1) for k, v in sym["czas_s"].items()},
        "para": list(para), "trojka": list(trojka),
        "przechodzi": [n for n, w in wyniki.items() if w["przechodzi"] and n != "los"],
        "wyniki": wyniki,
    }


# ---------- raport ----------

def _l(x: float, n: int = 2) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def _p(x: float) -> str:
    return "<0,001" if x < 0.001 else _l(x, 3)


def _zl(x: float) -> str:
    return f"{x:+.0f}".replace("-", "−") + " zł"


def blok_raportu(w: dict) -> str:
    R = w["wyniki"]
    L = [ZNACZNIK_OD, "",
         f"Policzono {w['policzono']}: {w['losowan']} losowań ({w['od']} - {w['do']}), ocenianych {w['ocenianych']} "
         f"po rozgrzewce {w['rozgrzewka']}; uczenie (wybór połączeń) do {w['uczenie_do']} ({w['losowan_uczenie']} losowań), "
         f"test poza próbą od {w['test_od']} ({w['losowan_test']} losowań). Los: {w['symulacji_losu']} losowych rankingów. "
         f"Czas obliczeń: {w['czas_s'] / 60:.0f} min.", "",
         "### Tabela 1. Trafienia w top-12 (los = 1,47 na 6 liczb) i wynik w zł", "",
         "Kolumny: średnia liczba wylosowanych liczb w 12 najwyżej ocenionych; różnica z losem i 95% przedział; p po poprawce "
         "Holma (wszystkie metody i k); wynik w zł = średni bilans na losowanie przy 20 zakładach po 5 zł z top-12 "
         f"(czysty los: {_zl(R['los']['cale']['zl_20_los'])}).", "",
         "| Metoda | Na czym polega | Cała historia: top-12 | różnica (95% CI) | p Holma | 2010-2026: top-12 | różnica (95% CI) | p Holma | zł / losowanie | Werdykt |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in R.items():
        c, t = r["cale"]["k"][12], r["test"]["k"][12]
        werdykt = "punkt odniesienia" if n == "los" else ("**przechodzi**" if r["przechodzi"] else "jak los")
        L.append(f"| `{n}` | {r['opis']} | {_l(c['srednia'], 3)} | {_l(c['roznica'], 3)} ({_l(c['ci'][0], 3)}; {_l(c['ci'][1], 3)}) "
                 f"| {_p(c['p_holm'])} | {_l(t['srednia'], 3)} | {_l(t['roznica'], 3)} ({_l(t['ci'][0], 3)}; {_l(t['ci'][1], 3)}) "
                 f"| {_p(t['p_holm'])} | {_zl(r['cale']['zl_20_z_top12'])} | {werdykt} |")
    L += ["", "### Tabela 2. Wszystkie k na latach 2010-2026 (test poza próbą): średnia trafień (p Holma)", "",
          "| Metoda | top-6 (los 0,73) | top-12 (los 1,47) | top-18 (los 2,20) | top-24 (los 2,94) |", "|---|---|---|---|---|"]
    for n, r in R.items():
        L.append(f"| `{n}` | " + " | ".join(f"{_l(r['test']['k'][k]['srednia'], 3)} ({_p(r['test']['k'][k]['p_holm'])})"
                                            for k in K) + " |")
    L += ["", "Najmniejsze p przed poprawką (cała historia, dowolne k): "
          + ", ".join(f"`{n}` top-{k} p = {_p(R[n]['cale']['k'][k]['p'])}"
                      for n, k in sorted(((n, k) for n in R for k in K), key=lambda x: R[x[0]]['cale']['k'][x[1]]['p'])[:5])
          + ". Przy " + str(len(R) * len(K)) + " testach kilka p poniżej 0,05 przed poprawką to rzecz normalna.", ""]
    # systemy
    L += ["### Tabela 3. Zakłady systemowe 7-12 liczb z top-n rankingu (cała historia)", "",
          "Zwrot na złotówkę (los: " + _l(EV_ZAKLADU / CENA, 3) + " zł z każdej złotówki dla każdego systemu) oraz jak często "
          "top-n zawierało co najmniej 4 wylosowane liczby (w nawiasie: los).", "",
          "| Metoda | " + " | ".join(f"system {n} ({comb(n, 6) * CENA:.0f} zł)" for n in SYSTEMY) + " |",
          "|---|" + "---|" * len(SYSTEMY)]
    for n, r in R.items():
        s = r["cale"]["systemy"]
        L.append(f"| `{n}` | " + " | ".join(
            f"{_l(s[m]['zwrot_na_zl'], 3)} zł; ≥4: {_l(100 * s[m]['co_najmniej'][4]['czestosc'], 2)}% "
            f"({_l(100 * s[m]['co_najmniej'][4]['los'], 2)}%)" for m in SYSTEMY) + " |")
    L += ["", "Wszystkie 6 liczb w top-12 (system 12 = szóstka): "
          + ", ".join(f"`{n}` {r['cale']['systemy'][12]['co_najmniej'][6]['razy']}" for n, r in R.items())
          + f" razy; los spodziewa się {w['ocenianych'] * hiper(49, 6, 12, 6):.2f} razy.", "",
          "### Tabela 4. Wariant 100 zł: 2 systemy po 7 liczb (rangi 1-7 i 8-14) + 6 zwykłych zakładów z top-12", "",
          "| Metoda | bilans na losowanie, cała historia | 2010-2026 | zwykłe 20 zakładów z top-12, cała historia |",
          "|---|---|---|---|"]
    for n, r in R.items():
        L.append(f"| `{n}` | {_zl(r['cale']['zl_2x7_plus_6'])} | {_zl(r['test']['zl_2x7_plus_6'])} | {_zl(r['cale']['zl_20_z_top12'])} |")
    L += ["", f"Wybrane na latach do 2009: para = {' + '.join(w['para'])}, trójka = {' + '.join(w['trojka'])}.",
          "Metody, które przeszły test poza próbą: " + (", ".join(w["przechodzi"]) if w["przechodzi"] else "**żadna**") + ".",
          "", ZNACZNIK_DO]
    return "\n".join(L)


def wstaw_do_raportu(blok: str, plik: Path = PLIK_RAPORT) -> None:
    tekst = plik.read_text(encoding="utf-8") if plik.exists() else f"# Lotto, etap 3\n\n{ZNACZNIK_OD}\n{ZNACZNIK_DO}\n"
    if ZNACZNIK_OD in tekst and ZNACZNIK_DO in tekst:
        a = tekst.index(ZNACZNIK_OD)
        b = tekst.index(ZNACZNIK_DO) + len(ZNACZNIK_DO)
        tekst = tekst[:a] + blok + tekst[b:]
    else:
        tekst = tekst.rstrip() + "\n\n" + blok + "\n"
    plik.write_text(tekst, encoding="utf-8")


def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--szybko", action="store_true", help="próba na 1500 losowaniach")
    a.add_argument("--symulacji", type=int, default=20_000)
    a = a.parse_args(argv)
    losowania = dane.wczytaj_csv()
    if not losowania:
        print("Brak dane/lotto.csv.")
        return 1
    w = policz_wszystko(losowania, szybko=a.szybko, symulacji=a.symulacji)
    plik = PLIK_JSON.with_name("symulacja_proba.json") if a.szybko else PLIK_JSON
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(_json(w), ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.szybko:
        wstaw_do_raportu(blok_raportu(w))
    print(f"Gotowe w {w['czas_s'] / 60:.1f} min. Przechodzi test poza próbą: {w['przechodzi'] or 'nic'}. Plik: {plik}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
