"""Testy poprawek po trzeciej recenzji geokodera (zlecenie Z3P5, PR #39): zdania recenzenta i decyzje prowadzącego.

Zasada nadrzędna: lepiej `brak` albo województwo niż zgadnięta gmina lub powiat; zasięg alertu nigdy nie jest węższy
niż w źródle (kod po „dla” i kod w nagłówku alertu nie znikają, chyba że to czysta hierarchia jednego miejsca).
"""

import unicodedata

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoduj  # noqa: E402
from teraz.geo.geokoder import BRAK  # noqa: E402


def kody(wynik):
    return set(wynik.teryt)


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


# --------------------------------------------------------------------------- P1-1: nagłówek alertu

@pytest.mark.parametrize("tekst, wymagane, nieobecne", [
    ("Alert RCB woj. małopolskie: w powiecie tatrzańskim lawiny.", {"12", "1217"}, set()),
    ("Alert RCB, woj. mazowieckie: w mieście Warszawa silny wiatr.", {"14", "1465011"}, set()),
    ("Woj. lubelskie: w powiecie chełmskim burze.", {"06", "0603"}, set()),
    ("Alert RCB: powiat tatrzański, w gminie Zakopane lawiny.", {"1217", "1217011"}, set()),
    # nagłówek po prefiksie bez dwukropka, z „w powiecie…” i „w gminie…”
    ("Ostrzeżenie woj. lubelskie, w powiecie chełmskim, w gminie Rejowiec: burze.", {"06", "0603153"}, set()),
    ("Komunikat powiat tatrzański, w gminie Zakopane: lawiny.", {"1217", "1217011"}, set()),
    # czysta hierarchia jednego miejsca (w na każdym poziomie, dopisek za nazwą) nadal się doprecyzowuje
    ("Alert RCB: w woj. lubelskim, w powiecie chełmskim, w gminie Rejowiec burze.", {"0603153"}, {"06", "0603"}),
    ("Alert RCB: pożar w Chełmie, woj. lubelskie.", {"0662011"}, {"06"}),
    ("Alert RCB: Zakopane (powiat tatrzański), lawiny.", {"1217011"}, {"1217"}),
])
def test_naglowek_alertu_nie_traci_szerszego_kodu(tekst, wymagane, nieobecne):
    w = geokoduj(tekst)
    assert wymagane <= kody(w), (tekst, w.teryt)
    assert not (nieobecne & kody(w)), (tekst, w.teryt)


# --------------------------------------------------------------------------- P1-2: sprzeczny kontekst powiatu

@pytest.mark.parametrize("tekst, powiat, fraza", [
    ("Pożar w Lesznie, powiat pruszkowski.", "1421", "Lesznie"),
    ("Wypadek w Grodzisku, powiat pruszkowski.", "1421", "Grodzisku"),
    ("Pożar w Dąbrowie (pow. tarnowski).", "1216", "Dąbrowie"),
    ("Pożar w Chełmie, powiat bocheński.", "1201", "Chełmie"),
    ("Wypadek w Ostrowie, powiat ostrołęcki.", "1415", "Ostrowie"),
    ("Wypadek w Bielsku, powiat hajnowski.", "2005", "Bielsku"),
])
def test_powiat_wykluczajacy_kandydatow_daje_sam_powiat(tekst, powiat, fraza):
    w = geokoduj(tekst)
    assert kody(w) == {powiat}, (tekst, w.teryt)
    # czwarta recenzja, P2-1: sprzeczny kontekst zostawia powiat (zasięg), ale pewność spada poniżej progu 0,8
    assert w.dokladnosc == "powiat" and 0 < w.pewnosc < 0.8
    assert dopasowanie(w, fraza).teryt == ()  # gmina zostaje tylko jako ślad


def test_powiat_pasujacy_do_kandydata_nadal_rozstrzyga_homonim():
    assert kody(geokoduj("Pożar w Dąbrowie (pow. dąbrowski).")) >= {"1204023"}  # Dąbrowa Tarnowska w powiecie dąbrowskim
    assert kody(geokoduj("Leszno (pow. warszawski zachodni): pożar.")) >= {"1432"}


