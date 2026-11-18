import json
import logging
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from requests.structures import CaseInsensitiveDict
from sentry_sdk import get_client
from sentry_sdk.integrations.stdlib import StdlibIntegration
from sentry_sdk.utils import event_from_exception

from news.models import Source, SourceAccessInstruction
from scraper.access_gate import AccessDenied
from teraz import tasks, transport, zbieranie
from teraz.models import Klasa, Pobranie, StatusPrzegladu, Wpis, Zdarzenie, Zrodlo
from teraz.retencja import wyczysc_wpisy
from teraz.transport import OdpowiedzHTTP, _BezTelemetriiFIRMS
from teraz.zbieranie import Adapter, BladFormatu
from teraz.zrodla import emsc, gios, rcb
from teraz.zrodla.cert_pl import AdapterCERT
from teraz.zrodla.firms import AdapterFIRMS
from teraz.zrodla.gdacs import AdapterGDACS
from teraz.zrodla.imgw_hydro import AdapterIMGWHydro
from teraz.zrodla.imgw_meteo import AdapterIMGWMeteo
from teraz.zrodla.pse_osp import AdapterPSE
from teraz.zrodla.usgs import AdapterUSGS

FIXTURES = Path(__file__).with_name("fixtures")
SCOPE = SourceAccessInstruction.Scope.CONTENT
LISTA = "rcb-lista-2026-11-17.html"
PSE = "pse-komunikaty-osp-2026-11-17.atom"
DNI = ("03", "09", "10")


def odpowiedz(plik, status=200, **naglowki):
    dane = (FIXTURES / plik).read_bytes() if plik else b""
    return OdpowiedzHTTP(status, CaseInsensitiveDict(naglowki), dane, "utf-8")


def karta_rcb(dzien):
    return f"alert-rcb-2026-11-{dzien}-zagrozenie-z-powietrza.html"


def link_rcb(dzien):
    return rcb.adres_karty(f"/web/rcb/alert-rcb---zagrozenie-z-powietrza-{dzien}11")


def zrodlo_parsera(adres="https://example.org/"):
    return Zrodlo(adres=adres)


@pytest.mark.parametrize("klasa,plik,oczekiwane", [
    (AdapterIMGWMeteo, "imgw_meteo.json", 1),
    (AdapterIMGWHydro, "imgw_hydro.json", 1),
    (AdapterFIRMS, "firms.csv", 2),
    (AdapterUSGS, "usgs.json", 1),
    (AdapterGDACS, "gdacs.rss", 1),
    (AdapterCERT, "cert_pl.rss", 1),
    (AdapterPSE, PSE, None),
    (emsc.AdapterEMSC, "emsc.json", 1),
])
def test_kontrakt_parsera(klasa, plik, oczekiwane):
    adapter = klasa(zrodlo_parsera())
    wpisy = adapter.parsuj(odpowiedz(plik))
    assert len(wpisy) == oczekiwane if oczekiwane is not None else len(wpisy) > 1
    for wpis in wpisy:
        assert wpis["tytul"] and wpis["zewnetrzny_id"]
        assert wpis["opublikowano_at"].tzinfo is not None
        assert wpis["dokladnosc"] in Wpis.Dokladnosc.values
        assert wpis["link"].startswith(("https://", "http://"))
        assert "<script" not in wpis["tresc"] and "%s" not in wpis["tytul"]
    if klasa is AdapterGDACS:
        assert wpisy[0]["miejsce"] == "Czechy"
    if klasa in (AdapterPSE, AdapterCERT):
        assert all(wpis["tresc"] == "" for wpis in wpisy)
    with pytest.raises(BladFormatu):
        adapter.parsuj(odpowiedz("zmieniony_format.txt"))


def test_meteo_kody_powiatow_i_czyszczenie():
    wpis, = AdapterIMGWMeteo(zrodlo_parsera()).parsuj(odpowiedz("imgw_meteo.json"))
    assert wpis["teryt"] == ["0201", "0210"]
    assert wpis["dokladnosc"] == Wpis.Dokladnosc.POWIAT
    assert wpis["tresc"] == "Wiatr w porywach."
    assert wpis["dokladna_godzina_publikacji"] is True
    assert wpis["opublikowano_at"].hour == 9
    assert wpis["czas_zrodlowy_at"].hour == 10


def test_hydro_stan_wody():
    adapter = AdapterIMGWHydro(zrodlo_parsera())
    wpis, = adapter.parsuj_stany(odpowiedz("imgw_stany.json"))
    assert "203 cm" in wpis["tytul"]
    assert wpis["miejsce"] == "Stacja testowa, Rzeka testowa"
    with pytest.raises(BladFormatu, match="stanów wód"):
        adapter.parsuj_stany(odpowiedz("zmieniony_format.txt"))


