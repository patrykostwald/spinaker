from datetime import timedelta
from itertools import product
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import caches
from django.urls import reverse
from django.utils import timezone
from redis.exceptions import ConnectionError, TimeoutError

from config import settings as ustawienia
from teraz.api import NIEPEWNOSC, StronicowanieTeraz, WpisyView
from teraz.cache import CZAS_CACHE, GENERACJA
from teraz.models import Klasa, StatusPrzegladu, Warstwa, Wpis, WylacznikKategorii, Zdarzenie, Zrodlo
from teraz.urls import urlpatterns

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("tryb,klasa,status,blokada", product(
    Zrodlo.Tryb.values, Klasa.values, StatusPrzegladu.values,
    ("brak", "nieaktywna", "warstwa", "klasa", "obie"),
))
def test_macierz_bramki(zrob_zrodlo, zrob_wpis, tryb, klasa, status, blokada):
    zrodlo = zrob_zrodlo(tryb=tryb)
    wpis = zrob_wpis(zrodlo, klasa=klasa, status_przegladu=status)
    if blokada in {"warstwa", "obie", "nieaktywna"}:
        WylacznikKategorii.objects.create(warstwa=zrodlo.warstwa, aktywny=blokada != "nieaktywna", powod="Test")
    if blokada in {"klasa", "obie", "nieaktywna"}:
        WylacznikKategorii.objects.create(klasa=klasa, aktywny=blokada != "nieaktywna", powod="Test")
    widoczny = (
        tryb == "publiczny" and (klasa == "zwykly" or status == "dopuszczony")
        and status != "wstrzymany" and blokada in {"brak", "nieaktywna"}
    )
    assert Wpis.objects.filter(pk=wpis.pk).publiczne().exists() is widoczny


def zdarzenie(tytul, *wpisy, **dane):
    teraz = timezone.now()
    zd = Zdarzenie.objects.create(tytul_roboczy=tytul, pierwszy_wpis_at=teraz, ostatni_wpis_at=teraz, **dane)
    zd.wpisy.add(*wpisy)
    return zd


def test_wszystkie_publiczne_endpointy_stosuja_bramke(client, zrob_zrodlo, zrob_wpis):
    publiczne = zrob_zrodlo("jawne", tryb=Zrodlo.Tryb.PUBLICZNY)
    wewnetrzne = zrob_zrodlo("wewnetrzne-marker")
    wyciszone = zrob_zrodlo("wyciszone", warstwa=Warstwa.IMGW_METEO, tryb=Zrodlo.Tryb.PUBLICZNY)
    WylacznikKategorii.objects.create(warstwa=wyciszone.warstwa, aktywny=True, powod="powod-marker")
    WylacznikKategorii.objects.create(klasa=Klasa.INFRASTRUKTURA, aktywny=True, powod="powod-klasa-marker")
    jawny = zrob_wpis(publiczne, klasa=Klasa.ZWYKLY, tytul="jawny-marker")
    ukryte = [
        zrob_wpis(wewnetrzne, klasa=Klasa.ZWYKLY, tytul="wewnetrzny-wpis-marker"),
        zrob_wpis(publiczne, klasa=Klasa.WRAZLIWY, tytul="wrazliwy-marker"),
        zrob_wpis(wyciszone, klasa=Klasa.ZWYKLY, tytul="wyciszony-marker"),
        zrob_wpis(publiczne, klasa=Klasa.INFRASTRUKTURA, status_przegladu=StatusPrzegladu.DOPUSZCZONY,
                  tytul="wyciszona-klasa-marker"),
    ]
    jawne_zdarzenie = zdarzenie("Jawne zdarzenie", jawny)
    ukryte_zdarzenia = [zdarzenie(wpis.tytul, jawny, wpis) for wpis in ukryte]
    ukryte_zdarzenia.extend(zdarzenie(wpis.tytul, wpis) for wpis in ukryte)
    zakazane = [wpis.tytul for wpis in ukryte] + [wewnetrzne.slug, "powod-marker", "powod-klasa-marker"]

    for wzorzec in urlpatterns:
        nazwa = f"teraz:{wzorzec.name}"
        kwargs = {"pk": jawne_zdarzenie.pk} if wzorzec.name == "zdarzenie" else {}
        adres = reverse(nazwa, kwargs=kwargs)
        parametry = {"od": (timezone.now() - timedelta(days=1)).isoformat(), "do": timezone.now().isoformat()} \
            if wzorzec.name == "os" else {}
        odpowiedz = client.get(adres, parametry)
        assert odpowiedz.status_code == 200, nazwa
        assert odpowiedz["Cache-Control"] == "no-store"
        assert all(tekst not in odpowiedz.content.decode() for tekst in zakazane), nazwa
        assert client.post(adres).status_code == 405
        if wzorzec.name == "zdarzenie":
            for ukryte_zdarzenie in ukryte_zdarzenia:
                assert client.get(reverse(nazwa, kwargs={"pk": ukryte_zdarzenie.pk})).status_code == 404

    assert client.get(reverse("teraz:wpisy")).json()["count"] == 1
    assert client.get(reverse("teraz:zdarzenia")).json()["count"] == 1
    warstwy = {w["warstwa"]: w for w in client.get(reverse("teraz:warstwy")).json()}
    assert warstwy[Warstwa.RCB]["liczba_wpisow_24h"] == 1
    assert warstwy[Warstwa.IMGW_METEO]["liczba_wpisow_24h"] == 0


