"""Testy geokodera komunikatów (TERYT i PRG) na tekstach alertów RCB i komunikatach Policji.

Oczekiwane listy miejsc są spisane ręcznie z treści komunikatów (nie z wyniku geokodera).
Teksty RCB to treści urzędowych alertów (gov.pl/web/rcb). Próbki Policji są skróconymi
parafrazami komunikatów z RSS policja.pl, bez nazwisk, wieku i adresów.

Przykłady z przeglądu (rzeki, kluby, skróty, zasięg, kraj, dzielnice, jednostki służb) mają oczekiwany
wynik wg decyzji prowadzącego projekt: lepiej `brak` albo województwo niż zgadnięta gmina lub powiat.
"""

import dataclasses
import json
import time

import pytest

pytest.importorskip("shapely")

from teraz.geo import geokoder, geokoduj, nazwa  # noqa: E402
from teraz.geo.geokoder import BRAK, KRAJ  # noqa: E402


def miejsca(wynik):
    """Zbiór pełnych nazw przyjętych jednostek, np. {'powiat włodawski, woj. lubelskie'}."""
    return {nazwa(k, pelna=True) for k in wynik.teryt}


def powiaty(wynik):
    """Zbiór (województwo, krótka nazwa powiatu) dla wyniku złożonego z powiatów."""
    return {(nazwa(k[:2], krotka=True), nazwa(k, krotka=True)) for k in wynik.teryt}


def uwagi(wynik):
    """Wszystkie uwagi wszystkich dopasowań."""
    return {u for d in wynik.dopasowania for u in d.uwagi}


def dopasowanie(wynik, fraza):
    return next(d for d in wynik.dopasowania if d.fraza == fraza)


# --------------------------------------------------------------------------- alerty RCB

ALERT_0311 = """Alert RCB - zagrożenie z powietrza (03.11)
03.11.2026
„UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Aktualizacja - 06:49
„UWAGA! Zakończył się atak powietrzny na Ukrainę. Brak zagrożenia na terenie Polski.”
Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego i podkarpackiego.
----------------------------------
„UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Alert RCB został wysłany do odbiorców na terenie woj. podkarpackiego i lubelskiego.
"""

ALERT_0911 = """Alert RCB - zagrożenie z powietrza (09.11)
09.11.2026
"UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Aktualizacja! - 22:41
„UWAGA! Zakończył się atak powietrzny na Ukrainę. Brak zagrożenia na terenie Polski.”
Alert RCB został wysłany do odbiorców na terenie części województwa:
- lubelskiego - powiaty: włodawski, łęczyński, świdnicki, Chełm, chełmski, krasnostawski, łukowski, Biała Podlaska, bialski, rycki, radzyński, parczewski, lubartowski
- podlaskiego- powiaty: Suwałki, suwalski, augustowski, sejneński, sokólski, Białystok, białostocki, zambrowski, wysokomazowiecki, bielski, hajnowski, siemiatycki
"UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Alert RCB został wysłany do odbiorców na terenie części województwa:
- lubelskiego - powiaty: włodawski, łęczyński, świdnicki, Chełm, chełmski, krasnostawski, łukowski, Biała Podlaska, bialski, rycki, radzyński, parczewski, lubartowski
- podlaskiego- powiaty: Suwałki, suwalski, augustowski, sejneński, sokólski, Białystok, białostocki, zambrowski, wysokomazowiecki, bielski, hajnowski, siemiatycki
"""

ALERT_1011 = """Alert RCB - zagrożenie z powietrza (10.11)
10.11.2026
„UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Aktualizacja - g. 10:55
„UWAGA! Zakończył się atak powietrzny na Ukrainę. Brak zagrożenia na terenie Polski.”
Alert RCB został wysłany do odbiorców na terenie części województwa lubelskiego - powiaty: włodawski, łęczyński, świdnicki, Chełm, chełmski, krasnostawski, łukowski, Biała Podlaska, bialski, rycki, radzyński, parczewski, lubartowski.
----------
10:20
„UWAGA! Rosyjski atak powietrzny na Ukrainie. Sytuacja jest monitorowana. Podniesiono gotowość Systemu Obrony Powietrznej RP. Oczekuj dalszych komunikatów.”
Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego - powiaty: włodawski, łęczyński, świdnicki, Chełm, chełmski, krasnostawski, łukowski, Biała Podlaska, bialski, rycki, radzyński, parczewski, lubartowski.
"""

LUBELSKIE_1011 = {
    "włodawski", "łęczyński", "świdnicki", "Chełm", "chełmski", "krasnostawski", "łukowski",
    "Biała Podlaska", "bialski", "rycki", "radzyński", "parczewski", "lubartowski",
}
PODLASKIE_0911 = {
    "Suwałki", "suwalski", "augustowski", "sejneński", "sokólski", "Białystok", "białostocki",
    "zambrowski", "wysokomazowiecki", "bielski", "hajnowski", "siemiatycki",
}


def test_alert_rcb_0311_dwa_wojewodztwa():
    w = geokoduj(ALERT_0311)
    assert w.teryt == ("06", "18")
    assert w.dokladnosc == "wojewodztwo"
    assert w.pewnosc >= 0.9
    # „Brak zagrożenia na terenie Polski” nie oznacza zasięgu krajowego
    assert not any(d.rodzaj == KRAJ for d in w.dopasowania)


def test_alert_rcb_0911_lista_powiatow_w_dwoch_wojewodztwach():
    w = geokoduj(ALERT_0911)
    assert w.dokladnosc == "powiat"
    assert w.pewnosc >= 0.85
    oczekiwane = {("lubelskie", n) for n in LUBELSKIE_1011} | {("podlaskie", n) for n in PODLASKIE_0911}
    assert powiaty(w) == oczekiwane
    assert len(w.teryt) == 25
    assert all(len(k) == 4 for k in w.teryt)
    # miasta na prawach powiatu to powiaty grodzkie (kody od 61), nie gminy
    assert {"0661", "0662", "2061", "2063"} <= set(w.teryt)


def test_alert_rcb_1011_jedno_wojewodztwo_trzynascie_powiatow():
    w = geokoduj(ALERT_1011)
    assert w.dokladnosc == "powiat"
    assert powiaty(w) == {("lubelskie", n) for n in LUBELSKIE_1011}
    assert len(w.teryt) == 13


def test_homonimy_powiatow_rozstrzyga_wojewodztwo_z_listy():
    # „bielski” i „świdnicki” istnieją w dwóch województwach; lista stoi pod województwem
    w = geokoduj(ALERT_0911)
    wynik = {nazwa(k, krotka=True): k for k in w.teryt}
    assert wynik["bielski"].startswith("20")  # podlaskie, nie śląskie
    assert wynik["świdnicki"].startswith("06")  # lubelskie, nie dolnośląskie


