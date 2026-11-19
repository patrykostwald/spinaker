"""Testy poprawek po drugim przeglądzie geokodera (zlecenie Z3-poprawki-2) i próby recenzenta (druga runda).

Oczekiwane wyniki wg decyzji prowadzącego: kod szerszy po „dla” albo w nagłówku alertu nigdy nie znika,
nazwa klubu blokuje także miasto po niej, lepiej `brak` albo województwo niż zgadnięta gmina lub powiat.
"""

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoduj  # noqa: E402
from teraz.geo.geokoder import BRAK, KRAJ  # noqa: E402


def kody(wynik):
    return set(wynik.teryt)


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


@pytest.mark.parametrize("tekst, wymagane, nieobecne", [
    # kod szerszy po „dla” albo w nagłówku alertu nigdy nie znika
    ("Ostrzeżenie dla województwa lubelskiego: miasto Chełm i gmina Rejowiec szczególnie zagrożone.",
     {"06", "0662011", "0603153"}, set()),
    ("Alert RCB: woj. mazowieckie, miasto Warszawa, silny wiatr.", {"14", "1465011"}, set()),
    ("Alert RCB dla powiatu tatrzańskiego, miasto Zakopane: lawiny.", {"1217", "1217011"}, set()),
    ("Ostrzeżenie dla woj. lubelskiego, gmina Rejowiec i powiat zamojski.", {"06", "0603153", "0620"}, set()),
    ("Ostrzeżenie dla woj. lubelskiego, w tym w Chełmie.", {"06", "0662011"}, set()),
    ("Wypadek w Zakopanem; ostrzeżenie dla powiatu tatrzańskiego.", {"1217", "1217011"}, set()),
    # czysta hierarchia jednego miejsca: szerszy kod znika
    ("Pożar w Chełmie, woj. lubelskie.", {"0662011"}, {"06"}),
    ("Zakopane (powiat tatrzański): lawina.", {"1217011"}, {"1217"}),
    ("W woj. lubelskim, w powiecie chełmskim, w gminie Rejowiec.", {"0603153"}, {"06", "0603"}),
    ("Leszno, woj. wielkopolskie: pożar.", {"3063011"}, {"30"}),
])
def test_zasieg_alertu_nie_znika_a_czysta_hierarchia_sie_doprecyzowuje(tekst, wymagane, nieobecne):
    w = geokoduj(tekst)
    assert wymagane <= kody(w), (tekst, w.teryt)
    assert not (nieobecne & kody(w)), (tekst, w.teryt)


