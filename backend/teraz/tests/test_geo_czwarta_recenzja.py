"""Testy poprawek po czwartej recenzji geokodera (zlecenie Z3P6, PR #39): zdania recenzenta i decyzje prowadzącego.

Zasada nadrzędna: lepiej `brak` niż zgadnięta gmina; zasięg nigdy węższy niż w źródle; pominięte miejsce nie podnosi
pewności (wynik po wycięciu nie powyżej 0,8, chyba że nic nie wycięto).
"""

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoder, geokoduj, slownik as sl  # noqa: E402

LUBLIN, CHELM, SWIDNIK, NYSA, KLODZKO = "0663011", "0662011", "0617011", "1607053", "0208021"
ZAKOPANE, KRAKOW, BUKOWINA, OPOLE, WROCLAW, BRZEG = "1217011", "1261011", "1217032", "1661011", "0264011", "1601011"
LUBIN, POLKOWICE, GLOGOW, TARNOW, RZESZOW, KRASNIK = "0211011", "0216043", "0203011", "1263011", "1863011", "0607011"
JAROSLAW, PRZEMYSL, LUBARTOW, WARSZAWA, LESZNO = "1804011", "1862011", "0608011", "1465011", "3063011"


def kody(wynik):
    return set(wynik.teryt)


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


# --------------------------------------------------------------------------- P1-A: lista dziedziczy rolę pierwszego elementu