@pytest.mark.parametrize("tekst, oczekiwane, dokladnosc", [
    ("„ĆWICZENIA: Dziś (06.11) w godz. 10:00-12:00 na terenie Gminy Mogilany odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój.”",
     {"gmina Mogilany, powiat krakowski, woj. małopolskie"}, "gmina"),
    ("„ĆWICZENIA: Dziś (06.11) w godz. 10:00-11:00 na terenie powiatu olkuskiego odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój.”",
     {"powiat olkuski, woj. małopolskie"}, "powiat"),
    ("„ĆWICZENIA: Jutro (06.11) w godz. 09:00-13:00 na terenie Gminy Bogatynia odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój.”",
     {"gmina Bogatynia, powiat zgorzelecki, woj. dolnośląskie"}, "gmina"),
    ("„ĆWICZENIA: Dziś (04.11) w godz. 10:00-18:00 na terenie powiatu sępoleńskiego odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój.”",
     {"powiat sępoleński, woj. kujawsko-pomorskie"}, "powiat"),
    ("„ĆWICZENIE: Dziś (03.11) w godz. 10:00-12:00 na terenie pow. radomszczańskiego odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój.”",
     {"powiat radomszczański, woj. łódzkie"}, "powiat"),
    ("„ĆWICZENIA: Dziś (29.10) w godz. 10.00-12.00 na terenie powiatu leskiego odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój\".",
     {"powiat leski, woj. podkarpackie"}, "powiat"),
    ("„ĆWICZENIA: Dziś (23.10) w godz. 10:00-12:00 na terenie gminy Skała odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój”.",
     {"gmina Skała, powiat krakowski, woj. małopolskie"}, "gmina"),
    ("„KOMUNIKAT: 8.11 od godz. 7:00 neutralizacja niewybuchu na ul. Bałuki w Szczecinie. Zachowaj bezpieczną odległość i stosuj się do poleceń służb. Śledź komunikaty.”",
     {"miasto Szczecin, woj. zachodniopomorskie"}, "gmina"),
    ("Dziś (16 listopada) w Kancelarii Prezesa Rady Ministrów w Warszawie rozpoczyna się VIII Seminarium Cyberbezpieczeństwa.",
     {"miasto Warszawa, woj. mazowieckie"}, "gmina"),
])
def test_alerty_rcb_treningi_i_komunikaty(tekst, oczekiwane, dokladnosc):
    w = geokoduj(tekst)
    assert miejsca(w) == oczekiwane
    assert w.dokladnosc == dokladnosc
    assert w.pewnosc >= 0.85


def test_ulica_w_komunikacie_nie_jest_miejscem():
    # „Bałuki” to ulica (dzielnica Łodzi), a nie gmina czy miasto
    w = geokoduj("neutralizacja niewybuchu na ul. Bałuki w Szczecinie")
    assert w.teryt == ("3262011",)


@pytest.mark.parametrize("tekst", [
    "„UWAGA! Dziś (07.11) prognozowana zła jakość powietrza - SMOG (pył zawieszony - PM10). Jeśli możesz, unikaj aktywności na zewnątrz i nie wietrz pomieszczeń.”",
    "„Pogoda: dziś (25.10) prognozowany silny wiatr. Zachowaj ostrożność podczas aktywności na zewnątrz.”",
    "„UWAGA! Rosyjski atak powietrzny na terenie Ukrainy. Sytuacja jest monitorowana. W przestrzeni RP operuje polskie lotnictwo. Oczekuj dalszych komunikatów.”",
])
def test_alerty_bez_miejsca_to_brak(tekst):
    w = geokoduj(tekst)
    assert (w.teryt, w.dokladnosc, w.pewnosc) == ((), BRAK, 0.0)


def test_alert_z_wieloznaczna_gmina_czernichow_nie_zgaduje_powiatu():
    # dwie gminy Czernichów: w woj. małopolskim i śląskim, tekst nie mówi, która
    tekst = "„ĆWICZENIA: Dziś (27.10) od godz. 10:00 na terenie gminy Czernichów odbędzie się trening systemu alarmowania z wykorzystaniem syren. Zachowaj spokój”."
    w = geokoduj(tekst)
    assert (w.teryt, w.dokladnosc, w.pewnosc) == ((), BRAK, 0.0)
    d = w.dopasowania[0]
    assert d.teryt == () and "niejednoznaczne" in d.uwagi
    assert {k[:2] for k in d.kandydaci} == {"12", "24"}
    assert len(d.kandydaci) == 2


def test_wiele_alertow_w_jednym_tekscie_laczy_miejsca():
    tekst = (
        "„ĆWICZENIA: Dziś (27.10) na terenie powiatu jaworskiego odbędzie się trening systemu alarmowania.”\n"
        "„ĆWICZENIA: Dziś (27.10) od godz. 10:00 na terenie gminy Czernichów odbędzie się trening systemu alarmowania.”"
    )
    w = geokoduj(tekst)
    assert miejsca(w) == {"powiat jaworski, woj. dolnośląskie"}
    assert w.dokladnosc == "powiat"
    assert w.pewnosc < 0.9, "nierozstrzygnięta nazwa obniża pewność całego wyniku"


# --------------------------------------------------------------------------- komunikaty Policji

POLICJA = [
    ("Napad na seniora. Policjanci z Nowej Rudy zatrzymali podejrzanego o rozbój mieszkańca miasta.",
     {"miasto Nowa Ruda, powiat kłodzki, woj. dolnośląskie"}, "gmina"),
    ("Policjant z Komendy Wojewódzkiej Policji w Bydgoszczy zatrzymał w czasie wolnym od służby złodzieja biżuterii.",
     {"województwo kujawsko-pomorskie"}, "wojewodztwo"),
    ("Dzielnicowy z Komendy Powiatowej Policji w Słubicach udzielił pomocy mężczyźnie, który zasłabł za kierownicą.",
     set(), "brak"),
    ("Kryminalni ze Słupska zatrzymali sprawcę wypadku, który w piątek w miejscowości Rumsko potrącił pieszego.",
     {"miasto Słupsk, woj. pomorskie"}, "gmina"),
    # Gdańsk to siedziba jednostki (zostaje w `dopasowania` z uwagą `jednostka`), zdarzenie było w Krakowie
    ("Kryminalni z Komendy Miejskiej Policji w Gdańsku zatrzymali mężczyznę, który pisał w internecie o zdarzeniu z 7 listopada w Krakowie.",
     {"miasto Kraków, woj. małopolskie"}, "gmina"),
    ("Dzięki czujności sąsiadów w Boguszowie-Gorcach uratowano życie starszego mężczyzny.",
     {"miasto Boguszów-Gorce, powiat wałbrzyski, woj. dolnośląskie"}, "gmina"),
    ("Poszukiwacze z Komendy Wojewódzkiej Policji w Lublinie zatrzymali w Chełmie poszukiwaną kobietę.",
     {"miasto Chełm, woj. lubelskie"}, "gmina"),
    # powiat tarnowski to osobna wzmianka (zasięg), więc zostaje obok gminy Tuchów; dokładność opisuje zasięg
    ("Dzielnicowy związany z Tuchowem i jego mieszkańcami to jeden z najdłużej służących w powiecie tarnowskim.",
     {"gmina Tuchów, powiat tarnowski, woj. małopolskie", "powiat tarnowski, woj. małopolskie"}, "powiat"),
    # Rzeszów to miejsce pochodzenia („mężczyzny z Rzeszowa”), a jednostka (KPP w Garwolinie) jest miejscem w zdaniu:
    # pochodzenie nie trafia do wyniku (trzecia recenzja, P2-6), zostaje w `dopasowania`
    ("Policjanci z Komendy Powiatowej Policji w Garwolinie ustalili tożsamość mężczyzny z Rzeszowa, który oszukiwał metodą na legendę.",
     {"powiat garwoliński, woj. mazowieckie"}, "powiat"),
    ("Centrum Szkolenia Policji w Legionowie i uczelnia podpisały w Warszawie porozumienie o współpracy.",
     {"miasto Legionowo, powiat legionowski, woj. mazowieckie", "miasto Warszawa, woj. mazowieckie"}, "gmina"),
    ("Policja stawia na dialog z młodzieżą. Kampania profilaktyczna, hejt w sieci i kryzysy emocjonalne.", set(), "brak"),
    ("Opolscy policjanci razem z Opolskim Urzędem Wojewódzkim realizują kampanię profilaktyczną.", set(), "brak"),
    ("Śląscy sportowcy w mundurach uhonorowani w legendarnym Kotle czarownic.", set(), "brak"),
    ("Obchody Święta Policji i Straży Granicznej Estonii, delegacji przewodniczył zastępca Komendanta Głównego.", set(), "brak"),
    ("Tragiczny finał sprzeczki. Łódzcy policjanci zatrzymali podejrzaną o zabójstwo męża.", set(), "brak"),
    ("Policjanci zatrzymali sprawcę kradzieży w Zielonej Górze i w Gorzowie Wielkopolskim.",
     {"miasto Zielona Góra, woj. lubuskie", "miasto Gorzów Wielkopolski, woj. lubuskie"}, "gmina"),
]


