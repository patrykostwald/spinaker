"""Testy poprawek po zamykającej recenzji geokodera (zlecenie Z3P8, PR #39): sześć blokerów recenzji R39b.

Każde zdanie z recenzji jest testem, razem z wariantami po stronie bezpiecznej (to, co ma zostać bez zmian).
Zasada ogólna bez zmian: wycięcie miejsca to pewność najwyżej 0,75 i nigdy nie podnosi pewności.
"""

import time

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoder, geokoduj  # noqa: E402

WARSZAWA, KRAKOW, LUBLIN, PLOCK, KIELCE = "1465011", "1261011", "0663011", "1462011", "2661011"
USTRON, WISLA = "2403021", "2403031"
LESZNO_MIASTO, LESZNO_MAZOWSZE, POW_LESZCZYNSKI, POW_PRUSZKOWSKI = "3063011", "1432042", "3013", "1421"
OPOLE_MIASTO, POW_OPOLSKI_OPOLSKIE, POW_OPOLSKI_LUBELSKIE, PONIATOWA = "1661011", "1609", "0612", "0612063"
POW_TATRZANSKI, ZAKOPANE = "1217", "1217011"


def kody(wynik):
    return set(wynik.teryt)


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


# --------------------------------------------------------------------------- 1. powiat z sąsiedniego miasta

