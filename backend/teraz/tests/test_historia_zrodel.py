"""Historia i zdrowie źródeł: pole rodzaj_lacza, /zrodla/, wpisy?na= oraz /os/.

Zasada: nigdy nie twierdzimy, że czegoś nie było; brak danych to `brak_danych` albo `null`, nie zero.
"""
import importlib
from datetime import datetime, timedelta, timezone as utc

import pytest
from django.core import signing
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.preview import SALT, key_digest
from teraz import historia
from teraz.models import Klasa, Pobranie, StatusPrzegladu, Warstwa, Wpis, WylacznikKategorii, Zrodlo
from teraz.zrodla.rejestr import ADAPTERY, RODZAJ_LACZA

pytestmark = pytest.mark.django_db
PUBLICZNY = Zrodlo.Tryb.PUBLICZNY


def zegar():
    """Teraz bez mikrosekund: parametr `na` ma dokładność sekundy, więc granice testujemy na pełnych sekundach."""
    return timezone.now().replace(microsecond=0)


def iso(czas):
    return czas.astimezone(utc.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def czas(tekst):
    return parse_datetime(tekst)


@pytest.fixture
def zrodlo(zrob_zrodlo):
    return zrob_zrodlo("jawne", tryb=PUBLICZNY, czestotliwosc_s=300)


@pytest.fixture
def pobranie_w():
    def zrob(zrodlo, kiedy, **zmiany):
        dane = dict(zrodlo=zrodlo, pobrano_at=kiedy, status_http=200, hash_tresci="a" * 64, wersja_parsera="test")
        dane.update(zmiany)
        return Pobranie.objects.create(**dane)
    return zrob


@pytest.fixture
def wpis_w(zrob_wpis):
    def zrob(zrodlo, kiedy, **zmiany):
        dane = dict(klasa=Klasa.ZWYKLY, opublikowano_at=kiedy, pobrano_at=kiedy, pewnosc_lokalizacji=0.9)
        dane.update(zmiany)
        return zrob_wpis(zrodlo, **dane)
    return zrob


def wersja(zastapiono, **pola):
    dane = {"zastapiono_at": zastapiono.isoformat(), "tytul": "Stary", "tresc": "Stara treść", "link": "https://test.example.org/wpis",
            "opublikowano_at": None, "czas_zrodlowy_at": None, "dokladna_godzina_publikacji": True, "miejsce": "",
            "teryt": [], "szerokosc": None, "dlugosc": None, "bbox": None, "dokladnosc": "brak", "pewnosc_lokalizacji": 0}
    dane.update(pola)
    return dane


# ------------------------------------------------------------------ rodzaj_lacza

@pytest.mark.parametrize("dostep,oczekiwany", [("x", "x"), ("api", "api"), ("rss", "rss"), ("html", "scraping"),
                                                ("websocket", "websocket")])
def test_rodzaj_lacza_domyslnie_ze_sposobu_dostepu(zrob_zrodlo, dostep, oczekiwany):
    adres = "wss://test.example.org/ws" if dostep == "websocket" else "https://test.example.org/"
    assert zrob_zrodlo("dom", sposob_dostepu=dostep, adres=adres).rodzaj_lacza == oczekiwany


def test_rodzaj_lacza_jawny_nie_jest_nadpisywany(zrob_zrodlo):
    zrodlo = zrob_zrodlo("reczny", sposob_dostepu="api", rodzaj_lacza="reczne")
    zrodlo.save()
    zrodlo.refresh_from_db()
    assert zrodlo.rodzaj_lacza == "reczne"


def test_rodzaj_lacza_wypelniany_takze_przy_update_fields(zrob_zrodlo):
    zrodlo = zrob_zrodlo("bez")
    Zrodlo.objects.filter(pk=zrodlo.pk).update(rodzaj_lacza="")
    zrodlo.refresh_from_db()
    zrodlo.nazwa = "Inna"
    zrodlo.save(update_fields=["nazwa"])
    zrodlo.refresh_from_db()
    assert zrodlo.rodzaj_lacza == "api"


def test_rejestr_adapterow_ma_rodzaj_lacza_zgodny_z_migracja():
    migracja = importlib.import_module("teraz.migrations.0006_rodzaj_lacza")
    assert set(RODZAJ_LACZA) == set(ADAPTERY)
    assert RODZAJ_LACZA == migracja.ADAPTERY
    assert set(RODZAJ_LACZA.values()) <= set(Zrodlo.RodzajLacza.values)


def test_migracja_wypelnila_rodzaj_dla_zrodel_z_rejestru():
    assert not Zrodlo.objects.filter(rodzaj_lacza="").exists()
    for slug, rodzaj in RODZAJ_LACZA.items():
        zrodlo = Zrodlo.objects.filter(slug=slug).first()
        if zrodlo:
            assert zrodlo.rodzaj_lacza == rodzaj, slug
    assert Zrodlo.objects.get(slug="emsc").rodzaj_lacza == "websocket"
    assert Zrodlo.objects.get(slug="dorsz").rodzaj_lacza == "x"  # bez adaptera: ze sposobu dostępu


# ------------------------------------------------------------------ /zrodla/

def test_zrodla_pola_i_tylko_publiczne(client, zrob_zrodlo):
    teraz = zegar()
    zrob_zrodlo("jawne", tryb=PUBLICZNY, czestotliwosc_s=60, ostatni_sukces_at=teraz, sposob_dostepu="rss",
                adres="https://test.example.org/rss", atrybucja="Źródło: test")
    zrob_zrodlo("wewn", tryb=Zrodlo.Tryb.WEWNETRZNY, ostatni_sukces_at=teraz)
    zrob_zrodlo("wyl", tryb=Zrodlo.Tryb.WYLACZONY)
    odpowiedz = client.get(reverse("teraz:zrodla"))
    assert odpowiedz.status_code == 200
    dane = odpowiedz.json()
    assert [z["slug"] for z in dane] == ["jawne"]
    assert set(dane[0]) == {"slug", "nazwa", "instytucja", "warstwa", "atrybucja", "rodzaj_lacza", "czestotliwosc_s",
                            "ostatni_sukces_at", "ostatni_blad", "luka"}
    assert dane[0]["rodzaj_lacza"] == "rss"
    assert dane[0]["luka"] is False and dane[0]["ostatni_blad"] is None


def test_zrodla_pomija_warstwe_z_aktywnym_wylacznikiem(client, zrob_zrodlo):
    zrob_zrodlo("rcb-test", tryb=PUBLICZNY, warstwa=Warstwa.RCB)
    zrob_zrodlo("gios-test", tryb=PUBLICZNY, warstwa=Warstwa.POWIETRZE)
    WylacznikKategorii.objects.create(warstwa=Warstwa.RCB, aktywny=True, powod="test")
    assert [z["slug"] for z in client.get(reverse("teraz:zrodla")).json()] == ["gios-test"]


def test_zrodla_luka_po_trzykrotnej_czestotliwosci(client, zrob_zrodlo):
    teraz = zegar()
    margines = timedelta(seconds=20)
    prog = timedelta(seconds=3 * 100)
    zrob_zrodlo("swieze", tryb=PUBLICZNY, czestotliwosc_s=100, ostatni_sukces_at=teraz - prog + margines)
    zrob_zrodlo("stare", tryb=PUBLICZNY, czestotliwosc_s=100, ostatni_sukces_at=teraz - prog - margines)
    zrob_zrodlo("nigdy", tryb=PUBLICZNY, czestotliwosc_s=100)
    luki = {z["slug"]: z["luka"] for z in client.get(reverse("teraz:zrodla")).json()}
    assert luki == {"swieze": False, "stare": True, "nigdy": True}


@pytest.mark.parametrize("wewnetrzny,blokada,kod", [
    ("", False, None),
    ("http_503", False, "blad_http"),
    ("BladFormatu: /srv/spin-clinic/secret.py linia 3", False, "blad_zrodla"),
    ("Dostęp wstrzymany: HTTP 403 lub wyzwanie bota.", False, "dostep_wstrzymany"),
    ("http_500", True, "dostep_wstrzymany"),
])
def test_zrodla_ostatni_blad_to_kod_ogolny(client, zrob_zrodlo, wewnetrzny, blokada, kod):
    zrob_zrodlo("blad", tryb=PUBLICZNY, ostatni_blad=wewnetrzny, kolejne_bledy=1 if wewnetrzny else 0,
                blokada_dostepu=blokada, adres="https://tajny-host.example.org/klucz", podstawa_prawna="tajna podstawa")
    odpowiedz = client.get(reverse("teraz:zrodla"))
    assert odpowiedz.json()[0]["ostatni_blad"] == kod
    tekst = odpowiedz.content.decode()
    for wyciek in ("secret.py", "tajny-host", "tajna podstawa", "/srv/"):
        assert wyciek not in tekst


# ------------------------------------------------------------------ wpisy?na=

def test_na_granice_czasu_publikacji(client, zrodlo, wpis_w):
    t = zegar() - timedelta(hours=5)
    wpis_w(zrodlo, t, tytul="dokladnie")
    adres = reverse("teraz:wpisy")
    assert [w["tytul"] for w in client.get(adres, {"na": iso(t)}).json()["results"]] == ["dokladnie"]
    assert client.get(adres, {"na": iso(t - timedelta(seconds=1))}).json()["results"] == []
    assert client.get(adres, {"na": iso(t + timedelta(seconds=1))}).json()["count"] == 1


def test_na_odtwarza_wersje_z_wersje(client, zrodlo, wpis_w):
    t0 = zegar() - timedelta(hours=10)
    t1, t2 = t0 + timedelta(hours=2), t0 + timedelta(hours=6)
    wpis_w(zrodlo, t0, tytul="Trzeci", wersje=[
        wersja(t1, tytul="Pierwszy", opublikowano_at=t0.isoformat()),
        wersja(t2, tytul="Drugi", opublikowano_at=t0.isoformat()),
    ])
    adres = reverse("teraz:wpisy")

    def dla(na):
        return client.get(adres, {"na": iso(na)}).json()["results"][0]

    assert dla(t0 + timedelta(hours=1))["tytul"] == "Pierwszy"
    assert dla(t1 - timedelta(seconds=1))["tytul"] == "Pierwszy"
    assert dla(t1)["tytul"] == "Drugi"  # w chwili zastąpienia obowiązuje już nowa wersja
    assert dla(t2 - timedelta(seconds=1))["tytul"] == "Drugi"
    assert dla(t2)["tytul"] == "Trzeci"
    assert dla(zegar())["tytul"] == "Trzeci"
    stara = dla(t0 + timedelta(hours=1))
    assert stara["stan"]["wersja"] == "poprzednia" and czas(stara["stan"]["obowiazywala_do"]) == t1
    nowa = dla(t2)
    assert nowa["stan"] == {"wersja": "biezaca", "obowiazywala_do": None}


def test_na_wpis_ponownie_wydany_pozniej_jest_widoczny_w_starej_wersji(client, zrodlo, wpis_w):
    t0 = zegar() - timedelta(hours=10)
    t1 = t0 + timedelta(hours=5)
    wpis_w(zrodlo, t1, tytul="Wydanie 2", pobrano_at=t0, wersje=[wersja(t1, tytul="Wydanie 1", opublikowano_at=t0.isoformat())])
    adres = reverse("teraz:wpisy")
    wynik = client.get(adres, {"na": iso(t0 + timedelta(hours=1))}).json()
    assert [w["tytul"] for w in wynik["results"]] == ["Wydanie 1"]
    assert czas(wynik["results"][0]["opublikowano_at"]) == t0
    assert [w["tytul"] for w in client.get(adres, {"na": iso(t1)}).json()["results"]] == ["Wydanie 2"]
    assert client.get(adres, {"na": iso(t0 - timedelta(hours=1))}).json()["results"] == []


def test_na_obcieta_historia_to_znacznik_bez_tresci(client, zrodlo, wpis_w):
    t0 = zegar() - timedelta(days=3)
    wersje = [wersja(t0 + timedelta(hours=i + 1), tytul=f"Stara {i}") for i in range(20)]
    wpis = wpis_w(zrodlo, t0, tytul="Bieżąca", wersje=wersje)
    wynik = client.get(reverse("teraz:wpisy"), {"na": iso(t0 + timedelta(minutes=30))}).json()
    assert wynik["results"] == [{"id": wpis.pk, "zrodlo": "jawne", "warstwa": "rcb", "brak_danych": True,
                                 "powod": "historia_niepelna"}]
    assert "Stara 0" not in str(wynik)


def test_na_wpis_pomiarowy_bez_historii_jest_w_brak_danych_nie_pominiety_po_cichu(client, zrodlo, wpis_w):
    t0 = zegar() - timedelta(hours=10)
    wpis_w(zrodlo, t0 + timedelta(hours=8), pobrano_at=t0, tytul="Pomiar")  # pobrany wcześniej, wersje=[]
    wynik = client.get(reverse("teraz:wpisy"), {"na": iso(t0 + timedelta(hours=1))}).json()
    assert wynik["results"] == []
    niepelne = [b for b in wynik["brak_danych"] if b["powod"] == "historia_niepelna"]
    assert len(niepelne) == 1 and niepelne[0]["zrodla"] == ["jawne"]
    assert czas(niepelne[0]["do"]) == t0 + timedelta(hours=1)


def test_na_starych_wersji_wpisu_wrazliwego_nie_pokazujemy(client, zrodlo, wpis_w):
    t0 = zegar() - timedelta(hours=10)
    t1 = t0 + timedelta(hours=4)
    wpis = wpis_w(zrodlo, t0, klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.DOPUSZCZONY, tytul="Zatwierdzony",
                  wersje=[wersja(t1, tytul="Niezatwierdzony szczegół", opublikowano_at=t0.isoformat(),
                                 miejsce="ulica Tajna 5", szerokosc=52.1, dlugosc=21.0)])
    adres = reverse("teraz:wpisy")
    wynik = client.get(adres, {"na": iso(t0 + timedelta(hours=1))}).json()
    assert wynik["results"][0]["brak_danych"] is True
    assert wynik["results"][0]["powod"] == "historia_niedostepna"
    tekst = str(wynik)
    assert "Niezatwierdzony" not in tekst and "Tajna" not in tekst and "52.1" not in tekst
    biezacy = client.get(adres, {"na": iso(t1)}).json()["results"][0]
    assert biezacy["id"] == wpis.pk and biezacy["tytul"] == "Zatwierdzony"
    assert biezacy["szerokosc"] is None and biezacy["miejsce"] == ""  # maskowanie jak dla wersji bieżącej


def test_na_nie_ujawnia_niepublicznych(client, zrob_zrodlo, wpis_w):
    t = zegar() - timedelta(hours=3)
    jawne = zrob_zrodlo("jawne", tryb=PUBLICZNY)
    wewn = zrob_zrodlo("wewn", tryb=Zrodlo.Tryb.WEWNETRZNY)
    inne = zrob_zrodlo("inne", tryb=PUBLICZNY, warstwa=Warstwa.POWIETRZE)
    wpis_w(jawne, t, tytul="widoczny")
    wpis_w(wewn, t, tytul="ukryty-wewnetrzny")
    wpis_w(jawne, t, tytul="ukryty-przeglad", klasa=Klasa.WRAZLIWY)
    wpis_w(jawne, t, tytul="ukryty-wstrzymany", klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.WSTRZYMANY)
    wpis_w(jawne, t, tytul="ukryty-pomiar", pomiar_aktywny=False)
    wpis_w(jawne, t, tytul="ukryty-usuniety", usunieto_at=t)
    wpis_w(inne, t, tytul="ukryty-wylacznik")
    WylacznikKategorii.objects.create(warstwa=Warstwa.POWIETRZE, aktywny=True, powod="test")
    wynik = client.get(reverse("teraz:wpisy"), {"na": iso(zegar())}).json()
    assert [w["tytul"] for w in wynik["results"]] == ["widoczny"]
    assert "ukryty" not in str(wynik)
    # to samo co bez parametru `na`
    assert client.get(reverse("teraz:wpisy")).json()["count"] == wynik["count"]


def test_na_z_przyszlosci_czyta_stan_na_teraz(client, zrodlo, wpis_w):
    wpis_w(zrodlo, zegar() - timedelta(minutes=5), tytul="teraz")
    wynik = client.get(reverse("teraz:wpisy"), {"na": iso(zegar() + timedelta(days=30))}).json()
    assert wynik["count"] == 1 and czas(wynik["na"]) <= timezone.now()


@pytest.mark.parametrize("zla", ["wczoraj", "2026-13-40T00:00:00Z", "12345"])
def test_na_zle_dane_to_400(client, zla):
    assert client.get(reverse("teraz:wpisy"), {"na": zla}).status_code == 400


def test_na_linki_stron_zachowuja_parametr(client, zrodlo, wpis_w, settings):
    t = zegar() - timedelta(hours=2)
    for numer in range(55):
        wpis_w(zrodlo, t - timedelta(minutes=numer))
    odpowiedz = client.get(reverse("teraz:wpisy"), {"na": iso(zegar())}).json()
    assert odpowiedz["next"] and "na=" in odpowiedz["next"]
    nastepna = client.get(odpowiedz["next"]).json()
    assert nastepna["results"] and "na" in nastepna


def test_na_luka_pobierania_oznaczona_dla_zrodel_bez_swiezego_sukcesu(client, zrob_zrodlo, pobranie_w):
    na = zegar() - timedelta(hours=1)
    zywe = zrob_zrodlo("zywe", tryb=PUBLICZNY, czestotliwosc_s=300)
    martwe = zrob_zrodlo("martwe", tryb=PUBLICZNY, czestotliwosc_s=300)
    zrob_zrodlo("nigdy", tryb=PUBLICZNY, czestotliwosc_s=300)
    pobranie_w(zywe, na - timedelta(seconds=800))  # w granicach 3 x 300 s
    pobranie_w(martwe, na - timedelta(seconds=1000))  # poza granicą
    pobranie_w(martwe, na + timedelta(minutes=5))  # po `na`: nie liczy się
    pobranie_w(zywe, na - timedelta(minutes=1), hash_tresci="", status_http=503)  # błąd: nie liczy się jako sukces
    luki = {b["zrodla"][0]: b for b in client.get(reverse("teraz:wpisy"), {"na": iso(na)}).json()["brak_danych"]
            if b["powod"] == "luka_pobierania"}
    assert set(luki) == {"martwe", "nigdy"}
    assert czas(luki["martwe"]["od"]) == na - timedelta(seconds=1000)
    assert luki["nigdy"]["od"] is None and czas(luki["nigdy"]["do"]) == na


def test_na_luka_retencji_po_wyczyszczeniu_wpisu(client, zrodlo, wpis_w):
    t = zegar() - timedelta(hours=3)
    adres = reverse("teraz:wpisy")
    assert client.get(adres, {"na": iso(zegar())}).json()["luka_retencji"] is False
    wpis_w(zrodlo, t, usunieto_at=t, status_przegladu=StatusPrzegladu.WSTRZYMANY)
    # testy nie wykonują on_commit, więc cache nie jest unieważniany: inny parametr to inny klucz
    wynik = client.get(adres, {"na": iso(zegar() + timedelta(seconds=7))}).json()
    assert wynik["luka_retencji"] is True and wynik["count"] == 0
    luka = [b for b in wynik["brak_danych"] if b["powod"] == "luka_retencji"]
    assert len(luka) == 1 and czas(luka[0]["od"]) == t and czas(luka[0]["do"]) == t  # okres wyczyszczonego wpisu
    assert client.get(adres, {"na": iso(t - timedelta(hours=1))}).json()["luka_retencji"] is False


def test_na_luka_retencji_dla_historii_starszej_niz_retencja_osobowa(client, zrodlo, wpis_w, settings):
    settings.TERAZ_RETENCJA_OSOBOWE_DNI = 30
    stary = zegar() - timedelta(days=45)
    wpis_w(zrodlo, stary, tytul="stary")
    wynik = client.get(reverse("teraz:wpisy"), {"na": iso(zegar())}).json()
    assert wynik["luka_retencji"] is True
    luka = [b for b in wynik["brak_danych"] if b["powod"] == "luka_retencji"]
    assert luka and luka[0]["od"] is None


def test_na_odpowiedz_z_cache_bez_ponownego_liczenia(client, zrodlo, wpis_w, monkeypatch):
    wpis_w(zrodlo, zegar() - timedelta(hours=1))
    parametry = {"na": iso(zegar() - timedelta(minutes=10))}
    pierwsza = client.get(reverse("teraz:wpisy"), parametry).json()

    def zakaz(*args, **kwargs):
        raise AssertionError("odpowiedź powinna pochodzić z cache")

    monkeypatch.setattr(historia, "wpisy_na", zakaz)
    assert client.get(reverse("teraz:wpisy"), parametry).json() == pierwsza


@pytest.mark.parametrize("adres,parametry", [
    ("teraz:wpisy", {"na": "2026-01-01T00:00:00Z"}),
    ("teraz:zrodla", {}),
    ("teraz:os", {"od": "2026-01-01T00:00:00Z", "do": "2026-01-03T00:00:00Z"}),
])
def test_bramka_flagi_404_przed_cache_bez_podgladu(client, zrodlo, settings, adres, parametry):
    settings.PREVIEW_KEY = "test-tylko-klucz-podgladu"
    url = reverse(adres)
    assert client.get(url, parametry).status_code == 200  # rozgrzanie cache
    settings.TERAZ_PUBLICZNE = False
    odpowiedz = client.get(url, parametry)
    assert odpowiedz.status_code == 404 and odpowiedz["Cache-Control"] == "private, no-store"
    client.cookies["sc_preview_sig"] = signing.dumps(key_digest(), salt=SALT)
    assert client.get(url, parametry).status_code == 200


# ------------------------------------------------------------------ /os/

def os_(client, od, do, krok="dzien"):
    return client.get(reverse("teraz:os"), {"od": iso(od), "do": iso(do), "krok": krok})


@pytest.mark.parametrize("parametry", [
    {}, {"od": "2026-01-01T00:00:00Z"}, {"do": "2026-01-01T00:00:00Z"},
    {"od": "2026-01-03T00:00:00Z", "do": "2026-01-01T00:00:00Z"},
    {"od": "2026-01-01T00:00:00Z", "do": "2026-01-03T00:00:00Z", "krok": "tydzien"},
    {"od": "2020-01-01T00:00:00Z", "do": "2026-01-03T00:00:00Z", "krok": "dzien"},
    {"od": "2026-01-01T00:00:00Z", "do": "2026-03-01T00:00:00Z", "krok": "godzina"},
])
def test_os_zle_parametry_to_400(client, parametry):
    assert client.get(reverse("teraz:os"), parametry).status_code == 400


def test_os_liczy_potwierdzone_z_pewnoscia_od_0_8_w_dobach_lokalnych(client, zrodlo, wpis_w):
    dzien = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
    start = dzien.replace(hour=0)
    nastepny = start + timedelta(days=1)
    wpis_w(zrodlo, start, pewnosc_lokalizacji=0.8)  # dokładnie północ lokalna: ta doba
    wpis_w(zrodlo, nastepny - timedelta(seconds=1), pewnosc_lokalizacji=1)
    wpis_w(zrodlo, nastepny, pewnosc_lokalizacji=0.9)  # następna doba
    wpis_w(zrodlo, dzien, pewnosc_lokalizacji=0.79)  # za mała pewność
    wpis_w(zrodlo, dzien, klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.DOPUSZCZONY)  # klasa wrażliwa bez lokalizacji
    wynik = os_(client, start, nastepny + timedelta(hours=1)).json()
    pierwszy, drugi = wynik["kubelki"][:2]
    assert czas(pierwszy["od"]) == start and czas(pierwszy["do"]) == nastepny
    assert pierwszy["liczba"] == 2 and drugi["liczba"] == 1
    assert wynik["krok"] == "dzien" and wynik["pewnosc_min"] == 0.8 and wynik["strefa"] == "Europe/Warsaw"


def test_os_nie_liczy_niepublicznych_i_nie_wycieka(client, zrob_zrodlo, wpis_w):
    t = zegar() - timedelta(hours=2)
    jawne = zrob_zrodlo("jawne", tryb=PUBLICZNY)
    wewn = zrob_zrodlo("wewn", tryb=Zrodlo.Tryb.WEWNETRZNY)
    wpis_w(jawne, t, tytul="liczony")
    wpis_w(wewn, t, tytul="ukryty")
    wpis_w(jawne, t, pomiar_aktywny=False)
    wpis_w(jawne, t, usunieto_at=t)
    wynik = os_(client, t, zegar()).json()
    assert sum(k["liczba"] or 0 for k in wynik["kubelki"]) == 1
    assert "ukryty" not in str(wynik) and "liczony" not in str(wynik)


def test_os_licznik_w_przegladzie_jest_osobny(client, zrob_zrodlo, wpis_w):
    t = zegar() - timedelta(hours=2)
    jawne = zrob_zrodlo("jawne", tryb=PUBLICZNY)
    wewn = zrob_zrodlo("wewn", tryb=Zrodlo.Tryb.WEWNETRZNY)
    inne = zrob_zrodlo("inne", tryb=PUBLICZNY, warstwa=Warstwa.POWIETRZE)
    wpis_w(jawne, t, klasa=Klasa.WRAZLIWY)
    wpis_w(jawne, t, klasa=Klasa.OSOBA_POSZUKIWANA)
    wpis_w(jawne, t, klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.DOPUSZCZONY)  # już opublikowany
    wpis_w(jawne, t, klasa=Klasa.WRAZLIWY, status_przegladu=StatusPrzegladu.WSTRZYMANY)
    wpis_w(wewn, t, klasa=Klasa.WRAZLIWY)  # źródło niepubliczne
    wpis_w(jawne, t, klasa=Klasa.WRAZLIWY, usunieto_at=t)
    wpis_w(inne, t, klasa=Klasa.WRAZLIWY)
    WylacznikKategorii.objects.create(warstwa=Warstwa.POWIETRZE, aktywny=True, powod="test")
    wpis_w(jawne, t)  # zwykły: do liczby potwierdzonych, nie do przeglądu
    wynik = os_(client, t, zegar()).json()
    assert sum(k["w_przegladzie"] for k in wynik["kubelki"]) == 2
    assert sum(k["liczba"] or 0 for k in wynik["kubelki"]) == 1
    assert set(wynik["kubelki"][0]) == {"od", "do", "liczba", "w_przegladzie", "luka_retencji", "luka_zrodel"}


def test_os_zero_przy_pokryciu_to_zero_a_bez_pokrycia_null(client, zrob_zrodlo, pobranie_w):
    dzis = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    zywe = zrob_zrodlo("zywe", tryb=PUBLICZNY, czestotliwosc_s=86400)
    pobranie_w(zywe, zegar() - timedelta(seconds=30))
    wynik = os_(client, dzis, zegar()).json()
    assert wynik["kubelki"][0]["liczba"] == 0 and wynik["kubelki"][0]["luka_zrodel"] == []
    assert wynik["brak_danych"] == []
    zrob_zrodlo("bez-pobran", tryb=PUBLICZNY, czestotliwosc_s=86400)
    wynik = os_(client, dzis, zegar() + timedelta(seconds=7)).json()  # inny klucz cache (on_commit w testach nie działa)
    dzisiaj = wynik["kubelki"][0]
    assert dzisiaj["liczba"] is None and dzisiaj["luka_zrodel"] == ["bez-pobran"]
    assert [(b["powod"], b["zrodla"]) for b in wynik["brak_danych"]] == [("luka_pobierania", ["bez-pobran"])]


def test_os_luka_pobierania_scala_sasiednie_przedzialy_i_ma_okres(client, zrob_zrodlo, pobranie_w):
    zrodlo = zrob_zrodlo("przerwa", tryb=PUBLICZNY, czestotliwosc_s=600)
    pelna_godzina = zegar().astimezone(utc.utc).replace(minute=0, second=0, microsecond=0)
    start = pelna_godzina - timedelta(hours=6)
    for godzina in (0, 1, 5):  # godziny 2, 3 i 4 bez pobrań; próg to 3 x 600 s = 30 min od ostatniego pobrania
        pobranie_w(zrodlo, start + timedelta(hours=godzina, minutes=55))
    wynik = os_(client, start, pelna_godzina + timedelta(minutes=1), krok="godzina").json()
    luki = [b for b in wynik["brak_danych"] if b["powod"] == "luka_pobierania"]
    assert luki and all(b["zrodla"] == ["przerwa"] for b in luki)
    nie_pokryte = [k for k in wynik["kubelki"] if k["luka_zrodel"] == ["przerwa"]]
    assert nie_pokryte
    # scalone w jeden okres: początek pierwszego i koniec ostatniego przedziału bez pokrycia
    assert czas(luki[0]["od"]) == czas(nie_pokryte[0]["od"])
    assert czas(luki[-1]["do"]) == czas(nie_pokryte[-1]["do"])
    assert wynik["kubelki"][1]["luka_zrodel"] == []  # pobranie w tej godzinie


def test_os_historia_starsza_niz_retencja_osobowa_to_luka_a_nie_zero(client, zrodlo, wpis_w, settings):
    settings.TERAZ_RETENCJA_OSOBOWE_DNI = 30
    stary = (zegar() - timedelta(days=60)).replace(hour=12)
    start = timezone.localtime(stary).replace(hour=0, minute=0, second=0, microsecond=0)
    wpis_w(zrodlo, stary)
    wynik = os_(client, start, start + timedelta(days=2)).json()
    pierwszy, drugi = wynik["kubelki"][:2]
    assert pierwszy["liczba"] == 1 and pierwszy["luka_retencji"] is True  # to, co mamy, nadal pokazujemy
    assert drugi["liczba"] is None and drugi["luka_retencji"] is True  # zero nie istnieje: brak danych
    assert wynik["luka_retencji"] is True
    luka = [b for b in wynik["brak_danych"] if b["powod"] == "luka_retencji"]
    assert luka and czas(luka[0]["od"]) == start


def test_os_wyczyszczony_wpis_oznacza_przedzial_luka_retencji(client, zrodlo, wpis_w, pobranie_w):
    t = zegar() - timedelta(hours=2)
    pobranie_w(zrodlo, zegar() - timedelta(seconds=10))
    wpis_w(zrodlo, t, usunieto_at=t, status_przegladu=StatusPrzegladu.WSTRZYMANY)
    kubelek = os_(client, t, zegar(), krok="godzina").json()["kubelki"]
    oznaczone = [k for k in kubelek if k["luka_retencji"]]
    assert len(oznaczone) == 1 and oznaczone[0]["liczba"] is None


def test_os_krok_godzina_i_przyciecie_do_teraz(client, zrodlo, wpis_w):
    teraz = zegar()
    wpis_w(zrodlo, teraz - timedelta(minutes=30))
    wynik = os_(client, teraz - timedelta(hours=3), teraz + timedelta(days=5), krok="godzina").json()  # do ścięte do teraz
    assert 3 <= len(wynik["kubelki"]) <= 5
    assert czas(wynik["kubelki"][-1]["od"]) <= teraz
    assert sum(k["liczba"] or 0 for k in wynik["kubelki"]) == 1
    assert all(czas(k["do"]) - czas(k["od"]) == timedelta(hours=1) for k in wynik["kubelki"])


def test_os_doba_w_zmianie_czasu_ma_23_godziny(client, zrodlo):
    start = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.get_default_timezone())
    wynik = os_(client, start, start + timedelta(days=1, hours=12)).json()
    assert czas(wynik["kubelki"][0]["do"]) - czas(wynik["kubelki"][0]["od"]) == timedelta(hours=23)


def test_os_odpowiedz_z_cache(client, zrodlo, monkeypatch):
    do = zegar()
    start = do - timedelta(days=2)
    pierwsza = os_(client, start, do).json()

    def zakaz(*args, **kwargs):
        raise AssertionError("odpowiedź powinna pochodzić z cache")

    monkeypatch.setattr(historia, "os_czasu", zakaz)
    assert os_(client, start, do).json() == pierwsza
