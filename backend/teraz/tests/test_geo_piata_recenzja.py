"""Testy poprawek po piątej recenzji geokodera (zlecenie Z3P7, PR #39): zdania recenzenta, decyzje prowadzącego
i zabezpieczenie strukturalne.

Zabezpieczenie: heurystyka, która wycina lub blokuje miejsce (pochodzenie, jednostka, rzeka, klub, imię, kraina,
powiat sprzeczny z nazwą), obniża pewność całego wyniku do najwyżej 0,75 (próg automatu to 0,8), gdy wycięte miejsce
byłoby inaczej w wyniku; wycięte miejsce zostaje w `dopasowania` z uwagą powodu. Nigdy nie podnosi pewności.
Bezsporne blokady (klub w zdaniu o sporcie, „na Wiśle”, „Nysa Kłodzka”, lista imion) pewności nie ruszają.
"""

import time
from pathlib import Path

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoder, geokoduj  # noqa: E402

WARSZAWA, KRAKOW, KALISZ, LUBLIN, PLOCK = "1465011", "1261011", "3061011", "0663011", "1462011"
NOWY_SACZ, ELBLAG, USTRON, WISLA, OLAWA, WROCLAW = "1262011", "2861011", "2403021", "2403031", "0215011", "0264011"
LESZNO_MIASTO, LESZNO_GMINA, POW_PRUSZKOWSKI, POW_WARSZAWSKI_ZACH, POW_LESZCZYNSKI = "3063011", "1432042", "1421", "1432", "3013"
OPOLE, KROSNO, BIELSKO = "1661011", "1861011", "2461011"
POW_OPOLSKI, POW_KROSNIENSKI, POW_BIELSKI = "1609", "1807", "2402"


def kody(wynik):
    return set(wynik.teryt)


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


# --------------------------------------------------------------------------- P1: rzeki

