"""Zasięg alertu RCB w API (recenzja PR #38, P1-2): kod województwa dla alertu do wybranych powiatów to przybliżenie.

Pole `zasieg` mówi, jak czytać kody TERYT: `obszar` (zasięg ze źródła), `przyblizony` (kod szerszy niż źródło, szczegóły
w `miejsce`), `brak`. Publiczne pole `miejsce` zostaje bez zmian, więc frontend może dopasować nazwy powiatów.
"""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.cache import caches
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from teraz.models import Klasa, StatusPrzegladu, Wpis, Zrodlo
from teraz.tests.test_zrodla import LISTA, SCOPE, karta_rcb, link_rcb, odpowiedz
from teraz.transport import OdpowiedzHTTP
from teraz.zbieranie import Adapter
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


# --- recenzja R38c, P1: jednostka dostaje województwo tylko z tego samego wyrażenia ---
ODBIORCY = "Alert RCB został wysłany do odbiorców "


def test_r38c_dwa_powiaty_kazdy_z_wlasnym_wojewodztwem():
    # zdanie recenzenta: wcześniej „lubelskie: świdnickim”, bo województwo po liście przechodziło do następnej listy
    alert = parsuj_akapity(ODBIORCY + "w powiecie włodawskim w woj. lubelskim oraz w powiecie świdnickim w woj. dolnośląskim.")
    assert alert["miejsce"].splitlines() == [
        "lubelskie", "dolnośląskie", "lubelskie: włodawskim", "dolnośląskie: świdnickim",
    ]
    assert alert["teryt"] == ["02", "06"] and alert["pewnosc_lokalizacji"] == 0.5


def test_r38c_zalecenie_nie_dopisuje_jednostek_do_zasiegu():
    # osobne zdanie, w tym samym akapicie albo w osobnym, nie jest zdaniem o odbiorcach
    w_akapicie = parsuj_akapity(ODBIORCY + "w powiecie włodawskim w woj. lubelskim. Omijaj miasto Chełm.")
    osobne = parsuj_akapity(ODBIORCY + "w powiecie włodawskim w woj. lubelskim.", "Omijaj miasto Chełm.", "Mieszkańcy miasta Chełm powinni uważać.")
    for alert in (w_akapicie, osobne):
        assert alert["miejsce"].splitlines() == ["lubelskie", "lubelskie: włodawskim"]


def test_r38c_cale_wojewodztwo_i_powiat_z_innego_zachowuja_zasiegi_osobno():
    alert = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego oraz w powiecie świdnickim w woj. dolnośląskim.")
    assert alert["miejsce"].splitlines() == ["lubelskiego", "dolnośląskie", "dolnośląskie: świdnickim"]
    assert alert["teryt"] == ["02", "06"] and alert["pewnosc_lokalizacji"] == 0.5
    # odwrotna kolejność: województwo z listą po nazwie całego województwa
    odwrotnie = parsuj_akapity(ODBIORCY + "na terenie woj. lubelskiego oraz w woj. dolnośląskim w powiecie świdnickim.")
    assert odwrotnie["miejsce"].splitlines() == ["lubelskiego", "dolnośląskie", "dolnośląskie: świdnickim"]


def test_r38c_nazwa_miedzy_wyliczeniami_nie_wiaze_sie_z_poprzednia_lista():
    # „oraz w woj.” otwiera nową grupę: województwo nie należy do powiatu przed spójnikiem
    alert = parsuj_akapity(ODBIORCY + "w woj. lubelskim w powiecie włodawskim oraz w woj. dolnośląskim w powiecie świdnickim.")
    assert alert["miejsce"].splitlines()[2:] == ["lubelskie: włodawskim", "dolnośląskie: świdnickim"]


def test_r38c_jednostka_bez_pewnego_wojewodztwa_zostaje_bez_wojewodztwa():
    # powiat po spójniku, bez własnej nazwy województwa: nie dziedziczy cudzego
    alert = parsuj_akapity(ODBIORCY + "w woj. lubelskim w powiecie włodawskim oraz w powiecie świdnickim.")
    assert alert["miejsce"].splitlines() == ["lubelskie", "lubelskie: włodawskim", "świdnickim"]
    assert alert["pewnosc_lokalizacji"] == 0.5


def test_r38c_czesc_wojewodztwa_obok_powiatu_z_innego_nie_wyglada_na_cale():
    alert = parsuj_akapity(ODBIORCY + "na terenie części woj. lubelskiego oraz w powiecie świdnickim w woj. dolnośląskim.")
    assert "lubelskie: część województwa" in alert["miejsce"].splitlines()


