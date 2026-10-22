import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analiza  # noqa: E402
import lotto  # noqa: E402
import strona  # noqa: E402

HISTORIA = analiza.symulowana_historia(80, ziarno=9)


def _eksperyment(tmp_path, z_wynikami=True):
    kup, dz = tmp_path / "kupony", tmp_path / "DZIENNIK.csv"
    rng = random.Random(1)
    d1, d2 = dt.date(2026, 10, 20), dt.date(2026, 10, 22)
    lotto.zapisz_kupon(lotto.utworz_kupon(d1, HISTORIA, rng, dt.datetime(2026, 10, 20, 9)), kup)
    lotto.zapisz_kupon(lotto.utworz_kupon(d2, HISTORIA, rng, dt.datetime(2026, 10, 22, 10, 15)), kup)
    if z_wynikami:
        lotto.sprawdz(dt.datetime(2026, 10, 21, 8), kup, dz,
                      lambda d: ((1, 2, 3, 4, 5, 6), dict(lotto.NAGRODY_SREDNIE), "srednie"))
    return kup, dz


def test_zbierz_kupon_na_najblizsze_i_dziennik(tmp_path):
    kup, dz = _eksperyment(tmp_path)
    d = strona.zbierz(dt.datetime(2026, 10, 22, 12), kup, dz, losowania=HISTORIA)
    assert d["najblizsze"]["data"] == "2026-10-22"
    assert d["kupon"]["losowanie_data"] == "2026-10-22" and d["kupon"]["zgodna"]
    assert d["kupon"]["zapisano"] == "2026-10-22T10:15:00"
    assert set(d["kupon"]["strategie"]) == set(lotto.strategie.STRATEGIE)
    s = d["dziennik"]["strategie"]
    assert d["dziennik"]["daty"] == ["2026-10-20"]
    for v in s.values():
        assert v["wydane"] == 100.0 and v["bilans"] == round(v["wygrane"] - 100.0, 2) and v["przebieg"] == [v["bilans"]]
    assert d["ostatnie"]["data"] == "2026-10-20" and d["ostatnie"]["liczby"] == [1, 2, 3, 4, 5, 6]


def test_zmieniony_kupon_ma_niezgodna_sume(tmp_path):
    kup, dz = _eksperyment(tmp_path, z_wynikami=False)
    plik = kup / "2026-10-22.json"
    k = json.loads(plik.read_text(encoding="utf-8"))
    k["strategie"]["los"][0] = [1, 2, 3, 4, 5, 6]
    plik.write_text(json.dumps(k), encoding="utf-8")
    d = strona.zbierz(dt.datetime(2026, 10, 22, 12), kup, dz, losowania=HISTORIA)
    assert d["kupon"]["zgodna"] is False
    assert "suma niezgodna" in strona.strona_html(d)


def test_generuj_pliki_i_zasady(tmp_path):
    kup, dz = _eksperyment(tmp_path)
    wyj = tmp_path / "strona"
    strona.generuj(dt.datetime(2026, 10, 22, 12), wyj, katalog_kuponow=kup, dziennik=dz, losowania=HISTORIA)
    for nazwa in ("index.html", "dane.json", "przeglad.html"):
        assert (wyj / nazwa).exists()
    json.loads((wyj / "dane.json").read_text(encoding="utf-8"))
    for nazwa in ("index.html", "przeglad.html"):
        h = (wyj / nazwa).read_text(encoding="utf-8")
        assert 'name="robots" content="noindex, nofollow"' in h
        assert not re.search(r"<script[^>]+src=|<link[^>]+stylesheet|@import|https?://[^\"']*\.(js|css)\b", h)
        assert "18 lat" in h and "801 889 880" in h
        assert "Kaunitz" not in h and "Betclic" not in h and "meczyki" not in h
    h = (wyj / "index.html").read_text(encoding="utf-8")
    assert "Eksperyment na wirtualnych pieniądzach, żadna strategia nie zwiększa szansy" in h
    assert 'href="przeglad.html"' in h
    assert "<svg" in h  # wykres bilansu
    assert h.count('role="tabpanel"') == len(lotto.strategie.STRATEGIE)