@pytest.mark.parametrize("tekst, oczekiwane, dokladnosc", POLICJA)
def test_komunikaty_policji(tekst, oczekiwane, dokladnosc):
    w = geokoduj(tekst)
    assert miejsca(w) == oczekiwane, w.dopasowania
    assert w.dokladnosc == dokladnosc
    if not oczekiwane:
        assert w.pewnosc == 0.0


def test_jednostka_policji_nie_podaje_miejsca_zdarzenia_na_poziomie_miasta():
    # komenda wojewódzka w Bydgoszczy obejmuje całe województwo: wynik to województwo, z uwagą
    w = geokoduj("Policjant z Komendy Wojewódzkiej Policji w Bydgoszczy zatrzymał złodzieja.")
    d = w.dopasowania[0]
    assert "jednostka" in d.uwagi and "spadek-do-wojewodztwa" in d.uwagi
    assert w.pewnosc <= 0.8


def test_rola_jednostki_nie_przechodzi_na_kolejne_miejsce():
    w = geokoduj("Poszukiwacze z Komendy Wojewódzkiej Policji w Lublinie zatrzymali w Chełmie poszukiwaną.")
    chelm = next(d for d in w.dopasowania if d.fraza == "Chełmie")
    assert "jednostka" not in chelm.uwagi


@pytest.mark.parametrize("tekst, fraza, kod, oczekiwane_uwagi", [
    # skróty jednostek: miejsce jednostki, nie zdarzenia (dokładność i pewność jak dla jednostek)
    ("Policjanci z KPP w Garwolinie zatrzymali kierowcę.", "Garwolinie", "1403", {"jednostka", "spadek-do-powiatu"}),
    ("Policjanci z kpp w Garwolinie zatrzymali kierowcę.", "Garwolinie", "1403", {"jednostka", "spadek-do-powiatu"}),
    ("Komunikat KWP w Lublinie o zatrzymaniu.", "Lublinie", "06", {"jednostka", "spadek-do-wojewodztwa"}),
    ("Rzecznik KWP w Bydgoszczy poinformował o sprawie.", "Bydgoszczy", "04", {"jednostka", "spadek-do-wojewodztwa"}),
    ("Funkcjonariusze KMP w Gdańsku zatrzymali podejrzanego.", "Gdańsku", "2261011", {"jednostka"}),
    ("Rzecznik KSP w Warszawie poinformował o sprawie.", "Warszawie", "1465011", {"jednostka"}),
    ("Strażacy z JRG w Lublinie gasili pożar.", "Lublinie", "0663011", {"jednostka"}),
    ("Strażacy z KP PSP w Garwolinie gasili pożar.", "Garwolinie", "1403", {"jednostka", "spadek-do-powiatu"}),
    ("Strażacy z KW PSP w Lublinie gasili pożar.", "Lublinie", "06", {"jednostka", "spadek-do-wojewodztwa"}),
    ("Strażacy z KM PSP w Gdańsku gasili pożar.", "Gdańsku", "2261011", {"jednostka"}),
    ("Policjanci z komisariatu w Pilawie zatrzymali nietrzeźwego.", "Pilawie", "1403103", {"jednostka"}),
    ("Policjanci z Komisariatu Policji w Pilawie zatrzymali nietrzeźwego.", "Pilawie", "1403103", {"jednostka"}),
    ("Sprawę prowadzi komenda powiatowa policji w Garwolinie.", "Garwolinie", "1403", {"jednostka", "spadek-do-powiatu"}),
])
def test_skroty_i_formy_malymi_literami_jednostek_sluzb(tekst, fraza, kod, oczekiwane_uwagi):
    w = geokoduj(tekst)
    d = dopasowanie(w, fraza)
    assert d.teryt == (kod,), d
    assert oczekiwane_uwagi <= set(d.uwagi)
    assert d.pewnosc <= 0.8


def test_jednostka_sluzby_nie_zaklada_roli_przy_zwyklym_miejscu():
    assert "jednostka" not in uwagi(geokoduj("Policjanci zatrzymali sprawcę w Lublinie."))
    # „km” to kilometry, nie jednostka
    assert "jednostka" not in uwagi(geokoduj("Samochód przejechał 20 km w Lublinie."))
    # rola jednostki nie przechodzi na drugie miejsce w zdaniu
    w = geokoduj("Policjanci z KPP w Garwolinie zatrzymali kierowcę w Łaskarzewie.")
    assert "jednostka" not in dopasowanie(w, "Łaskarzewie").uwagi
    assert w.teryt == ("1403021",), "powiat jednostki to tylko kontekst, gdy w tekście jest węższe miejsce"


# --------------------------------------------------------------------------- fleksja

@pytest.mark.parametrize("tekst, nazwa_miasta", [
    ("w Szczecinie", "Szczecin"), ("na terenie Szczecina", "Szczecin"), ("ze Szczecinem", "Szczecin"),
    ("w Poznaniu", "Poznań"), ("do Poznania", "Poznań"),
    ("we Wrocławiu", "Wrocław"), ("pod Wrocławiem", "Wrocław"),
    ("w Krakowie", "Kraków"), ("z Krakowa", "Kraków"),
    ("w Łodzi", "Łódź"), ("z Łodzi", "Łódź"),
    ("w Gdyni", "Gdynia"), ("do Gdyni", "Gdynia"),
    ("w Kielcach", "Kielce"), ("w Katowicach", "Katowice"), ("w Gliwicach", "Gliwice"),
    ("w Opolu", "Opole"), ("w Toruniu", "Toruń"), ("w Rzeszowie", "Rzeszów"),
    ("w Przemyślu", "Przemyśl"), ("w Białymstoku", "Białystok"), ("z Białegostoku", "Białystok"),
    ("w Krasnymstawie", "Krasnystaw"), ("do Krasnegostawu", "Krasnystaw"),
    ("w Zielonej Górze", "Zielona Góra"), ("w Gorzowie Wielkopolskim", "Gorzów Wielkopolski"),
    ("w Nowym Sączu", "Nowy Sącz"), ("w Rudzie Śląskiej", "Ruda Śląska"),
    ("w Piotrkowie Trybunalskim", "Piotrków Trybunalski"), ("w Kędzierzynie-Koźlu", "Kędzierzyn-Koźle"),
    ("w Bielsku-Białej", "Bielsko-Biała"), ("w Jastrzębiu-Zdroju", "Jastrzębie-Zdrój"),
    ("w Sopocie", "Sopot"), ("w Sosnowcu", "Sosnowiec"), ("z Sosnowca", "Sosnowiec"),
    ("w Zabrzu", "Zabrze"), ("w Tychach", "Tychy"), ("w Bytomiu", "Bytom"), ("w Radomiu", "Radom"),
    ("w Częstochowie", "Częstochowa"), ("w Kaliszu", "Kalisz"), ("w Rybniku", "Rybnik"),
    ("w Suwałkach", "Suwałki"), ("w Siedlcach", "Siedlce"),
])
def test_odmiana_nazw_miast(tekst, nazwa_miasta):
    w = geokoduj(tekst)
    assert len(w.teryt) == 1, w.dopasowania
    assert nazwa(w.teryt[0], krotka=True) == nazwa_miasta
    assert w.dokladnosc == "gmina"