@pytest.mark.parametrize("tekst, oczekiwane", [
    # „mieszkańcy” w mianowniku liczby mnogiej to dotknięci zdarzeniem: żaden element listy nie jest pochodzeniem
    ("Mieszkańcy Lublina i Chełma bez prądu.", {LUBLIN, CHELM}),
    ("Mieszkańcy Lublina, Świdnika i Chełma bez prądu.", {LUBLIN, SWIDNIK, CHELM}),
    # „z” bez osoby w pobliżu to nie pochodzenie
    ("Ewakuowano 200 osób z Nysy i Kłodzka.", {NYSA, KLODZKO}),
    ("Wiatr z Opola i Wrocławia przewrócił drzewa w Brzegu.", {OPOLE, WROCLAW, BRZEG}),
    # osoba przy „z”: wszystkie elementy listy to pochodzenie, więc zostaje tylko miejsce zdarzenia
    ("Pogotowie z Lublina i Chełma w akcji w Świdniku.", {SWIDNIK}),
    ("Turyści z Zakopanego i Krakowa utknęli w Bukowinie Tatrzańskiej.", {BUKOWINA}),
    ("Kierowca z Lublina, Świdnika i Chełma zginął w Krakowie.", {KRAKOW}),
    ("Strażacy z Lublina oraz Chełma gasili pożar w Świdniku.", {SWIDNIK}),
    # nierozpoznana nazwa w środku listy nie przerywa dziedziczenia
    ("Turyści z Zakopanego, Poronina i Krakowa utknęli w Bukowinie Tatrzańskiej.", {BUKOWINA}),
    # lista pochodzenia jest też jedynym miejscem: zostaje
    ("Turyści z Zakopanego i Krakowa wrócili do domu.", {ZAKOPANE, KRAKOW}),
    ("Mieszkańca Lublina i Chełma uratowano.", {LUBLIN, CHELM}),
    # osobny przyimek przed drugą nazwą kończy listę: Kraków to miejsce zdarzenia
    ("Turyści z Zakopanego i w Krakowie utknęli.", {KRAKOW}),
])
def test_lista_dziedziczy_role_pierwszego_elementu(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_pominiete_pochodzenie_zostaje_w_dopasowaniach_z_uwagami():
    w = geokoduj("Turyści z Zakopanego i Krakowa utknęli w Bukowinie Tatrzańskiej.")
    for fraza in ("Zakopanego", "Krakowa"):
        assert {"poza-wynikiem", "pochodzenie"} <= set(dopasowanie(w, fraza).uwagi), fraza
    assert dopasowanie(w, "Zakopanego").teryt == (ZAKOPANE,)  # ślad zostaje z kodem


# --------------------------------------------------------------------------- P1-B: „od”, „z” bez osoby i trasa nie wycinają miejsc

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Trzęsienie ziemi 10 km od Lubina, odczuwalne w Polkowicach.", {LUBIN, POLKOWICE}),
    ("Wstrząs 5 km od Polkowic odczuwalny w Lubinie i Głogowie.", {POLKOWICE, LUBIN, GLOGOW}),
    ("Burze przesuwają się od Tarnowa po Rzeszów.", {TARNOW, RZESZOW}),
    ("Opady w Krakowie, z Tarnowa nadciąga burza.", {KRAKOW, TARNOW}),
    ("Z Kłodzka ewakuowano 300 osób, w Nysie trwa akcja.", {KLODZKO, NYSA}),
    # cel trasy nierozpoznany („Janowa” to skrót wielu gmin), a trasa nie wycina początku
    ("Trasa z Lublina przez Kraśnik do Janowa zamknięta.", {LUBLIN, KRASNIK}),
    ("Droga z Lublina do Chełma zamknięta.", {LUBLIN, CHELM}),
    ("Pociąg z Krakowa przez Tarnów do Rzeszowa opóźniony.", {KRAKOW, TARNOW, RZESZOW}),
    # trasa z osobą: lista pochodzenia ze słowem „do” za sobą zostaje w całości
    ("Kierowca z Lublina jechał do Chełma.", {LUBLIN, CHELM}),
    ("Kierowca z Lublina do Janowa zginął w Chełmie.", {LUBLIN, CHELM}),
])
def test_trasa_i_kierunek_nie_wycinaja_miejsc(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert not any("poza-wynikiem" in d.uwagi for d in w.dopasowania)


def test_pewnosc_nie_rosnie_po_wycieciu_miejsca():
    # zdanie bez wycięcia: pewność czystego wyniku się nie zmienia
    assert geokoduj("Wypadek w Warszawie.").pewnosc == 0.9
    # z wycięciem pochodzenia lub jednostki: nie powyżej 0,8, nigdy wyżej niż przed wycięciem
    w = geokoduj("Kierowca z Lublina rozbił samochód w Warszawie.")
    assert kody(w) == {WARSZAWA} and w.pewnosc == 0.8
    w = geokoduj("Policjanci z KMP w Płocku zatrzymali w gminie Słupno.")
    assert kody(w) == {"1419122"} and w.pewnosc == 0.8
    # wycięte miejsce o niskiej pewności obniża wynik („Tarnów” bez kontekstu to homonim: 0,65)
    w = geokoduj("Kierowca z Tarnowa rozbił samochód w Warszawie.")
    assert kody(w) == {WARSZAWA} and w.pewnosc <= 0.65


# stary kontra nowy: zdania, które mają dawać dokładnie ten sam wynik co przed czwartą recenzją
# (wartości zapisane z wersji 873cf468; wyjątek świadomy: pewność po wycięciu jednostki nie powyżej 0,8)
BEZ_ZMIAN = [
    ("Kierowca z Lublina zginął w Chełmie.", (CHELM,), 0.65),
    ("Strażacy z Lublina.", (LUBLIN,), 0.9),
    ("Mieszkańca Lublina uratowano.", (LUBLIN,), 0.9),
    ("Pożar w Lesznie, woj. wielkopolskie.", (LESZNO,), 0.9),
    ("Pożar hali w Lesznie (woj. wielkopolskie).", (LESZNO,), 0.9),
    ("Sąd Rejonowy w Chełmie skazał mieszkańca Lublina.", (CHELM,), 0.65),
    ("Policjanci z Koła zatrzymali w Chełmie kierowcę.", (CHELM,), 0.65),
    ("Droga z Lublina do Chełma zamknięta.", (CHELM, LUBLIN), 0.65),
    ("Pociąg z Krakowa do Warszawy opóźniony.", (KRAKOW, WARSZAWA), 0.9),
    ("Kierowca z Lublina jechał do Chełma.", (CHELM, LUBLIN), 0.65),
    ("Pożar w Kaliszu (powiat kaliski).", ("3007", "3061011"), 0.9),
    ("Pożar w gminie Tarnów (powiat tarnowski).", ("1216092",), 0.9),
    ("Poziom wody w Odrze we Wrocławiu rośnie.", (WROCLAW,), 0.9),
    ("Mieszkaniec Lublina zginął w pożarze.", (LUBLIN,), 0.9),
    ("Kierowca z Lublina zasłabł.", (LUBLIN,), 0.9),
    ("Komunikat dla mieszkańców Lublina. Pożar w Chełmie.", (CHELM, LUBLIN), 0.65),
    ("Burmistrz rozmawiał z Tuchowem w Krakowie.", ("1216103", KRAKOW), 0.75),
    ("Mieszkanka Lublina zginęła w pożarze w Chełmie.", (CHELM,), 0.65),
    ("Pochodzący z Lublina mężczyzna został zatrzymany w Chełmie.", (CHELM,), 0.65),
    ("Policjanci z KMP w Płocku zatrzymali w gminie Słupno.", ("1419122",), 0.8),  # było 0,9: wycięto jednostkę
    ("Pożar w Chełmie, woj. lubelskie.", (CHELM,), 0.65),
    ("Pożar w Zakopanem (powiat tatrzański).", (ZAKOPANE,), 0.85),
    ("Pożar w Dąbrowie (pow. dąbrowski).", ("1204023",), 0.75),
    ("Pożar w Wiśle.", ("2403031",), 0.85),
    ("Kibice Wisły zatrzymani w Płocku.", ("1462011",), 0.9),
    ("Andrzej Kalisz przemawiał w Poznaniu.", ("3064011",), 0.9),
    ("Pożar w Kazimierzu Dolnym.", ("0614043",), 0.75),
    ("Pożar w Janowie Lubelskim.", ("0605053",), 0.75),
    ("Pożar w Nysie.", (NYSA,), 0.75),
    ("Alert RCB: woj. małopolskie, w powiecie tatrzańskim lawiny.", ("12", "1217"), 0.95),
    ("Wypadek w Opolu. Mieszkańcy Krakowa wrócili do domu.", (KRAKOW, OPOLE), 0.9),
    ("Tomasz Opole ogłosił wyniki.", (), 0.0),
    ("Jarosław Kaczyński przemawiał w Rzeszowie.", (RZESZOW,), 0.9),
]


@pytest.mark.parametrize("tekst, teryt, pewnosc", BEZ_ZMIAN)
def test_zdania_bez_zmiany_wyniku_wzgledem_poprzedniej_wersji(tekst, teryt, pewnosc):
    w = geokoduj(tekst)
    assert (w.teryt, w.pewnosc) == (tuple(sorted(teryt)), pewnosc), tekst


# --------------------------------------------------------------------------- P2-1: miasto i powiat o jego nazwie

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Pożar w Lesznie (powiat leszczyński).", {"3013", LESZNO}),
    ("Pożar w Lesznie, powiat leszczyński.", {"3013", LESZNO}),
    ("Pożar w Kaliszu (powiat kaliski).", {"3007", "3061011"}),
    ("Pożar w Krakowie, powiat krakowski.", {"1206", KRAKOW}),
])
def test_miasto_i_powiat_o_jego_nazwie_sa_zgodne(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert kody(w) == oczekiwane, (tekst, w.teryt)
    assert w.pewnosc >= 0.8


@pytest.mark.parametrize("tekst, powiat, fraza", [
    ("Pożar w Krakowie, powiat pruszkowski.", "1421", "Krakowie"),
    ("Wypadek w Nowym Targu, powiat tatrzański.", "1217", "Nowym Targu"),
    ("Pożar w Lublinie (powiat chełmski).", "0603", "Lublinie"),
    ("Pożar w Zakopanem, powiat nowotarski.", "1211", "Zakopanem"),
])
def test_naprawde_sprzeczny_kontekst_daje_powiat_bez_nazwy_i_pewnosc_ponizej_progu(tekst, powiat, fraza):
    w = geokoduj(tekst)
    assert kody(w) == {powiat}, (tekst, w.teryt)  # zasięg zostaje, nazwa to `brak`
    assert dopasowanie(w, fraza).teryt == ()
    assert 0 < w.pewnosc < 0.8


def test_powiat_w_osobnym_zdaniu_albo_za_lacznikiem_nie_wyklucza_jednoznacznej_nazwy():
    # inny powiat w tekście to osobna wzmianka: jednoznaczna nazwa zostaje, pewność bez obniżki
    for tekst in ("Alert dla powiatu krakowskiego. Pożar w Warszawie.", "Pożar w Warszawie i w powiecie krakowskim."):
        w = geokoduj(tekst)
        assert WARSZAWA in kody(w) and w.pewnosc >= 0.8, tekst


def test_pary_miast_i_powiatow_sa_w_danych():
    s = sl.slownik()
    pary = geokoder._powiaty_o_nazwie_miast()
    assert len(pary) == len(geokoder._POWIAT_O_NAZWIE_MIASTA)  # każda para z tabeli istnieje w teryt.json
    for grodzki, ziemski in pary.items():
        assert s.jednostki[grodzki].rodzaj == "grodzki" and s.jednostki[ziemski].rodzaj == "ziemski"
        assert grodzki[:2] == ziemski[:2]
        assert s.jednostki[ziemski].nazwa == geokoder._POWIAT_O_NAZWIE_MIASTA[s.jednostki[grodzki].nazwa]


# --------------------------------------------------------------------------- P2-2: gmina wiejska tylko przy jawnym „gmina X”

# miejscownik nazw miast na prawach powiatu, które mają gminę wiejską o tej samej nazwie w „swoim” powiecie ziemskim
MIEJSCOWNIKI = {
    "Grudziądz": "Grudziądzu", "Włocławek": "Włocławku", "Biała Podlaska": "Białej Podlaskiej", "Chełm": "Chełmie",
    "Zamość": "Zamościu", "Skierniewice": "Skierniewicach", "Tarnów": "Tarnowie", "Siedlce": "Siedlcach",
    "Przemyśl": "Przemyślu", "Łomża": "Łomży", "Suwałki": "Suwałkach", "Elbląg": "Elblągu",
}


def _gminy_wiejskie_bez_wlasnej_miejscowosci():
    """Gminy wiejskie o nazwie miasta na prawach powiatu, leżące w powiecie ziemskim o jego nazwie (wyznaczone na danych)."""
    s = sl.slownik()
    wynik = []
    for grodzki, ziemski in sorted(geokoder._powiaty_o_nazwie_miast().items()):
        miasto = s.jednostki[grodzki].nazwa
        wynik += [(miasto, grodzki, ziemski, j.kod) for j in s.gminy if j.kod[:4] == ziemski and j.nazwa == miasto and j.rodzaj == "wiejska"]
    return wynik


def test_lista_gmin_wiejskich_bez_wlasnej_miejscowosci_pochodzi_z_danych():
    nazwy = {m for m, *_ in _gminy_wiejskie_bez_wlasnej_miejscowosci()}
    assert nazwy == set(MIEJSCOWNIKI)  # nowe dane muszą wymusić uzupełnienie testu, a nie przejść po cichu


@pytest.mark.parametrize("miasto, grodzki, ziemski, wiejska", _gminy_wiejskie_bez_wlasnej_miejscowosci())
def test_w_miescie_z_powiatem_o_tej_nazwie_to_miasto_a_nie_gmina_wiejska(miasto, grodzki, ziemski, wiejska):
    powiat = sl.jednostka(ziemski).nazwa
    w = geokoduj(f"Pożar w {MIEJSCOWNIKI[miasto]} (powiat {powiat}).")
    assert grodzki + "011" in kody(w) and wiejska not in kody(w), (miasto, w.teryt)
    assert ziemski in kody(w)  # powiat z tekstu zostaje jako zasięg
    # jawne „gmina X” wybiera gminę wiejską
    w = geokoduj(f"Pożar w gminie {miasto} (powiat {powiat}).")
    assert wiejska in kody(w) and grodzki + "011" not in kody(w), (miasto, w.teryt)


@pytest.mark.parametrize("tekst, miasto", [
    ("Pożar w Tarnowie (powiat tarnowski).", TARNOW),
    ("Pożar w Tarnowie.", TARNOW),
    ("Pożar w Chełmie (powiat chełmski).", CHELM),
    ("Pożar w Siedlcach (powiat siedlecki).", "1464011"),
    ("Pożar w Zamościu (powiat zamojski).", "0664011"),
])
def test_zdania_z_recenzji_p2_2_daja_miasto(tekst, miasto):
    w = geokoduj(tekst)
    assert miasto in kody(w), (tekst, w.teryt)
    assert not any(k.endswith(("2", "3")) and len(k) == 7 for k in w.teryt), (tekst, w.teryt)  # żadna gmina wiejska ani miejsko-wiejska


# --------------------------------------------------------------------------- P2-3: imię i nazwa

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Wypadek na trasie Jarosław Przemyśl.", {JAROSLAW, PRZEMYSL}),
    ("Kościół św. Anny Lubartów.", {LUBARTOW}),
    ("Kościół im. Anny Lubartów.", {LUBARTOW}),
    ("Wita Kraków: turyści wrócili.", {KRAKOW}),
    # imiona przed nazwą gminy nadal oznaczają osobę
    ("Andrzej Kalisz przemawiał w Poznaniu.", {"3064011"}),
    ("Rzecznik Tomasz Kalisz przemawiał w Poznaniu.", {"3064011"}),
    ("Lucyna Brzeg i Maciej Opole ogłosili wyniki.", set()),
    ("Anna Kalisz-Nowak przemawiała w Poznaniu.", {"3064011"}),
])
def test_regula_imie_i_nazwa(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


def test_poprzedni_wyraz_bedacy_gmina_nie_robi_osoby():
    # Bolesław i Hanna to też nazwy gmin (wiejskich): „Hanna Lublin” to dwa miejsca, a nie osoba z nazwiskiem
    assert LUBLIN in kody(geokoduj("Hanna Lublin to nazwa kawiarni w Chełmie."))
    assert KRAKOW in kody(geokoduj("Bolesław Kraków to ulica w Rzeszowie."))


# --------------------------------------------------------------------------- P2-4: rzeka po słowach hydrologicznych

@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Poziom Wisły w Warszawie rośnie.", {WARSZAWA}),
    ("Stan Wisły w Krakowie jest alarmowy.", {KRAKOW}),
    ("Stan wód Wisły w Krakowie jest alarmowy.", {KRAKOW}),
    ("Fala kulminacyjna Wisły dotarła do Warszawy.", {WARSZAWA}),
    ("Wylew Wisły zagraża Warszawie.", {WARSZAWA}),
    ("Przekroczenie stanu Warty w Poznaniu.", {"3064011"}),
    ("Wylew Warty w Poznaniu.", {"3064011"}),
    ("Rzeka Wisła przybiera w Krakowie.", {KRAKOW}),
    ("Na brzegu Wisły w Warszawie ewakuowano ludzi.", {WARSZAWA}),
    ("Poziom Odry we Wrocławiu rośnie.", {WROCLAW}),
    ("Poziom Bugu w Wyszkowie rośnie.", {"1435053"}),
    ("Poziom Sanu w Przemyślu rośnie.", {PRZEMYSL}),
    ("Fala na Nysie Kłodzkiej dotarła do Opola.", {OPOLE}),
])
def test_rzeka_po_slowie_hydrologicznym_nie_daje_gminy(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Pożar w Wiśle.", {"2403031"}),
    ("Wypadek w Wiśle, w pobliżu rynku.", {"2403031"}),
    ("Pożar w Wiśle. Poziom Wisły w Warszawie rośnie.", {"2403031", WARSZAWA}),
])
def test_miasto_wisla_poza_kontekstem_rzeki_zostaje(tekst, oczekiwane):
    assert kody(geokoduj(tekst)) == oczekiwane, tekst
