"""Testy słownika TERYT i granic PRG (geokoder Teraz)."""

import json
import math
import re
import shutil
import time
from pathlib import Path

import pytest

shapely = pytest.importorskip("shapely")

from teraz import geo  # noqa: E402
from teraz.geo import granice, nazwa, powiat_gminy, przecina, slownik as sl, w_ktorym_powiecie, w_ktorym_wojewodztwie, wojewodztwo_powiatu  # noqa: E402

DANE = sl.DANE


def test_slownik_ma_pelny_zestaw_jednostek():
    s = sl.slownik()
    assert (len(s.wojewodztwa), len(s.powiaty), len(s.gminy)) == (16, 380, 2479)
    assert s.stan == "2026-11-10"
    assert "GUGiK" in s.atrybucja and "10.11.2026" in s.atrybucja
    grodzkie = [p for p in s.powiaty if p.rodzaj == "grodzki"]
    assert len(grodzkie) == 66
    assert all(int(p.kod[2:]) >= 61 for p in grodzkie)
    assert all(int(p.kod[2:]) < 61 for p in s.powiaty if p.rodzaj == "ziemski")


def test_kody_tworza_spojna_hierarchie():
    s = sl.slownik()
    for gmina in s.gminy:
        assert len(gmina.kod) == 7
        assert gmina.kod[:4] in s.jednostki and gmina.kod[:2] in s.jednostki
        assert gmina.rodzaj == {"1": "miejska", "2": "wiejska", "3": "miejsko-wiejska"}[gmina.kod[-1]]
    for powiat in s.powiaty:
        assert powiat.kod[:2] in s.jednostki
    # miasto na prawach powiatu ma dokładnie jedną gminę
    for powiat in (p for p in s.powiaty if p.rodzaj == "grodzki"):
        assert len([g for g in s.gminy if g.kod[:4] == powiat.kod]) == 1


def test_znane_kody_miast_na_prawach_powiatu():
    assert nazwa("0661", krotka=True) == "Biała Podlaska"
    assert nazwa("0662", krotka=True) == "Chełm"
    assert nazwa("0663", krotka=True) == "Lublin"
    assert nazwa("1465", krotka=True) == "Warszawa"
    assert nazwa("2061", krotka=True) == "Białystok"
    assert nazwa("2063", krotka=True) == "Suwałki"
    assert nazwa("3262", krotka=True) == "Szczecin"


def test_nazwa_do_wyswietlania():
    assert nazwa("06") == "województwo lubelskie"
    assert nazwa("0619") == "powiat włodawski"
    assert nazwa("0662") == "miasto Chełm (powiat grodzki)"
    assert nazwa("3262011") == "miasto Szczecin"
    assert nazwa("1206092") == "gmina Mogilany"
    assert nazwa("1206092", pelna=True) == "gmina Mogilany, powiat krakowski, woj. małopolskie"
    assert nazwa("3262011", pelna=True) == "miasto Szczecin, woj. zachodniopomorskie"
    assert nazwa("1206092", krotka=True) == "Mogilany"


def test_wojewodztwo_powiatu_i_powiat_gminy():
    assert wojewodztwo_powiatu("0619") == "06"
    assert wojewodztwo_powiatu("1206092") == "12"
    assert wojewodztwo_powiatu("06") == "06"
    assert powiat_gminy("1206092") == "1206"
    assert powiat_gminy("0662011") == "0662"
    with pytest.raises(ValueError):
        powiat_gminy("06")
    with pytest.raises(KeyError):
        wojewodztwo_powiatu("9999")
    with pytest.raises(KeyError):
        nazwa("0000000")


def test_pliki_danych_maja_rozsadny_rozmiar():
    rozmiary = {p.name: p.stat().st_size for p in DANE.iterdir() if p.is_file()}
    assert {"teryt.json", "granice_powiaty.geojson", "granice_wojewodztwa.geojson"} <= set(rozmiary)
    assert sum(rozmiary.values()) < 4 * 1024 * 1024
    assert not any(n.endswith((".shp", ".dbf", ".shx")) for n in rozmiary), "surowe pliki PRG nie należą do repozytorium"


def test_granice_maja_wszystkie_jednostki_i_sa_poprawne():
    powiaty, woj = granice._powiaty(), granice._wojewodztwa()
    assert sorted(powiaty.kody) == sorted(p.kod for p in sl.slownik().powiaty)
    assert sorted(woj.kody) == sorted(w.kod for w in sl.slownik().wojewodztwa)
    assert all(g.is_valid and not g.is_empty for g in powiaty.geometrie + woj.geometrie)