def test_powiat_nie_jest_dopisany_na_podstawie_sasiedniego_miasta():
    w = geokoduj("Alerty: miasto Opole, powiat opolski (gmina Poniatowa).")
    assert kody(w) == {OPOLE_MIASTO, PONIATOWA}, w.teryt
    assert w.pewnosc < 0.8
    powiat = dopasowanie(w, "opolski")
    assert powiat.teryt == () and "sprzeczne-gminy" in powiat.uwagi


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Alerty: powiat opolski (gmina Poniatowa).", {POW_OPOLSKI_LUBELSKIE, PONIATOWA}),
    ("Alerty: powiat opolski, w gminie Poniatowa.", {POW_OPOLSKI_LUBELSKIE, PONIATOWA}),
    ("Alerty: miasto Opole, powiat opolski.", {OPOLE_MIASTO, POW_OPOLSKI_OPOLSKIE}),
])
def test_powiat_wieloznaczny_zgodny_z_gmina_obok_zostaje_rozstrzygniety(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane and w.pewnosc >= 0.9, (tekst, w.teryt, w.pewnosc)


def test_gmina_po_kropce_nie_rozstrzyga_powiatu():
    # „Poniatowa” stoi w następnym zdaniu: to osobna wzmianka, a powiat jest dopiskiem do Opola (1609)
    w = geokoduj("Alerty: Opole (powiat opolski). Gmina Poniatowa: bez prądu.")
    assert kody(w) == {OPOLE_MIASTO, POW_OPOLSKI_OPOLSKIE, PONIATOWA}, w.teryt
    assert w.pewnosc >= 0.9


# --------------------------------------------------------------------------- 2. „przez” jako przyczyna

@pytest.mark.parametrize("tekst", [
    "Kierowca z Krakowa miał wypadek w Warszawie przez śliską nawierzchnię.",
    "Kierowca z Krakowa miał wypadek w Warszawie przez mgłę.",
    "Kierowca z Krakowa miał wypadek w Warszawie przez awarię.",
    "Kierowca z Krakowa miał wypadek w Warszawie do wieczora.",
])
def test_przez_przed_rzeczownikiem_pospolitym_to_przyczyna_nie_trasa(tekst):
    w = geokoduj(tekst)
    assert kody(w) == {WARSZAWA}, (tekst, w.teryt)
    assert w.pewnosc <= 0.75
    assert "pochodzenie" in dopasowanie(w, "Krakowa").uwagi


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kierowca z Krakowa jechał do Warszawy.", {KRAKOW, WARSZAWA}),
    ("Kierowca z Krakowa jechał przez Kielce do Warszawy i miał wypadek.", {KRAKOW, KIELCE, WARSZAWA}),
    ("Kierowca z Krakowa kierował się przez Kielce i miał wypadek w Warszawie.", {KRAKOW, KIELCE, WARSZAWA}),
    ("Kierowca z Lublina do Janowa zginął w Chełmie.", {LUBLIN, "0662011"}),
])
def test_trasa_po_slowie_ruchu_lub_przy_nazwie_zostaje(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert w.pewnosc >= 0.65


# --------------------------------------------------------------------------- 3. dopisek województwa wygrywa

def test_dopisek_wojewodztwa_wygrywa_z_osobnym_zdaniem_alertu():
    w = geokoduj("Awaria w Lesznie (woj. mazowieckie). Alert dla powiatu leszczyńskiego.")
    assert kody(w) == {LESZNO_MAZOWSZE, POW_LESZCZYNSKI}, w.teryt
    assert w.pewnosc < 0.8  # konflikt dopisku z powiatem alertu: do przeglądu
    assert "konflikt-kontekstu" in dopasowanie(w, "Lesznie").uwagi


@pytest.mark.parametrize("tekst, oczekiwane, minimum", [
    ("Awaria w Lesznie (woj. mazowieckie).", {LESZNO_MAZOWSZE}, 0.9),
    ("Awaria w Lesznie, woj. wielkopolskie. Alert dla powiatu leszczyńskiego.", {LESZNO_MIASTO, POW_LESZCZYNSKI}, 0.9),
    # powiat alertu niezwiązany z żadnym kandydatem nie jest konfliktem: Leszno rozstrzyga dopisek
    ("Awaria w Lesznie (woj. mazowieckie). Alert dla powiatu pruszkowskiego.", {LESZNO_MAZOWSZE, POW_PRUSZKOWSKI}, 0.9),
])
def test_dopisek_wojewodztwa_bez_konfliktu(tekst, oczekiwane, minimum):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane and w.pewnosc >= minimum, (tekst, w.teryt, w.pewnosc)


# --------------------------------------------------------------------------- 4. zasięg jawny się nie zawęża

def test_wymienione_wprost_powiat_i_gmina_zostaja_oba():
    w = geokoduj("Alert obowiązuje w powiecie tatrzańskim, zwłaszcza w gminie Zakopane.")
    assert kody(w) == {POW_TATRZANSKI, ZAKOPANE}, w.teryt


@pytest.mark.parametrize("tekst", [
    "Alert dla powiatu tatrzańskiego i gminy Zakopane.",
    "Alert obowiązuje w powiecie tatrzańskim, a także w gminie Zakopane.",
])
def test_wyliczenie_zasiegu_zachowuje_powiat(tekst):
    assert kody(geokoduj(tekst)) == {POW_TATRZANSKI, ZAKOPANE}, tekst


@pytest.mark.parametrize("tekst", [
    "Alert w powiecie tatrzańskim, w gminie Zakopane.",
    "Alert w woj. małopolskim, w powiecie tatrzańskim, w gminie Zakopane.",
])
def test_czysta_hierarchia_nadal_zwija_sie_do_gminy(tekst):
    assert kody(geokoduj(tekst)) == {ZAKOPANE}, tekst


def test_nierozstrzygniety_powiat_nie_zostawia_samej_warszawy_z_wysoka_pewnoscia():
    w = geokoduj("Ostrzeżenie dla Warszawy i powiatu opolskiego.")
    assert w.pewnosc < 0.8, (w.teryt, w.pewnosc)
    assert "niejednoznaczne" in dopasowanie(w, "opolskiego").uwagi
    assert {WARSZAWA} <= kody(w)


# --------------------------------------------------------------------------- 5. klub

def test_samo_slowo_mecz_nie_czyni_wisly_klubem():
    w = geokoduj("W Wiśle i w Ustroniu odwołano mecze.")
    assert kody(w) == {WISLA, USTRON}, w.teryt


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Odwołano mecze w Wiśle i w Ustroniu.", {WISLA, USTRON}),
    ("Drużyna spędziła obóz w Wiśle.", {WISLA}),  # miejscownik po „w”: miejsce, nawet ze słowem klubowym
    ("Kibice Wisły zatrzymani w Płocku.", {PLOCK}),
    ("Piłkarze Wisły grali w Ustroniu.", {USTRON}),
    ("Wisła Kraków przegrała mecz w Płocku.", {PLOCK}),
])
def test_kontekst_klubowy_wymaga_dopelniacza_lub_miasta_klubu(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_sam_mecz_z_nazwa_w_dopelniaczu_to_wyciecie_z_obnizka():
    w = geokoduj("Mecz Wisły w Płocku odwołany.")
    assert kody(w) == {PLOCK} and w.pewnosc <= 0.75, (w.teryt, w.pewnosc)
    assert "klub" in dopasowanie(w, "Wisły").uwagi


# --------------------------------------------------------------------------- 6. nazwisko przy zdarzeniu na poziomie powiatu

def test_nazwisko_przy_powiecie_nie_trafia_do_zasiegu():
    w = geokoduj("Hanna Kraków zaginęła w powiecie pruszkowskim.")
    assert kody(w) == {POW_PRUSZKOWSKI}, w.teryt
    assert w.pewnosc <= 0.75
    assert "imie" in dopasowanie(w, "Kraków").uwagi


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Hanna Kraków zaginęła w woj. mazowieckim.", {"14"}),
    ("Hanna Kraków zaginęła w Warszawie.", {WARSZAWA}),
    ("Hanna Kraków zaginęła koło Pruszkowa, powiat pruszkowski.", {"1421021"}),
])
def test_nazwisko_przy_zdarzeniu_wyzszego_poziomu(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane and w.pewnosc <= 0.75, (tekst, w.teryt, w.pewnosc)


def test_imie_z_nazwa_bez_miejsca_zdarzenia_zostaje_miejscem():
    w = geokoduj("Hanna Kraków zaginęła.")
    assert kody(w) == {KRAKOW} and w.pewnosc >= 0.9


# --------------------------------------------------------------------------- wydajność i zabezpieczenie

ZDANIA_RECENZJI = (
    "Alerty: miasto Opole, powiat opolski (gmina Poniatowa). "
    "Kierowca z Krakowa miał wypadek w Warszawie przez śliską nawierzchnię. "
    "Awaria w Lesznie (woj. mazowieckie). Alert dla powiatu leszczyńskiego. "
    "Alert obowiązuje w powiecie tatrzańskim, zwłaszcza w gminie Zakopane. "
    "Ostrzeżenie dla Warszawy i powiatu opolskiego. "
    "W Wiśle i w Ustroniu odwołano mecze. "
    "Hanna Kraków zaginęła w powiecie pruszkowskim. "
)


def test_czas_na_20_tys_znakow_ponizej_pol_sekundy():
    tekst = (ZDANIA_RECENZJI * (geokoder.MAKS_DLUGOSC // len(ZDANIA_RECENZJI) + 1))[:geokoder.MAKS_DLUGOSC]
    najlepszy = min(_czas(tekst) for _ in range(3))
    assert najlepszy < 0.5, najlepszy


def _czas(tekst):
    start = time.perf_counter()
    geokoduj(tekst)
    return time.perf_counter() - start


def test_wycieta_nazwa_nie_podnosi_pewnosci_i_nie_daje_wyjatku_w_wariantach():
    for tekst in ZDANIA_RECENZJI.split(". "):
        for wariant in (tekst, tekst.upper(), tekst.lower(), tekst + " " + tekst):
            w = geokoduj(wariant)
            assert 0.0 <= w.pewnosc <= 1.0