def test_pusty_dziennik_i_brak_kuponow(tmp_path):
    d = strona.zbierz(dt.datetime(2026, 10, 23, 12), tmp_path / "brak", tmp_path / "brak.csv", losowania=HISTORIA)
    assert d["kupon"] is None and d["dziennik"]["daty"] == []
    assert d["najblizsze"]["data"] == "2026-10-24"  # piątek -> sobota
    h = strona.strona_html(d)
    assert "Jeszcze bez wyników" in h and "Kuponów jeszcze nie ma" in h


def test_przeglad_tabela_i_markdown():
    md = ("# Tytuł\n\n| # | Pozycja | Legalne | EV | Kapitał | Czas | Ocena |\n|---|---|---|---|---|---|---|\n"
          "| 1 | Turnieje | tak | dodatnia | 0 zł | 5 h | **8** |\n\n- punkt [źródło](https://example.org/a)\n  - pod\n"
          "- bonus ([meczyki](https://meczyki.pl/x))\n\nAkapit <script>alert(1)</script>\n")
    t = strona.przeglad_tabela(md)
    assert t == [{"nr": 1, "pozycja": "Turnieje", "legalne": "tak", "ev": "dodatnia", "ocena": 8}]
    h = strona.markdown_html(md)
    assert "<h1>Tytuł</h1>" in h and "<table" in h and "<ul><li>pod</li></ul>" in h
    assert 'href="https://example.org/a" rel="nofollow noopener noreferrer"' in h
    assert "meczyki.pl" not in h and "<script>" not in h and "&lt;script&gt;" in h


def test_prawdziwy_przeglad_ma_12_pozycji():
    md = strona.PRZEGLAD_MD.read_text(encoding="utf-8")
    t = strona.przeglad_tabela(md)
    assert len(t) == 12 and t[0]["ocena"] == 8 and t[-1]["ocena"] == 0


def test_lotto_sprawdz_odswieza_strone(monkeypatch):
    wywolania = []
    monkeypatch.setattr(lotto, "sprawdz", lambda: 0)
    monkeypatch.setattr(lotto, "odswiez_strone", lambda: wywolania.append(1) or 0)
    assert lotto.main(["sprawdz"]) == 0
    assert lotto.main(["strona"]) == 0
    assert len(wywolania) == 2


def test_blad_strony_nie_zatrzymuje_automatu(monkeypatch):
    def zly(*a, **k):
        raise RuntimeError("zepsute")
    monkeypatch.setattr(strona, "generuj", zly)
    monkeypatch.setattr(lotto.dane, "loguj", lambda t: None)
    assert lotto.odswiez_strone() == 1


def test_sekcja_etap3_z_wynikow_symulacji():
    k12 = lambda sr, p: {"k": {"12": {"srednia": sr, "p_holm": p}}}  # noqa: E731
    w = {"test_od": "2010-01-02", "losowan_test": 2630, "przechodzi": [], "wyniki": {
        "los": {"test": k12(1.46, 1.0), "cale": {"zl_20_los": -77.0}},
        "czeste": {"test": k12(1.49, 1.0)}, "zimne": {"test": k12(1.44, 1.0)}, "borda": {"test": k12(1.48, 1.0)}}}
    z = strona.etap3_skrot(w)
    assert z["technik"] == 2 and z["polaczen"] == 1 and z["najlepsza"] == "czeste"
    h = strona.sekcja_etap3({"etap3": z})
    assert "Etap 3: 2 technik, wynik" in h and "żadna nie zawęża okna" in h and "1,47" in h
    assert strona.sekcja_etap3({"etap3": {}}) == ""
