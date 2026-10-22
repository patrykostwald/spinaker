import datetime as dt
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analiza  # noqa: E402
import dane  # noqa: E402
import lotto  # noqa: E402
import strategie  # noqa: E402

HISTORIA = analiza.symulowana_historia(120, ziarno=3)


@pytest.mark.parametrize("nazwa", list(strategie.STRATEGIE))
@pytest.mark.parametrize("zakladow", [20, 33])
def test_generator_poprawne_zaklady_i_limit(nazwa, zakladow):
    rng = random.Random(1)
    szostki = frozenset(l.maska for l in HISTORIA)
    zaklady = strategie.STRATEGIE[nazwa]([l.liczby for l in HISTORIA], zakladow, rng, szostki)
    assert len(zaklady) == zakladow
    for z in zaklady:
        assert strategie.poprawny(z)            # 6 różnych liczb 1-49
        assert list(z) == sorted(z)
    for i in range(len(zaklady)):
        for j in range(i):
            assert strategie.wspolne(zaklady[i], zaklady[j]) <= 2


def test_historia_i_rzadko_grane_omijaja_dawne_szostki():
    rng = random.Random(2)
    dawny = (1, 2, 3, 4, 5, 6)
    szostki = frozenset({strategie.maska(dawny)})
    # wymuszenie: los zawsze proponuje dawną szóstkę albo nową
    propozycje = iter([dawny, (7, 8, 9, 10, 11, 12)] * 5)
    wynik = strategie._dobierz(1, lambda: next(propozycje), lambda m, z: m not in szostki)
    assert wynik == [(7, 8, 9, 10, 11, 12)]
    for z in strategie.rzadko_grane([], 20, rng, szostki):
        assert sum(x >= 32 for x in z) >= 3 and not strategie.wzorek(z)


def test_gorace_i_zimne_patrza_tylko_na_przeszlosc():
    hist = [(1, 2, 3, 4, 5, 6)] * strategie.OKNO
    rng = random.Random(3)
    pula_gor = set(strategie._czestosci(hist, random.Random(0))[:strategie.PULA_GORZIM])
    assert set(range(1, 7)) <= pula_gor
    zim = strategie.zimne(hist, 5, rng)
    assert all(not (set(z) & set(range(1, 7))) for z in zim)


def test_sprawdzanie_trafien():
    nagrody = {3: 35.0, 4: 200.0, 5: 7500.0, 6: 3e6}
    wynik = lotto.policz([[1, 2, 3, 4, 5, 6], [1, 2, 3, 10, 11, 12], [40, 41, 42, 43, 44, 45], [1, 2, 3, 4, 20, 21]],
                         (1, 2, 3, 4, 5, 6), nagrody)
    assert wynik["trafienia"] == [6, 3, 0, 4]
    assert wynik["t"] == {3: 1, 4: 1, 5: 0, 6: 1}
    assert wynik["wygrana"] == 3e6 + 35 + 200


def test_blokada_nadpisania(tmp_path):
    teraz = dt.datetime(2026, 10, 22, 12, 0)  # czwartek przed losowaniem
    kupon = lotto.utworz_kupon(lotto.najblizsze_losowanie(teraz), HISTORIA, random.Random(4), teraz)
    plik = lotto.zapisz_kupon(kupon, tmp_path)
    tresc = plik.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        lotto.zapisz_kupon(lotto.utworz_kupon(dt.date(2026, 10, 22), HISTORIA, random.Random(5), teraz), tmp_path)
    assert plik.read_text(encoding="utf-8") == tresc
    assert lotto.generuj(teraz, tmp_path) == 0          # polecenie też nie nadpisuje
    assert plik.read_text(encoding="utf-8") == tresc


def test_suma_kontrolna_wykrywa_zmiane():
    teraz = dt.datetime(2026, 10, 22, 12, 0)
    kupon = lotto.utworz_kupon(dt.date(2026, 10, 22), HISTORIA, random.Random(6), teraz)
    assert lotto.suma_kontrolna(kupon) == kupon["sha256"]
    kupon["strategie"]["los"][0] = [1, 2, 3, 4, 5, 6]
    assert lotto.suma_kontrolna(kupon) != kupon["sha256"]


def test_terminy():
    assert lotto.najblizsze_losowanie(dt.datetime(2026, 10, 22, 12)) == dt.date(2026, 10, 22)  # czw. rano
    assert lotto.najblizsze_losowanie(dt.datetime(2026, 10, 22, 21, 45)) == dt.date(2026, 10, 24)  # po sprzedaży
    assert lotto.najblizsze_losowanie(dt.datetime(2026, 10, 25, 9)) == dt.date(2026, 10, 27)  # niedziela -> wt.


def test_sprawdz_zalegle_raz(tmp_path):
    kupony, dziennik = tmp_path / "kupony", tmp_path / "DZIENNIK.csv"
    for d in (dt.date(2026, 10, 20), dt.date(2026, 10, 22)):
        lotto.zapisz_kupon(lotto.utworz_kupon(d, HISTORIA, random.Random(7), dt.datetime.combine(d, dt.time(9))), kupony)
    wyniki = {dt.date(2026, 10, 20): ((1, 2, 3, 4, 5, 6), dict(lotto.NAGRODY_SREDNIE), "test")}
    teraz = dt.datetime(2026, 10, 23, 8)
    lotto.sprawdz(teraz, kupony, dziennik, wynik_dla=wyniki.get)
    assert lotto.sprawdzone(dziennik) == {"2026-10-20"}         # 22.10 bez wyniku - czeka
    wyniki[dt.date(2026, 10, 22)] = ((7, 8, 9, 10, 11, 12), dict(lotto.NAGRODY_SREDNIE), "test")
    lotto.sprawdz(teraz, kupony, dziennik, wynik_dla=wyniki.get)
    lotto.sprawdz(teraz, kupony, dziennik, wynik_dla=wyniki.get)  # drugi raz nic nie dopisuje
    linie = dziennik.read_text(encoding="utf-8").strip().splitlines()
    assert len(linie) == 1 + 2 * len(strategie.STRATEGIE)
    assert lotto.raport(dziennik) == 0


def test_parsery_i_kontrola():
    tekst = "1. 27.01.1957 8,12,31,39,43,45\n2. 03.02.1957 5,10,11,22,25,27\n4. 17.02.1957 1,2,3,4,5,6\n"
    los = dane.parsuj_archiwum(tekst)
    assert los[0].liczby == (8, 12, 31, 39, 43, 45)
    k = dane.kontrola(los)
    assert k["liczba_losowan"] == 3 and k["luki_w_numeracji"] == [3]
    js = {"items": [{"results": [{"gameType": "Lotto", "drawSystemId": 7, "drawDate": "2026-10-20T20:00:00Z",
                                  "resultsJson": [6, 5, 4, 3, 2, 1]}]}]}
    assert dane.parsuj_lotto_pl_wyniki(json.dumps(js)) == [(7, dt.date(2026, 10, 20), (1, 2, 3, 4, 5, 6))]


def test_statystyka():
    assert abs(analiza.SREDNIA_TEORIA - 0.7347) < 1e-4
    assert abs(sum(analiza.p_trafien(k) for k in range(7)) - 1) < 1e-12
    # chi2 sf: mediana chi2(48) ok. 47.33
    assert abs(analiza.chi2_sf_parzyste(47.335, 48) - 0.5) < 0.01