def test_wyliczenie_miast_i_wojewodztw():
    assert {nazwa(k, krotka=True) for k in geokoduj("Bydgoszcz, Toruń oraz Włocławek").teryt} == {"Bydgoszcz", "Toruń", "Włocławek"}
    w = geokoduj("W województwie podlaskim i warmińsko-mazurskim silny wiatr.")
    assert w.teryt == ("20", "28") and w.dokladnosc == "wojewodztwo"
    w = geokoduj("na terenie woj. lubelskiego, podkarpackiego oraz małopolskiego")
    assert w.teryt == ("06", "12", "18")


def test_powiaty_z_odmiana_i_wyliczeniem():
    w = geokoduj("Komunikat dla mieszkańców powiatów przemyskiego, lubaczowskiego i jarosławskiego.")
    assert powiaty(w) == {("podkarpackie", "przemyski"), ("podkarpackie", "lubaczowski"), ("podkarpackie", "jarosławski")}
    assert w.dokladnosc == "powiat"
    assert {nazwa(k, krotka=True) for k in geokoduj("w powiecie tarnowskim").teryt} == {"tarnowski"}
    assert {nazwa(k, krotka=True) for k in geokoduj("na obszarze powiatu kędzierzyńsko-kozielskiego").teryt} == {"kędzierzyńsko-kozielski"}


def test_miasto_na_prawach_powiatu_z_odmianami_formy_urzedowej():
    for tekst in ("na terenie m. st. Warszawy", "w m.st. Warszawie", "w Warszawie", "miasto Warszawa"):
        assert geokoduj(tekst).teryt == ("1465011",), tekst


def test_dzielnica_warszawy_to_warszawa_ale_gmina_wola_nie_istnieje():
    assert geokoduj("w dzielnicy Wola w Warszawie").teryt == ("1465011",)
    assert geokoduj("na terenie dzielnicy Mokotów").teryt == ("1465011",)
    # nie ma gminy „Wola”: są tylko „Wola Krzysztoporska” itp.; „gmina Wola” to brak, nie zgadywanie
    w = geokoduj("w gminie Wola")
    assert (w.teryt, w.dokladnosc) == ((), BRAK)
    assert geokoduj("w gminie Wola Krzysztoporska").dokladnosc == "gmina"


# --------------------------------------------------------------------------- homonimy

def test_homonimy_gmin_bez_kontekstu_spadaja_do_brak_albo_wyzej():
    # Dąbrowa: dwie gminy wiejskie w różnych województwach
    w = geokoduj("na terenie gminy Dąbrowa")
    assert (w.teryt, w.dokladnosc, w.pewnosc) == ((), BRAK, 0.0)
    assert {k[:2] for k in w.dopasowania[0].kandydaci} == {"04", "16"}
    # Adamów: dwie gminy w tym samym województwie (lubelskim), ale w różnych powiatach: spadek do województwa
    w = geokoduj("w gminie Adamów")
    assert (w.teryt, w.dokladnosc) == (("06",), "wojewodztwo")
    assert w.pewnosc <= 0.6
    assert "spadek-do-wojewodztwa" in w.dopasowania[0].uwagi
    # Mielec: gmina miejska i wiejska w jednym powiecie, wyraźny znacznik „gmina”: spadek do powiatu
    w = geokoduj("w gminie Mielec")
    assert w.dokladnosc == "powiat" and nazwa(w.teryt[0], krotka=True) == "mielecki"
    assert w.pewnosc <= 0.7


def test_homonimy_gmin_rozstrzyga_kontekst_powiatu_lub_wojewodztwa():
    assert miejsca(geokoduj("na terenie gminy Dąbrowa w powiecie mogileńskim")) == {"gmina Dąbrowa, powiat mogileński, woj. kujawsko-pomorskie"}
    assert miejsca(geokoduj("gmina Dąbrowa, woj. opolskie")) == {"gmina Dąbrowa, powiat opolski, woj. opolskie"}
    assert miejsca(geokoduj("w gminie Czernichów w powiecie żywieckim")) == {"gmina Czernichów, powiat żywiecki, woj. śląskie"}
    assert miejsca(geokoduj("w gminie Czernichów, woj. małopolskie")) == {"gmina Czernichów, powiat krakowski, woj. małopolskie"}
    assert geokoduj("w gminie Adamów w powiecie łukowskim").teryt == ("0611032",)


def test_homonimy_rozne_wojewodztwa_to_brak_dla_miast_i_powiatow():
    for tekst in ("w Brzezinach", "gmina Brzeziny", "w Bolesławcu", "w Świdnicy", "Dzielnicowy z Komendy Powiatowej Policji w Słubicach"):
        w = geokoduj(tekst)
        assert (w.teryt, w.dokladnosc) == ((), BRAK), tekst
    for tekst in ("w powiecie opolskim", "powiat bielski", "powiat świdnicki"):
        w = geokoduj(tekst)
        assert (w.teryt, w.dokladnosc) == ((), BRAK), tekst
    assert miejsca(geokoduj("w powiecie opolskim, woj. lubelskie")) == {"powiat opolski, woj. lubelskie"}
    assert miejsca(geokoduj("w powiecie opolskim, woj. opolskie")) == {"powiat opolski, woj. opolskie"}


def test_dluzsze_nazwy_wygrywaja_z_krotszymi_homonimami():
    assert miejsca(geokoduj("w Dąbrowie Górniczej")) == {"miasto Dąbrowa Górnicza, woj. śląskie"}
    assert miejsca(geokoduj("w Dąbrowie Tarnowskiej")) == {"gmina Dąbrowa Tarnowska, powiat dąbrowski, woj. małopolskie"}
    assert miejsca(geokoduj("gmina Nowa Wieś Lęborska")) == {"gmina Nowa Wieś Lęborska, powiat lęborski, woj. pomorskie"}


def test_miasto_na_prawach_powiatu_wygrywa_z_wiejskim_homonimem_ale_z_niska_pewnoscia():
    w = geokoduj("zatrzymano w Chełmie")
    assert w.teryt == ("0662011",) and w.dokladnosc == "gmina"
    assert w.pewnosc == 0.65
    assert "preferowane-miasto" in w.dopasowania[0].uwagi and len(w.dopasowania[0].kandydaci) >= 2
    # wyraźne „gmina Chełm” oznacza gminę wiejską, nie miasto
    assert miejsca(geokoduj("gmina Chełm")) == {"gmina Chełm, powiat chełmski, woj. lubelskie"}
    # miasto wygrywa z wiejską gminą tego samego powiatu (Mielec), nigdy z gminą z innego powiatu
    assert miejsca(geokoduj("w Mielcu")) == {"miasto Mielec, powiat mielecki, woj. podkarpackie"}


