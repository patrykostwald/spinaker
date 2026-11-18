import json
import socket
from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest
from billiard.exceptions import SoftTimeLimitExceeded
from django.core.cache import caches
from django.urls import reverse
from django.utils import timezone
from requests import Response

from news.models import Source, SourceAccessInstruction, SourceDailyFetchBudget
from teraz import tasks, transport
from teraz.cache import GENERACJA
from teraz.models import Klasa, Pobranie, StatusPrzegladu, Wpis, Zrodlo
from teraz.retencja import wyczysc_wpisy
from teraz.zbieranie import Adapter, BladFormatu


def odpowiedz(status, tresc=b"", **naglowki):
    response = Response()
    response.status_code = status
    response.headers.update(naglowki)
    response._content = tresc
    response._content_consumed = True
    return response


@pytest.fixture
def publiczny_dns(monkeypatch):
    dns = Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(transport.socket, "getaddrinfo", dns)
    return dns


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.1", "169.254.9.1", "[::1]", "prywatny.example.org"])
def test_ssrf_blokuje_lokalne_adresy_i_dns(host, monkeypatch):
    dns = Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443))])
    wyslij = Mock()
    monkeypatch.setattr(transport.socket, "getaddrinfo", dns)
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    with pytest.raises(transport.BladPobrania):
        transport.pobierz_http(f"https://{host}/komunikaty")
    wyslij.assert_not_called()
    assert dns.call_count == (1 if host.startswith("prywatny") else 0)


@pytest.mark.parametrize("adres", ["file:///tmp/test", "https://test.example.org:81/", "https://test.example.org/%2e%2e/inne"])
def test_niedozwolony_adres(adres):
    with pytest.raises(transport.BladPobrania):
        transport.pobierz_http(adres)


@pytest.mark.parametrize("naglowek", [False, True])
def test_limit_rozmiaru(publiczny_dns, monkeypatch, naglowek):
    dane = odpowiedz(200, b"012345678")
    if naglowek:
        dane.headers["Content-Length"] = "9"
        dane.iter_content = Mock(side_effect=AssertionError("Nie powinno czytać zbyt długiej odpowiedzi."))
    monkeypatch.setattr(transport, "LIMIT_ROZMIARU", 8)
    monkeypatch.setattr(transport.HTTPAdapter, "send", Mock(return_value=dane))
    with pytest.raises(transport.BladPobrania, match="limit rozmiaru") as blad:
        transport.pobierz_http("https://test.example.org/komunikaty")
    assert blad.value.status_http == 200


def test_przypiety_https_odstep_i_brak_przekierowania(publiczny_dns, monkeypatch):
    wyslij = Mock(return_value=odpowiedz(302, Location="https://nastepny.example.org/"))
    cfg = Mock(wraps=transport.HTTPAdapter.init_poolmanager)

    def init(adapter, *args, **kwargs):
        return cfg(adapter, *args, **kwargs)

    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    monkeypatch.setattr(transport.HTTPAdapter, "init_poolmanager", init)
    przed = Mock()
    assert transport.pobierz_http("https://test.example.org/komunikaty", przed_zadaniem=przed).status == 302
    with pytest.raises(transport.LimitHosta):
        transport.pobierz_http("https://test.example.org/inne", przed_zadaniem=przed)
    wyslij.assert_called_once()
    przed.assert_called_once()
    req = wyslij.call_args.args[0]
    assert urlsplit(req.url).hostname == "93.184.216.34"
    assert req.headers["Host"] == "test.example.org"
    assert req.headers["User-Agent"] == transport.USER_AGENT
    assert wyslij.call_args.kwargs["verify"] is True
    assert wyslij.call_args.kwargs["proxies"] == {}
    assert cfg.call_args.kwargs["server_hostname"] == cfg.call_args.kwargs["assert_hostname"] == "test.example.org"


class ParserTestowy(Adapter):
    def parsuj(self, odpowiedz):
        return [dict(zewnetrzny_id="ten-sam", tytul="Komunikat", tresc=odpowiedz.tresc.decode(),
                     link="https://test.example.org/jeden", opublikowano_at=timezone.now(), klasa=Klasa.ZWYKLY)]