def test_wylacznik_uniewaznia_rozgrzany_cache(client, zrob_zrodlo, zrob_wpis, django_capture_on_commit_callbacks):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY)
    zd = zdarzenie("Jawne zdarzenie", wpis)
    wpisy_url = reverse("teraz:wpisy")
    zd_url = reverse("teraz:zdarzenie", args=[zd.pk])
    assert client.get(wpisy_url).json()["count"] == 1
    assert client.get(zd_url).status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        WylacznikKategorii.objects.create(klasa=Klasa.ZWYKLY, aktywny=True, powod="Decyzja dyżuru")
    assert client.get(wpisy_url).json()["count"] == 0
    assert client.get(zd_url).status_code == 404


def test_potwierdzenie_wymaga_redaktora_i_dwoch_instytucji(zrob_zrodlo, zrob_wpis, django_user_model):
    pierwsze = zrob_zrodlo("a", tryb=Zrodlo.Tryb.PUBLICZNY)
    drugie = zrob_zrodlo("b", tryb=Zrodlo.Tryb.PUBLICZNY, instytucja="Druga instytucja")
    wpis = zrob_wpis(pierwsze, klasa=Klasa.ZWYKLY)
    drugi = zrob_wpis(drugie, klasa=Klasa.ZWYKLY)
    zd = zdarzenie("Potwierdzone", wpis, status=Zdarzenie.Status.POTWIERDZONE)
    assert not Zdarzenie.objects.publiczne().exists()
    zd.zweryfikowal = django_user_model.objects.create_user(username="redaktor")
    zd.zweryfikowano_at = timezone.now()
    zd.save()
    assert not Zdarzenie.objects.publiczne().exists()
    zd.wpisy.add(drugi)
    assert Zdarzenie.objects.publiczne().get() == zd


