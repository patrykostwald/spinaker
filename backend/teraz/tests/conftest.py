import socket
from uuid import uuid4

import pytest
from django.core.cache import caches
from django.utils import timezone

from teraz.models import Pobranie, Warstwa, Wpis, Zrodlo


@pytest.fixture(autouse=True)
def offline(settings, tmp_path, monkeypatch):
    def zakaz_sieci(*args, **kwargs):
        raise AssertionError("Test Teraz próbował się połączyć z siecią.")

    monkeypatch.setattr(socket, "getaddrinfo", zakaz_sieci)
    monkeypatch.setattr(socket.socket, "connect", zakaz_sieci)
    settings.CACHES = {
        alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": uuid4().hex}
        for alias in settings.CACHES
    }
    settings.TERAZ_ZRZUTY_ROOT = tmp_path / "zrzuty"
    # testy kontraktu API zakładają publiczny start; bramkę przed startem sprawdza test_bramka_flagi.py
    settings.TERAZ_PUBLICZNE = True
    yield
    caches["teraz"].clear()
    caches["default"].clear()


@pytest.fixture
def zrob_zrodlo():
    def zrob(slug="testowe", **zmiany):
        dane = dict(slug=slug, nazwa=slug, instytucja="Instytucja testowa", warstwa=Warstwa.RCB,
                    sposob_dostepu=Zrodlo.SposobDostepu.API, adres="https://test.example.org/komunikaty")
        dane.update(zmiany)
        return Zrodlo.objects.create(**dane)
    return zrob


@pytest.fixture
def zrob_wpis():
    def zrob(zrodlo, **zmiany):
        teraz = timezone.now()
        pobranie = Pobranie.objects.create(zrodlo=zrodlo, pobrano_at=teraz, status_http=200,
                                          hash_tresci="a" * 64, wersja_parsera="test")
        dane = dict(zrodlo=zrodlo, pobranie=pobranie, zewnetrzny_id=uuid4().hex, tytul="Komunikat testowy",
                    tresc="Treść komunikatu", link="https://test.example.org/wpis", opublikowano_at=teraz, pobrano_at=teraz)
        dane.update(zmiany)
        return Wpis.objects.create(**dane)
    return zrob