def test_powiat_nie_przenosi_na_wojewodztwo_ani_na_miasto_spoza_powiatu():
    # miasto o nazwie powiatu jest z nim zgodne (czwarta recenzja, P2-1): Leszno i powiat leszczyński
    w = geokoduj("UWAGA! POŻAR W LESZNIE. MIESZKAŃCY POWIATU LESZCZYŃSKIEGO PROSZENI O ZAMKNIĘCIE OKIEN.")
    assert kody(w) == {"3013", "3063011"}
    w = geokoduj("Pożar w Lesznie, powiat pruszkowski, woj. wielkopolskie.")
    assert "3063011" not in kody(w) and "1421" in kody(w)


# --------------------------------------------------------------------------- P1-3: „Główna” to nie Głowno

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Komenda Główna Policji: w Warszawie zatrzymano 3 osoby.", {"1465011"}),
    ("Komendant Główny Policji odwiedził Radom.", {"1463011"}),
    ("Rada Główna Szkolnictwa Wyższego obradowała w Lublinie.", {"0663011"}),
])
def test_glowny_nie_daje_glowna(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert not any("Głown" in d.fraza and "Główn" not in d.fraza for d in w.dopasowania)
    assert not any(d.fraza.startswith("Główn") and d.teryt for d in w.dopasowania)


@pytest.mark.parametrize("forma", ["Główna", "Główny", "Główne", "Główną", "Głównej", "Głównych", "Głównego", "Głównym", "GŁÓWNA", "GŁÓWNY"])
def test_formy_przymiotnikowe_glownego_nie_daja_gminy(forma):
    assert geokoduj(f"Rada {forma} zebrała się dzisiaj.").teryt == ()
    assert geokoduj(f"Spotkanie {forma} Policji w Lublinie.").teryt == ("0663011",)


@pytest.mark.parametrize("tekst", ["Pożar w Głownie.", "Mieszkańcy Głowna proszeni o ostrożność.", "Wypadek pod Głownem."])
def test_glowno_w_prawdziwych_formach_nadal_dziala(tekst):
    assert geokoduj(tekst).teryt == ("1020011",), tekst  # miasto Głowno (woj. łódzkie)


# --------------------------------------------------------------------------- P2-1: „dla woj. X - powiaty: A, B”

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Ostrzeżenie dla woj. lubelskiego - powiaty: chełmski, włodawski.", {"06", "0603", "0619"}),
    ("Alert RCB dla województwa podkarpackiego - powiaty: bieszczadzki, leski.", {"18", "1801", "1821"}),
    ("Ostrzeżenie dla województwa lubelskiego: powiaty chełmski i włodawski.", {"06", "0603", "0619"}),
])
def test_kod_po_dla_zostaje_obok_listy_powiatow(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_lista_powiatow_pod_wojewodztwem_bez_dla_nadal_daje_same_powiaty():
    w = geokoduj("Alert RCB został wysłany na terenie części województwa:\n- lubelskiego - powiaty: włodawski, chełmski")
    assert kody(w) == {"0603", "0619"}


# --------------------------------------------------------------------------- P2-2: klub bez miasta

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kibice Wisły zatrzymani w Płocku.", {"1462011"}),
    ("Kibice Legii zatrzymani w Płocku.", {"1462011"}),
    ("Po meczu Wisły policja zatrzymała pseudokibiców w Płocku.", {"1462011"}),
    ("Piłkarze Śląska wrócili do Wrocławia.", {"0264011"}),
    ("Trener Lecha zwiedził Gdańsk.", {"2261011"}),
    ("Derby Odry. Zatrzymano kibiców w Brzegu.", {"1601011"}),
])
def test_klub_bez_miasta_przy_slowie_sportowym_blokuje_sam_siebie(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)


@pytest.mark.parametrize("tekst", ["Pożar w Wiśle.", "Burze w Wiśle i Ustroniu.", "Wypadek w Wiśle. Kibice Legii wrócili do domu."])
def test_klub_bez_kontekstu_sportowego_zostaje_gmina(tekst):
    assert "2403031" in kody(geokoduj(tekst)), tekst  # gmina Wisła istnieje


# --------------------------------------------------------------------------- P2-3: gminy w liczbie mnogiej

@pytest.mark.parametrize("tekst", ["Utonięcie w Zawadzie.", "Utonięcie w Kozie.", "Kolizja w Mrozie.", "Wypadek w Marce.", "Pożar w Brodzie."])
def test_miejscownik_liczby_pojedynczej_nie_daje_gminy_o_nazwie_w_liczbie_mnogiej(tekst):
    assert geokoduj(tekst).teryt == (), tekst


