"""Zasięg alertu RCB w API (recenzja PR #38, P1-2): kod województwa dla alertu do wybranych powiatów to przybliżenie.

Pole `zasieg` mówi, jak czytać kody TERYT: `obszar` (zasięg ze źródła), `przyblizony` (kod szerszy niż źródło, szczegóły
w `miejsce`), `brak`. Publiczne pole `miejsce` zostaje bez zmian, więc frontend może dopasować nazwy powiatów.
"""
import pytest
from django.core.cache import caches
from django.urls import reverse

from teraz.models import Klasa, Wpis, Zrodlo
from teraz.tests.test_zrodla import karta_rcb, link_rcb, odpowiedz
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
    assert "Chełm" in miejsca and "chełmski" in miejsca
    assert "Lublin" not in miejsca and "lubelski" not in miejsca


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
