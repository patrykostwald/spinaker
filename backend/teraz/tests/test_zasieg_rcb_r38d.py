"""Czwarta recenzja PR #38 (Z6R5, zlecenie Z6P5): parser alertów RCB jest zachowawczy.

Zasada: gdy zdanie zawiera wyłączenie albo zalecenie, albo nie da się jednoznacznie wskazać odbiorców, parser nie dopisuje
jednostek do zasięgu, a zasięg jest przybliżony. Fałszywe „nie ma na liście” i fałszywe „wymieniony” są gorsze niż „sprawdź
treść komunikatu”. Etykiety w „Moim powiecie” sprawdza frontend-spin/tests/146-*.test.cjs na wynikach tego parsera.
"""
import json
from pathlib import Path

import pytest

from teraz.models import Klasa
from teraz.tests.test_zasieg_rcb import ODBIORCY, POLA, parsuj_akapity, wpis_z_api, zrodlo_rcb  # noqa: F401
from teraz.tests.test_zrodla import link_rcb
from teraz.zrodla import rcb

pytestmark = pytest.mark.django_db
DANE = json.loads((Path(rcb.__file__).with_name("jednostki_powiaty.json")).read_text(encoding="utf-8"))
WOJ = {kod: nazwa for kod, nazwa in DANE["wojewodztwa"]}  # kod -> mianownik („lubelskie”)
PLIK_FRONTU = Path(__file__).resolve().parents[3] / "frontend-spin/public/teraz/teryt-powiaty.json"


def mianownik(kod):
    return WOJ[kod]


def dopelniacz(kod):
    return WOJ[kod][:-2] + "iego"


def miejscownik(kod):
    return WOJ[kod][:-2] + "im"


def linie(alert):
    return alert["miejsce"].splitlines()


def objete(alert):
    """Linie `miejsce` bez znaczników wyłączeń i niepewności: to, co alert obejmuje."""
    return [linia for linia in linie(alert) if not linia.startswith(rcb.PREFIKSY_ZNACZNIKOW)]


# --- kopia słownika w backendzie zgadza się z plikiem frontu ---
def test_kopia_slownika_jednostek_zgadza_sie_z_plikiem_frontu():
    if not PLIK_FRONTU.exists():
        pytest.skip("brak katalogu frontu (obraz backendu)")
    front = json.loads(PLIK_FRONTU.read_text(encoding="utf-8"))
    assert DANE["wojewodztwa"] == [[w["kod"], w["nazwa"]] for w in front["wojewodztwa"]]
    assert DANE["powiaty"] == [[p["kod"], p["nazwa"]] for p in front["powiaty"]]


def test_rdzenie_wojewodztw_w_parserze_zgadzaja_sie_z_danymi():
    assert {kod: rdzen + "ie" for rdzen, kod in rcb.WOJEWODZTWA.items()} == WOJ


# --- P1-1: wyłączenia ---
@pytest.mark.parametrize("zdanie,kod,wylaczone", [
    ("na terenie województwa podlaskiego z wyłączeniem powiatu białostockiego.", "20", ["podlaskie: białostockiego"]),
    ("na terenie woj. lubelskiego z wyjątkiem miasta Lublin.", "06", ["lubelskie: miasto Lublin"]),
    ("na terenie woj. lubelskiego z wyłączeniem powiatów: chełmskiego i włodawskiego.", "06",
     ["lubelskie: chełmskiego", "lubelskie: włodawskiego"]),
    ("na terenie woj. lubelskiego poza powiatem chełmskim.", "06", ["lubelskie: chełmskim"]),
    ("na terenie woj. lubelskiego oprócz miasta Chełm.", "06", ["lubelskie: miasto Chełm"]),
    ("na terenie woj. lubelskiego bez powiatu włodawskiego.", "06", ["lubelskie: włodawskiego"]),
    ("na terenie woj. lubelskiego z wyłączeniem Chełma i Lublina.", "06", ["lubelskie: Chełma", "lubelskie: Lublina"]),
])
def test_wylaczone_jednostki_nie_sa_objete_zasiegiem(zdanie, kod, wylaczone):
    alert = parsuj_akapity(ODBIORCY + zdanie)
    assert len(objete(alert)) == 1 and objete(alert)[0].startswith(WOJ[kod][:-2]), "tylko województwo; wyłączone nie są objęte"
    assert linie(alert)[1:] == [rcb.PREFIKS_WYLACZONE + linia for linia in wylaczone]
    assert alert["teryt"] == [kod]
    assert alert["pewnosc_lokalizacji"] == 0.5, "zasięg przybliżony, nie całe województwo"