def test_granice_powiatow_tworza_pokrywe_bez_szczelin_i_nakladek():
    geometrie = granice._powiaty().geometrie
    if hasattr(shapely, "coverage_is_valid"):
        assert shapely.coverage_is_valid(geometrie)
    suma = shapely.union_all(geometrie)
    assert suma.geom_type == "Polygon", "Polska to jeden obszar bez dziur"
    assert not suma.interiors
    assert abs(suma.area - sum(g.area for g in geometrie)) < 1e-9  # brak nakładek


def test_granice_wojewodztw_sa_suma_powiatow():
    powiaty, woj = granice._powiaty(), granice._wojewodztwa()
    for kod, geom in zip(woj.kody, woj.geometrie):
        czesci = [g for k, g in zip(powiaty.kody, powiaty.geometrie) if k[:2] == kod]
        assert geom.symmetric_difference(shapely.union_all(czesci)).area < 1e-9


def test_punkt_wewnatrz_kazdej_jednostki_trafia_do_swojego_powiatu():
    # „szer” i „dl” w słowniku to punkty wewnątrz surowych granic PRG; po uproszczeniu muszą nadal trafiać
    s = sl.slownik()
    for gmina in s.gminy:
        assert w_ktorym_powiecie(gmina.szer, gmina.dl, tolerancja_m=0) == gmina.kod[:4], gmina.kod
    for powiat in s.powiaty:
        assert w_ktorym_powiecie(powiat.szer, powiat.dl, tolerancja_m=0) == powiat.kod, powiat.kod


@pytest.mark.parametrize("lat, lon, oczekiwana", [
    (52.2318, 21.0060, "Warszawa"),  # Pałac Kultury
    (50.0617, 19.9373, "Kraków"),  # Rynek Główny
    (54.3520, 18.6466, "Gdańsk"),
    (51.1079, 17.0385, "Wrocław"),
    (50.0412, 21.9991, "Rzeszów"),
    (49.7838, 22.7678, "Przemyśl"),
    (53.1325, 23.1688, "Białystok"),
    (53.4285, 14.5528, "Szczecin"),
])
def test_znane_miasta_trafiaja_w_powiat_grodzki(lat, lon, oczekiwana):
    kod = w_ktorym_powiecie(lat, lon)
    assert nazwa(kod, krotka=True) == oczekiwana
    assert sl.jednostka(kod).rodzaj == "grodzki"


@pytest.mark.parametrize("lat, lon, powiat, wojewodztwo", [
    (49.2992, 19.9496, "tatrzański", "małopolskie"),  # Zakopane
    (50.8661, 20.6286, "Kielce", "świętokrzyskie"),
    (50.4476, 23.4137, "tomaszowski", "lubelskie"),  # Tomaszów Lubelski
    (54.7928, 18.4092, "pucki", "pomorskie"),  # Władysławowo
    (49.4707, 22.3306, "leski", "podkarpackie"),  # Lesko
])
def test_miejscowosci_trafiaja_w_dobre_powiaty(lat, lon, powiat, wojewodztwo):
    kod = w_ktorym_powiecie(lat, lon)
    assert nazwa(kod, krotka=True) == powiat
    assert nazwa(w_ktorym_wojewodztwie(lat, lon), krotka=True) == wojewodztwo


def test_punkt_przy_granicy_powiatow_jest_deterministyczny_i_nalezy_do_jednego_z_sasiadow():
    powiaty = granice._powiaty()
    a, b = granice.geometria("1261"), granice.geometria("1206")  # Kraków i powiat krakowski
    wspolna = a.intersection(b)
    assert not wspolna.is_empty and wspolna.length > 0.1
    linia = max(getattr(wspolna, "geoms", [wspolna]), key=lambda g: g.length)
    punkt = linia.interpolate(0.5, normalized=True)
    wynik = w_ktorym_powiecie(punkt.y, punkt.x, tolerancja_m=0)
    assert wynik in ("1261", "1206")
    assert wynik == min("1261", "1206"), "na wspólnej granicy wygrywa niższy kod"
    assert w_ktorym_powiecie(punkt.y, punkt.x, tolerancja_m=0) == wynik
    # kilkadziesiąt metrów w głąb każdego z powiatów
    srodek_a, srodek_b = a.representative_point(), b.representative_point()
    assert w_ktorym_powiecie(srodek_a.y, srodek_a.x) == "1261"
    assert w_ktorym_powiecie(srodek_b.y, srodek_b.x) == "1206"
    assert powiaty.indeks["1261"] != powiaty.indeks["1206"]