def test_filtry_i_uogolniona_lokalizacja(client, zrob_zrodlo, zrob_wpis):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    teraz = timezone.now()
    punkt = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, teryt=["0264011"], szerokosc=51.1, dlugosc=17.0)
    obszar = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, teryt=["1465011", "0264"], bbox=[16.5, 50.5, 17.0, 51.5])
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, teryt=["1402011"], opublikowano_at=teraz - timedelta(days=3))
    wojskowy = zrob_wpis(zrodlo, klasa=Klasa.WOJSKO_GRANICA, status_przegladu=StatusPrzegladu.DOPUSZCZONY,
                         teryt=["0264011"], szerokosc=51.1, dlugosc=17.0, bbox=[16.9, 51.0, 17.1, 51.2])
    adres = reverse("teraz:wpisy")
    params = {"warstwa": Warstwa.RCB, "od": (teraz - timedelta(days=1)).isoformat(),
              "do": (teraz + timedelta(minutes=1)).isoformat(), "teryt": "0264", "bbox": "16.95,51,17.05,51.2"}
    odpowiedz = client.get(adres, params)
    assert odpowiedz.status_code == 200
    assert {w["id"] for w in odpowiedz.json()["results"]} == {punkt.pk, obszar.pk}
    wojskowy_json = next(w for w in client.get(adres, {"teryt": "02"}).json()["results"] if w["id"] == wojskowy.pk)
    assert wojskowy_json["teryt"] == ["02"]
    assert wojskowy_json["dokladnosc"] == "wojewodztwo"
    assert all(wojskowy_json[p] is None for p in ("szerokosc", "dlugosc", "bbox"))
    assert all(w["id"] != wojskowy.pk for w in client.get(adres, {"teryt": "0264"}).json()["results"])
    for filtry in ({"teryt": "02%"}, {"bbox": "16,NaN,17,52"}, {"bbox": "17,50,16,51"},
                   {"warstwa": "błąd"}, {"od": "2026-11-18T00:00:00Z", "do": "2026-11-17T00:00:00Z"}):
        assert client.get(adres, filtry).status_code == 400


def test_stan_luka_blad_i_brak_ujawnienia_bledow(client, zrob_zrodlo):
    teraz = timezone.now()
    zrob_zrodlo("luka", tryb=Zrodlo.Tryb.PUBLICZNY, czestotliwosc_s=300,
               ostatnie_pobranie_at=teraz, ostatni_sukces_at=teraz - timedelta(minutes=11))
    zrob_zrodlo("blad", tryb=Zrodlo.Tryb.PUBLICZNY, warstwa=Warstwa.PSP, czestotliwosc_s=301,
               ostatnie_pobranie_at=teraz, ostatni_sukces_at=teraz - timedelta(minutes=6),
               ostatni_blad="blad-prywatny-marker", kolejne_bledy=1)
    zrob_zrodlo("swieze", tryb=Zrodlo.Tryb.PUBLICZNY, warstwa=Warstwa.SG,
               ostatnie_pobranie_at=teraz, ostatni_sukces_at=teraz - timedelta(minutes=4))
    odpowiedz = client.get(reverse("teraz:stan"))
    linie = {linia["warstwa"]: linia for linia in odpowiedz.json()["warstwy"]}
    for warstwa in (Warstwa.RCB, Warstwa.PSP):
        assert linie[warstwa]["komunikat"] == "nie mamy pewności, sprawdź Alert RCB i 112"
        assert linie[warstwa]["ostatnie_pobranie"] == f"ostatnie pobranie: {timezone.localtime(teraz):%H:%M}"
        assert linie[warstwa]["komunikaty"] == "komunikatów z 24 h: 0"
    assert linie[Warstwa.SG]["komunikat"] == ""
    assert odpowiedz.json()["informacja"] == "To nie jest strona urzędowa"
    assert all(slowo not in odpowiedz.content.decode().lower() for slowo in ("spokojnie", "bezpiecznie", "blad-prywatny-marker"))
    warstwy = {w["warstwa"]: w for w in client.get(reverse("teraz:warstwy")).json()}
    assert warstwy[Warstwa.RCB]["luka"] is True
    assert warstwy[Warstwa.PSP]["luka"] is False