def test_r38c_probka_rcb_3_listopada_calych_wojewodztw():
    for alert in rcb.AdapterRCB(Zrodlo(adres="https://example.org/")).parsuj(odpowiedz(karta_rcb("03"))):
        assert sorted(alert["miejsce"].splitlines()) == ["lubelskiego", "podkarpackiego"]
        assert alert["teryt"] == ["06", "18"] and alert["pewnosc_lokalizacji"] == 1


def test_r38c_probka_rcb_9_listopada_kazdy_powiat_w_swoim_wojewodztwie():
    alert = rcb.AdapterRCB(Zrodlo(adres="https://example.org/")).parsuj(odpowiedz(karta_rcb("09")))[0]
    linie = alert["miejsce"].splitlines()
    assert linie[:2] == ["lubelskiego", "podlaskiego"]
    assert "lubelskie: Chełm" in linie and "podlaskie: Białystok" in linie
    assert "podlaskie: Chełm" not in linie and "lubelskie: Białystok" not in linie
    assert not [m for m in linie if m.endswith(("Lublin", ": lubelski"))]


def test_r38c_probka_rcb_10_listopada_chelm_tak_lublin_nie():
    alert = rcb.AdapterRCB(Zrodlo(adres="https://example.org/")).parsuj(odpowiedz(karta_rcb("10")))[0]
    linie = alert["miejsce"].splitlines()
    assert "lubelskie: Chełm" in linie and "lubelskie: chełmski" in linie
    assert not [m for m in linie if m.endswith(("Lublin", ": lubelski"))]


# --- recenzja R38c, P2: nowa wersja parsera przetwarza ponownie zapisane karty (także archiwalne) ---
STARE_MIEJSCE = "lubelskie: świdnickim"


def parser_v3(monkeypatch):
    """Parser sprzed poprawki: ta sama karta daje stare, błędne `miejsce`."""
    prawdziwy = rcb.parsuj_karte

    def stary(odp, adres):
        wyniki = prawdziwy(odp, adres)
        for wynik in wyniki:
            wynik["miejsce"] = STARE_MIEJSCE
        return wyniki
    monkeypatch.setattr(rcb, "parsuj_karte", stary)
    monkeypatch.setattr(rcb.AdapterRCB, "wersja_parsera", "3")


def parser_biezacy(monkeypatch):
    monkeypatch.undo()


def podstaw_siec(monkeypatch, adres):
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([adres], 1))
    pobierz = Mock(side_effect=lambda url, naglowki: (odpowiedz(LISTA if "?page=" in url or url == rcb.LISTA else karta_rcb("10")), SCOPE))
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    return pobierz


def sprawdz_odswiezone(zrodlo, liczba):
    assert zrodlo.wpisy.count() == liczba, "bez duplikatów wpisów"
    miejsca = {w.miejsce for w in zrodlo.wpisy.all()}
    assert STARE_MIEJSCE not in "\n".join(miejsca)
    assert all("lubelskie: Chełm" in m.splitlines() and "lubelskie: świdnicki" in m.splitlines() for m in miejsca)


def test_r38c_wersja_parsera_jest_nowsza_niz_3():
    assert rcb.AdapterRCB.wersja_parsera == "4" and rcb.ArchiwumRCB.wersja_parsera == "4"


def test_r38c_ta_sama_tresc_nowa_wersja_parsera_parsuje_ponownie(monkeypatch, zrodlo_rcb):
    adres = link_rcb("10")
    pobierz = podstaw_siec(monkeypatch, adres)
    czas = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: czas)
    parser_v3(monkeypatch)
    rcb.AdapterRCB(zrodlo_rcb).zbierz()
    liczba = zrodlo_rcb.wpisy.count()
    assert liczba == 2 and {w.miejsce for w in zrodlo_rcb.wpisy.all()} == {STARE_MIEJSCE}
    # wpis wrażliwy, już dopuszczony: istniejąca reguła wymaga ponownego przeglądu, gdy zmienia się miejsce
    wrazliwy = zrodlo_rcb.wpisy.get(zewnetrzny_id=zrodlo_rcb.wpisy.order_by("pk").first().zewnetrzny_id)
    zrodlo_rcb.wpisy.filter(pk=wrazliwy.pk).update(klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.DOPUSZCZONY)
    zwykly = zrodlo_rcb.wpisy.exclude(pk=wrazliwy.pk).get()
    status_zwyklego = zwykly.status_przegladu

    # kontrola: ta sama wersja i identyczna treść, parsera nie uruchamiamy (stan, który zauważył recenzent)
    czas += timedelta(minutes=11)
    rcb.AdapterRCB(zrodlo_rcb).zbierz()
    assert {w.miejsce for w in zrodlo_rcb.wpisy.all()} == {STARE_MIEJSCE}
    assert zrodlo_rcb.wpisy.get(pk=wrazliwy.pk).status_przegladu == StatusPrzegladu.DOPUSZCZONY

    # nowa wersja parsera i prawdziwy parser: ta sama treść jest czytana od nowa
    monkeypatch.undo()
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([adres], 1))
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    monkeypatch.setattr(timezone, "now", lambda: czas)
    czas += timedelta(minutes=11)
    rcb.AdapterRCB(zrodlo_rcb).zbierz()
    sprawdz_odswiezone(zrodlo_rcb, liczba)
    assert zrodlo_rcb.wpisy.get(pk=wrazliwy.pk).status_przegladu == StatusPrzegladu.DO_PRZEGLADU
    assert zrodlo_rcb.wpisy.exclude(pk=wrazliwy.pk).get().status_przegladu == status_zwyklego
    assert zrodlo_rcb.wpisy.get(pk=wrazliwy.pk).klasa == Klasa.WRAZLIWY