def test_punkty_poza_polska_i_nieprawidlowe():
    assert w_ktorym_powiecie(52.52, 13.40) is None  # Berlin
    assert w_ktorym_powiecie(55.0, 17.0) is None  # Bałtyk
    assert w_ktorym_wojewodztwie(48.0, 20.0) is None
    with pytest.raises(ValueError):
        w_ktorym_powiecie(200.0, 10.0)
    with pytest.raises(ValueError):
        w_ktorym_powiecie(50.0, 400.0)


def test_punkt_tuz_za_granica_dostaje_najblizszy_powiat_tylko_w_tolerancji():
    polska = shapely.union_all(granice._powiaty().geometrie)
    pas = polska.buffer(0.0015).difference(polska)  # pas ok. 100-170 m na zewnątrz granicy
    punkt = pas.representative_point()
    assert w_ktorym_powiecie(punkt.y, punkt.x, tolerancja_m=0) is None
    assert w_ktorym_powiecie(punkt.y, punkt.x) is not None  # w domyślnej tolerancji (250 m)
    daleko = polska.buffer(0.05).difference(polska.buffer(0.04)).representative_point()  # ok. 4-5 km
    assert w_ktorym_powiecie(daleko.y, daleko.x) is None


def _przesun(lat, lon, na_polnoc_m=0.0, na_wschod_m=0.0):
    return (lat + na_polnoc_m / granice._M_NA_STOPIEN,
            lon + na_wschod_m / (granice._M_NA_STOPIEN * math.cos(math.radians(lat))))


def _skrajny_wierzcholek(os):
    """Najdalszy wierzchołek Polski na wschód (os=0) albo północ (os=1): od niego odmierzamy metry na zewnątrz."""
    polska = shapely.union_all(granice._powiaty().geometrie)
    ob = polska.geoms if hasattr(polska, "geoms") else [polska]
    punkty = [p for g in ob for p in g.exterior.coords]
    return max(punkty, key=lambda p: p[os])


def test_tolerancja_jest_w_metrach_a_nie_w_stopniach_na_wschodzie_i_polnocy():
    # stopień długości jest na naszej szerokości ok. 1,5 raza krótszy niż stopień szerokości: tolerancja liczona
    # w stopniach dawałaby inne metry na wschód niż na północ
    for os, kierunek in ((0, "na_wschod_m"), (1, "na_polnoc_m")):
        lon, lat = _skrajny_wierzcholek(os)
        for metry, powinno_byc in ((100, True), (200, True), (320, False), (450, False), (3000, False)):
            punkt = _przesun(lat, lon, **{kierunek: metry})
            wynik = w_ktorym_powiecie(*punkt)
            assert (wynik is not None) == powinno_byc, (kierunek, metry, wynik)
        # własna tolerancja też w metrach
        assert w_ktorym_powiecie(*_przesun(lat, lon, **{kierunek: 600}), tolerancja_m=700) is not None
        assert w_ktorym_powiecie(*_przesun(lat, lon, **{kierunek: 800}), tolerancja_m=700) is None


def test_punkt_za_granica_panstwa_to_none_a_tuz_przy_granicy_dostaje_powiat():
    lon, lat = _skrajny_wierzcholek(0)  # wschodnia granica z Ukrainą lub Białorusią
    assert w_ktorym_powiecie(*_przesun(lat, lon, na_wschod_m=150)) is not None
    assert w_ktorym_powiecie(*_przesun(lat, lon, na_wschod_m=1500)) is None
    assert w_ktorym_wojewodztwie(*_przesun(lat, lon, na_wschod_m=1500)) is None
    assert w_ktorym_powiecie(*_przesun(lat, lon, na_wschod_m=150), tolerancja_m=0) is None


def test_atrybucja_pochodzi_z_danych_a_nie_z_kodu():
    assert geo.ATRYBUCJA == sl.slownik().atrybucja
    assert "GUGiK" in geo.ATRYBUCJA and "10.11.2026" in geo.ATRYBUCJA
    assert "ATRYBUCJA" in geo.__all__
    with pytest.raises(AttributeError):
        geo.NIE_MA_TAKIEGO_ATRYBUTU
    # podmoduł `slownik` nie może być przesłonięty funkcją o tej samej nazwie
    assert hasattr(sl, "DANE") and hasattr(geo.slownik, "slownik")


# --------------------------------------------------------------------------- sprawdzenie danych przy starcie

@pytest.fixture
def kopia_danych(tmp_path):
    katalog = tmp_path / "dane"
    shutil.copytree(DANE, katalog)
    return katalog