@pytest.mark.parametrize("dzien,pierwsza,aktualizacja,kody,pewnosc", [
    ("03", None, (6, 49), ["06", "18"], 1),
    ("09", None, (22, 41), ["06", "20"], 0.5),
    ("10", (10, 20), (10, 55), ["06"], 0.5),
])
def test_rcb_karty(dzien, pierwsza, aktualizacja, kody, pewnosc):
    adapter = rcb.AdapterRCB(zrodlo_parsera(link_rcb(dzien)))
    alert, odwolanie = adapter.parsuj(odpowiedz(karta_rcb(dzien)))
    assert alert["tytul"] == f"Alert RCB - zagrożenie z powietrza ({dzien}.11)"
    assert alert["opublikowano_at"].day == int(dzien)
    assert alert["dokladna_godzina_publikacji"] is False
    assert "Oczekuj dalszych komunikatów." in alert["tresc"]
    assert alert["tresc"].count("Sytuacja jest monitorowana.") == 1
    assert "Brak zagrożenia na terenie Polski." in odwolanie["tresc"]
    assert odwolanie["status_zdarzenia"] == Zdarzenie.Status.ODWOLANE
    assert alert["zdarzenie_id"] == odwolanie["zdarzenie_id"]
    assert alert["teryt"] == odwolanie["teryt"] == kody
    # całe województwa (03.11) to potwierdzony zasięg; wybrane powiaty (09.11, 10.11) dają kod województwa tylko jako przybliżenie
    assert alert["pewnosc_lokalizacji"] == odwolanie["pewnosc_lokalizacji"] == pewnosc
    assert "lubelskiego" in alert["miejsce"]
    if dzien != "03":
        assert "włodawski" in alert["miejsce"]
    if pierwsza:
        assert (alert["czas_zrodlowy_at"].hour, alert["czas_zrodlowy_at"].minute) == pierwsza
    else:
        assert alert["czas_zrodlowy_at"] is None
    assert (odwolanie["czas_zrodlowy_at"].hour, odwolanie["czas_zrodlowy_at"].minute) == aktualizacja
    with pytest.raises(BladFormatu, match="RCB"):
        adapter.parsuj(odpowiedz("zmieniony_format.txt"))


def test_rcb_realna_lista_i_paginacja():
    linki, stron = rcb.parsuj_liste(odpowiedz(LISTA))
    strona2, _ = rcb.parsuj_liste(odpowiedz("rcb-lista-strona2-2026-11-17.html"))
    assert len(linki) == len(strona2) == 10 and stron > 2
    assert {link_rcb(dzien) for dzien in DNI}.issubset(linki)
    assert not set(linki).intersection(strona2)
    with pytest.raises(BladFormatu, match="listy kart"):
        rcb.parsuj_liste(odpowiedz("zmieniony_format.txt"))


def test_rcb_miejsce_zawiera_tylko_nazwy_jednostek():
    dane = """<article class="article-area__article">
        <h2>Alert RCB</h2><p class="event-date">10.11.2026</p>
        <div class="editor-content">
            <p>- lubelskie - powiaty: włodawski, Chełm, ul. Leśna 12</p>
            <p>- ul. Mazowieckiego 4</p>
            <p>gminy: Pruszków, Nowa Wieś; miasta: Warszawa</p>
            <p>Alert RCB pozostaje w mocy.</p>
        </div></article>""".encode()
    alert, = rcb.parsuj_karte(OdpowiedzHTTP(200, {}, dane, "utf-8"), link_rcb("10"))
    # jednostka dostaje województwo tylko z własnej linii (gminy z linii bez województwa zostają bez niego), typ gminy i miasta w nazwie
    assert set(alert["miejsce"].splitlines()) == {
        "lubelskie", "lubelskie: włodawski", "lubelskie: Chełm",
        "gmina Pruszków", "gmina Nowa Wieś", "miasto Warszawa",
    }
    assert "ul. Leśna 12" in alert["tresc"] and alert["teryt"] == ["06"]