@pytest.mark.parametrize(("interwal", "wiek", "luka"), [
    (3600, None, True),
    (3600, 7201, True),
    (3600, 7200, False),
    (60, 301, True),
    (60, 300, False),
])
def test_luka_przy_zatrzymanym_workerze(client, zrob_zrodlo, monkeypatch, interwal, wiek, luka):
    teraz = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: teraz)
    zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY, czestotliwosc_s=interwal,
               ostatni_sukces_at=None if wiek is None else teraz - timedelta(seconds=wiek))

    warstwa = next(w for w in client.get(reverse("teraz:warstwy")).json() if w["warstwa"] == Warstwa.RCB)
    linia = next(w for w in client.get(reverse("teraz:stan")).json()["warstwy"] if w["warstwa"] == Warstwa.RCB)
    assert warstwa["luka"] is warstwa["zrodla"][0]["luka"] is luka
    assert warstwa["blad"] is False
    assert linia["komunikat"] == (NIEPEWNOSC if luka else "")


def test_linia_stanu_liczy_komunikaty_z_24_godzin(client, zrob_zrodlo, zrob_wpis):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, opublikowano_at=timezone.now() - timedelta(hours=25))
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, opublikowano_at=timezone.now() - timedelta(hours=23))
    linia = next(w for w in client.get(reverse("teraz:stan")).json()["warstwy"] if w["warstwa"] == Warstwa.RCB)
    assert linia["ostatnie_pobranie"] == "brak w naszych danych"
    assert linia["komunikaty"] == "komunikatów z 24 h: 1"


def test_wylaczona_warstwa_ukrywa_zrodla_i_ich_swiezosc(
    client, zrob_zrodlo, zrob_wpis, django_capture_on_commit_callbacks,
):
    teraz = timezone.now()
    zrodlo = zrob_zrodlo("jawne-zrodlo", tryb=Zrodlo.Tryb.PUBLICZNY,
                         ostatnie_pobranie_at=teraz, ostatni_sukces_at=teraz, kolejne_bledy=1)
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY)
    adres = reverse("teraz:warstwy")
    assert b"jawne-zrodlo" in client.get(adres).content
    with django_capture_on_commit_callbacks(execute=True):
        WylacznikKategorii.objects.create(warstwa=zrodlo.warstwa, aktywny=True, powod="Decyzja dyżuru")
    odpowiedz = client.get(adres)
    assert b"jawne-zrodlo" not in odpowiedz.content
    warstwa = next(w for w in odpowiedz.json() if w["warstwa"] == zrodlo.warstwa)
    assert warstwa["wylaczona"] is True
    assert warstwa["zrodla"] == []
    assert warstwa["ostatnie_pobranie_at"] is warstwa["ostatni_sukces_at"] is None
    assert warstwa["luka"] is warstwa["blad"] is False
    assert warstwa["liczba_wpisow_24h"] == 0


def test_nieznana_klasa_ma_dokladnosc_powiatu(client, zrob_zrodlo, zrob_wpis):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=Klasa.NIEZNANA, status_przegladu=StatusPrzegladu.DOPUSZCZONY,
                     teryt=["0264011"], szerokosc=51.1, dlugosc=17.0, bbox=[16.9, 51.0, 17.1, 51.2])
    adres = reverse("teraz:wpisy")
    wynik, = client.get(adres, {"teryt": "0264"}).json()["results"]
    assert wynik["id"] == wpis.pk
    assert wynik["teryt"] == ["0264"]
    assert wynik["dokladnosc"] == "powiat"
    assert all(wynik[pole] is None for pole in ("szerokosc", "dlugosc", "bbox"))
    assert client.get(adres, {"teryt": "0264011"}).json()["count"] == 0
    assert client.get(adres, {"bbox": "16.9,51,17.1,51.2"}).json()["count"] == 0