@pytest.mark.parametrize("miasto, wojewodztwo_tekst, oczekiwane", [
    ("Lesznie", "wielkopolskie", "miasto Leszno, woj. wielkopolskie"),
    ("Olsztynie", "warmińsko-mazurskie", "miasto Olsztyn, woj. warmińsko-mazurskie"),
])
def test_miasto_z_wiejskim_homonimem_w_innym_wojewodztwie_wymaga_kontekstu(miasto, wojewodztwo_tekst, oczekiwane):
    # Leszno i Olsztyn mają gminę wiejską o tej samej nazwie w innym województwie: bez kontekstu `brak`
    for tekst in (f"Pożar w {miasto}.", f"Pożar w {miasto} i okolicach."):
        w = geokoduj(tekst)
        assert (w.teryt, w.dokladnosc, w.pewnosc) == ((), BRAK, 0.0), tekst
        d = w.dopasowania[0]
        assert "homonim" in d.uwagi and d.teryt == () and len(d.kandydaci) == 2
        assert len({k[:2] for k in d.kandydaci}) == 2
    # kontekst województwa rozstrzyga
    w = geokoduj(f"Pożar w {miasto}. Alert dla woj. {wojewodztwo_tekst}.")
    assert oczekiwane in miejsca(w)
    assert w.pewnosc >= 0.85


def test_pierwsze_slowo_bez_przyimka_tez_jest_homonimem():
    # „Leszno: pożar” nie zamienia wiejskiego homonima w pewne miasto (homonimię liczymy przed filtrem przyimka)
    for tekst in ("Leszno: pożar hali.", "Olsztyn. Pożar hali.", "Leszno - pożar hali."):
        w = geokoduj(tekst)
        assert (w.teryt, w.dokladnosc) == ((), BRAK), tekst
        assert "homonim" in w.dopasowania[0].uwagi
    # bez homonima w innym województwie miasto bez przyimka nadal działa
    assert miejsca(geokoduj("Słupsk: pożar hali.")) == {"miasto Słupsk, woj. pomorskie"}
    # województwo w osobnym zdaniu rozstrzyga homonim i zostaje jako zasięg obok miasta
    assert miejsca(geokoduj("Leszno: pożar hali. Woj. wielkopolskie.")) == {"miasto Leszno, woj. wielkopolskie", "województwo wielkopolskie"}
    assert miejsca(geokoduj("Leszno, woj. wielkopolskie: pożar hali.")) == {"miasto Leszno, woj. wielkopolskie"}


# --------------------------------------------------------------------------- skrócone nazwy

@pytest.mark.parametrize("tekst", [
    "Zderzenie w Grodzisku.", "Wypadek w Ostrowie.", "Wypadek w Bielsku.", "Wypadek w Jastrzębiu.",
    "Wypadek w Mińsku.", "Wypadek w Tomaszowie.", "Wypadek w Środzie.", "Pożar w Kędzierzynie.",
    "Wypadek w Starogardzie.", "Pożar w Dąbrowie.", "Zderzenie w Nowym Dworze.",
])
def test_skrocone_nazwy_bez_kontekstu_to_brak_z_uwaga_skrot(tekst):
    w = geokoduj(tekst)
    assert (w.teryt, w.dokladnosc, w.pewnosc) == ((), BRAK, 0.0), tekst
    assert "skrot" in uwagi(w)


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Pożar w Kędzierzynie. Ostrzeżenie dla woj. opolskiego.", "miasto Kędzierzyn-Koźle, powiat kędzierzyńsko-kozielski, woj. opolskie"),
    ("Wypadek w Grodzisku, woj. wielkopolskie.", "gmina Grodzisk Wielkopolski, powiat grodziski, woj. wielkopolskie"),
    ("Wypadek w Dąbrowie, woj. opolskie.", "gmina Dąbrowa, powiat opolski, woj. opolskie"),
])
def test_skrot_z_jednoznacznym_kontekstem_wojewodztwa(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert oczekiwane in miejsca(w), w.dopasowania
    d = next(d for d in w.dopasowania if "skrot" in d.uwagi)
    assert "kontekst" in d.uwagi and d.pewnosc <= 0.75


def test_skrot_z_kontekstem_ktory_niczego_nie_potwierdza_to_brak():
    # „Mińsk” to tylko Mińsk Mazowiecki (woj. mazowieckie); woj. śląskie go nie potwierdza, więc nie zgadujemy
    w = geokoduj("Wypadek w Mińsku, woj. śląskie.")
    assert w.teryt == ("24",), "zostaje tylko wymienione województwo"
    d = dopasowanie(w, "Mińsku")
    assert d.teryt == () and "skrot" in d.uwagi
    # ten sam skrót z właściwym województwem
    w = geokoduj("Wypadek w Mińsku, woj. mazowieckie.")
    assert [nazwa(k, krotka=True) for k in w.teryt] == ["Mińsk Mazowiecki"]


def test_skrot_z_kontekstem_w_innym_zdaniu_nie_znosi_zasiegu():
    # województwo rozstrzygnęło skrót, ale jest osobną wzmianką o zasięgu: zostaje obok miasta
    w = geokoduj("Pożar w Kędzierzynie. Ostrzeżenie dla woj. opolskiego.")
    assert w.teryt == ("16", "1603011")
    assert w.dokladnosc == "wojewodztwo"
    # zapis adresowy w jednym zdaniu doprecyzowuje, a nie dodaje zasięgu
    assert geokoduj("Pożar w Kędzierzynie, woj. opolskie.").teryt == ("1603011",)


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("Pożar w Brzegu.", {"miasto Brzeg, powiat brzeski, woj. opolskie"}),  # miasto o tej nazwie (Brzeg Dolny to inna gmina)
    ("Pożar w Opolu.", {"miasto Opole, woj. opolskie"}),
    ("Pożar w Tarnowie.", {"miasto Tarnów, woj. małopolskie"}),
    ("Wypadek w Wadowicach.", {"gmina Wadowice, powiat wadowicki, woj. małopolskie"}),
    ("Wypadek w Kaliszu.", {"miasto Kalisz, woj. wielkopolskie"}),
    ("Zderzenie w Opolu Lubelskim.", {"gmina Opole Lubelskie, powiat opolski, woj. lubelskie"}),
    ("Policja w Policach.", {"gmina Police, powiat policki, woj. zachodniopomorskie"}),
])
def test_pelne_nazwy_miast_nie_sa_skrotami(tekst, oczekiwane):
    assert miejsca(geokoduj(tekst)) == oczekiwane


def test_skrot_nie_psuje_nowych_przymiotnikow_i_innych_zdan():
    # „Nowym” to początek wielu nazw („Nowy Sącz”), ale samo nie jest skrótem miejsca
    w = geokoduj("W Nowym Roku zatrzymano sprawcę w Lublinie.")
    assert miejsca(w) == {"miasto Lublin, woj. lubelskie"}
    assert w.pewnosc >= 0.9


# --------------------------------------------------------------------------- rzeki i kluby

def test_rzeka_przed_miastem_nie_jest_miejscem():
    w = geokoduj("IMGW: stan ostrzegawczy przekroczony na Wiśle w Tczewie.")
    assert w.teryt == ("2214011",)  # Tczew, nie Wisła (woj. śląskie)
    assert not any(d.fraza == "Wiśle" for d in w.dopasowania)


@pytest.mark.parametrize("tekst", [
    "Ostrzeżenie hydrologiczne: wzrost stanów wody na Nysie Kłodzkiej.",
    "Ostrzeżenie hydrologiczne: wzrost stanów wody na Nysie Łużyckiej.",
    "Stan alarmowy na Pilicy i Warcie.",
    "Wezbranie na Wieprzu.",
    "Wezbranie na Narwi i Bugu.",
    "Podwyższony stan wody w rzece Warta.",
    "Fala kulminacyjna na Odrze, Wiśle i Sanie.",
    "Kajakarze płynęli nad Wartą.",
    "Pożar na Nysie Kłodzkiej.",
    "Wylew rzeki: Wisła przekroczyła stan alarmowy.",
])
def test_rzeki_nie_daja_gmin_o_tej_samej_nazwie(tekst):
    w = geokoduj(tekst)
    assert (w.teryt, w.dokladnosc) == ((), BRAK), w.dopasowania


