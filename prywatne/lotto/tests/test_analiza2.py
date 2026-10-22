import datetime as dt
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analiza  # noqa: E402
import analiza2  # noqa: E402
import dane  # noqa: E402

HISTORIA = analiza.symulowana_historia(1500, ziarno=5)


def test_chi2_sf_zgodne_z_tablicami():
    assert abs(analiza2.chi2_sf(3.841, 1) - 0.05) < 1e-3
    assert abs(analiza2.chi2_sf(11.07, 5) - 0.05) < 1e-3
    assert abs(analiza2.chi2_sf(65.17, 48) - 0.05) < 2e-3
    # dla parzystych stopni swobody zgodne ze wzorem zamkniętym z analiza.py
    assert abs(analiza2.chi2_sf(62.33, 48) - analiza.chi2_sf_parzyste(62.33, 48)) < 1e-9


def test_dwumian_ogon():
    n, p = 20, 0.5
    dokladnie = sum(math.comb(n, j) for j in range(15, n + 1)) / 2 ** n
    assert abs(analiza2.dwumian_ogon(15, n, p) - dokladnie) < 1e-12
    assert analiza2.dwumian_ogon(0, n, p) == 1.0


def test_poprawki_wielokrotnych_testow():
    p = [0.01, 0.04, 0.03, 0.5]
    assert analiza2.bonferroni(p) == [0.04, 0.16, 0.12, 1.0]
    q = analiza2.benjamini_hochberg(p)
    assert [round(x, 4) for x in q] == [0.04, 0.0533, 0.0533, 0.5]
    assert all(qi >= pi for qi, pi in zip(q, p))


def test_klucze_par_i_trojek():
    for c in [(1, 2), (48, 49), (3, 17, 49)]:
        assert analiza2._odklucz(analiza2._klucz(c), len(c)) == c
    licz = analiza2.zlicz_grupy([(1, 2, 3, 4, 5, 6)], 2)
    assert len(licz) == 15 and set(licz.values()) == {1}


def test_idealny_los_nie_daje_sygnalow():
    w = analiza2.policz_wszystko(HISTORIA, szybko=True)
    assert w["epoki"]["istotnych_po_poprawce"] == 0
    assert w["pary_trojki"]["pary"]["istotnych_bh"] == 0
    assert abs(w["zaleznosc"]["miary"][0]["dane"] - 36 / 49) < 0.05
    assert {m["model"] for m in w["przewidywanie"]["modele"]} >= {"markow", "los", "czeste_ostatnie_50"}
    blok = analiza2.blok_raportu(w)
    assert "Werdykt automatu" in blok


def test_wykrywa_sztuczna_nierownosc():
    """Maszyna, która nie lubi liczby 49: test epok i przewidywanie muszą to złapać."""
    rng = random.Random(3)
    wagi = [1.0] * 48 + [0.2]
    los = []
    start = dt.date(1990, 1, 2)
    for i in range(4000):
        wyb: set[int] = set()
        while len(wyb) < 6:
            wyb.add(rng.choices(range(1, 50), weights=wagi)[0])
        los.append(dane.Losowanie(i + 1, start + dt.timedelta(days=3 * i), tuple(sorted(wyb))))
    e = analiza2.test_epok(los)
    assert e["istotnych_po_poprawce"] > 0
    h = analiza2.hipoteza_z_uczenia(los, od=dt.date(2010, 1, 1))
    assert h["wybrany"] == "40-49" and h["kierunek"] == "rzadziej" and h["potwierdzona"]


def test_przewidywanie_bez_podgladania_przyszlosci():
    """Zmiana losowania po dacie testu nie może zmienić typów na wcześniejsze losowania."""
    a = analiza2.test_przewidywania(HISTORIA, od=HISTORIA[1000].data)
    zmienione = list(HISTORIA)
    zmienione[-1] = dane.Losowanie(zmienione[-1].numer, zmienione[-1].data, (1, 2, 3, 4, 5, 6))
    b = analiza2.test_przewidywania(zmienione, od=HISTORIA[1000].data)
    # inne tylko ostatnie losowanie, więc różnica sumy trafień najwyżej 6 na model
    for ma, mb in zip(a["modele"], b["modele"]):
        assert abs(ma["srednio_trafien"] - mb["srednio_trafien"]) * a["losowan_testowych"] <= 6 + 1e-6


def test_pokrycie_nie_zmienia_sredniej():
    w = analiza2.test_pokrycia(20, random.Random(1), losowan_na_zestaw=50)
    for k in ("losowe_bez_ograniczen", "rozpisane_max_2_wspolne"):
        assert abs(w[k]["srednio_trafien_na_zaklad"] - 36 / 49) < 0.03


def test_wstaw_do_raportu(tmp_path):
    plik = tmp_path / "R.md"
    plik.write_text(f"Werdykt\n{analiza2.ZNACZNIK_OD}\nstare\n{analiza2.ZNACZNIK_DO}\nkoniec\n", encoding="utf-8")
    analiza2.wstaw_do_raportu("NOWE", plik)
    t = plik.read_text(encoding="utf-8")
    assert "NOWE" in t and "stare" not in t and t.startswith("Werdykt") and t.endswith("koniec\n")
