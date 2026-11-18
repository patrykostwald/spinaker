"""Zasięg alertu RCB w API (recenzja PR #38, P1-2): kod województwa dla alertu do wybranych powiatów to przybliżenie.

Pole `zasieg` mówi, jak czytać kody TERYT: `obszar` (zasięg ze źródła), `przyblizony` (kod szerszy niż źródło, szczegóły
w `miejsce`), `brak`. Publiczne pole `miejsce` zostaje bez zmian, więc frontend może dopasować nazwy powiatów.
"""
import pytest
from django.core.cache import caches
from django.urls import reverse

from teraz.models import Klasa, Wpis, Zrodlo
from teraz.tests.test_zrodla import karta_rcb, link_rcb, odpowiedz
from teraz.transport import OdpowiedzHTTP
from teraz.zrodla import rcb

pytestmark = pytest.mark.django_db
POLA = ("tytul", "tresc", "miejsce", "teryt", "dokladnosc", "pewnosc_lokalizacji", "czas_zrodlowy_at",
        "dokladna_godzina_publikacji", "opublikowano_at")


@pytest.fixture
def zrodlo_rcb():
    zrodlo = Zrodlo.objects.get(slug="rcb")
    zrodlo.tryb = Zrodlo.Tryb.PUBLICZNY
    zrodlo.save()
    return zrodlo


def zapisz_karte(zrodlo, zrob_wpis, dzien, **zmiany):
    alert = rcb.AdapterRCB(zrodlo).parsuj(odpowiedz(karta_rcb(dzien)))[0]
    dane = {pole: alert[pole] for pole in POLA}
    dane.update(zmiany)
    return zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, link=link_rcb(dzien), **dane)


def wpis_z_api(client, wpis):
    caches["teraz"].clear()  # w teście bez on_commit generacja cache się nie zmienia
    wyniki = client.get(reverse("teraz:wpisy")).json()["results"]
    return next(w for w in wyniki if w["id"] == wpis.pk)


def test_alert_dla_wybranych_powiatow_ma_zasieg_przyblizony(client, zrodlo_rcb, zrob_wpis):
    wpis = zapisz_karte(zrodlo_rcb, zrob_wpis, "10")
    dane = wpis_z_api(client, wpis)
    assert dane["teryt"] == ["06"]
    assert dane["zasieg"] == "przyblizony"
    assert dane["pewnosc_lokalizacji"] == 0.5
    miejsca = dane["miejsce"].splitlines()
    assert "lubelskie: Chełm" in miejsca and "lubelskie: chełmski" in miejsca
    assert not [m for m in miejsca if m.endswith(("Lublin", ": lubelski"))]


def test_starszy_wpis_rcb_z_pewnoscia_1_tez_jest_przyblizony(client, zrodlo_rcb, zrob_wpis):
    # wiersze zapisane przed poprawką parsera mają pewność 1; o zasięgu rozstrzyga lista jednostek w `miejsce`
    wpis = zapisz_karte(zrodlo_rcb, zrob_wpis, "10", pewnosc_lokalizacji=1)
    assert wpis_z_api(client, wpis)["zasieg"] == "przyblizony"


def test_alert_dla_calych_wojewodztw_ma_zasieg_obszar(client, zrodlo_rcb, zrob_wpis):
    wpis = zapisz_karte(zrodlo_rcb, zrob_wpis, "03")
    dane = wpis_z_api(client, wpis)
    assert dane["teryt"] == ["06", "18"] and dane["zasieg"] == "obszar"


def test_zasieg_brak_i_uogolniony(client, zrodlo_rcb, zrob_wpis, zrob_zrodlo):
    bez_kodow = zrob_wpis(zrodlo_rcb, klasa=Klasa.ZWYKLY, teryt=[])
    assert wpis_z_api(client, bez_kodow)["zasieg"] == "brak"
    inne = zrob_zrodlo("powiatowe", tryb=Zrodlo.Tryb.PUBLICZNY)
    powiat = zrob_wpis(inne, klasa=Klasa.ZWYKLY, teryt=["0662"], dokladnosc=Wpis.Dokladnosc.POWIAT, pewnosc_lokalizacji=1)
    assert wpis_z_api(client, powiat)["zasieg"] == "obszar"