def test_cache_swiezosc_wygasa_bez_zmiany_generacji(
    client, zrob_zrodlo, monkeypatch, django_capture_on_commit_callbacks,
):
    from django.core.cache.backends import locmem

    zegar = locmem.time.time()
    monkeypatch.setattr(locmem, "time", Mock(**{"time.return_value": zegar}))
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    adres = reverse("teraz:warstwy")
    odpowiedz = client.get(adres).json()
    cache = caches["teraz"]
    generacja = cache.get(GENERACJA)
    assert generacja
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        zrodlo.ostatni_sukces_at = timezone.now()
        zrodlo.ostatnie_pobranie_at = zrodlo.ostatni_sukces_at
        zrodlo.save(update_fields=["ostatnie_pobranie_at", "ostatni_sukces_at", "ostatni_blad", "kolejne_bledy"])
        zrodlo.kolejne_bledy = 1
        zrodlo.save()
    assert callbacks == []
    assert client.get(adres).json() == odpowiedz
    locmem.time.time.return_value = zegar + CZAS_CACHE + 1
    assert client.get(adres).json() != odpowiedz
    assert cache.get(GENERACJA) == generacja
    with django_capture_on_commit_callbacks(execute=True):
        zrodlo.tryb = Zrodlo.Tryb.WEWNETRZNY
        zrodlo.save(update_fields=["tryb"])
    assert cache.get(GENERACJA) != generacja


def test_cache_pomija_obce_parametry_i_zachowuje_filtry_oraz_strone(client, zrob_zrodlo, zrob_wpis, monkeypatch):
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY)
    zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY)
    adres = reverse("teraz:wpisy")
    monkeypatch.setattr(StronicowanieTeraz, "page_size", 1)
    pobierz = WpisyView.get_queryset
    wywolania = Mock()

    def obserwuj(view):
        wywolania()
        return pobierz(view)

    monkeypatch.setattr(WpisyView, "get_queryset", obserwuj)
    pierwsza = client.get(adres, {"warstwa": Warstwa.RCB, "smieci": "dowolna-wartosc", "page": "01"}).json()
    z_cache = client.get(adres, {"smieci": "inna-wartosc", "warstwa": Warstwa.RCB})
    assert z_cache.json() == pierwsza
    assert z_cache["Cache-Control"] == "no-store"
    wywolania.assert_called_once()
    assert parse_qs(urlsplit(pierwsza["next"]).query) == {"page": ["2"], "warstwa": [Warstwa.RCB]}
    druga = client.get(pierwsza["next"]).json()
    assert pierwsza["results"] != druga["results"]
    assert parse_qs(urlsplit(druga["previous"]).query) == {"warstwa": [Warstwa.RCB]}
    assert client.get(adres, {"warstwa": Warstwa.SG}).json()["count"] == 0
    assert client.get(adres, {"warstwa": "błędna"}).status_code == 400
    assert client.get(adres, {"page": "0"}).status_code == 404


def test_alias_redis_ma_krotkie_timeouty():
    assert ustawienia.CACHES["teraz"]["OPTIONS"] == {"socket_connect_timeout": 0.5, "socket_timeout": 0.5}


@pytest.mark.parametrize(("metoda", "blad"), [
    ("get", ConnectionError),
    ("get_or_set", TimeoutError),
    ("set", ConnectionError),
])
def test_api_odpowiada_przy_bledzie_cache(client, zrob_zrodlo, monkeypatch, metoda, blad):
    zrob_zrodlo("widoczne-bez-cache", tryb=Zrodlo.Tryb.PUBLICZNY)
    cache = caches["teraz"]
    oryginal = getattr(cache, metoda)

    def zerwane_polaczenie(klucz, *args, **kwargs):
        if metoda != "set" or (klucz.startswith("api:") and klucz != GENERACJA):
            raise blad("Testowy błąd Redis")
        return oryginal(klucz, *args, **kwargs)

    monkeypatch.setattr(cache, metoda, zerwane_polaczenie)
    odpowiedz = client.get(reverse("teraz:warstwy"))
    assert odpowiedz.status_code == 200
    assert b"widoczne-bez-cache" in odpowiedz.content