def test_sprawdz_dane_przechodzi_na_prawdziwych_plikach():
    s = geo.sprawdz_dane()
    assert (len(s.wojewodztwa), len(s.powiaty), len(s.gminy)) == (16, 380, 2479)


def test_sprawdz_dane_na_kopii_plikow_przechodzi(kopia_danych):
    assert geo.sprawdz_dane(kopia_danych).stan == "2026-11-10"


def test_sprawdz_dane_brak_pliku(kopia_danych):
    (kopia_danych / "teryt.json").unlink()
    with pytest.raises(geo.BladDanych, match=r"Brak pliku danych geokodera: teryt\.json"):
        geo.sprawdz_dane(kopia_danych)


def test_sprawdz_dane_uszkodzony_json(kopia_danych):
    (kopia_danych / "teryt.json").write_text('{"stan": "2026-11-10", "wojewodztwa": [', encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"Uszkodzony plik danych geokodera: teryt\.json"):
        geo.sprawdz_dane(kopia_danych)


def test_sprawdz_dane_zly_uklad_slownika(kopia_danych):
    surowe = json.loads((kopia_danych / "teryt.json").read_text(encoding="utf-8"))
    del surowe["gminy"]
    (kopia_danych / "teryt.json").write_text(json.dumps(surowe), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"teryt\.json: zły układ danych"):
        geo.sprawdz_dane(kopia_danych)


@pytest.mark.parametrize("zmiana, komunikat", [
    (lambda s: s["gminy"][0].__setitem__(2, "wiejska"), r"gmina 0201011 ma rodzaj 'wiejska'"),
    (lambda s: s["gminy"][0].__setitem__(0, "02010"), r"zły kod '02010'"),
    (lambda s: s["gminy"][0].__setitem__(3, 10.0), r"współrzędne spoza Polski"),
    (lambda s: s["powiaty"][0].__setitem__(2, "grodzki"), r"powiat 0201 ma rodzaj 'grodzki'"),
    (lambda s: s["wojewodztwa"].pop(), r"jednostka 3201 nie ma nadrzędnej jednostki"),
    (lambda s: s["gminy"][0].__setitem__(1, " "), r"pusta nazwa"),
])
def test_sprawdz_dane_niespojny_slownik(kopia_danych, zmiana, komunikat):
    surowe = json.loads((kopia_danych / "teryt.json").read_text(encoding="utf-8"))
    zmiana(surowe)
    (kopia_danych / "teryt.json").write_text(json.dumps(surowe), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=komunikat):
        geo.sprawdz_dane(kopia_danych)


@pytest.mark.parametrize("zmiana, komunikat", [
    (lambda s: s["gminy"][0].__setitem__(3, "52"), r"współrzędne, które nie są liczbami"),
    (lambda s: s["gminy"][0].__setitem__(4, "19.5"), r"współrzędne, które nie są liczbami"),
    (lambda s: s["gminy"][0].__setitem__(3, None), r"współrzędne, które nie są liczbami"),
    (lambda s: s["powiaty"][0].__setitem__(3, True), r"współrzędne, które nie są liczbami"),
    (lambda s: s["gminy"].append(list(s["gminy"][0])), r"powtórzony kod '0201011'"),
    (lambda s: s["powiaty"].append(list(s["powiaty"][0])), r"powtórzony kod '0201'"),
    (lambda s: s["wojewodztwa"].append(list(s["wojewodztwa"][0])), r"powtórzony kod '02'"),
])
def test_sprawdz_dane_wspolrzedne_jako_tekst_i_powtorzony_kod(kopia_danych, zmiana, komunikat):
    surowe = json.loads((kopia_danych / "teryt.json").read_text(encoding="utf-8"))
    zmiana(surowe)
    (kopia_danych / "teryt.json").write_text(json.dumps(surowe), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=komunikat):
        geo.sprawdz_dane(kopia_danych)


@pytest.mark.parametrize("tresc", [None, "to nie jest json", '{"features": 5}', '{"features": [{"properties": {}}]}', "[]"])
def test_warstwa_granic_czyta_plik_przez_wczytaj_json(kopia_danych, monkeypatch, tresc):
    # ten sam czytelny błąd co w `sprawdz_dane`, a nie surowy FileNotFoundError / JSONDecodeError / KeyError
    plik = kopia_danych / "granice_powiaty.geojson"
    if tresc is None:
        plik.unlink()
    else:
        plik.write_text(tresc, encoding="utf-8")
    monkeypatch.setattr(granice, "DANE", kopia_danych)
    with pytest.raises(geo.BladDanych, match=r"granice_powiaty\.geojson"):
        granice._Warstwa("granice_powiaty.geojson")