@pytest.mark.django_db
@pytest.mark.parametrize("klasa", [Klasa.WRAZLIWY, Klasa.NIEZNANA])
@pytest.mark.parametrize("zmiana", [
    {"tresc": "Sprostowanie"},
    {"teryt": ["14"]},
    {"szerokosc": 52, "dlugosc": 21},
    {"bbox": [20, 51, 22, 53]},
    {"dokladnosc": Wpis.Dokladnosc.WOJEWODZTWO},
])
def test_zmieniony_wpis_wymaga_ponownego_przegladu(zrob_zrodlo, zrob_wpis, monkeypatch, klasa, zmiana):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=klasa, status_przegladu=StatusPrzegladu.DOPUSZCZONY,
                     przeglad_zmiana_at=timezone.now())
    dane = {pole: getattr(wpis, pole) for pole in ("zewnetrzny_id", "tytul", "tresc", "link", "klasa", "opublikowano_at")}
    monkeypatch.setattr(Adapter, "pobierz", Mock(return_value=(
        transport.OdpowiedzHTTP(200, {}, b"wersja", "utf-8"), SourceAccessInstruction.Scope.CONTENT,
    )))
    monkeypatch.setattr(ParserTestowy, "parsuj", lambda self, odp: [{**dane, **zmiana}])
    assert Wpis.objects.publiczne().filter(pk=wpis.pk).exists()
    ParserTestowy(zrodlo).zbierz()
    wpis.refresh_from_db()
    assert wpis.klasa == klasa
    assert wpis.status_przegladu == StatusPrzegladu.DO_PRZEGLADU and wpis.przeglad_zmiana_at is None
    assert not Wpis.objects.publiczne().filter(pk=wpis.pk).exists()


@pytest.mark.django_db
def test_zwykly_wpis_z_zaznaczona_dokladnoscia_i_ograniczona_historia(zrob_zrodlo, zrob_wpis, monkeypatch):
    zrodlo = zrob_zrodlo()
    wpis = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, wersje=[{"tresc": str(n)} for n in range(25)])
    dane = {pole: getattr(wpis, pole) for pole in ("zewnetrzny_id", "tytul", "tresc", "link", "klasa", "opublikowano_at")}
    monkeypatch.setattr(Adapter, "pobierz", Mock(return_value=(
        transport.OdpowiedzHTTP(200, {}, b"wersja", "utf-8"), SourceAccessInstruction.Scope.CONTENT,
    )))
    monkeypatch.setattr(ParserTestowy, "parsuj", lambda self, odp: [
        dict(dane, szerokosc=52, dlugosc=21, dokladnosc=Wpis.Dokladnosc.PUNKT),
    ])
    ParserTestowy(zrodlo).zbierz()
    wpis.refresh_from_db()
    assert wpis.klasa == Klasa.ZWYKLY
    assert len(wpis.wersje) == 20 and wpis.wersje[0]["tresc"] == "6"
    assert wpis.wersje[-1]["zwiekszono_dokladnosc"] is True
    assert wpis.wersje[-1]["dokladnosc"] == Wpis.Dokladnosc.BRAK


def test_gleboki_json_jest_bledem_formatu():
    odp = transport.OdpowiedzHTTP(200, {}, b"[" * 5000 + b"]" * 5000, "utf-8")
    dekoder = json.JSONDecoder()
    dekoder.scan_once = json.scanner.py_make_scanner(dekoder)
    with pytest.raises(BladFormatu) as blad:
        ParserTestowy(Zrodlo())._parsuj(lambda odpowiedz: dekoder.decode(odpowiedz.tresc.decode()), odp)
    assert isinstance(blad.value.__cause__, RecursionError)


@pytest.mark.django_db
@pytest.mark.parametrize("tresc,typ,blokada", [
    (b"<html><head><title>Access denied</title></head></html>", "text/html", True),
    (b"<html><head><title>Access denied</title></head></html>", "", True),
    (b"<rss><channel><title>Access denied</title></channel></rss>", "application/rss+xml", False),
    (b'<?xml version="1.0"?><atom:feed><title>Access denied</title></atom:feed>', "text/html", False),
])
def test_tytul_odmowy_tylko_w_html(zrob_zrodlo, monkeypatch, tresc, typ, blokada):
    zrodlo = zrob_zrodlo(sposob_dostepu=Zrodlo.SposobDostepu.RSS)
    naglowki = {"Content-Type": typ} if typ else {}
    monkeypatch.setattr(Adapter, "pobierz", Mock(return_value=(
        transport.OdpowiedzHTTP(200, naglowki, tresc, "utf-8"), SourceAccessInstruction.Scope.CONTENT,
    )))
    ParserTestowy(zrodlo).zbierz()
    zrodlo.refresh_from_db()
    assert zrodlo.blokada_dostepu is blokada
    assert zrodlo.wpisy.exists() is not blokada


@pytest.mark.django_db
@pytest.mark.parametrize("status", [502, None])
def test_blad_nastepnego_zadania_ma_wlasny_status(zrob_zrodlo, monkeypatch, status):
    class DwaZadania(ParserTestowy):
        limit_zadan = 2

        def przeprowadz(self, cykl):
            cykl.wykonaj(self.zrodlo.adres)
            cykl.wykonaj(f"{self.zrodlo.adres}/kolejny")

    zrodlo = zrob_zrodlo()
    monkeypatch.setattr(Adapter, "pobierz", Mock(side_effect=[
        (transport.OdpowiedzHTTP(200, {}, b"komunikat", "utf-8"), SourceAccessInstruction.Scope.CONTENT),
        transport.BladPobrania("Błąd drugiego żądania.", status_http=status),
    ]))
    assert DwaZadania(zrodlo).zbierz().status_http == status
    assert list(zrodlo.pobrania.order_by("pk").values_list("status_http", flat=True)) == [200, status]