def test_miasto_o_nazwie_rzeki_dziala_poza_kontekstem_rzeki():
    # bez „na/nad”, bez rzeki i bez komunikatu hydrologicznego to miasto
    assert miejsca(geokoduj("Pożar w Wiśle.")) == {"miasto Wisła, powiat cieszyński, woj. śląskie"}
    assert miejsca(geokoduj("Pożar w Nysie.")) == {"gmina Nysa, powiat nyski, woj. opolskie"}


def test_komunikat_hydrologiczny_zachowuje_inne_miasta():
    w = geokoduj("Ostrzeżenie hydrologiczne: stan alarmowy na Wiśle w Tczewie i na Odrze w Opolu.")
    assert miejsca(w) == {"miasto Opole, woj. opolskie", "miasto Tczew, powiat tczewski, woj. pomorskie"}


@pytest.mark.parametrize("tekst, oczekiwane", [
    # nazwa klubu blokuje także miasto stojące po niej („Wisła Kraków” to drużyna, nie miejsce zdarzenia)
    ("Mecz Wisły Kraków z Legią Warszawa.", set()),
    ("Wisła Kraków przegrała wczoraj.", set()),
    ("Wisła Płock wygrała mecz.", set()),
    ("Odra Opole zagra w Opolu.", {"Opole"}),  # miasto zdarzenia w tym samym zdaniu zostaje
    ("Warta Poznań zremisowała z Lechem.", set()),
    ("Raków Częstochowa pokonał rywala.", set()),
    ("Kibice Wisły Kraków zatrzymani w Płocku.", {"Płock"}),
    ("Kibice Legii Warszawa zatrzymani w Płocku.", {"Płock"}),
    ("Kibice Lecha Poznań i Śląska Wrocław starli się w Łodzi.", {"Łódź"}),
    ("Mecz Odra Opole z Rakowem Częstochowa.", set()),
    ("Zatrzymani kibice Pogoni Szczecin, Górnika Zabrze i Cracovii Kraków w Lublinie.", {"Lublin"}),
])
def test_kluby_sportowe_blokuja_tez_miasto_po_nazwie_klubu(tekst, oczekiwane):
    w = geokoduj(tekst)
    assert {nazwa(k, krotka=True) for k in w.teryt} == oczekiwane
    assert (w.dokladnosc == BRAK) == (not oczekiwane)
    assert not any(d.fraza.startswith(("Wisł", "Wart", "Rakow", "Raków")) for d in w.dopasowania)


@pytest.mark.parametrize("klub", [
    "Legia", "Lech", "Śląsk", "Pogoń", "Jagiellonia", "Górnik", "Korona", "Zagłębie", "Wisła", "Odra", "Raków", "Cracovia",
    "Arka", "Lechia", "Widzew", "ŁKS", "Stal", "Motor", "Warta", "Piast", "Ruch", "Polonia", "Resovia", "GKS", "Puszcza",
    "Stomil", "Znicz",
])
def test_kazdy_klub_z_listy_blokuje_miasto_po_nazwie(klub):
    w = geokoduj(f"Zatrzymano kibiców. {klub} Lublin przegrał.")
    assert not any(d.fraza == "Lublin" for d in w.dopasowania), (klub, w.dopasowania)
    assert geokoduj(f"Kibice z Lublina i {klub} Gdańsk.").teryt == ("0663011",)


@pytest.mark.parametrize("tekst", [
    "Mecz Legii Warszawa.", "Mecz z Legią Warszawa.", "Mecz Legia Warszawa.", "Mecz Lecha Poznań.", "Mecz Lechem Poznań.",
    "Mecz Śląska Wrocław.", "Mecz Pogoni Szczecin.", "Mecz Pogonią Szczecin.", "Mecz Jagiellonii Białystok.",
    "Mecz Górnika Zabrze.", "Mecz Koronie Kielce.", "Mecz Zagłębia Lubin.", "Mecz Cracovii Kraków.", "Mecz Arce Gdynia.",
    "Mecz Lechii Gdańsk.", "Mecz Widzewa Łódź.", "Mecz Stali Mielec.", "Mecz Motorem Lublin.", "Mecz Piastem Gliwice.",
    "Mecz Ruchu Chorzów.", "Mecz Polonią Warszawa.", "Mecz Resovii Rzeszów.", "Mecz Puszczą Niepołomice.", "Mecz Zniczem Pruszków.",
])
def test_kluby_w_kazdym_przypadku(tekst):
    assert geokoduj(tekst).dokladnosc == BRAK, tekst


def test_slowo_klubu_przed_miastem_po_przecinku_albo_z_przyimkiem_nie_blokuje():
    # blokada dotyczy nazwy klubu zaraz przed miastem; przecinek, przyimek i koniec zdania ją przerywają
    assert geokoduj("Wypadek: Ruch, Lublin.").teryt == ("0663011",)
    assert geokoduj("Zawody na Wiśle. Kraków.").teryt == ("1261011",)
    assert geokoduj("Wypadek. Stal w Lublinie.").teryt == ("0663011",)


# --------------------------------------------------------------------------- szum, adresy, kraj

@pytest.mark.parametrize("tekst", [
    "Koło domu stał samochód.",  # „Koło” na początku zdania to nie miasto
    "Nowy Jork i Nowe prawo",  # „Nowe” to gmina, ale „Nowy Jork” nie
    "Nowe prawo weszło w życie",
    "Włochy i Hiszpania",
    "Warszawski sąd i warszawska policja",  # przymiotniki to nie miejsce
    "Gdańskiego sądu dotyczy wyrok",
    "Wołomin",  # miejsko-wiejska gmina bez przyimka: za mało pewności
    "Zachowaj ostrożność podczas aktywności na zewnątrz",
    "",
    "   ",
])
def test_szum_nie_daje_miejsca(tekst):
    assert geokoduj(tekst).dokladnosc == BRAK


def test_none_i_pusty_tekst():
    for wejscie in (None, "", "\n"):
        w = geokoduj(wejscie)
        assert (w.teryt, w.dokladnosc, w.pewnosc, w.dopasowania) == ((), BRAK, 0.0, ())


def test_kolo_w_srodku_zdania_jest_miastem_i_przyimek_w_malych_literach_nie():
    assert miejsca(geokoduj("Policjanci z Koła zatrzymali mężczyznę")) == {"miasto Koło, powiat kolski, woj. wielkopolskie"}
    assert miejsca(geokoduj("stał koło Lublina")) == {"miasto Lublin, woj. lubelskie"}


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("ul. Gdańska 5 w Lublinie", {"miasto Lublin, woj. lubelskie"}),
    ("przy ulicy Krakowskiej w Kielcach", {"miasto Kielce, woj. świętokrzyskie"}),
    ("na ul. Jana Pawła II w Białymstoku", {"miasto Białystok, woj. podlaskie"}),
    ("al. Warszawska 10, Kielce", {"miasto Kielce, woj. świętokrzyskie"}),
    ("Wypadek na ul. Długiej 5, Gdańsk.", {"miasto Gdańsk, woj. pomorskie"}),
    ("Kolizja na ul. Chełmskiej w Lublinie.", {"miasto Lublin, woj. lubelskie"}),
    ("w miejscowości Dąbrowa koło Lublina", {"miasto Lublin, woj. lubelskie"}),
    ("we wsi Stare Babice, w pobliżu Kielc", {"miasto Kielce, woj. świętokrzyskie"}),
    ("ul. Łódzka", set()),
])
def test_adresy_ulice_i_wsie_sa_ignorowane(tekst, oczekiwane):
    assert miejsca(geokoduj(tekst)) == oczekiwane