def test_zasieg_czesciowy_rozroznia_tekst():
    assert rcb.zasieg_czesciowy("lubelskiego\npodkarpackiego") is False
    assert rcb.zasieg_czesciowy("lubelskiego\nChełm") is True
    assert rcb.zasieg_czesciowy("lubelskiego", "na terenie części województwa lubelskiego") is True
    assert rcb.zasieg_czesciowy("") is False


def parsuj_akapity(*akapity):
    html = ('<article class="article-area__article"><h2>Alert RCB</h2><p class="event-date">10.11.2026</p>'
            '<div class="editor-content">' + "".join(f"<p>{akapit}</p>" for akapit in akapity) + "</div></article>")
    return rcb.parsuj_karte(OdpowiedzHTTP(200, {}, html.encode(), "utf-8"), link_rcb("10"))[0]


def test_jednostki_zachowuja_wojewodztwo_i_typ():
    # próba recenzenta R38b: ten sam powiat „świdnicki” w dwóch województwach, na liście tylko lubelski
    alert = parsuj_akapity(
        "Alert RCB został wysłany do odbiorców na terenie: woj. lubelskiego - powiat: świdnicki; "
        "woj. dolnośląskiego - powiat: wałbrzyski.",
    )
    assert alert["miejsce"].splitlines() == [
        "lubelskiego", "dolnośląskiego", "lubelskie: świdnicki", "dolnośląskie: wałbrzyski",
    ]
    assert alert["teryt"] == ["02", "06"] and alert["pewnosc_lokalizacji"] == 0.5


def test_jednostki_bez_dwukropka_po_wojewodztwie_i_gminy_miasta():
    alert = parsuj_akapity(
        "Alert RCB został wysłany do odbiorców na terenie woj. lubelskim: powiat świdnicki; "
        "w woj. dolnośląskim: powiat wałbrzyski, miasto Świdnica, gmina Żarów.",
    )
    assert alert["miejsce"].splitlines()[2:] == [
        "lubelskie: świdnicki", "dolnośląskie: wałbrzyski", "dolnośląskie: miasto Świdnica", "dolnośląskie: gmina Żarów",
    ]


def test_wojewodztwa_przed_lista_nie_przypisuja_jednostek_do_jednego_z_nich():
    alert = parsuj_akapity("Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego i podkarpackiego - powiaty: A, B.")
    assert alert["miejsce"].splitlines() == ["lubelskiego", "podkarpackiego", "A", "B"]


def test_wojewodztwo_nie_przechodzi_do_nastepnej_linii():
    alert = parsuj_akapity("Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego:", "- powiaty: Chełm, włodawski")
    assert alert["miejsce"].splitlines() == ["lubelskiego", "Chełm", "włodawski"]


def test_powiaty_bez_dwukropka_to_zasieg_przyblizony(client, zrodlo_rcb, zrob_wpis):
    # „w powiatach chełmskim i włodawskim” bez dwukropka: nie cały region (recenzja R38b, P1-1)
    alert = parsuj_akapity("Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego w powiatach chełmskim i włodawskim.")
    assert alert["miejsce"].splitlines() == ["lubelskiego", "lubelskie: chełmskim", "lubelskie: włodawskim"]
    assert alert["teryt"] == ["06"] and alert["pewnosc_lokalizacji"] == 0.5
    dane = {pole: alert[pole] for pole in POLA}
    wpis = zrob_wpis(zrodlo_rcb, klasa=Klasa.ZWYKLY, link=link_rcb("10"), **dane)
    assert wpis_z_api(client, wpis)["zasieg"] == "przyblizony"
    # stary wiersz (pewność 1, bez rozpoznanych powiatów w `miejsce`) też nie jest „obszarem”: rozstrzyga zdanie o odbiorcach
    stary = zrob_wpis(zrodlo_rcb, klasa=Klasa.ZWYKLY, link=link_rcb("09"), **{**dane, "miejsce": "lubelskiego", "pewnosc_lokalizacji": 1})
    assert wpis_z_api(client, stary)["zasieg"] == "przyblizony"


def test_zdanie_o_calym_wojewodztwie_zostaje_obszarem():
    alert = parsuj_akapity("Alert RCB został wysłany do odbiorców na terenie woj. lubelskiego i podkarpackiego.")
    assert alert["miejsce"].splitlines() == ["lubelskiego", "podkarpackiego"]
    assert alert["pewnosc_lokalizacji"] == 1
