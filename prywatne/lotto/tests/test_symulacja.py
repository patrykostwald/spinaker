import sys
from math import comb
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etap3"))

import symulacja as s  # noqa: E402

N, ROZ, T0 = 420, 260, 340


def _historie():
    X = s.losowa_historia(N, ziarno=3)
    Y = np.array(X)
    Y[T0:] = s.losowa_historia(N - T0, ziarno=99)   # inna przyszłość od losowania T0
    return X, Y


TECHNIKI = [t.nazwa for t in s.wszystkie_techniki()]


@pytest.mark.parametrize("i", range(len(TECHNIKI)), ids=TECHNIKI)
def test_brak_podgladania_przyszlosci(i):
    """Ranking na losowanie t (t <= T0) nie może zależeć od losowań t, t+1, ...: zmieniamy przyszłość od T0
    i oceny dla t <= T0 muszą być identyczne."""
    X, Y = _historie()
    a = s.symuluj(X, [s.wszystkie_techniki()[i]], rozgrzewka=ROZ, postep=False)["oceny"]
    b = s.symuluj(Y, [s.wszystkie_techniki()[i]], rozgrzewka=ROZ, postep=False)["oceny"]
    nazwa = next(iter(a))
    do = T0 - ROZ + 1                     # wiersze dla t = ROZ..T0
    assert np.array_equal(a[nazwa][:do], b[nazwa][:do])


def test_przeszlosc_tylko_do_odczytu():
    X = s.losowa_historia(50)
    with pytest.raises(ValueError):
        X[0, 0] = 1


def test_przyrostowy_stan_zgodny_z_liczeniem_od_zera():
    X = s.losowa_historia(300, ziarno=5)
    for T in (s.Czeste, s.Pary, s.Markow, s.Zalegle, s.HazardPrzerw):
        t = T()
        for n in range(100, 300, 37):
            t.wynik(X[:n])
        assert np.allclose(t.wynik(X[:299]), T().wynik(X[:299]))
        # krótsza przeszłość zeruje stan, a nie miesza go z przyszłością
        assert np.allclose(t.wynik(X[:150]), T().wynik(X[:150]))


def test_czeste_i_zalegle_liczone_dobrze():
    X = s.losowa_historia(200, ziarno=8)
    assert np.array_equal(s.Czeste().wynik(X), X.sum(0))
    z = s.Zalegle().wynik(X)
    ostatnio = np.array([np.flatnonzero(X[:, j]).max() for j in range(49)])
    assert np.array_equal(z, 200 - ostatnio)


def test_stacking_bez_podgladania():
    X = s.losowa_historia(1300, ziarno=1)
    sym = s.symuluj(X, [s.Czeste(), s.Gorace(), s.Zalegle()], rozgrzewka=100, postep=False)
    rangi = list(sym["rangi"].values())
    Xp = np.array(X[100:])
    a = s.stacking(rangi, Xp, co=300, minimum=300)
    Xp2 = Xp.copy()
    Xp2[700:] = s.losowa_historia(len(Xp) - 700, ziarno=4)
    b = s.stacking(rangi, Xp2, co=300, minimum=300)
    assert np.array_equal(a[:700], b[:700])


def test_rangi_i_borda():
    rng = np.random.default_rng(0)
    oceny = rng.random((5, 49))
    r = s.na_rangi(oceny, rng)
    assert all(sorted(w) == list(range(49)) for w in r.tolist())
    assert (np.argmin(r, 1) == np.argmax(oceny, 1)).all()
    assert np.array_equal(s.borda([r, r, r]), r)


def test_pozycje_trafien():
    rangi = np.tile(np.arange(49, dtype=np.int8), (1, 1))
    Xp = np.zeros((1, 49), dtype=np.int8)
    Xp[0, [0, 5, 11, 12, 30, 48]] = 1
    poz = s.pozycje_trafien(rangi, Xp)
    assert poz.tolist() == [[0, 5, 11, 12, 30, 48]]
    assert int((poz < 12).sum()) == 3


def test_hipergeometryczny_i_nagrody():
    assert abs(sum(s.hiper(49, 6, 6, j) for j in range(7)) - 1) < 1e-12
    assert abs(s.hiper(49, 6, 12, 6) - 924 / 13_983_816) < 1e-15
    # system 7 z 6 trafionymi: 1 szóstka i 6 piątek
    assert s.wygrana_systemu(6, 7) == s.NAGRODY[6] + 6 * s.NAGRODY[5]
    # system 12 z 3 trafionymi: C(3,3)*C(9,3) trójek
    assert s.wygrana_systemu(3, 12) == comb(9, 3) * s.NAGRODY[3]
    # zakład z puli 12 zawierającej 6 wylosowanych: średnia = średnia po wszystkich 924 zakładach systemu 12
    assert abs(s.ev_zakladu_z_puli(6) - s.wygrana_systemu(6, 12) / 924) < 1e-9
    # system na losowej puli ma ten sam zwrot na złotówkę co zwykły zakład
    for n in s.SYSTEMY:
        sr = sum(s.hiper(49, 6, n, h) * s.wygrana_systemu(h, n) for h in range(7))
        assert abs(sr / (comb(n, 6) * s.CENA) - s.EV_ZAKLADU / s.CENA) < 1e-9


def test_holm():
    assert s.holm([0.01, 0.04, 0.03, 0.5]) == [0.04, 0.09, 0.09, 0.5]


def test_ocena_losowego_rankingu_bliska_losowi():
    rng = np.random.default_rng(2)
    poz = np.sort(np.argsort(rng.random((3000, 49)), axis=1)[:, :6], axis=1)
    w = s.ocen(poz, 500, rng)
    for k in s.K:
        assert abs(w["k"][k]["roznica"]) < 0.06
        a, b = w["k"][k]["ci"]
        assert a < w["k"][k]["roznica"] < b and b - a < 0.15
    assert w["systemy"][7]["koszt_zl"] == 35.0


def test_raport_i_wstawianie(tmp_path):
    rng = np.random.default_rng(3)
    poz = np.sort(np.argsort(rng.random((400, 49)), axis=1)[:, :6], axis=1)
    jedna = {"opis": "test", "cale": s.ocen(poz, 200, rng), "uczenie": s.ocen(poz[:200], 200, rng),
             "test": s.ocen(poz[200:], 200, rng), "przechodzi": False}
    for okres in ("cale", "uczenie", "test"):
        for k in s.K:
            jedna[okres]["k"][k]["p_holm"] = 1.0
    w = {"policzono": "x", "losowan": 900, "od": "a", "do": "b", "rozgrzewka": 500, "ocenianych": 400,
         "uczenie_do": "c", "test_od": "d", "losowan_uczenie": 200, "losowan_test": 200, "symulacji_losu": 200,
         "czas_s": 60, "para": ["a", "b"], "trojka": ["a", "b", "c"], "przechodzi": [],
         "wyniki": {"los": jedna, "czeste": jedna}}
    blok = s.blok_raportu(w)
    assert "**żadna**" in blok and "`czeste`" in blok
    plik = tmp_path / "R.md"
    plik.write_text(f"# R\n\nwstęp\n\n{s.ZNACZNIK_OD}\nstare\n{s.ZNACZNIK_DO}\n\nkoniec\n", encoding="utf-8")
    s.wstaw_do_raportu(blok, plik)
    t = plik.read_text(encoding="utf-8")
    assert "stare" not in t and "wstęp" in t and "koniec" in t and t.count(s.ZNACZNIK_OD) == 1