def test_wylaczenie_nie_dopisuje_wojewodztwa_z_wylaczonej_czesci():
    # województwo występujące tylko w części wyłączonej nie wchodzi do kodów TERYT
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego z wyłączeniem powiatu świdnickiego w woj. dolnośląskim.")
    assert alert["teryt"] == ["06"]
    assert rcb.PREFIKS_WYLACZONE + "dolnośląskie: świdnickiego" in linie(alert)


def test_wylaczenie_bez_rozpoznanej_jednostki_to_znacznik_ogolny():
    for zdanie in ("na terenie woj. lubelskiego poza terenami leśnymi.", "na terenie całej Polski z wyłączeniem woj. mazowieckiego."):
        alert = parsuj_akapity(ODBIORCY + zdanie)
        assert rcb.LINIA_WYLACZENIE_OGOLNE in linie(alert)
        assert alert["pewnosc_lokalizacji"] in (0.5, 0)
    assert parsuj_akapity(ODBIORCY + "na terenie całej Polski z wyłączeniem woj. mazowieckiego.")["teryt"] == []


def test_slabe_wylaczenie_bez_jednostek_niczego_nie_zastrzega():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego.", "Alert nie dotyczy pozostałych terenów kraju.")
    assert linie(alert) == ["lubelskiego"] and alert["pewnosc_lokalizacji"] == 1
    z_jednostka = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego.", "Alert nie dotyczy miasta Lublin.")
    # osobne zdanie nie wiąże wyłączenia z województwem (front czyta je jak jednostkę bez województwa)
    assert linie(z_jednostka) == ["lubelskiego", "wyłączone: miasto Lublin"]


def test_bez_w_innym_znaczeniu_nie_ucina_zdania():
    alert = parsuj_akapity(ODBIORCY + "bez względu na miejsce zamieszkania, na terenie woj. lubelskiego.")
    assert linie(alert) == ["lubelskiego"] and alert["pewnosc_lokalizacji"] == 1


def test_wylaczenie_w_api_zasieg_przyblizony(client, zrodlo_rcb, zrob_wpis):  # noqa: F811
    alert = parsuj_akapity(ODBIORCY + "na terenie województwa podlaskiego z wyłączeniem powiatu białostockiego.")
    dane = {pole: alert[pole] for pole in POLA}
    wpis = zrob_wpis(zrodlo_rcb, klasa=Klasa.ZWYKLY, link=link_rcb("10"), **dane)
    api = wpis_z_api(client, wpis)
    assert api["zasieg"] == "przyblizony" and api["teryt"] == ["20"]


# --- P1-2: kilka województw w miejscowniku ---
def test_drugie_wojewodztwo_w_miejscowniku_nie_przepada():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskim i podkarpackim.")
    assert linie(alert) == ["lubelskie", "podkarpackie"]
    assert alert["teryt"] == ["06", "18"] and alert["pewnosc_lokalizacji"] == 1


def test_wojewodztwa_w_miejscowniku_przed_powiatem_z_innego():
    alert = parsuj_akapity(ODBIORCY + "w woj. pomorskim i zachodniopomorskim oraz w powiecie świdnickim w woj. lubelskim.")
    assert linie(alert) == ["pomorskie", "zachodniopomorskie", "lubelskie", "lubelskie: świdnickim"]
    assert alert["teryt"] == ["06", "22", "32"] and alert["pewnosc_lokalizacji"] == 0.5


@pytest.mark.parametrize("koncowka", ["im", "ym", "ej"])
def test_koncowki_miejscownika(koncowka):
    alert = parsuj_akapity(ODBIORCY + f"w woj. lubelsk{koncowka} i podkarpack{koncowka}.")
    assert linie(alert) == ["lubelskie", "podkarpackie"]


def formy(kod):
    return {
        "mianownik": f"woj. {mianownik(kod)}",
        "dopelniacz": f"na terenie województwa {dopelniacz(kod)}",
        "miejscownik": f"w woj. {miejscownik(kod)}",
    }


@pytest.mark.parametrize("kod", sorted(WOJ))
@pytest.mark.parametrize("przypadek", ["mianownik", "dopelniacz", "miejscownik"])
def test_kazde_z_16_wojewodztw_w_kazdym_przypadku(kod, przypadek):
    alert = parsuj_akapity(ODBIORCY + formy(kod)[przypadek] + ".")
    assert alert["teryt"] == [kod] and alert["pewnosc_lokalizacji"] == 1
    assert len(linie(alert)) == 1 and rcb.NAZWA_WOJ.fullmatch(linie(alert)[0])
    assert linie(alert)[0].startswith(WOJ[kod][:-2]) and linie(alert)[0] == linie(alert)[0].lower()