@pytest.mark.django_db
def test_rcb_limit_zadan_etag_i_odstep_na_karte(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    pierwsza, druga = link_rcb("03"), link_rcb("09")
    bazowy = czas = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: czas)
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([pierwsza, druga] if odp.tresc == b"2" else [pierwsza], 1))
    pobierz = Mock(side_effect=[
        (OdpowiedzHTTP(200, {"ETag": '"1"'}, b"1", "utf-8"), SCOPE), (odpowiedz(karta_rcb("03"), ETag='"k1"'), SCOPE),
        (odpowiedz(None, 304), SCOPE),
        (OdpowiedzHTTP(200, {"ETag": '"2"'}, b"2", "utf-8"), SCOPE), (odpowiedz(karta_rcb("09"), ETag='"k2"'), SCOPE),
        (odpowiedz(None, 304), SCOPE),
        (odpowiedz(None, 304), SCOPE), (odpowiedz(None, 304), SCOPE),
    ])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    for minuty, oczekiwane in [
        (0, [rcb.LISTA, pierwsza]),
        (1, [rcb.LISTA]),
        (2, [rcb.LISTA, druga]),
        (9, [rcb.LISTA]),
        (10, [rcb.LISTA, pierwsza]),
    ]:
        czas = bazowy + timedelta(minutes=minuty)
        start = pobierz.call_count
        rcb.AdapterRCB(zrodlo).zbierz()
        assert [wywolanie.args[0] for wywolanie in pobierz.call_args_list[start:]] == oczekiwane
    assert pobierz.call_args_list[2].args[1] == {"If-None-Match": '"1"'}
    assert pobierz.call_args_list[6].args[1] == {"If-None-Match": '"2"'}
    assert pobierz.call_args_list[7].args[1] == {"If-None-Match": '"k1"'}


@pytest.mark.django_db
def test_rcb_blad_karty_przesuwa_kolejke(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    pierwsza, druga = link_rcb("03"), link_rcb("09")
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([pierwsza, druga], 1))
    pobierz = Mock(side_effect=[
        (odpowiedz(LISTA, ETag='"lista"'), SCOPE), (odpowiedz(None, 404), SCOPE),
        (odpowiedz(None, 304), SCOPE), (odpowiedz(karta_rcb("09")), SCOPE),
    ])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    assert rcb.AdapterRCB(zrodlo).zbierz().status_http == 404
    zrodlo.refresh_from_db()
    assert zrodlo.stan_adaptera["bledy_kolejki"] == 1 and zrodlo.kolejne_bledy == 1
    assert rcb.AdapterRCB(zrodlo).zbierz().status_http == 200
    assert [wywolanie.args[0] for wywolanie in pobierz.call_args_list] == [rcb.LISTA, pierwsza, rcb.LISTA, druga]