def test_zasieg_krajowy_tylko_przy_wyraznym_sformulowaniu():
    w = geokoduj("Alert dla mieszkańców w całej Polsce")
    assert (w.teryt, w.dokladnosc) == ((), KRAJ)
    assert geokoduj("Komunikat obowiązuje w całym kraju").dokladnosc == KRAJ
    assert geokoduj("Brak zagrożenia na terenie Polski.").dokladnosc == BRAK
    assert geokoduj("Atak na Ukrainie, gotowość sił RP").dokladnosc == BRAK


@pytest.mark.parametrize("tekst", [
    "Ostrzeżenie obowiązuje w całym kraju.",
    "Komunikat obowiązuje w całym kraju",
    "Ostrzeżenie dotyczy całego kraju i obowiązuje do jutra.",
    "Alert RCB na terenie całego kraju.",
    "Ostrzeżenie dla całej Polski.",
    "Alert dla mieszkańców w całej Polsce",
    "W całym kraju obowiązują ostrzeżenia przed wiatrem.",
])
def test_kraj_przy_slowach_o_zasiegu(tekst):
    w = geokoduj(tekst)
    assert w.dokladnosc == KRAJ, tekst
    assert w.pewnosc == 0.7 and w.teryt == ()
    assert any(d.rodzaj == KRAJ for d in w.dopasowania)


@pytest.mark.parametrize("tekst", [
    "Policjanci z całej Polski zabezpieczali mecz.",
    "Najwięcej wypadków w całym kraju odnotowano wczoraj.",
    "Kibice z całej Polski przyjechali do miasta.",
    "Na terenie Polski obowiązują ostrzeżenia.",
    "Brak zagrożenia na terenie Polski.",
])
def test_kraj_nie_przy_zwyklych_zdaniach(tekst):
    w = geokoduj(tekst)
    assert w.dokladnosc == BRAK, tekst
    assert not any(d.rodzaj == KRAJ for d in w.dopasowania)


def test_kraj_nie_zeruje_innych_trafien_i_nie_zmienia_pewnych_miejsc():
    w = geokoduj("Policjanci z całej Polski zabezpieczali mecz w Krakowie.")
    assert w.teryt == ("1261011",) and w.dokladnosc == "gmina"
    w = geokoduj("Ostrzeżenie dla całej Polski. Najsilniejszy wiatr w Gdańsku.")
    assert w.dokladnosc == KRAJ
    assert w.teryt == ("2261011",), "konkretne miejsce zostaje w teryt obok zasięgu krajowego"
    assert w.pewnosc <= 0.7
    assert {d.rodzaj for d in w.dopasowania} == {KRAJ, "gmina"}


def test_pozycje_zasiegu_krajowego_sa_liczone_na_tekscie_oryginalnym():
    # „İ” zmienia długość po lower(): pozycje muszą nadal wskazywać oryginalny fragment
    tekst = "İİİ İİİ Komunikat obowiązuje w całym kraju."
    w = geokoduj(tekst)
    d = next(d for d in w.dopasowania if d.rodzaj == KRAJ)
    assert tekst[d.start:d.koniec] == d.fraza == "w całym kraju"
    tekst = "İİİ Pożar w Lublinie."
    w = geokoduj(tekst)
    d = w.dopasowania[0]
    assert tekst[d.start:d.koniec] == d.fraza == "Lublinie"


def test_regiony_to_wojewodztwa_z_nizsza_pewnoscia():
    w = geokoduj("Gołoledź na Podkarpaciu i w Małopolsce")
    assert w.teryt == ("12", "18") and w.dokladnosc == "wojewodztwo"
    assert w.pewnosc == 0.75
    assert geokoduj("Mazowsze").teryt == ("14",)


def test_wielkie_litery_wymagaja_znacznika_dla_slow_pospolitych():
    w = geokoduj("UWAGA W GMINIE SKAŁA I W POWIECIE OLKUSKIM")
    assert miejsca(w) == {"gmina Skała, powiat krakowski, woj. małopolskie", "powiat olkuski, woj. małopolskie"}
    assert geokoduj("KOŁO DOMU STAŁ SAMOCHÓD").dokladnosc == BRAK


# --------------------------------------------------------------------------- dzielnice Warszawy

DZIELNICE_WARSZAWY = [
    "Bemowo", "Białołęka", "Bielany", "Mokotów", "Ochota", "Praga-Południe", "Praga-Północ", "Rembertów",
    "Targówek", "Ursus", "Ursynów", "Wawer", "Wesoła", "Wilanów", "Włochy", "Wola", "Śródmieście", "Żoliborz",
]


def test_lista_dzielnic_ma_18_pozycji():
    assert len(DZIELNICE_WARSZAWY) == len(set(DZIELNICE_WARSZAWY)) == 18
    assert set(DZIELNICE_WARSZAWY) == set(geokoder._DZIELNICE_WARSZAWY)


@pytest.mark.parametrize("dzielnica", DZIELNICE_WARSZAWY)
def test_dzielnice_warszawy_nie_daja_gmin_takze_bez_slowa_dzielnica(dzielnica):
    for tekst in (f"Do zdarzenia doszło w {dzielnica}.", f"Do zdarzenia doszło na {dzielnica}.", f"{dzielnica}: pożar."):
        w = geokoduj(tekst)
        assert not any(len(k) == 7 for k in w.teryt), (tekst, w.dopasowania)


def test_bielany_to_dzielnica_warszawy_a_nie_gmina_pod_sochaczewem():
    w = geokoduj("Do zdarzenia doszło na Bielanach w Warszawie.")
    assert w.teryt == ("1465011",)
    w = geokoduj("Do zdarzenia doszło na Bielanach.")
    assert (w.teryt, w.dokladnosc) == ((), BRAK)
    # wyraźne „gmina Bielany” oznacza gminę, a „dzielnica Bielany” dzielnicę Warszawy
    assert geokoduj("w gminie Bielany").teryt == ("1429022",)
    assert geokoduj("w dzielnicy Bielany").teryt == ("1465011",)
    # dłuższa nazwa gminy wygrywa z dzielnicą („Wola Krzysztoporska”)
    assert geokoduj("w gminie Wola Krzysztoporska").dokladnosc == "gmina"


# --------------------------------------------------------------------------- zasięg alertu

def test_zasieg_wojewodztwa_zostaje_obok_dokladniejszego_miejsca():
    w = geokoduj("Ostrzeżenie dla województwa mazowieckiego. Najsilniejsze opady w Warszawie.")
    assert w.teryt == ("14", "1465011")
    assert w.dokladnosc == "wojewodztwo", "dokładność opisuje zasięg, nie najmniejsze miejsce"
    assert {d.fraza for d in w.dopasowania} == {"mazowieckiego", "Warszawie"}
    # dokładniejsze miejsce jest w dopasowaniach, z własną dokładnością
    assert dopasowanie(w, "Warszawie").dokladnosc == "gmina"


def test_zasieg_powiatu_zostaje_obok_miasta_w_powiecie():
    w = geokoduj("Ostrzeżenie dla powiatu tatrzańskiego. Silny wiatr w Zakopanem.")
    assert w.teryt == ("1217", "1217011")
    assert w.dokladnosc == "powiat"