def lista_nazw(kody, przypadek, spojnik):
    nazwy = [{"mianownik": mianownik, "dopelniacz": dopelniacz, "miejscownik": miejscownik}[przypadek](kod) for kod in kody]
    return ", ".join(nazwy[:-1]) + f" {spojnik} " + nazwy[-1] if len(nazwy) > 1 else nazwy[0]


@pytest.mark.parametrize("przypadek", ["mianownik", "dopelniacz", "miejscownik"])
@pytest.mark.parametrize("spojnik", ["i", "oraz"])
@pytest.mark.parametrize("liczba", [2, 3])
def test_listy_wojewodztw_po_2_i_3_w_kazdym_przypadku(przypadek, spojnik, liczba):
    kody = sorted(WOJ)
    for poczatek in range(len(kody)):  # każde województwo jest raz pierwsze, kolejne ze wszystkich 16 po kolei
        wybrane = [kody[(poczatek + i * 5) % len(kody)] for i in range(liczba)]
        przedrostek = {"mianownik": "woj. ", "dopelniacz": "na terenie województw ", "miejscownik": "w woj. "}[przypadek]
        alert = parsuj_akapity(ODBIORCY + przedrostek + lista_nazw(wybrane, przypadek, spojnik) + ".")
        assert alert["teryt"] == sorted(wybrane), (przypadek, wybrane, linie(alert))
        assert alert["pewnosc_lokalizacji"] == 1 and len(linie(alert)) == liczba


# --- P1-3: zalecenie nie zawęża i nie dopisuje ---
def test_zalecenie_po_zdaniu_o_wojewodztwie_nie_dopisuje_jednostki():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskim. Dla mieszkańców miasta Chełm zalecamy pozostanie w domach.")
    assert linie(alert) == ["lubelskie"], "bez jednostki-śmiecia „miasto Chełm zalecamy…”"
    assert alert["teryt"] == ["06"] and alert["pewnosc_lokalizacji"] == 1, "całe województwo lubelskie"


def test_zalecenie_w_zdaniu_z_powiatem_nie_dopisuje_jednostki():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskim.", "W powiecie chełmskim zalecamy pozostanie w domach.")
    assert linie(alert) == ["lubelskie"] and alert["pewnosc_lokalizacji"] == 1
    sam = parsuj_akapity("W powiecie chełmskim zalecamy pozostanie w domach.")
    assert linie(sam) == [] and sam["teryt"] == []


@pytest.mark.parametrize("zdanie", [
    "Dla mieszkańców powiatu włodawskiego prosimy o pozostanie w domach.",
    "Mieszkańcy powiatu włodawskiego nie powinni opuszczać domów.",
    "W powiecie włodawskim należy unikać wychodzenia z domu.",
    "W miastach Chełm i Zamość mieszkańcy powinni się schronić.",
    "Mieszkańcom gminy Żarów zalecane jest zachowanie ostrożności.",
    "Dla powiatu świdnickiego: pozostań w domu.",
])
def test_zalecenie_w_dowolnym_miejscu_zdania_nie_jest_zdaniem_odbiorcow(zdanie):
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego.", zdanie)
    assert linie(alert) == ["lubelskiego"] and alert["pewnosc_lokalizacji"] == 1


def test_zasieg_czesciowy_sprawdza_zdanie_odbiorcow_nie_caly_akapit():
    akapit = ODBIORCY + "na terenie woj. lubelskim. Dla mieszkańców powiatu chełmskiego zalecamy pozostanie w domach."
    assert rcb.zasieg_czesciowy("lubelskie", akapit) is False
    assert rcb.zasieg_czesciowy("lubelskie", ODBIORCY + "na terenie woj. lubelskim w powiatach chełmskim i włodawskim.") is True


def test_zdanie_naglowkowe_z_zaleceniem_czytamy_do_zalecenia():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego, gdzie zalecamy pozostanie w domach.")
    assert linie(alert) == ["lubelskiego"] and alert["pewnosc_lokalizacji"] == 1