@pytest.mark.parametrize("tekst, oczekiwane, pewnosc", [
    ("Przerwa w dostawie wody w Wiśle i w Ustroniu.", {WISLA, USTRON}, 0.85),
    ("Brak wody w Oławie i we Wrocławiu.", {OLAWA, WROCLAW}, 0.65),
    ("Brak wody w Wiśle.", {WISLA}, 0.85),
    ("Woda w Oławie podtopiła piwnice we Wrocławiu.", {OLAWA, WROCLAW}, 0.65),
])
def test_woda_nie_uruchamia_blokady_rzeki(tekst, oczekiwane, pewnosc):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane and w.pewnosc == pewnosc, (tekst, w.teryt, w.pewnosc)
    assert not any("poza-wynikiem" in d.uwagi for d in w.dopasowania)


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Poziom Wisły w Warszawie rośnie.", {WARSZAWA}),
    ("Stan wód Wisły w Krakowie jest alarmowy.", {KRAKOW}),
    ("Wylew Wisły zagraża Warszawie.", {WARSZAWA}),
    ("Fala kulminacyjna Wisły dotarła do Warszawy.", {WARSZAWA}),
])
def test_slowo_hydrologiczne_tuz_przed_nazwa_nadal_blokuje_rzeke(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, tekst
    assert "rzeka" in next(d for d in w.dopasowania if "poza-wynikiem" in d.uwagi).uwagi


# --------------------------------------------------------------------------- P1: powiaty

def test_dopisek_powiatu_ma_pierwszenstwo_przed_powiatem_z_osobnego_zdania():
    w = geokoduj("Pożar w Lesznie (powiat pruszkowski). Alert dla powiatu leszczyńskiego.")
    assert kody(w) == {POW_PRUSZKOWSKI, POW_LESZCZYNSKI}, w.teryt  # bez miasta Leszno
    assert dopasowanie(w, "Lesznie").teryt == () and "powiat-wyklucza" in dopasowanie(w, "Lesznie").uwagi
    assert 0 < w.pewnosc < 0.8
    # dopisek zgodny z gminą: gmina Leszno (mazowieckie) zostaje, bez pewności wyższej niż przedtem
    w = geokoduj("Pożar w Lesznie (powiat warszawski zachodni). Alert dla powiatu leszczyńskiego.")
    assert kody(w) == {LESZNO_GMINA, POW_LESZCZYNSKI}, w.teryt
    assert w.pewnosc <= 0.9
    # kolejność odwrotna: osobne zdanie jest przed nazwą
    w = geokoduj("Alert dla powiatu leszczyńskiego. Pożar w Lesznie (powiat warszawski zachodni).")
    assert LESZNO_GMINA in kody(w) and LESZNO_MIASTO not in kody(w), w.teryt


def test_dopisek_rozstrzyga_wieloznaczna_nazwe_mimo_innego_powiatu_w_tekscie():
    w = geokoduj("Pożar w Czernichowie (powiat krakowski). Alert dla powiatu żywieckiego.")
    assert kody(w) == {"1206012", "2417"}, w.teryt  # gmina Czernichów z powiatu krakowskiego i osobny powiat żywiecki
    assert "kontekst" in dopasowanie(w, "Czernichowie").uwagi
    # nazwa jednoznaczna i powiat z innego zdania: bez zmiany
    w = geokoduj("Alert dla powiatu krakowskiego. Pożar w Warszawie.")
    assert WARSZAWA in kody(w) and w.pewnosc >= 0.8


def test_powiat_z_osobnego_zdania_nadal_rozstrzyga_nazwe_bez_dopisku():
    w = geokoduj("Pożar w Lesznie. Alert dla powiatu leszczyńskiego.")
    assert kody(w) == {LESZNO_MIASTO, POW_LESZCZYNSKI}, w.teryt


@pytest.mark.parametrize("miasto, kod_miasta, powiat, kod_powiatu", [
    ("Opolu", OPOLE, "opolski", POW_OPOLSKI),
    ("Krośnie", KROSNO, "krośnieński", POW_KROSNIENSKI),
    ("Bielsku-Białej", BIELSKO, "bielski", POW_BIELSKI),
])
def test_miasto_z_powiatem_o_homonimicznej_nazwie_daje_oba_kody(miasto, kod_miasta, powiat, kod_powiatu):
    # nazwa powiatu jest w Polsce wieloznaczna (opolski: lubelskie i opolskie); dopisek tuż za miastem rozstrzyga
    for tekst in (f"Pożar w {miasto} (powiat {powiat}).", f"Pożar w {miasto}, powiat {powiat}.",
                  f"Pożar w {miasto} (pow. {powiat})."):
        w = geokoduj(tekst)
        assert kody(w) == {kod_miasta, kod_powiatu}, (tekst, w.teryt)
        assert w.pewnosc >= 0.8, (tekst, w.pewnosc)


def test_pary_homonimicznych_powiatow_sa_w_tabeli():
    pary = geokoder._powiaty_o_nazwie_miast()
    assert pary["1661"] == POW_OPOLSKI and pary["1861"] == POW_KROSNIENSKI and pary["2461"] == POW_BIELSKI


def test_homonimiczny_powiat_bez_pasujacego_miasta_nie_jest_zgadywany():
    # dopisek rozstrzyga tylko powiat zgodny z gminą przed nim; „opolski” obok Krakowa to nadal homonim bez kodu
    w = geokoduj("Pożar w Krakowie (powiat opolski).")
    assert kody(w) == {KRAKOW}, w.teryt
    assert geokoduj("Alert dla powiatu opolskiego.").teryt == ()


# --------------------------------------------------------------------------- P1: imiona

@pytest.mark.parametrize("tekst, odrzucone", [
    ("Hanna Kraków zaginęła w Warszawie.", "Kraków"),
    ("Zaginięcie Wita Kalisza zgłoszono w Warszawie.", "Kalisza"),
    ("Wit Kalisz zaginął w Warszawie.", "Kalisz"),
])
def test_nazwa_po_imieniu_przy_wyraznym_miejscu_z_przyimkiem_odpada(tekst, odrzucone):
    w = geokoduj(tekst)
    assert kody(w) == {WARSZAWA}, (tekst, w.teryt)
    assert w.pewnosc == 0.75
    d = dopasowanie(w, odrzucone)
    assert {"poza-wynikiem", "imie"} <= set(d.uwagi) and d.teryt  # kandydat odrzucony z uwagą


@pytest.mark.parametrize("tekst, oczekiwane", [
    # bez miejsca z przyimkiem nazwa po imieniu zostaje miejscem (jak dotąd)
    ("Hanna Kraków zaginęła.", {KRAKOW}),
    ("Wita Kraków: turyści wrócili.", {KRAKOW}),
    ("Zaginięcie Wita Kalisza.", {KALISZ}),
    # poprzedni wyraz jest miastem: trasa, dwa miejsca
    ("Jarosław Przemyśl koło Rzeszowa.", {"1804011", "1862011", "1863011"}),
    # definicja „X to nazwa…”
    ("Hanna Lublin to nazwa kawiarni w Chełmie.", {LUBLIN, "0662011"}),
    ("Bolesław Kraków to ulica w Rzeszowie.", {KRAKOW, "1863011"}),
    # to samo miejsce w innej wzmiance
    ("Hanna Kraków zaginęła w Krakowie.", {KRAKOW}),
    # imię z listy, które nie jest gminą: nazwisko, bez zmiany pewności
    ("Andrzej Kalisz przemawiał w Poznaniu.", {"3064011"}),
])
def test_nazwa_po_imieniu_bez_zmian_poza_przypadkiem_spornym(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_nazwisko_po_imieniu_z_listy_nie_obniza_pewnosci():
    w = geokoduj("Andrzej Kalisz przemawiał w Poznaniu.")
    assert w.pewnosc == 0.9 and not any("poza-wynikiem" in d.uwagi for d in w.dopasowania)


# --------------------------------------------------------------------------- P1: pochodzenie i trasa

def test_mieszkancy_z_miast_to_dotknieci_zdarzeniem():
    w = geokoduj("Mieszkańcy z Krakowa i Warszawy bez prądu, awarie także w Lublinie.")
    assert kody(w) == {LUBLIN, KRAKOW, WARSZAWA}, w.teryt
    for fraza in ("Krakowa", "Warszawy"):
        assert "dotkniety-zdarzeniem" in dopasowanie(w, fraza).uwagi
        assert "poza-wynikiem" not in dopasowanie(w, fraza).uwagi
    # inni ludzie „z” miasta nadal mają pochodzenie
    w = geokoduj("Turyści z Krakowa i Warszawy utknęli w Lublinie.")
    assert kody(w) == {LUBLIN}


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kierowca z Lublina jechał dziś rano do Warszawy i miał wypadek w Płocku.", {LUBLIN, WARSZAWA, PLOCK}),
    ("Kierowca z Lublina jechał do Warszawy i miał wypadek w Płocku.", {LUBLIN, WARSZAWA, PLOCK}),
    ("Kierowca z Lublina jechał przez Kraków i miał wypadek w Płocku.", {LUBLIN, KRAKOW, PLOCK}),
    # okno trasy kończy się na „i” i na końcu zdania: „do” za nimi nie należy do kierowcy
    ("Kierowca z Lublina zasłabł w Płocku i jechał do Warszawy.", {PLOCK, WARSZAWA}),
    ("Kierowca z Lublina zasłabł w Płocku. Karetka jechała do Warszawy.", {PLOCK, WARSZAWA}),
])
def test_okno_trasy_to_piec_wyrazow_do_spojnika_i(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_po_wypadku_nie_jest_znacznikiem_trasy():
    w = geokoduj("Kierowca z Krakowa zmarł po wypadku w Warszawie.")
    assert kody(w) == {WARSZAWA} and w.pewnosc <= 0.75, (w.teryt, w.pewnosc)
    assert "pochodzenie" in dopasowanie(w, "Krakowa").uwagi
    # „po” przed nazwą to nadal trasa („od A po B”)
    assert kody(geokoduj("Burze przesuwają się od Tarnowa po Rzeszów.")) == {"1263011", "1863011"}


def test_nierozstrzygniety_element_listy_przekazuje_role_dalej():
    w = geokoduj("Kierowcy z Olsztyna i Elbląga utknęli w Nowym Sączu.")
    assert kody(w) == {NOWY_SACZ}, w.teryt  # Olsztyn bez rozstrzygnięcia nie przerywa listy pochodzenia
    assert "pochodzenie" in dopasowanie(w, "Elbląga").uwagi
    assert w.pewnosc <= 0.75
    # lista bez wycięcia (jedyne miejsce) zostaje
    assert kody(geokoduj("Kierowcy z Olsztyna i Elbląga utknęli.")) == {ELBLAG}


# --------------------------------------------------------------------------- zabezpieczenie strukturalne

# (tekst, powód w uwagach wyciętego miejsca, fraza wyciętego miejsca, kody wyniku)
SPORNE = [
    ("Kierowca z Lublina rozbił samochód w Warszawie.", "pochodzenie", "Lublina", {WARSZAWA}),
    ("Policjanci z KMP w Płocku zatrzymali w gminie Słupno.", "jednostka", "Płocku", {"1419122"}),
    ("Poziom Wisły w Warszawie rośnie.", "rzeka", "Wisły", {WARSZAWA}),
    ("Wody Polskie: stan wody w Wiśle w Płocku.", "rzeka", "Wiśle", {PLOCK}),
    ("Wisła Kraków zaginęła w Warszawie.", "klub", "Kraków", {WARSZAWA}),
    ("Wypadek w Warszawie. Pożar w Kotlinie Kłodzkiej.", "kraina", "Kotlinie", {WARSZAWA}),
    ("Hanna Kraków zaginęła w Warszawie.", "imie", "Kraków", {WARSZAWA}),
    ("Pożar w Lesznie (powiat pruszkowski).", "powiat-wyklucza", "Lesznie", {POW_PRUSZKOWSKI}),
    # powiat z osobnego zdania wyklucza nazwę, którą bez niego przyjęto by jako miasto (Chełm: 0,65): też do przeglądu
    ("Pożar w Chełmie. Alert dla powiatu bocheńskiego.", "powiat-wyklucza", "Chełmie", {"1201"}),
]


@pytest.mark.parametrize("tekst, powod, fraza, oczekiwane", SPORNE)
def test_sporne_wyciecie_obniza_pewnosc_do_przegladu_i_zostaje_w_dopasowaniach(tekst, powod, fraza, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert w.pewnosc <= geokoder.PEWNOSC_PO_WYCIECIU_MAX == 0.75 and w.pewnosc > 0, (tekst, w.pewnosc)
    assert w.pewnosc < 0.8  # poniżej progu automatu
    assert powod in dopasowanie(w, fraza).uwagi, (tekst, dopasowanie(w, fraza))


@pytest.mark.parametrize("powod", geokoder.HEURYSTYKI_WYCINAJACE)
def test_kazda_heurystyka_wycinajaca_ma_przypadek_w_testach(powod):
    assert powod in {p for _, p, _, _ in SPORNE}


@pytest.mark.parametrize("tekst, pewnosc", [
    # klub w zdaniu o sporcie, jawna rzeka, drugi człon rzeki, imię z listy (nie gmina): wycięcie bezsporne
    ("Kibice Wisły Kraków zatrzymani w Płocku.", 0.9),
    ("Wisła Kraków przegrała mecz w Płocku.", 0.9),
    ("IMGW: stan ostrzegawczy przekroczony na Wiśle w Tczewie.", 0.65),  # Tczew to homonim, jak przed zmianą
    ("Burza nad Wisłą w Płocku.", 0.9),
    ("Rzeka Wisła przybiera w Krakowie.", 0.9),
    ("Fala na Nysie Kłodzkiej dotarła do Opola.", 0.9),
    ("Alert RCB dla mieszkańców powiatów: kłodzkiego, nyskiego. Stan alarmowy na Nysie Kłodzkiej.", 0.95),
    ("Andrzej Kalisz przemawiał w Poznaniu.", 0.9),
    ("Jarosław Kaczyński przemawiał w Rzeszowie.", 0.9),
])
def test_bezsporne_wyciecie_nie_obniza_pewnosci(tekst, pewnosc):
    w = geokoduj(tekst)
    assert w.pewnosc == pewnosc, (tekst, w.pewnosc)
    assert not any("poza-wynikiem" in d.uwagi for d in w.dopasowania), tekst


def test_wyciete_miejsce_obecne_w_wyniku_z_innej_wzmianki_niczego_nie_zmienia():
    w = geokoduj("Kierowca z Lublina zginął w Lublinie.")
    assert kody(w) == {LUBLIN} and w.pewnosc == 0.9
    w = geokoduj("Hanna Kraków zaginęła w Krakowie.")
    assert kody(w) == {KRAKOW} and w.pewnosc == 0.9


def test_wycieciu_przy_pustym_wyniku_nic_nie_zostaje_w_dopasowaniach():
    # nie ma czego obniżać: wynik jest `brak`, a ślad blokady klubu nie trafia do dopasowań (jak dotąd)
    w = geokoduj("Wisła Kraków przegrała wczoraj.")
    assert w.teryt == () and w.pewnosc == 0.0
    assert not any(d.fraza.startswith("Wisł") for d in w.dopasowania)


def test_pewnosc_z_wycieciem_nie_przekracza_pewnosci_przed_wycieciem():
    # wycięte miejsce o niskiej pewności (Tarnów bez kontekstu: 0,65) obniża wynik także poniżej 0,75
    w = geokoduj("Kierowca z Tarnowa rozbił samochód w Warszawie.")
    assert w.pewnosc <= 0.65


# Niezmiennik na zdaniach z wielu recenzji: wynik z wyciętym miejscem, którego nie ma w `teryt`, nie ma pewności > 0,75.
ZDANIA_NIEZMIENNIK = [t for t, *_ in SPORNE] + [
    "Hanna Kraków zaginęła w Warszawie. Mieszkańcy z Krakowa i Warszawy bez prądu, awarie także w Lublinie.",
    "Kierowca z Lublina jechał dziś rano do Warszawy i miał wypadek w Płocku.",
    "Kierowcy z Olsztyna i Elbląga utknęli w Nowym Sączu.",
    "Kierowca z Krakowa zmarł po wypadku w Warszawie.",
    "Turyści z Zakopanego i Krakowa utknęli w Bukowinie Tatrzańskiej.",
    "Sąd Rejonowy w Chełmie skazał mieszkańca Lublina.",
    "Powódź w Nysie i Opolu.",
    "Pożar w Kotlinie Kłodzkiej i w Gorzowie Wielkopolskim.",
    "Wisła Płock wygrała mecz w Lublinie.",
    "Zaginięcie Wita Kalisza zgłoszono w Warszawie.",
    "Pożar w Lesznie (powiat pruszkowski). Alert dla powiatu leszczyńskiego.",
]


@pytest.mark.parametrize("tekst", ZDANIA_NIEZMIENNIK)
def test_niezmiennik_wyciete_miejsce_spoza_wyniku_obniza_pewnosc(tekst):
    w = geokoduj(tekst)
    for d in w.dopasowania:
        if "poza-wynikiem" in d.uwagi and d.teryt and d.teryt[0] not in w.teryt:
            assert 0 < w.pewnosc <= 0.75, (tekst, w.pewnosc, d)


def test_readme_opisuje_zabezpieczenie_i_wszystkie_heurystyki():
    readme = (Path(geokoder.__file__).parent / "README.md").read_text(encoding="utf-8")
    assert "PEWNOSC_PO_WYCIECIU_MAX" in readme and "0,75" in readme
    for powod in geokoder.HEURYSTYKI_WYCINAJACE:
        assert f"`{powod}`" in readme, powod


# --------------------------------------------------------------------------- wydajność

def test_dwadziescia_tysiecy_znakow_trwa_ponizej_pol_sekundy():
    wzor = ("Kierowca z Lublina jechał do Warszawy i miał wypadek w Płocku. Hanna Kraków zaginęła w Warszawie. "
            "Poziom Wisły w Krakowie rośnie. Pożar w Lesznie (powiat leszczyński). Mieszkańcy z Krakowa i Warszawy bez prądu. ")
    tekst = (wzor * (geokoder.MAKS_DLUGOSC // len(wzor) + 1))[:geokoder.MAKS_DLUGOSC]
    geokoduj("rozgrzewka")
    czasy = []
    for _ in range(3):
        start = time.perf_counter()
        geokoduj(tekst)
        czasy.append(time.perf_counter() - start)
    assert min(czasy) < 0.5, czasy