def test_sprawdz_dane_niespojne_granice(kopia_danych):
    plik = kopia_danych / "granice_powiaty.geojson"
    dane = json.loads(plik.read_text(encoding="utf-8"))
    brakujacy = dane["features"].pop()["properties"]["kod"]
    plik.write_text(json.dumps(dane), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=rf"granice_powiaty\.geojson: kody niezgodne ze słownikiem \(brakuje: \['{brakujacy}'\]"):
        geo.sprawdz_dane(kopia_danych)
    dane["features"].append({"type": "Feature", "properties": {"kod": brakujacy}, "geometry": None})
    plik.write_text(json.dumps(dane), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"obiekt bez kodu lub geometrii"):
        geo.sprawdz_dane(kopia_danych)
    dane["features"][-1]["geometry"] = {"type": "Point", "coordinates": [20.0, 50.0]}
    plik.write_text(json.dumps(dane), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=rf"zła geometria dla kodu {brakujacy}"):
        geo.sprawdz_dane(kopia_danych)


def test_sprawdz_dane_uszkodzone_granice_wojewodztw(kopia_danych):
    (kopia_danych / "granice_wojewodztwa.geojson").write_text("to nie jest json", encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"granice_wojewodztwa\.geojson"):
        geo.sprawdz_dane(kopia_danych)


def test_wczytaj_slownik_z_uszkodzonego_pliku_daje_czytelny_blad(kopia_danych):
    (kopia_danych / "teryt.json").write_bytes(b"\xff\xfe\x00 nie utf-8")
    with pytest.raises(sl.BladDanych, match=r"teryt\.json"):
        sl.wczytaj_slownik(kopia_danych)


# --------------------------------------------------------------------------- zależności i skrypt budowy

def test_requirements_przypina_shapely_21_do_3():
    plik = Path(__file__).resolve().parents[2] / "requirements.txt"
    if not plik.exists():
        pytest.skip("brak requirements.txt (testy uruchomione poza repozytorium)")
    wiersze = [w.strip() for w in plik.read_text(encoding="utf-8").splitlines() if w.strip().startswith("shapely")]
    assert wiersze == ["shapely>=2.1,<3"]


def test_naglowek_zbuduj_dane_przypina_wersje_narzedzi_do_budowy():
    zrodlo = (Path(sl.__file__).parent / "zbuduj_dane.py").read_text(encoding="utf-8")
    naglowek = zrodlo.split('"""')[1]
    assert re.search(r"pyshp==\d+\.\d+\.\d+", naglowek) and re.search(r"pyproj==\d+\.\d+\.\d+", naglowek)


def test_przecina_prostokat_z_jednostkami():
    warszawa = (20.85, 52.10, 21.20, 52.35)  # zachód, południe, wschód, północ
    assert przecina("14", warszawa)
    assert przecina("1465", warszawa)
    assert przecina("1465011", warszawa)  # gmina: sprawdzana po powiecie
    assert not przecina("1261", warszawa)  # Kraków
    assert not przecina("06", warszawa)  # lubelskie
    assert przecina(["1261", "1465"], warszawa)
    assert not przecina(["1261", "0663"], warszawa)
    wszystko = (14.0, 49.0, 24.5, 55.0)
    assert all(przecina(w.kod, wszystko) for w in sl.slownik().wojewodztwa)


def test_przecina_prostokat_na_styku_i_nieprawidlowy():
    krak = granice.geometria("1261").bounds
    assert przecina("1261", krak)
    punktowy = (19.9373, 50.0617, 19.9373, 50.0617)
    assert przecina("1261", punktowy)
    with pytest.raises(ValueError):
        przecina("1261", (21.0, 52.0, 20.0, 53.0))  # zachód większy od wschodu
    with pytest.raises(ValueError):
        przecina("1261", (19.0, 91.0, 20.0, 92.0))
    with pytest.raises(KeyError):
        przecina("9999", krak)


def test_wyszukiwanie_punktu_jest_szybkie():
    w_ktorym_powiecie(52.2, 21.0)  # rozgrzewka (wczytanie granic)
    start = time.perf_counter()
    for i in range(2000):
        w_ktorym_powiecie(49.5 + (i % 50) * 0.1, 15.0 + (i % 90) * 0.1)
    assert (time.perf_counter() - start) / 2000 < 0.002  # średnio poniżej 2 ms