def test_burza_w_zawadzie_nie_dokleja_zawad_z_podlaskiego():
    w = geokoduj("Burza w Zawadzie, gmina Tarnów.")
    assert not any(k.startswith("20") for k in w.teryt), w.teryt


@pytest.mark.parametrize("tekst, kod", [
    ("Pożar w Zawadach.", "2002152"), ("Wypadek w gminie Zawady.", "2002152"), ("Pożar w Markach.", "1434021"),
    ("Kolizja w Mrozach.", "1412123"), ("Wypadek w Kozach.", "2402072"),
])
def test_formy_liczby_mnogiej_nadal_daja_gmine(tekst, kod):
    assert geokoduj(tekst).teryt == (kod,), tekst


def test_dopelniacz_liczby_mnogiej_z_zmiana_o_na_o_kreskowane_nadal_dziala():
    # reguła „ó” z P1-3 dotyczy tylko nazw rzeczownikowych na „-o”, nie „z Kóz” (Kozy)
    assert geokoduj("Strażacy z Kóz gasili pożar.").teryt == ("2402072",)


def test_nazwa_wieloznaczna_w_liczbie_mnogiej_jest_rozpoznana_ale_bez_kontekstu_to_brak():
    d = geokoduj("Zatrzymanie w Brodach.").dopasowania[0]  # Brody w dwóch województwach
    assert d.fraza == "Brodach" and len(d.kandydaci) > 1 and d.teryt == ()