@pytest.mark.parametrize("stan_archiwum", [
    {"strona": 1, "stron": 1, "karty": [], "zakonczone": True, "wersja_parsera": "3"},
    {"strona": 1, "stron": 1, "karty": [], "zakonczone": True},  # zapisane przed wprowadzeniem znacznika wersji
    {"strona": 2, "stron": 5, "karty": [], "wersja_parsera": "3"},  # przejście w połowie
])
def test_r38c_archiwum_zapisane_starszym_parserem_jest_czytane_od_nowa(monkeypatch, zrodlo_rcb, stan_archiwum):
    adres = link_rcb("10")
    podstaw_siec(monkeypatch, adres)
    parser_v3(monkeypatch)
    rcb.ArchiwumRCB(zrodlo_rcb).zbierz()
    rcb.ArchiwumRCB(zrodlo_rcb).zbierz()
    assert zrodlo_rcb.wpisy.count() == 2 and {w.miejsce for w in zrodlo_rcb.wpisy.all()} == {STARE_MIEJSCE}
    zrodlo_rcb.refresh_from_db()
    zrodlo_rcb.stan_adaptera["archiwum"] = dict(stan_archiwum)
    zrodlo_rcb.save(update_fields=["stan_adaptera"])

    monkeypatch.undo()
    pobierz = podstaw_siec(monkeypatch, adres)
    rcb.ArchiwumRCB(zrodlo_rcb).zbierz()  # strona 1 listy
    rcb.ArchiwumRCB(zrodlo_rcb).zbierz()  # karta
    zrodlo_rcb.refresh_from_db()
    assert [w.args[0].split("?")[-1] for w in pobierz.call_args_list][:1] == ["page=1&size=10"]
    assert zrodlo_rcb.stan_adaptera["archiwum"]["wersja_parsera"] == "4" and zrodlo_rcb.stan_adaptera["archiwum"]["zakonczone"]
    sprawdz_odswiezone(zrodlo_rcb, 2)


def test_r38c_archiwum_zapisane_biezacym_parserem_nie_wraca(monkeypatch, zrodlo_rcb):
    zrodlo_rcb.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [], "zakonczone": True, "wersja_parsera": "4"}}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    pobierz = podstaw_siec(monkeypatch, link_rcb("10"))
    rcb.ArchiwumRCB(zrodlo_rcb).zbierz()
    assert pobierz.call_count == 0


@pytest.mark.parametrize("wersja,ponownie", [("3", True), (None, True), ("4", False)])
def test_r38c_polecenie_archiwum_wraca_do_kart_starszej_wersji(monkeypatch, zrodlo_rcb, wersja, ponownie):
    # archiwum RCB działa tylko przez to polecenie: stary znacznik „zakonczone” nie może go zatrzymać po zmianie parsera
    stan = {"strona": 1, "stron": 1, "karty": [], "zakonczone": True}
    if wersja:
        stan["wersja_parsera"] = wersja
    zrodlo_rcb.stan_adaptera = {"archiwum": stan}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    pobierz = podstaw_siec(monkeypatch, link_rcb("10"))
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    call_command("teraz_rcb_archiwum", limit=2)
    assert (pobierz.call_count == 2) is ponownie
    zrodlo_rcb.refresh_from_db()
    assert zrodlo_rcb.stan_adaptera["archiwum"].get("wersja_parsera") == ("4" if ponownie else wersja)
    assert zrodlo_rcb.wpisy.count() == (2 if ponownie else 0)