def test_zasieg_alertu_dokladnosc_opisuje_zasieg_a_gminy_zostaja_w_dopasowaniach():
    w = geokoduj("Ostrzeżenie dla województwa lubelskiego: miasto Chełm i gmina Rejowiec szczególnie zagrożone.")
    assert w.dokladnosc == "wojewodztwo"
    assert {d.fraza for d in w.dopasowania} >= {"lubelskiego", "Chełm", "Rejowiec"}


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kibice Wisły Kraków zatrzymani w Płocku.", {"1462011"}),
    ("Kibice Legii Warszawa zatrzymani w Płocku.", {"1462011"}),
    ("Kibice Lecha Poznań i Śląska Wrocław starli się w Łodzi.", {"1061011"}),
    ("Mecz Odra Opole z Rakowem Częstochowa.", set()),
    ("Wisła Kraków Wisła Kraków ", set()),
    ("Pożar w Wiśle Kraków.", set()),
    ("Raków Częstochowa wygrał.", set()),
])
def test_kluby_przyklady_z_przegladu(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane
    assert (w.dokladnosc == BRAK) == (not oczekiwane)


@pytest.mark.parametrize("tekst", [
    "Strażacy z całej Polski wysłali pomoc do Kłodzka.",
    "Najwięcej wypadków w całym kraju dotyczy pieszych.",
    "Najwięcej wypadków w całym kraju dotyczy pieszych. Wypadek w Łodzi.",
    "Mieszkańcy całej Polski dotychczas wpłacili 2 mln zł na Wisłę.",
    "Policjanci w całym kraju wprowadzili wzmożone kontrole.",
    "Pomoc dotarła z całego kraju.",
    "Najwięcej zgłoszeń z całego kraju napłynęło z Poznania.",
])
def test_kraj_nie_wynika_z_z_calej_polski_ani_ze_statystyki(tekst):
    w = geokoduj(tekst)
    assert w.dokladnosc != KRAJ, tekst
    assert not any(d.rodzaj == KRAJ for d in w.dopasowania), tekst


def test_kraj_zostaje_przy_slowach_o_zasiegu_i_nie_kasuje_miast():
    assert geokoduj("Alert RCB: Uwaga! Silny wiatr. Ostrzeżenie obowiązuje w całym kraju do godz. 18.").dokladnosc == KRAJ
    w = geokoduj("Akcja prowadzona na terenie całego kraju, w tym w Gdańsku.")
    assert w.dokladnosc == KRAJ and kody(w) == {"2261011"}


@pytest.mark.parametrize("tekst", [
    "Pożar w Kotlinie Kłodzkiej.", "Turyści zaginęli w Górach Stołowych.", "Pożar w Puszczy Białowieskiej.",
    "Pożar w Puszczy Niepołomickiej.", "Wypadek w Borach Tucholskich.", "Ratownicy w Dolinie Kościeliskiej.",
    "Ćwiczenia w Lesie Kabackim.",
])
def test_krainy_nie_daja_gmin(tekst):
    w = geokoduj(tekst)
    assert w.dokladnosc == BRAK and w.teryt == (), (tekst, w.teryt)


def test_krainy_obok_prawdziwego_miejsca_zostawiaja_tylko_miejsce():
    assert kody(geokoduj("Wypadek w Wadowicach. Pożar w Puszczy Niepołomickiej.")) == {"1218093"}
    assert kody(geokoduj("Wypadek w Zakopanem, w Tatrach i w Bieszczadach.")) == {"1217011"}


def test_polska_nie_jest_gmina_i_nie_obniza_pewnosci_pozostalych_miejsc():
    bazowa = geokoduj("Wypadek w Krakowie.")
    w = geokoduj("Wypadek w Krakowie. W Polsce obowiązują ostrzeżenia.")
    assert kody(w) == kody(bazowa) == {"1261011"}
    assert w.pewnosc == bazowa.pewnosc
    assert geokoduj("Alert dla Polski: silny wiatr.").teryt == ()


@pytest.mark.parametrize("tekst, oczekiwane, w_dopasowaniach", [
    ("Policjanci z KMP w Płocku zatrzymali w gminie Słupno.", {"1419122"}, "Płocku"),
    ("Policjanci z KMP w Płocku zatrzymali sprawcę kradzieży w Gostyninie.", {"1404011"}, "Płocku"),
    ("Prokuratura Okręgowa w Lublinie wszczęła śledztwo w sprawie zdarzenia w Chełmie.", {"0662011"}, "Lublinie"),
    ("KM PSP w Nowym Sączu: pożar budynku w Starym Sączu.", {"1210163"}, "Nowym Sączu"),
    ("Policjanci z Wydziału Kryminalnego KWP w Katowicach zatrzymali członków grupy w Sosnowcu.", {"2475011"}, "Katowicach"),
])
def test_miejsce_jednostki_obok_miejsca_zdarzenia_nie_trafia_do_teryt(tekst, oczekiwane, w_dopasowaniach):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane
    assert "jednostka" in dopasowanie(w, w_dopasowaniach).uwagi


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Policjanci z KMP w Płocku zatrzymali sprawcę.", {"1462011"}),
    ("KM PSP w Nowym Sączu: pożar.", {"1262011"}),
    ("Prokuratura Okręgowa w Lublinie wszczęła śledztwo.", {"0663011"}),
])
def test_jedyne_miejsce_jednostki_zachowuje_sie_jak_dotad(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane and w.pewnosc <= 0.8


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Alert RCB dla powiatów: bieszczadzkiego (woj. podkarpackie), tatrzańskiego (woj. małopolskie).", {"1801", "1217"}),
    ("Alert RCB dla powiatów: limanowskiego (woj. małopolskie) oraz bieszczadzkiego (woj. podkarpackie).", {"1207", "1801"}),
    ("Alert RCB dla powiatów: nowosądeckiego, limanowskiego (woj. małopolskie) oraz bieszczadzkiego (woj. podkarpackie).",
     {"1210", "1207", "1801"}),
    ("Ostrzeżenie dla powiatów: kłodzkiego i wałbrzyskiego (dolnośląskie).", {"0208", "0221"}),
])
def test_lista_powiatow_z_wojewodztwem_w_nawiasie_sie_nie_urywa(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, w.teryt
    assert w.dokladnosc == "powiat"


@pytest.mark.parametrize("znak", ["­", "​", "‌", "‍", "﻿"])
def test_znaki_niewidoczne_nie_psuja_nazwy_i_pozycji(znak):
    tekst = f"Pożar w Łodzi{znak} i we Wroc{znak}ławiu."
    w = geokoduj(tekst)
    assert kody(w) == {"1061011", "0264011"}
    for d in w.dopasowania:
        assert tekst[d.start:d.koniec] == d.fraza
    assert geokoduj("Wroc­ławiu").teryt == ("0264011",)


def test_leszno_z_obcym_powiatem_zostawia_slad_a_kontekst_powiatu_rozstrzyga_homonim():
    w = geokoduj("Leszno (pow. warszawski zachodni): pożar.")
    assert any(d.fraza == "Leszno" for d in w.dopasowania)
    assert "1432" in kody(w)
    # miasto na prawach powiatu i powiat o jego nazwie są zgodne (czwarta recenzja, P2-1): miasto i powiat
    w = geokoduj("UWAGA! POŻAR W LESZNIE. MIESZKAŃCY POWIATU LESZCZYŃSKIEGO PROSZENI O ZAMKNIĘCIE OKIEN.")
    assert kody(w) == {"3013", "3063011"}
    assert dopasowanie(w, "LESZNIE").teryt == ("3063011",)


@pytest.mark.parametrize("tekst, oczekiwane, dokladnosc", [
    ("RCB: Ostrzeżenie dla województw: małopolskiego, śląskiego i podkarpackiego. Możliwe podtopienia w Krakowie.",
     {"12", "24", "18", "1261011"}, "wojewodztwo"),
    ("Alert RCB dla mieszkańców powiatu bielskiego (woj. śląskie). Nie zbliżaj się do rzek.", {"2402"}, "powiat"),
    ("Alert RCB dla mieszkańców powiatów: kłodzkiego, nyskiego. Stan alarmowy na Nysie Kłodzkiej.", {"0208", "1607"}, "powiat"),
    ("Komunikat RCB: na terenie całego kraju możliwe oblodzenia. Szczególnie w Lublinie.", {"0663011"}, KRAJ),
    ("Funkcjonariusze z Komisariatu Policji w Ząbkach zatrzymali 25-latka.", {"1434031"}, "gmina"),
    ("Wypadek w Bielsku-Białej.", {"2461011"}, "gmina"),
    ("W Grodzisku Mazowieckim (pow. grodziski, woj. mazowieckie) doszło do wypadku.", {"1405043"}, "gmina"),
    ("Do zdarzenia doszło w Grodzisku, powiat grodziski, woj. wielkopolskie.", {"3005023"}, "gmina"),
    ("Pożar hali w Lesznie (woj. wielkopolskie).", {"3063011"}, "gmina"),
    ("Pożar w Olsztynie. Na miejscu 5 zastępów KM PSP Olsztyn.", set(), BRAK),
    ("IMGW: ostrzeżenie hydrologiczne 2. stopnia dla zlewni Warty w województwie wielkopolskim.", {"30"}, "wojewodztwo"),
    ("IMGW: przekroczenie stanu alarmowego na Wiśle w Warszawie.", {"1465011"}, "gmina"),
    ("Powódź w Nysie. Ewakuacja mieszkańców.", set(), BRAK),
    ("Burze z gradem w Wiśle i Ustroniu.", {"2403031", "2403021"}, "gmina"),
    ("Stan wody na Odrze w Opolu i we Wrocławiu przekroczył stan ostrzegawczy.", {"1661011", "0264011"}, "gmina"),
    ("Tomaszów: zatrzymano złodzieja.", set(), BRAK),
    ("Pożar w miejscowości Wola, gmina Pszczyna.", {"2410053"}, "gmina"),
    ("Wypadek w Łodzi. Zasięg ostrzeżenia: powiat łódzki wschodni.", {"1006", "1061011"}, "powiat"),
    # kod po „dla” nigdy nie znika: województwo zostaje obok powiatów (trzecia recenzja, P2-1)
    ("Alert RCB dla województwa podkarpackiego - powiaty: bieszczadzki, leski.", {"18", "1801", "1821"}, "wojewodztwo"),
    ("Utrudnienia w powiatach limanowskim i nowosądeckim.", {"1207", "1210"}, "powiat"),
    ("Alert RCB dla powiatu chełmskiego. Utrudnienia w Rejowcu.", {"0603", "0603153"}, "powiat"),
])
def test_proby_recenzenta_druga_runda(tekst, oczekiwane, dokladnosc):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert w.dokladnosc == dokladnosc, (tekst, w.dokladnosc)