@pytest.fixture
def z_karta(zrob_zrodlo):
    zrodlo = zrob_zrodlo(zrodlo_dostepu=Source.objects.create(name="Testowy katalog"))
    karta = SourceAccessInstruction.objects.create(
        source=zrodlo.zrodlo_dostepu, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API, endpoint=zrodlo.adres,
        allowed_scope=SourceAccessInstruction.Scope.SNAPSHOT, terms_url="https://test.example.org/zasady",
        evidence={"weryfikacja": "Test"}, reviewed_at=timezone.now(), reviewed_by="Testowy redaktor",
        valid_until=timezone.now() + timedelta(days=1), minimum_interval_seconds=3, daily_request_cap=10,
    )
    return zrodlo, karta


@pytest.mark.django_db
def test_hash_etag_304_zrzut_i_idempotencja(z_karta, publiczny_dns, monkeypatch, settings):
    zrodlo, karta = z_karta
    monkeypatch.setattr(transport, "_zarezerwuj_hosta", Mock())
    etag = '"wersja-1"'
    modyfikacja = "Tue, 17 Nov 2026 09:00:00 GMT"
    wyslij = Mock(side_effect=[
        odpowiedz(200, "Café  \r\nLinia\t\r\n".encode(), ETag=etag, **{"Last-Modified": modyfikacja}),
        odpowiedz(304),
        odpowiedz(200, "Cafe\u0301\nLinia\n".encode(), ETag='"wersja-2"'),
        odpowiedz(200, "Treść ma nową wersję".encode()),
    ])
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    adapter = ParserTestowy(zrodlo)
    pierwsze = adapter.zbierz()
    assert pierwsze.zrzut.storage.exists(pierwsze.zrzut.name)
    with pytest.raises(ValueError, match="publicznego adresu"):
        _ = pierwsze.zrzut.url
    wpis = Wpis.objects.get()
    wpis.status_przegladu = StatusPrzegladu.WSTRZYMANY
    wpis.save()
    drugie, trzecie, czwarte = (adapter.zbierz() for _ in range(3))

    assert [p.status_http for p in (pierwsze, drugie, trzecie, czwarte)] == [200, 304, 200, 200]
    assert pierwsze.hash_tresci == drugie.hash_tresci == trzecie.hash_tresci != czwarte.hash_tresci
    assert drugie.bez_zmian and trzecie.bez_zmian and not czwarte.bez_zmian
    assert not drugie.zrzut and not trzecie.zrzut
    assert czwarte.zrzut.name != pierwsze.zrzut.name
    assert len(list(settings.TERAZ_ZRZUTY_ROOT.glob("*.bin"))) == 2
    assert czwarte.wpisy_w_zrzucie.get() == wpis
    assert (Pobranie.objects.count(), Wpis.objects.count()) == (4, 1)
    assert Wpis.objects.get().status_przegladu == StatusPrzegladu.WSTRZYMANY
    assert SourceDailyFetchBudget.objects.get(instruction=karta).used == 4
    assert wyslij.call_args_list[1].args[0].headers["If-None-Match"] == etag
    assert wyslij.call_args_list[1].args[0].headers["If-Modified-Since"] == modyfikacja
    assert wyslij.call_args_list[2].args[0].headers["If-None-Match"] == etag
    zrodlo.refresh_from_db()
    assert zrodlo.ostatni_sukces_at == czwarte.pobrano_at
    assert zrodlo.ostatnie_pobranie_at and zrodlo.kolejne_bledy == 0


@pytest.mark.django_db
def test_brak_karty_blokuje_przed_dns(zrob_zrodlo, publiczny_dns, monkeypatch):
    wyslij = Mock()
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    zrodlo = zrob_zrodlo()
    pobranie = ParserTestowy(zrodlo).zbierz()
    assert pobranie.status_http is None and not pobranie.zrzut
    zrodlo.refresh_from_db()
    assert zrodlo.ostatni_blad == "AccessDenied" and zrodlo.kolejne_bledy == 1
    publiczny_dns.assert_not_called()
    wyslij.assert_not_called()


@pytest.mark.django_db
def test_karta_metadanych_i_wygasniecie_limitu(z_karta, publiczny_dns, monkeypatch):
    zrodlo, karta = z_karta
    karta.allowed_scope = SourceAccessInstruction.Scope.METADATA
    karta.daily_request_cap = 1
    karta.save()
    monkeypatch.setattr(transport, "_zarezerwuj_hosta", Mock())
    wyslij = Mock(return_value=odpowiedz(200, b"Surowa odpowiedz"))
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    assert not ParserTestowy(zrodlo).zbierz().zrzut
    assert Wpis.objects.get().tresc == ""
    assert ParserTestowy(zrodlo).zbierz().status_http is None
    wyslij.assert_called_once()