@pytest.mark.parametrize("nazwa", ["ala ma kota i psa", "Xyz Abc Def Ghi", "xyz", "Xyz"])
def test_twardy_limit_nazwy_jednostki(nazwa):
    # w powiecie obowiązuje słownik, więc „Xyz” też odpada; „Xyz” jako miasto czy gmina byłoby dozwolone (wielka litera)
    alert = parsuj_akapity(ODBIORCY + f"na terenie woj. lubelskiego w powiatach: chełmski, {nazwa}.")
    assert objete(alert) == ["lubelskiego", "lubelskie: chełmski"]
    assert rcb.LINIA_NIEUSTALONE in linie(alert), "lista niepełna: front nie powie „nie ma na liście”"


def test_adres_nie_jest_nieustalona_jednostka():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego w powiatach: chełmski, ul. Lubelska 5.")
    assert linie(alert) == ["lubelskiego", "lubelskie: chełmski"]


def test_zalecenie_po_liscie_powiatow_jest_odciete_bez_znacznika():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego w powiatach: chełmski, zalecamy pozostanie w domach.")
    assert linie(alert) == ["lubelskiego", "lubelskie: chełmski"]


def test_miasto_i_gmina_z_wielkiej_litery_poza_slownikiem_sa_dozwolone():
    alert = parsuj_akapity(ODBIORCY + "w woj. dolnośląskim: miasto Świdnica, gmina Żarów.")
    assert objete(alert) == ["dolnośląskie", "dolnośląskie: miasto Świdnica", "dolnośląskie: gmina Żarów"]
    assert rcb.LINIA_NIEUSTALONE not in linie(alert)


# --- P2: nawiasy ---
def test_wojewodztwo_w_nawiasie_po_liscie_wiaze_wszystkie_jednostki():
    alert = parsuj_akapity(ODBIORCY + "w powiatach: bielski, cieszyński, żywiecki (woj. śląskie).")
    assert objete(alert) == ["śląskie", "śląskie: bielski", "śląskie: cieszyński", "śląskie: żywiecki"]
    assert alert["teryt"] == ["24"] and alert["pewnosc_lokalizacji"] == 0.5


def test_wojewodztwo_z_powiatem_w_nawiasie():
    alert = parsuj_akapity(ODBIORCY + "w woj. lubelskim (powiat świdnicki) oraz woj. lubelskim (powiat włodawski).")
    assert objete(alert) == ["lubelskie", "lubelskie: świdnicki", "lubelskie: włodawski"]


# --- P3: „w mieście”, wielkie litery ---
def test_w_miescie_krakow_jest_rozpoznane():
    alert = parsuj_akapity(ODBIORCY + "w mieście Kraków.")
    assert linie(alert) == ["miasto Kraków"]
    alert = parsuj_akapity(ODBIORCY + "w woj. małopolskim w mieście Kraków.")
    assert linie(alert) == ["małopolskie", "małopolskie: miasto Kraków"]


def test_miasta_w_miejscowniku_z_wojewodztwem():
    alert = parsuj_akapity(ODBIORCY + "w miastach Gdańsk, Gdynia i Sopot w woj. pomorskim.")
    assert objete(alert) == ["pomorskie", "pomorskie: miasto Gdańsk", "pomorskie: miasto Gdynia", "pomorskie: miasto Sopot"]


def test_wielkie_litery_nie_psuja_zapisu_nazw():
    alert = parsuj_akapity("ALERT RCB ZOSTAŁ WYSŁANY DO ODBIORCÓW NA TERENIE WOJ. LUBELSKIEGO W POWIATACH: CHEŁM, WŁODAWSKI.")
    assert linie(alert) == ["lubelskiego", "lubelskie: Chełm", "lubelskie: włodawski"]
    assert alert["teryt"] == ["06"]
    miejscownik_wielkimi = parsuj_akapity(ODBIORCY + "W WOJ. LUBELSKIM I PODKARPACKIM.")
    assert linie(miejscownik_wielkimi) == ["lubelskie", "podkarpackie"]
    miasta = parsuj_akapity(ODBIORCY + "W WOJ. MAŁOPOLSKIM W MIEŚCIE KRAKÓW I GMINIE WIELKA WIEŚ.")
    # gmina po „i” otwiera nowe wyrażenie (reguła R38c), więc bez województwa; nazwy w formie ze słownika albo Wielkimi Literami
    assert linie(miasta) == ["małopolskie", "małopolskie: miasto Kraków", "gmina Wielka Wieś"]
    assert not [linia for linia in linie(miasta) if "LUBELSK" in linia or "MAŁOPOLSK" in linia]
