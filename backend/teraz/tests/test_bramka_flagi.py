"""Bramka API „Teraz” przed publicznym startem (recenzja PR #38, P1-1).

Flaga TERAZ_PUBLICZNE (zmienna NEXT_PUBLIC_TERAZ_ENABLED) wyłączona: każdy punkt końcowy /api/teraz/* wpuszcza tylko ważny
podpisany podgląd (sc_preview_sig) albo personel, także gdy wspólny cache odpowiedzi jest rozgrzany. Reszta dostaje 404.
"""
import pytest
from django.core import signing
from django.urls import reverse

from news.preview import SALT, key_digest
from teraz.models import Klasa, Zdarzenie, Zrodlo
from teraz.urls import urlpatterns

pytestmark = pytest.mark.django_db


@pytest.fixture
def dane(zrob_zrodlo, zrob_wpis, settings):
    settings.PREVIEW_KEY = "test-tylko-klucz-podgladu"
    zrodlo = zrob_zrodlo("jawne", tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, tytul="marker-przed-startem")
    zdarzenie = Zdarzenie.objects.create(tytul_roboczy="Zdarzenie", pierwszy_wpis_at=wpis.opublikowano_at,
                                         ostatni_wpis_at=wpis.opublikowano_at)
    zdarzenie.wpisy.add(wpis)
    return zdarzenie


def adresy(zdarzenie):
    return [reverse(f"teraz:{w.name}", kwargs={"pk": zdarzenie.pk} if w.name == "zdarzenie" else {}) for w in urlpatterns]


def podpis():
    return signing.dumps(key_digest(), salt=SALT)


def test_flaga_wylaczona_anonim_dostaje_404_mimo_rozgrzanego_cache(client, dane, settings):
    lista = adresy(dane)
    assert len(lista) == 5
    for adres in lista:  # rozgrzanie wspólnego cache przy publicznym starcie
        assert client.get(adres).status_code == 200, adres
    settings.TERAZ_PUBLICZNE = False
    for adres in lista:
        odpowiedz = client.get(adres)
        assert odpowiedz.status_code == 404, adres
        assert "marker-przed-startem" not in odpowiedz.content.decode(), adres
        assert odpowiedz["Cache-Control"] == "private, no-store", adres
        assert client.get(adres, {"page": "1"}).status_code == 404, adres
        assert client.post(adres).status_code == 404, adres


def test_flaga_wylaczona_wazny_podglad_200_bez_wspolnego_cache(client, dane, settings, monkeypatch):
    settings.TERAZ_PUBLICZNE = False
    client.cookies["sc_preview_sig"] = podpis()
    from django.core.cache import caches
    odczyty = []
    teraz_cache = caches["teraz"]
    oryginal_get, oryginal_set = teraz_cache.get, teraz_cache.set

    def get(klucz, *a, **k):
        odczyty.append(klucz)
        return oryginal_get(klucz, *a, **k)

    def set_(klucz, *a, **k):
        odczyty.append(klucz)
        return oryginal_set(klucz, *a, **k)

    monkeypatch.setattr(teraz_cache, "get", get)
    monkeypatch.setattr(teraz_cache, "set", set_)
    for adres in adresy(dane):
        odpowiedz = client.get(adres)
        assert odpowiedz.status_code == 200, adres
        assert odpowiedz["Cache-Control"] == "private, no-store", adres
        assert "Cookie" in odpowiedz["Vary"], adres
    assert "marker-przed-startem" in client.get(reverse("teraz:wpisy")).content.decode()
    # odpowiedzi z podglądu ani nie czytają, ani nie zasilają wspólnego cache odpowiedzi
    assert odczyty  # throttling dalej używa tego aliasu, więc podmiana działa
    assert not [klucz for klucz in odczyty if str(klucz).startswith("api:")]


@pytest.mark.parametrize("ciasteczko", ["zly-podpis", "", signing.dumps("inny-skrot", salt=SALT)])
def test_flaga_wylaczona_zly_podpis_404(client, dane, settings, ciasteczko):
    settings.TERAZ_PUBLICZNE = False
    client.cookies["sc_preview_sig"] = ciasteczko
    client.cookies["sc_preview"] = "1"
    for adres in adresy(dane):
        assert client.get(adres).status_code == 404, adres


def test_flaga_wylaczona_podglad_bez_klucza_serwera_404(client, dane, settings):
    cookie = podpis()
    settings.TERAZ_PUBLICZNE = False
    settings.PREVIEW_KEY = ""
    client.cookies["sc_preview_sig"] = cookie
    assert client.get(reverse("teraz:wpisy")).status_code == 404


def test_flaga_wylaczona_personel_200_zwykly_uzytkownik_404(client, dane, settings, django_user_model):
    settings.TERAZ_PUBLICZNE = False
    zwykly = django_user_model.objects.create_user("czytelnik", password="x")
    client.force_login(zwykly)
    assert client.get(reverse("teraz:wpisy")).status_code == 404
    personel = django_user_model.objects.create_user("redakcja", password="x", is_staff=True)
    client.force_login(personel)
    for adres in adresy(dane):
        odpowiedz = client.get(adres)
        assert odpowiedz.status_code == 200, adres
        assert odpowiedz["Cache-Control"] == "private, no-store", adres


def test_zly_naglowek_uwierzytelnienia_tez_daje_404(client, dane, settings):
    settings.TERAZ_PUBLICZNE = False
    assert client.get(reverse("teraz:wpisy"), HTTP_AUTHORIZATION="Basic ???").status_code == 404


def test_flaga_wlaczona_anonim_200(client, dane, settings):
    settings.TERAZ_PUBLICZNE = True
    for adres in adresy(dane):
        odpowiedz = client.get(adres)
        assert odpowiedz.status_code == 200, adres
        assert odpowiedz["Cache-Control"] == "no-store", adres


@pytest.mark.parametrize("wartosc,oczekiwana", [("true", True), ("", False), ("false", False), ("1", False), ("True", False)])
def test_flaga_czyta_te_sama_zmienna_co_frontend(monkeypatch, wartosc, oczekiwana):
    import environ
    monkeypatch.setenv("NEXT_PUBLIC_TERAZ_ENABLED", wartosc)
    assert (environ.Env()("NEXT_PUBLIC_TERAZ_ENABLED", default="") == "true") is oczekiwana
    from pathlib import Path
    ustawienia = (Path(__file__).resolve().parents[2] / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'TERAZ_PUBLICZNE = env("NEXT_PUBLIC_TERAZ_ENABLED", default="") == "true"' in ustawienia