@pytest.mark.django_db
def test_blad_http_nie_zastepuje_walidatora_i_sukces_resetuje_licznik(z_karta, publiczny_dns, monkeypatch):
    zrodlo, _ = z_karta
    monkeypatch.setattr(transport, "_zarezerwuj_hosta", Mock())
    wyslij = Mock(side_effect=[odpowiedz(200, b"Komunikat", ETag='"wlasciwy"'),
                              odpowiedz(503, ETag='"blad"'), odpowiedz(304)])
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    adapter = ParserTestowy(zrodlo)
    poprzednie = adapter.zbierz()
    assert adapter.zbierz().status_http == 503
    zrodlo.refresh_from_db()
    assert zrodlo.kolejne_bledy == 1 and zrodlo.ostatni_sukces_at == poprzednie.pobrano_at
    assert adapter.zbierz().status_http == 304
    zrodlo.refresh_from_db()
    assert zrodlo.kolejne_bledy == 0 and not zrodlo.ostatni_blad
    assert wyslij.call_args.args[0].headers["If-None-Match"] == '"wlasciwy"'


@pytest.mark.django_db
def test_wolny_strumien_zapisuje_start_i_blad_miekkiego_limitu(z_karta, publiczny_dns, monkeypatch):
    zrodlo, _ = z_karta
    monkeypatch.setitem(tasks.ADAPTERY, zrodlo.slug, ParserTestowy)
    odpowiedz_http = odpowiedz(200)

    def wolny_strumien(chunk_size):
        assert chunk_size == 8 * 1024
        zrodlo.refresh_from_db()
        assert zrodlo.ostatnie_pobranie_at is not None and zrodlo.ostatni_sukces_at is None
        yield b"poczatek"
        raise SoftTimeLimitExceeded()

    odpowiedz_http.iter_content = wolny_strumien
    wyslij = Mock(return_value=odpowiedz_http)
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)

    tasks.zbierz_zrodlo(zrodlo.pk)
    start = zrodlo.ostatnie_pobranie_at
    zrodlo.refresh_from_db()
    assert zrodlo.ostatnie_pobranie_at == start and zrodlo.ostatni_sukces_at is None
    assert zrodlo.ostatni_blad == "SoftTimeLimitExceeded" and zrodlo.kolejne_bledy == 1
    assert not zrodlo.pobrania.get().zrzut
    assert not Wpis.objects.exists()
    assert wyslij.call_args.kwargs["timeout"] == (3, 8)
    assert caches["teraz"].get(f"zbieranie:zrodlo:{zrodlo.pk}") is None


@pytest.mark.django_db
def test_nowopobrany_wpis_uniewaznia_cache(
    client, z_karta, publiczny_dns, monkeypatch, django_capture_on_commit_callbacks,
):
    zrodlo, _ = z_karta
    zrodlo.tryb = Zrodlo.Tryb.PUBLICZNY
    zrodlo.save(update_fields=["tryb"])
    monkeypatch.setattr(transport.HTTPAdapter, "send", Mock(return_value=odpowiedz(200, b"Komunikat")))
    adres = reverse("teraz:wpisy")
    assert client.get(adres).json()["count"] == 0
    generacja = caches["teraz"].get(GENERACJA)
    with django_capture_on_commit_callbacks(execute=True):
        ParserTestowy(zrodlo).zbierz()
    assert caches["teraz"].get(GENERACJA) != generacja
    assert client.get(adres).json()["count"] == 1


@pytest.mark.django_db
def test_ponowne_pobranie_nie_przywraca_usunietego_wpisu_ani_zrzutu(z_karta, publiczny_dns, monkeypatch):
    zrodlo, _ = z_karta
    monkeypatch.setattr(transport, "_zarezerwuj_hosta", Mock())
    wyslij = Mock(side_effect=[odpowiedz(200, b"Pierwsza tresc"), odpowiedz(200, b"Zmieniona tresc")])
    monkeypatch.setattr(transport.HTTPAdapter, "send", wyslij)
    adapter = ParserTestowy(zrodlo)
    pierwsze = adapter.zbierz()
    wpis = Wpis.objects.get()
    assert wyczysc_wpisy(Wpis.objects.filter(pk=wpis.pk), "Żądanie usunięcia danych.") == 1
    drugie = adapter.zbierz()
    assert pierwsze.zrzut and not drugie.zrzut and not drugie.bez_zmian
    assert Wpis.objects.get().pk == wpis.pk
    assert not Wpis.objects.get().tresc