# --------------------------------------------------------------------------- P2-4: imiona i nazwiska

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Prezydent Andrzej Kalisz spotkał się z wojewodą.", set()),
    ("Jarosław Kaczyński i Tomasz Opole odwiedzili Kraków.", {"1261011"}),
    ("Maciej Brzeg, rzecznik KPP.", set()),
    ("Rozmawiała z Marią Opole i Pawłem Kielce.", set()),
    ("Anna Kalisz powiedziała dziennikarzom, że w Opolu było spokojnie.", {"1661011"}),
    ("Z Pawłem Kielce nie rozmawiano.", set()),
])
def test_imie_przed_nazwa_gminy_bez_przyimka_to_nazwisko(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kalisz: pożar hali.", {"3061011"}),
    ("Policjanci zatrzymali Andrzeja w Kaliszu.", {"3061011"}),
    ("Pożar. Opole zgłasza zagrożenie.", {"1661011"}),
    ("Maria zamieszkała w Kaliszu.", {"3061011"}),
])
def test_nazwy_miejsc_obok_imion_nadal_dzialaja(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


# --------------------------------------------------------------------------- P2-5: NFC

def test_tekst_w_postaci_rozlozonej_daje_ten_sam_wynik_co_zlozony():
    zlozony = "Pożar w Krakowie i Łodzi, woj. łódzkie."
    rozlozony = unicodedata.normalize("NFD", zlozony)
    assert rozlozony != zlozony
    assert geokoduj(rozlozony).teryt == geokoduj(zlozony).teryt
    assert {"1261011", "1061011"} <= kody(geokoduj(rozlozony))


def test_pozycje_przy_nfd_wskazuja_oryginal_razem_z_akcentem_na_koncu():
    rozlozony = unicodedata.normalize("NFD", "Pożar w Gdańsku i we Wrocławiu, Łódź.")
    w = geokoduj(rozlozony)
    assert kody(w) == {"2261011", "0264011", "1061011"}
    for d in w.dopasowania:
        assert rozlozony[d.start:d.koniec] == d.fraza
    assert dopasowanie(w, unicodedata.normalize("NFD", "Gdańsku")).koniec - dopasowanie(w, unicodedata.normalize("NFD", "Gdańsku")).start == 8


def test_nfd_z_znakami_niewidocznymi_i_krajem():
    tekst = unicodedata.normalize("NFD", "Obowiązuje w całym kraju. Pożar w Łodzi​ i w Gdańsku.")
    w = geokoduj(tekst)
    assert kody(w) == {"1061011", "2261011"} and w.dokladnosc == "kraj"
    for d in w.dopasowania:
        assert tekst[d.start:d.koniec] == d.fraza


# --------------------------------------------------------------------------- P2-6: miejsce pochodzenia

def test_sad_w_chelmie_skazal_mieszkanca_lublina():
    w = geokoduj("Sąd Rejonowy w Chełmie skazał mieszkańca Lublina.")
    assert kody(w) == {"0662011"}
    assert "jednostka" in dopasowanie(w, "Chełmie").uwagi
    lublina = dopasowanie(w, "Lublina")
    assert lublina.teryt == ("0663011",) and {"pochodzenie", "poza-wynikiem"} <= set(lublina.uwagi)


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Kierowca z Lublina rozbił samochód w Chełmie.", {"0662011"}),
    # „mieszkańcy” w mianowniku liczby mnogiej to dotknięci zdarzeniem, nie pochodzenie (czwarta recenzja, P1-A)
    ("Mieszkańcy Lublina ucierpieli w wypadku w Chełmie.", {"0662011", "0663011"}),
    ("Mieszkańca Lublina potrącono w Chełmie.", {"0662011"}),
    ("Mieszkanka Lublina zginęła w pożarze w Chełmie.", {"0662011"}),
    ("Pochodzący z Lublina mężczyzna został zatrzymany w Chełmie.", {"0662011"}),
    ("Policjanci z Koła zatrzymali mężczyznę w Chełmie.", {"0662011"}),
    # jedyne miejsce, także pochodzenia, zostaje
    ("Mieszkaniec Lublina zginął w pożarze.", {"0663011"}),
    ("Kierowca z Lublina zasłabł.", {"0663011"}),
    # adresat alertu i trasa „z A do B” to nie pochodzenie
    ("Komunikat dla mieszkańców Lublina. Pożar w Chełmie.", {"0663011", "0662011"}),
    ("Pociąg z Lublina do Chełma opóźniony.", {"0663011", "0662011"}),
    # „z Tuchowem” (narzędnik) to nie pochodzenie
    ("Burmistrz rozmawiał z Tuchowem w Krakowie.", {"1261011", "1216103"}),
])
def test_miejsce_pochodzenia_nie_trafia_do_teryt_gdy_jest_miejsce_zdarzenia(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_jednostka_pominieta_w_wyniku_ma_uwage_w_dopasowaniu():
    w = geokoduj("Policjanci z KMP w Płocku zatrzymali w gminie Słupno.")
    assert kody(w) == {"1419122"}
    assert {"jednostka", "poza-wynikiem"} <= set(dopasowanie(w, "Płocku").uwagi)
    assert "poza-wynikiem" not in dopasowanie(w, "Słupno").uwagi


# --------------------------------------------------------------------------- P3

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Pożar w Ostrowie Wlkp.", {"3017011"}),
    ("Pożar w Mińsku Maz.", {"1412011"}),
    ("Wypadek w Gorzowie Wlkp. i w Bielsku Podl.", {"0861011", "2003011"}),
    ("Alert dla woj. małop. i woj. mazow.", {"12", "14"}),
    ("Ostrzeżenie dla woj. wlkp.", {"30"}),
    ("Alert RCB: woj. lub. burze.", set()),  # „lub.” jest wieloznaczne (lubelskie, lubuskie)
])
def test_skroty_z_kropka(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) >= oczekiwane, tekst
    if not oczekiwane:
        assert geokoduj(tekst).teryt == ()


def test_lista_powiatow_rozdzielona_srednikiem_daje_kody_powiatow():
    w = geokoduj("Alert RCB: powiaty: tatrzański; nowotarski; limanowski.")
    assert kody(w) == {"1217", "1211", "1207"} and w.dokladnosc == "powiat"
    w = geokoduj("Alert RCB: woj. małopolskie - powiaty: tatrzański; nowotarski.")
    assert kody(w) == {"1217", "1211"}  # bez „dla” województwo jest nagłówkiem listy


@pytest.mark.parametrize("wejscie", [5, 3.5, b"Pozar w Lublinie", ["Lublin"], {"a": 1}, object()])
def test_zly_typ_wejscia_daje_brak_z_uwaga(wejscie):
    w = geokoduj(wejscie)
    assert w.dokladnosc == BRAK and w.teryt == () and w.pewnosc == 0.0
    assert w.uwagi == ("zly-typ-wejscia",)


@pytest.mark.parametrize("wejscie", [None, "", "   ", "\n\t"])
def test_puste_wejscie_daje_brak_bez_uwagi(wejscie):
    w = geokoduj(wejscie)
    assert w.dokladnosc == BRAK and w.uwagi == ()