@pytest.mark.django_db
def test_rcb_usunieta_aktualizacja_nie_wraca_po_przesunieciu(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    adres = link_rcb("10")
    zrodlo.stan_adaptera = {"archiwum": {"strona": 1, "stron": 2, "karty": [adres]}}
    zrodlo.save(update_fields=["stan_adaptera"])
    pierwsza = b"<h3>Aktualizacja 10:55</h3><p>Komunikat testowy pierwszej aktualizacji.</p>"
    druga = b"<h3>Aktualizacja 10:55</h3><p>Komunikat testowy drugiej aktualizacji.</p>"

    def karta(aktualizacje):
        tresc = (b'<article class="article-area__article"><h2>Alert RCB</h2>'
                 b'<div class="event-date">10.11.2026</div><div class="editor-content">'
                 b'<p>Pierwszy komunikat</p>' + aktualizacje + b'</div></article>')
        return OdpowiedzHTTP(200, {}, tresc, "utf-8"), SCOPE

    pobierz = Mock(side_effect=[karta(pierwsza + druga), karta(druga + pierwsza)])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    rcb.ArchiwumRCB(zrodlo).zbierz()
    usuwany = zrodlo.wpisy.filter(tresc__contains="drugiej aktualizacji")
    assert wyczysc_wpisy(usuwany, "Żądanie usunięcia danych.") == 1
    zrodlo.refresh_from_db()
    zrodlo.stan_adaptera["archiwum"]["karty"] = [adres]
    zrodlo.save(update_fields=["stan_adaptera"])
    rcb.ArchiwumRCB(zrodlo).zbierz()
    assert zrodlo.wpisy.count() == 3
    assert not usuwany.exists()
    assert zrodlo.wpisy.filter(tresc__contains="pierwszej aktualizacji").count() == 1


@pytest.mark.django_db
def test_powtorka_rcb_wspolny_zapis_i_walidatory(monkeypatch, client):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    oczekiwane = {link_rcb(dzien): karta_rcb(dzien) for dzien in DNI}
    pobierane = {}

    def pobierz(self, adres, naglowki):
        nazwa = LISTA if adres == rcb.LISTA else oczekiwane[adres]
        etag = f'"{nazwa}"'
        if adres in pobierane:
            assert naglowki == {"If-None-Match": etag}
            return odpowiedz(None, 304), SCOPE
        assert not naglowki
        pobierane[adres] = True
        return odpowiedz(nazwa, ETag=etag), SCOPE

    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    parsuj = rcb.parsuj_liste

    def lista_trzech(odp):
        lista, stron = parsuj(odp)
        return [link for link in lista if link in oczekiwane], stron

    monkeypatch.setattr(rcb, "parsuj_liste", lista_trzech)
    for _ in range(4):
        rcb.AdapterRCB(zrodlo).zbierz()
    assert Wpis.objects.filter(zrodlo=zrodlo).count() == 6
    assert Zdarzenie.objects.filter(zrodlo_automatu=zrodlo).count() == 3
    for zdarzenie in Zdarzenie.objects.filter(zrodlo_automatu=zrodlo):
        assert zdarzenie.status == Zdarzenie.Status.ODWOLANE and zdarzenie.przygotowane_automatycznie
        assert zdarzenie.wpisy.count() == 2
    assert zrodlo.pobrania.filter(status_http=304).count() == 3
    assert zrodlo.pobrania.count() == 7
    assert not Wpis.objects.publiczne().filter(zrodlo=zrodlo).exists()
    zdarzenie = Zdarzenie.objects.filter(zrodlo_automatu=zrodlo).first()
    assert client.get(reverse("teraz:zdarzenia")).json()["count"] == 0
    assert client.get(reverse("teraz:zdarzenie", args=[zdarzenie.pk])).status_code == 404


@pytest.mark.django_db
def test_rcb_postep_archiwum(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    zrodlo.zrodlo_dostepu = Source.objects.create(name="Katalog RCB")
    zrodlo.save(update_fields=["zrodlo_dostepu"])
    adres = link_rcb("03")
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([adres], 1))
    mock = Mock(side_effect=[(odpowiedz(LISTA), SCOPE), (odpowiedz(karta_rcb("03")), SCOPE)])
    monkeypatch.setattr(Adapter, "pobierz", mock)
    rcb.ArchiwumRCB(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert zrodlo.stan_adaptera["archiwum"]["karty"] == [adres]
    rcb.ArchiwumRCB(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert zrodlo.stan_adaptera["archiwum"]["zakonczone"]
    assert zrodlo.ostatnie_pobranie_at is None
    assert zrodlo.ostatnia_proba_archiwum_at is not None
    assert tasks.nalezne_zrodla().filter(pk=zrodlo.pk).exists()
    assert mock.call_args_list[0].args[0].endswith("?page=1&size=10")
    assert mock.call_args_list[1].args[0] == adres


@pytest.mark.django_db
def test_archiwum_rcb_pomija_niedostepna_karte(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    pierwsza, druga = link_rcb("03"), link_rcb("09")
    zrodlo.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [pierwsza, druga]}}
    zrodlo.save(update_fields=["stan_adaptera"])
    pobierz = Mock(side_effect=[(odpowiedz(None, 404), SCOPE), (odpowiedz(karta_rcb("09")), SCOPE)])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    call_command("teraz_rcb_archiwum", limit=2)
    zrodlo.refresh_from_db()
    assert zrodlo.stan_adaptera["archiwum"]["zakonczone"]
    assert zrodlo.stan_adaptera["bledy_kolejki"] == 1
    assert [wywolanie.args[0] for wywolanie in pobierz.call_args_list] == [pierwsza, druga]


@pytest.mark.django_db
def test_wersja_imgw_nie_znosi_wstrzymania_i_usuniecia(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="imgw_meteo")
    oryginal = odpowiedz("imgw_meteo.json")
    zmiana = OdpowiedzHTTP(200, {}, oryginal.tresc.replace(b"Wiatr w porywach.", b"Silniejsze porywy."), "utf-8")
    powtorka = OdpowiedzHTTP(200, {}, oryginal.tresc.replace(b"Wiatr w porywach.", b"Trzecia wersja."), "utf-8")
    monkeypatch.setattr(Adapter, "pobierz", Mock(side_effect=[(o, SCOPE) for o in (oryginal, zmiana, powtorka)]))
    adapter = AdapterIMGWMeteo(zrodlo)
    adapter.zbierz()
    wpis = zrodlo.wpisy.get()
    wpis.status_przegladu = StatusPrzegladu.WSTRZYMANY
    wpis.save(update_fields=["status_przegladu"])
    adapter.zbierz()
    wpis.refresh_from_db()
    assert wpis.tresc == "Silniejsze porywy."
    assert wpis.wersje[0]["tresc"] == "Wiatr w porywach."
    assert wpis.status_przegladu == StatusPrzegladu.WSTRZYMANY
    assert wpis.zdarzenia.get().status == Zdarzenie.Status.KOMUNIKAT_OFICJALNY
    assert wyczysc_wpisy(zrodlo.wpisy.all(), "Test usunięcia") == 1
    adapter.zbierz()
    wpis.refresh_from_db()
    assert wpis.usunieto_at and not wpis.wersje and not wpis.tresc
    assert zrodlo.wpisy.count() == 1


@pytest.mark.django_db
def test_stan_wody_nadpisuje_ostatni_pomiar_bez_historii(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="imgw_hydro")
    ostrzezenia = odpowiedz("imgw_hydro.json")
    pomiar = odpowiedz("imgw_stany.json")
    aktualny = pomiar.tresc.replace(b'"203"', b'"211"').replace(b"11:00:00", b"12:00:00")
    nowy = OdpowiedzHTTP(200, {}, aktualny, "utf-8")
    pobierz = Mock(side_effect=[(odp, SCOPE) for odp in (ostrzezenia, pomiar, ostrzezenia, nowy, ostrzezenia, pomiar)])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    for _ in range(3):
        AdapterIMGWHydro(zrodlo).zbierz()
    pomiar = zrodlo.wpisy.get(zewnetrzny_id="stan:101")
    assert "211 cm" in pomiar.tytul and pomiar.opublikowano_at.astimezone(rcb.WARSZAWA).hour == 12
    assert not pomiar.wersje
    assert zrodlo.wpisy.count() == 2


@pytest.mark.django_db
def test_gios_przejscia_kategorii_i_stan_partii(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="gios")
    zrodlo.tryb = Zrodlo.Tryb.PUBLICZNY
    zrodlo.save(update_fields=["tryb"])
    plik = odpowiedz("gios_indeksy.json")

    def pomiar(kategoria, godzina, ident=52):
        dane = json.loads(plik.tresc)
        rekord = dane["AqIndex"]
        rekord["Identyfikator stacji pomiarowej"] = ident
        rekord["Wartość indeksu"] = kategoria
        rekord["Data wykonania obliczeń indeksu"] = f"2026-11-17 {godzina}:00:00"
        return OdpowiedzHTTP(200, {}, json.dumps(dane).encode(), "utf-8")

    gios_emisja = iter([pomiar(4, "10"), pomiar(4, "11"), pomiar(5, "12"), pomiar(3, "13"), pomiar(4, "14")])

    def pobierz(self, url, naglowki):
        if "station/findAll" in url:
            return odpowiedz("gios_stacje.json"), SCOPE
        if url.endswith("/52"):
            return next(gios_emisja), SCOPE
        return pomiar(1, "10", 53), SCOPE

    assert len(gios.AdapterGIOS(zrodlo).parsuj_stacje(odpowiedz("gios_stacje.json"))[0]) == 2
    for parser in (gios.AdapterGIOS(zrodlo).parsuj_stacje, gios.AdapterGIOS(zrodlo).parsuj_indeksy):
        with pytest.raises(BladFormatu, match="GIOŚ"):
            parser(odpowiedz("zmieniony_format.txt"))
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    monkeypatch.setattr(gios.AdapterGIOS, "limit_zadan", 2)
    for godzina, kategoria in enumerate((4, 4, 5, 3, 4), start=10):
        adapter = gios.AdapterGIOS(zrodlo)
        adapter.zbierz()
        zrodlo.refresh_from_db()
        assert zrodlo.stan_adaptera["kolejka"] == ["53"]
        assert zrodlo.kontynuacja_at < timezone.now() + timedelta(minutes=2)
        adapter.zbierz()
        zrodlo.refresh_from_db()
        assert zrodlo.stan_adaptera["kolejka"] == []
        assert zrodlo.kontynuacja_at > timezone.now() + timedelta(minutes=55)
        aktualny = zrodlo.wpisy.get(zewnetrzny_id="indeks:52")
        assert aktualny.opublikowano_at.astimezone(rcb.WARSZAWA).hour == godzina
        assert zrodlo.stan_adaptera["indeksy"]["52"][1] == kategoria
        assert aktualny.pomiar_aktywny == (kategoria in (4, 5)) and not aktualny.wersje
        assert Wpis.objects.publiczne().filter(pk=aktualny.pk).exists() == (kategoria in (4, 5))
        if kategoria == 5:
            assert "bardzo zły" in aktualny.tytul
    assert zrodlo.wpisy.count() == 2
    assert (aktualny.szerokosc, aktualny.dlugosc) == (52.1, 21.1)


@pytest.mark.django_db
def test_gios_blad_stacji_nie_blokuje_nastepnej(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="gios")
    pomiar = odpowiedz("gios_indeksy.json")
    rekord = json.loads(pomiar.tresc)
    rekord["AqIndex"]["Identyfikator stacji pomiarowej"] = 53
    druga = OdpowiedzHTTP(200, {}, json.dumps(rekord).encode(), "utf-8")
    pobierz = Mock(side_effect=[
        (odpowiedz("gios_stacje.json"), SCOPE), (odpowiedz(None, 503), SCOPE), (druga, SCOPE),
    ])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    gios.AdapterGIOS(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert [wywolanie.args[0].rsplit("/", 1)[-1] for wywolanie in pobierz.call_args_list[1:]] == ["52", "53"]
    assert zrodlo.stan_adaptera["kolejka"] == []
    assert zrodlo.stan_adaptera["bledy_kolejki"] == 1 and zrodlo.kolejne_bledy == 1
    assert zrodlo.wpisy.get().zewnetrzny_id == "indeks:53"


@pytest.mark.django_db
def test_firms_bez_listy_obiektow_jest_nieznany_i_niepubliczny(monkeypatch, settings):
    zrodlo = Zrodlo.objects.get(slug="firms")
    zrodlo.tryb = Zrodlo.Tryb.PUBLICZNY
    zrodlo.save(update_fields=["tryb"])
    settings.TERAZ_FIRMS_OBIEKTY_WRAZLIWE = []
    monkeypatch.setattr(Adapter, "pobierz", Mock(return_value=(odpowiedz("firms.csv"), SCOPE)))
    AdapterFIRMS(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert zrodlo.stan_adaptera["ostrzezenie"] == "brak listy obiektów wrażliwych"
    assert set(zrodlo.wpisy.values_list("klasa", "status_przegladu")) == {(Klasa.NIEZNANA, StatusPrzegladu.DO_PRZEGLADU)}
    assert not zrodlo.wpisy.publiczne().exists()


@pytest.mark.django_db
@pytest.mark.parametrize("echo_w_kodowaniu", [False, True])
def test_firms_brak_klucza_i_maskowanie(monkeypatch, settings, caplog, echo_w_kodowaniu):
    zrodlo = Zrodlo.objects.get(slug="firms")
    settings.TERAZ_FIRMS_MAP_KEY = ""
    settings.TERAZ_FIRMS_OBIEKTY_WRAZLIWE = []
    siec = Mock()
    karta = Mock(endpoint=zrodlo.adres, minimum_interval_seconds=3,
                 allowed_scope=SourceAccessInstruction.Scope.SNAPSHOT)
    monkeypatch.setattr(AdapterFIRMS, "karta_dostepu", Mock(return_value=karta))
    monkeypatch.setattr(transport, "require_approved_instruction", Mock(return_value=karta))
    monkeypatch.setattr(transport, "pobierz_http", siec)
    assert AdapterFIRMS(zrodlo).zbierz().status_http is None
    zrodlo.refresh_from_db()
    assert zrodlo.ostatni_blad == "FIRMS: skonfiguruj TERAZ_FIRMS_MAP_KEY."
    assert zrodlo.stan_adaptera["ostrzezenie"] == "brak listy obiektów wrażliwych"
    siec.assert_not_called()

    klucz_testowy = "WYMYSLONY_KLUCZ_OFFLINE_123"
    settings.TERAZ_FIRMS_MAP_KEY = klucz_testowy
    settings.TERAZ_FIRMS_OBIEKTY_WRAZLIWE = [(52.1, 21.1)]
    siec.side_effect = [
        odpowiedz("firms.csv", ETag=klucz_testowy),
        OdpowiedzHTTP(200, {}, b"" if echo_w_kodowaniu else klucz_testowy.encode(),
                      klucz_testowy if echo_w_kodowaniu else "utf-8"),
    ]
    AdapterFIRMS(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert "poufne dane" in zrodlo.ostatni_blad
    assert "ostrzezenie" not in zrodlo.stan_adaptera
    assert Klasa.INFRASTRUKTURA in zrodlo.wpisy.values_list("klasa", flat=True)
    assert set(Zdarzenie.objects.filter(zrodlo_automatu=zrodlo).values_list("status", flat=True)) == {"zgloszone"}
    assert not zrodlo.pobrania.exclude(zrzut="").exists()
    for model in (Pobranie, Wpis, Zdarzenie, Zrodlo):
        assert klucz_testowy not in str(list(model.objects.values()))
    assert klucz_testowy not in caplog.text
    assert siec.call_count == 2 and all(klucz_testowy in call.args[0] for call in siec.call_args_list)


@pytest.mark.django_db
@pytest.mark.parametrize("status,naglowki", [(403, {}), (200, {"cf-mitigated": "challenge"})])
def test_wyzwanie_blokuje_nastepne_proby(status, naglowki, monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    siec = Mock(return_value=(odpowiedz(None, status, **naglowki), SCOPE))
    monkeypatch.setattr(Adapter, "pobierz", siec)
    assert rcb.AdapterRCB(zrodlo).zbierz().status_http == status
    zrodlo.refresh_from_db()
    assert zrodlo.blokada_dostepu and zrodlo.ostatni_blad
    assert rcb.AdapterRCB(zrodlo).zbierz() is None
    assert not tasks.nalezne_zrodla().filter(pk=zrodlo.pk).exists()
    siec.assert_called_once()


@pytest.mark.django_db
def test_emsc_tylko_karta_websocket_i_wspolny_zapis():
    zrodlo = Zrodlo.objects.get(slug="emsc")
    zrodlo.zrodlo_dostepu = Source.objects.create(name="EMSC test")
    zrodlo.save(update_fields=["zrodlo_dostepu"])
    assert not tasks.nalezne_zrodla().filter(pk=zrodlo.pk).exists()
    adapter = emsc.AdapterEMSC(zrodlo)
    with pytest.raises(AccessDenied):
        adapter.karta_dostepu(zrodlo.adres)
    SourceAccessInstruction.objects.create(
        source=zrodlo.zrodlo_dostepu, status=SourceAccessInstruction.Status.APPROVED,
        channel="websocket", endpoint=zrodlo.adres, allowed_scope=SCOPE,
        terms_url="https://www.seismicportal.eu/terms.html", evidence={"próbka": "test"},
        reviewed_by="Test", reviewed_at=timezone.now(), valid_until=timezone.now() + timedelta(days=1),
        daily_request_cap=100,
    )
    with pytest.raises(AccessDenied):
        adapter.karta_dostepu("wss://www.seismicportal.eu/fdsnws/event/1/query")
    wiadomosc = odpowiedz("emsc.json").tresc
    adapter.przyjmij(wiadomosc)
    adapter.przyjmij(wiadomosc)
    assert zrodlo.wpisy.count() == 1 and zrodlo.pobrania.count() == 2
    assert zrodlo.wpisy.get().wersje == []


@pytest.mark.django_db
def test_rejestr_i_atrybucja_w_api(client, zrob_wpis, django_capture_on_commit_callbacks):
    assert Zrodlo.objects.count() == 25
    assert not Zrodlo.objects.filter(tryb=Zrodlo.Tryb.PUBLICZNY).exists()
    assert set(Zrodlo.objects.filter(tryb=Zrodlo.Tryb.WYLACZONY).values_list("slug", flat=True)) == {
        "policja_poszukiwani", "kmzb", "gddkia_kpd", "gddkia_mapa", "notam",
    }
    assert Zrodlo.objects.get(slug="plk").redystrybucja_pro == "deny"
    assert Zrodlo.objects.get(slug="imgw_hydro").rekomendowany_tryb == Zrodlo.Tryb.WEWNETRZNY
    cert = Zrodlo.objects.get(slug="cert_pl")
    zrob_wpis(cert, klasa=Klasa.ZWYKLY)
    assert client.get(reverse("teraz:wpisy")).json()["count"] == 0
    assert all(not w["atrybucja"] for w in client.get(reverse("teraz:warstwy")).json())
    with django_capture_on_commit_callbacks(execute=True):
        cert.tryb = Zrodlo.Tryb.PUBLICZNY
        cert.save(update_fields=["tryb"])
    wpis, = client.get(reverse("teraz:wpisy")).json()["results"]
    assert wpis["atrybucja"] == cert.atrybucja
    warstwa = next(w for w in client.get(reverse("teraz:warstwy")).json() if w["warstwa"] == cert.warstwa)
    assert warstwa["atrybucja"] == [cert.atrybucja]
    assert warstwa["zrodla"][0]["atrybucja"] == cert.atrybucja


@pytest.mark.django_db
def test_transport_firms_maskuje_sciezke_w_logu(monkeypatch, settings, caplog):
    zrodlo = Zrodlo.objects.get(slug="firms")
    klucz_testowy = "WYMYSLONY_KLUCZ_OFFLINE_456"
    settings.TERAZ_FIRMS_MAP_KEY = klucz_testowy
    karta = Mock(endpoint=zrodlo.adres, minimum_interval_seconds=3, allowed_scope=SCOPE)
    monkeypatch.setattr(AdapterFIRMS, "karta_dostepu", lambda self, adres: karta)
    monkeypatch.setattr(transport, "require_approved_instruction", Mock(return_value=karta))
    monkeypatch.setattr(zbieranie, "reserve_daily_fetch_budget", lambda karta: True)
    monkeypatch.setattr(zbieranie, "sleep", lambda sekundy: None)
    logger = logging.getLogger("urllib3.connectionpool")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        def siec(adres, naglowki, *, minimalny_odstep, przed_zadaniem):
            przed_zadaniem()
            assert klucz_testowy in adres
            assert isinstance(get_client(), _BezTelemetriiFIRMS)
            assert get_client().get_integration(StdlibIntegration) is None
            logger.debug("Pobrano %s", adres)
            return odpowiedz("firms.csv")

        monkeypatch.setattr(transport, "pobierz_http", siec)
        AdapterFIRMS(zrodlo).zbierz()
    assert "Pobrano https://" in caplog.text and "/***/" in caplog.text
    assert klucz_testowy not in caplog.text
    assert zrodlo.pobrania.count() == 2


@pytest.mark.django_db
def test_firms_wyjatek_zbierania_bez_klucza_w_zdarzeniu_sentry(monkeypatch, settings):
    zrodlo = Zrodlo.objects.get(slug="firms")
    zrodlo.zrodlo_dostepu = Source.objects.create(name="FIRMS test")
    zrodlo.save(update_fields=["zrodlo_dostepu"])
    SourceAccessInstruction.objects.create(
        source=zrodlo.zrodlo_dostepu, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API, endpoint=zrodlo.adres, allowed_scope=SCOPE,
        terms_url="https://firms.modaps.eosdis.nasa.gov/", evidence={"próbka": "test"},
        reviewed_by="Test", reviewed_at=timezone.now(), valid_until=timezone.now() + timedelta(days=1),
        daily_request_cap=10, allowed_path_patterns=["/api/area/csv/{token}/VIIRS_NOAA20_NRT/14.0,48.9,24.2,55.0/{int}"],
    )
    klucz_testowy = "WYMYSLONY_KLUCZ_OFFLINE_SENTRY"
    settings.TERAZ_FIRMS_MAP_KEY = klucz_testowy
    zdarzenia = []
    adresy = []
    zapisz_blad = AdapterFIRMS._zapisz_blad

    def siec(adres, naglowki, **opcje):
        adresy.append(adres)
        raise RuntimeError(adres)

    def przechwyc(adapter, cykl, exc):
        event, _ = event_from_exception(exc)
        zdarzenia.append(event)
        return zapisz_blad(adapter, cykl, exc)

    monkeypatch.setattr(transport, "pobierz_http", siec)
    monkeypatch.setattr(AdapterFIRMS, "_zapisz_blad", przechwyc)
    AdapterFIRMS(zrodlo).zbierz()
    adres, = adresy
    assert klucz_testowy in adres
    zdarzenie, = zdarzenia
    assert klucz_testowy not in json.dumps(zdarzenie, ensure_ascii=False)
    wyjatek, = zdarzenie["exception"]["values"]
    assert wyjatek["type"] == "BladPobrania"
    assert any(ramka["function"] == "zbierz" and "vars" in ramka for ramka in wyjatek["stacktrace"]["frames"])


@pytest.mark.django_db
def test_firms_pelny_adres_podlega_konkretniejszej_odmowie_dostepu(monkeypatch, settings):
    zrodlo = Zrodlo.objects.get(slug="firms")
    zrodlo.zrodlo_dostepu = Source.objects.create(name="FIRMS test")
    zrodlo.save(update_fields=["zrodlo_dostepu"])
    SourceAccessInstruction.objects.create(
        source=zrodlo.zrodlo_dostepu, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API, endpoint=zrodlo.adres, allowed_scope=SCOPE,
        terms_url="https://firms.modaps.eosdis.nasa.gov/", evidence={"próbka": "test"},
        reviewed_by="Test", reviewed_at=timezone.now(), valid_until=timezone.now() + timedelta(days=1),
        daily_request_cap=10,
    )
    klucz_testowy = "WYMYSLONY_KLUCZ_OFFLINE_BRAMKA"
    settings.TERAZ_FIRMS_MAP_KEY = klucz_testowy
    SourceAccessInstruction.objects.create(
        version=2, source=zrodlo.zrodlo_dostepu, status=SourceAccessInstruction.Status.SUSPENDED,
        channel=SourceAccessInstruction.Channel.API, endpoint=f"{zrodlo.adres}/{klucz_testowy}",
    )
    siec = Mock()
    monkeypatch.setattr(transport, "pobierz_http", siec)
    AdapterFIRMS(zrodlo).zbierz()
    siec.assert_not_called()
    zrodlo.refresh_from_db()
    assert zrodlo.ostatni_blad == "AccessDenied"