def test_zasieg_powiatow_z_lista_i_dokladniejsze_miejsce():
    w = geokoduj("Alert RCB dla powiatów: tatrzańskiego, nowotarskiego i bielskiego. Najsilniejszy wiatr w Zakopanem.")
    assert {"1211", "1217", "1217011"} == set(w.teryt)  # bielski jest niejednoznaczny, nie zgadujemy
    assert w.dokladnosc == "powiat"


def test_zapis_adresowy_doprecyzowuje_a_nie_dodaje_zasiegu():
    # hierarchia jednego miejsca: szersze kody znikają
    assert geokoduj("w woj. lubelskim, w powiecie chełmskim, w gminie Chełm").teryt == ("0603032",)
    assert geokoduj("w gminie Chełm w powiecie chełmskim").teryt == ("0603032",)
    # lista powiatów pod województwem (RCB): województwo jest tylko nagłówkiem listy
    w = geokoduj("woj. lubelskie - powiaty: włodawski, chełmski")
    assert w.teryt == ("0603", "0619") and w.dokladnosc == "powiat"
    # miasto z województwem w zapisie adresowym
    assert geokoduj("Chełm, woj. lubelskie").teryt == ("0662011",)
    assert geokoduj("Policja w Lublinie (woj. lubelskie)").teryt == ("0663011",)


def test_wezszy_kod_z_jednostki_i_ze_spadku_nie_zostaje_obok_wezszego_miejsca():
    # powiat komendy jest tylko miejscem jednostki: znika, gdy w tekście jest węższe miejsce w nim zawarte
    w = geokoduj("Komenda Powiatowa Policji w Garwolinie informuje o wypadku w Łaskarzewie.")
    assert w.teryt == ("1403021",)
    # ale gdy węższego miejsca nie ma, zostaje
    assert geokoduj("Komenda Powiatowa Policji w Garwolinie informuje.").teryt == ("1403",)


# --------------------------------------------------------------------------- struktura wyniku

def test_struktura_wyniku_i_dopasowania():
    tekst = "Alert dla woj. lubelskiego, w Szczecinie i w gminie Mogilany."
    w = geokoduj(tekst)
    assert w.teryt == tuple(sorted(set(w.teryt)))
    assert 0.0 <= w.pewnosc <= 1.0
    # województwo zostaje, bo żadne z pozostałych miejsc nie leży w nim (to osobne wzmianki)
    assert set(w.teryt) == {"06", "3262011", "1206092"}
    assert w.dokladnosc == "wojewodztwo"
    for d in w.dopasowania:
        assert tekst[d.start:d.koniec] == d.fraza
        assert 0.0 <= d.pewnosc <= 1.0
    slownik = w.jako_dict()
    assert slownik["teryt"] == list(w.teryt) and slownik["dopasowania"][0]["fraza"] == w.dopasowania[0].fraza
    assert json.loads(json.dumps(slownik)) == slownik, "jako_dict daje czysty JSON"


def test_wezszy_kod_zastepuje_szerszy_ktory_go_zawiera():
    w = geokoduj("w woj. lubelskim, w powiecie chełmskim, w gminie Chełm")
    assert w.teryt == ("0603032",) and w.dokladnosc == "gmina"  # gmina wiejska Chełm; powiat i województwo to tylko kontekst
    w = geokoduj("woj. lubelskie - powiaty: włodawski, chełmski")
    assert w.teryt == ("0603", "0619") and w.dokladnosc == "powiat"


def test_wynik_jest_deterministyczny():
    assert geokoduj(ALERT_0911) == geokoduj(ALERT_0911)


def test_wynik_i_dopasowanie_to_krotki_niezmienne_i_hashowalne():
    w = geokoduj("Policjanci z KPP w Garwolinie zatrzymali kierowcę w Łaskarzewie i w Lublinie. Alert dla woj. lubelskiego.")
    assert isinstance(w.teryt, tuple) and isinstance(w.dopasowania, tuple) and isinstance(w.uwagi, tuple)
    assert all(isinstance(d.teryt, tuple) and isinstance(d.kandydaci, tuple) and isinstance(d.uwagi, tuple) for d in w.dopasowania)
    assert hash(w) == hash(geokoduj("Policjanci z KPP w Garwolinie zatrzymali kierowcę w Łaskarzewie i w Lublinie. Alert dla woj. lubelskiego."))
    assert len({w, geokoduj(ALERT_0911), geokoduj(ALERT_0911)}) == 2
    for pusty in (geokoduj(None), geokoduj("nic"), geokoduj("w całym kraju obowiązuje alert")):
        assert isinstance(pusty.teryt, tuple) and isinstance(pusty.dopasowania, tuple)
        hash(pusty)
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.teryt = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.dopasowania[0].teryt = ()


# --------------------------------------------------------------------------- wydajność

def test_geokodowanie_komunikatu_trwa_kilka_milisekund():
    geokoduj("rozgrzewka")
    tekst = ALERT_0911 + "\n" + POLICJA[4][0] + "\n" + POLICJA[7][0]
    start = time.perf_counter()
    for _ in range(50):
        geokoduj(tekst)
    srednio_ms = (time.perf_counter() - start) / 50 * 1000
    assert srednio_ms < 15, f"średnio {srednio_ms:.1f} ms"
    krotki = "Policjanci z Koła zatrzymali mężczyznę w Chełmie."
    start = time.perf_counter()
    for _ in range(500):
        geokoduj(krotki)
    assert (time.perf_counter() - start) / 500 * 1000 < 2


@pytest.mark.parametrize("wzor", ["powiat lubelski, ", "powiat lubelski. ", "w Lublinie ", "woj. lubelskie, powiat chełmski, "])
def test_tekst_680_kb_jest_obcinany_i_liczy_sie_ponizej_sekundy(wzor):
    geokoduj("rozgrzewka")
    tekst = wzor * (680_000 // len(wzor))
    assert len(tekst) >= 670_000
    start = time.perf_counter()
    w = geokoduj(tekst)
    czas = time.perf_counter() - start
    assert czas < 1.0, f"{czas:.2f} s"
    assert "obcieto-tekst" in w.uwagi
    assert all(d.koniec <= geokoder.MAKS_DLUGOSC for d in w.dopasowania)
    assert w.dokladnosc != BRAK


def test_limit_dlugosci_nie_tnie_wyrazu_i_nie_dodaje_uwagi_dla_krotkiego_tekstu():
    assert geokoduj("Pożar w Lublinie.").uwagi == ()
    tekst = "x " * (geokoder.MAKS_DLUGOSC // 2 - 3) + "Lublinie w Lublinie"  # nazwa przekracza granicę
    w = geokoduj(tekst)
    assert "obcieto-tekst" in w.uwagi
    assert not any(d.fraza.endswith("Lubl") for d in w.dopasowania)


@pytest.mark.parametrize("wzor, powtorzen", [("powiat lubelski, ", 6000), ("w Lublinie ", 9000), ("woj. lubelskie, powiat chełmski. ", 3000)])
def test_algorytm_jest_liniowy_takze_bez_limitu_dlugosci(monkeypatch, wzor, powtorzen):
    # indeks województw i zakresów po pozycji zamiast skanowania wszystkich poprzednich trafień
    monkeypatch.setattr(geokoder, "MAKS_DLUGOSC", 10**9)
    geokoduj("rozgrzewka")
    tekst = wzor * powtorzen
    start = time.perf_counter()
    geokoduj(tekst)
    pojedynczy = time.perf_counter() - start
    start = time.perf_counter()
    geokoduj(tekst * 3)
    potrojony = time.perf_counter() - start
    assert potrojony < max(pojedynczy * 6, 0.3), f"1x: {pojedynczy:.2f} s, 3x: {potrojony:.2f} s"
    assert potrojony < 3.0
