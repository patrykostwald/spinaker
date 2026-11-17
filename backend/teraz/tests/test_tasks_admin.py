from copy import copy
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import caches
from django.core.files.base import ContentFile
from django.template import Context
from django.template.context import BaseContext
from django.urls import reverse
from django.utils import timezone

from config.celery import app
from teraz import tasks
from teraz.cache import GENERACJA
from teraz.models import Klasa, Pobranie, StatusPrzegladu, Warstwa, Wpis, WylacznikKategorii, Zdarzenie, Zrodlo
from teraz.schedule import beat_schedule


def test_routing_i_harmonogram():
    for zadanie in (tasks.zbierz_nalezne_zrodla, tasks.zbierz_zrodlo, tasks.usun_stare_zrzuty, tasks.usun_zrzuty_na_zadanie):
        assert app.amqp.router.route({}, zadanie.name)["queue"].name == "teraz"
    assert app.amqp.router.route({}, "news.tasks.seba_task")["queue"].name == "celery"
    assert app.amqp.router.route({}, "scraper.tasks.archive_batch")["queue"].name == "celery"
    for nazwa, wpis in beat_schedule.items():
        assert app.conf.beat_schedule[nazwa] == wpis
        assert wpis["options"]["expires"] > 0
    assert tasks.zbierz_zrodlo.acks_late is False
    assert tasks.zbierz_zrodlo.soft_time_limit == 40 < tasks.zbierz_zrodlo.time_limit


@pytest.mark.django_db
def test_planowanie_tylko_naleznych_zarejestrowanych_zrodel(zrob_zrodlo, monkeypatch):
    teraz = timezone.now()
    zrodlo = zrob_zrodlo("teraz-testowy")
    zrob_zrodlo("nieznane")
    zrob_zrodlo("za-wczesnie", ostatnie_pobranie_at=teraz - timedelta(minutes=3))
    zrob_zrodlo("wylaczone", tryb=Zrodlo.Tryb.WYLACZONY)
    drugie = zrob_zrodlo("nalezne", ostatnie_pobranie_at=teraz - timedelta(minutes=6))
    for slug in ("za-wczesnie", "wylaczone", "nalezne"):
        monkeypatch.setitem(tasks.ADAPTERY, slug, tasks.ADAPTERY["teraz-testowy"])
    zaplanuj = Mock()
    monkeypatch.setattr(tasks.zbierz_zrodlo, "apply_async", zaplanuj)
    tasks.zbierz_nalezne_zrodla()
    assert {wywolanie.args[0] for wywolanie in zaplanuj.call_args_list} == {(zrodlo.pk,), (drugie.pk,)}
    assert all(0 <= c.kwargs["countdown"] <= 5 and c.kwargs["expires"] == 120 for c in zaplanuj.call_args_list)
    tasks.zbierz_zrodlo(zrodlo.pk)
    tasks.zbierz_zrodlo(zrodlo.pk)
    assert Pobranie.objects.filter(zrodlo=zrodlo).count() == 1


@pytest.mark.django_db
def test_retencja_usuwa_pliki_i_zachowuje_metadane(zrob_zrodlo, zrob_wpis):
    zrodlo = zrob_zrodlo()
    wpis = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY)
    teraz = timezone.now()

    def zrzut(dni, nazwa, **dane):
        p = Pobranie(zrodlo=zrodlo, pobrano_at=teraz - timedelta(days=dni), status_http=200,
                     hash_tresci="a" * 64, wersja_parsera="1", **dane)
        p.zrzut.save(nazwa, ContentFile(b"Dowod"))
        return p, p.zrzut.name

    zwykly, zwykly_plik = zrzut(91, "zwykly.bin")
    wczesny, wczesny_plik = zrzut(31, "wczesny.bin", dane_osobowe=True)
    zmieniony, zmieniony_plik = zrzut(31, "zmieniony.bin")
    zmieniony.wpisy_w_zrzucie.add(wpis)
    wpis.klasa = Klasa.OSOBA_POSZUKIWANA
    wpis.save()
    aktualny, aktualny_plik = zrzut(29, "aktualny.bin", dane_osobowe=True)
    dluga_retencja, dluga_retencja_plik = zrzut(31, "dluga.bin")

    tasks.usun_stare_zrzuty()
    tasks.usun_stare_zrzuty()
    for pobranie, plik in [(zwykly, zwykly_plik), (wczesny, wczesny_plik), (zmieniony, zmieniony_plik)]:
        pobranie.refresh_from_db()
        assert not pobranie.zrzut
        assert not pobranie.zrzut.storage.exists(plik)
        assert pobranie.hash_tresci == "a" * 64
    for pobranie, plik in [(aktualny, aktualny_plik), (dluga_retencja, dluga_retencja_plik)]:
        pobranie.refresh_from_db()
        assert pobranie.zrzut.storage.exists(plik)


@pytest.fixture
def klient_admina(client, monkeypatch):
    # Django 5.1 kopiuje kontekst przez copy(super()), które zmieniło się w Pythonie 3.14.
    # W obrazie produkcyjnym działa Python 3.11. Poprawka obowiązuje wyłącznie w tym teście.
    try:
        copy(Context())
    except AttributeError:
        def kopiuj_kontekst(self):
            kopia = object.__new__(type(self))
            kopia.__dict__.update(self.__dict__)
            kopia.dicts = self.dicts[:]
            return kopia

        monkeypatch.setattr(BaseContext, "__copy__", kopiuj_kontekst)
    return client


def akcja(client, model, nazwa, pk):
    return client.post(reverse(f"admin:teraz_{model}_changelist"),
                       {"action": nazwa, "_selected_action": [pk], "index": "0"})


@pytest.mark.django_db
def test_admin_dostep_i_akcje(klient_admina, django_user_model, zrob_zrodlo, zrob_wpis):
    client = klient_admina
    wydawca = django_user_model.objects.create_superuser(username="wydawca")
    redaktor = django_user_model.objects.create_user(username="redaktor", is_staff=True)
    redaktor.user_permissions.add(*Permission.objects.filter(content_type__app_label="teraz"))
    zrodlo = zrob_zrodlo(podstawa_prawna="Zatwierdzona podstawa", rejestr_podstaw_url="https://rejestr.example.org/1")
    wpis = zrob_wpis(zrodlo, klasa=Klasa.WRAZLIWY)
    wylacznik = WylacznikKategorii.objects.create(warstwa=zrodlo.warstwa, powod="Decyzja redakcji")
    pola_zrodla = {pole: getattr(zrodlo, pole) for pole in ("slug", "nazwa", "instytucja", "warstwa", "sposob_dostepu",
                                                           "adres", "czestotliwosc_s", "podstawa_prawna", "rejestr_podstaw_url")}

    client.force_login(redaktor)
    akcja(client, "zrodlo", "przelacz_na_publiczne", zrodlo.pk)
    zrodlo.refresh_from_db()
    assert zrodlo.tryb == Zrodlo.Tryb.WEWNETRZNY
    adres = reverse("admin:teraz_zrodlo_change", args=[zrodlo.pk])
    odpowiedz = client.post(adres, {**pola_zrodla, "tryb": Zrodlo.Tryb.PUBLICZNY, "_save": "1"})
    assert odpowiedz.context["adminform"].form.errors["tryb"]
    assert akcja(client, "wpis", "dopusc", wpis.pk).status_code == 302
    wpis.refresh_from_db()
    assert wpis.status_przegladu == StatusPrzegladu.DOPUSZCZONY
    assert wpis.przeglad_zmienil == redaktor and wpis.przeglad_zmiana_at
    czas_dopuszczenia = wpis.przeglad_zmiana_at
    assert akcja(client, "wpis", "wstrzymaj", wpis.pk).status_code == 302
    wpis.refresh_from_db()
    assert wpis.status_przegladu == StatusPrzegladu.WSTRZYMANY
    assert wpis.przeglad_zmienil == redaktor and wpis.przeglad_zmiana_at >= czas_dopuszczenia
    assert akcja(client, WylacznikKategorii._meta.model_name, "wlacz_wylacznik", wylacznik.pk).status_code == 302
    wylacznik.refresh_from_db()
    assert wylacznik.aktywny and wylacznik.zmienil == redaktor and wylacznik.zmiana_at

    client.force_login(wydawca)
    assert akcja(client, "zrodlo", "przelacz_na_publiczne", zrodlo.pk).status_code == 302
    zrodlo.refresh_from_db()
    assert zrodlo.tryb == Zrodlo.Tryb.PUBLICZNY and zrodlo.tryb_zmienil == wydawca and zrodlo.tryb_zmiana_at
    wpis.pobranie.zrzut.save("prywatny.bin", ContentFile(b"Dowod"))
    podglad = client.get(reverse("admin:teraz_pobranie_change", args=[wpis.pobranie_id]))
    assert podglad.status_code == 200 and "prywatny.bin" in podglad.content.decode()
    assert '/media/private/teraz/' not in podglad.content.decode()
    assert client.get(reverse(f"admin:teraz_{Zdarzenie._meta.model_name}_changelist")).status_code == 200
    client.force_login(redaktor)
    assert client.post(adres, {"tryb": Zrodlo.Tryb.WYLACZONY, "_save": "1"}).status_code == 302
    zrodlo.refresh_from_db()
    assert zrodlo.tryb == Zrodlo.Tryb.WYLACZONY


@pytest.mark.django_db
def test_wpis_w_adminie_jest_tylko_do_odczytu(klient_admina, django_user_model, zrob_zrodlo, zrob_wpis):
    redaktor = django_user_model.objects.create_user(username="redaktor", is_staff=True)
    redaktor.user_permissions.add(Permission.objects.get(content_type__app_label="teraz", codename="change_wpis"))
    klient_admina.force_login(redaktor)
    wewnetrzne = zrob_zrodlo("wewnetrzne")
    publiczne = zrob_zrodlo("publiczne", tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(wewnetrzne, klasa=Klasa.WOJSKO_GRANICA, teryt=["02"])
    adres = reverse("admin:teraz_wpis_change", args=[wpis.pk])
    assert klient_admina.get(adres).status_code == 200
    for dane in (
        {"klasa": Klasa.ZWYKLY},
        {"zrodlo": publiczne.pk},
        {"teryt": '["0264011"]', "szerokosc": "51.1", "dlugosc": "17", "bbox": "[16,50,18,52]"},
    ):
        assert klient_admina.post(adres, {**dane, "_save": "1"}).status_code == 403
    wpis.refresh_from_db()
    assert wpis.klasa == Klasa.WOJSKO_GRANICA
    assert wpis.zrodlo == wewnetrzne
    assert wpis.teryt == ["02"]
    assert wpis.szerokosc is wpis.dlugosc is wpis.bbox is None


@pytest.mark.django_db
def test_dopuszczenie_i_wstrzymanie_uniewazniaja_opublikowane_wpisy(
    klient_admina, django_user_model, zrob_zrodlo, zrob_wpis, django_capture_on_commit_callbacks,
):
    klient_admina.force_login(django_user_model.objects.create_superuser(username="wydawca"))
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=Klasa.WRAZLIWY)
    adres = reverse("teraz:wpisy")
    assert klient_admina.get(adres).json()["count"] == 0
    for ruch, oczekiwane in (("dopusc", 1), ("wstrzymaj", 0)):
        with django_capture_on_commit_callbacks(execute=True):
            assert akcja(klient_admina, "wpis", ruch, wpis.pk).status_code == 302
        assert klient_admina.get(adres).json()["count"] == oczekiwane
    with django_capture_on_commit_callbacks(execute=True):
        wpis.refresh_from_db()
        wpis.klasa = Klasa.ZWYKLY
        wpis.save(update_fields=["klasa"])
    klucz = caches["teraz"].get(GENERACJA)
    with django_capture_on_commit_callbacks(execute=True):
        wpis.klasa = Klasa.WRAZLIWY
        wpis.save(update_fields=["klasa"])
    assert caches["teraz"].get(GENERACJA) != klucz


@pytest.mark.django_db
def test_zdjecie_wylacznika_wymaga_odrebnego_uprawnienia(klient_admina, django_user_model):
    redaktor = django_user_model.objects.create_user(username="dyzurny", is_staff=True)
    model = WylacznikKategorii._meta.model_name
    redaktor.user_permissions.add(Permission.objects.get(
        content_type__app_label="teraz", codename=f"change_{model}",
    ))
    wylacznik = WylacznikKategorii.objects.create(warstwa=Warstwa.RCB, powod="Decyzja redakcji")
    klient_admina.force_login(redaktor)
    assert akcja(klient_admina, model, "wlacz_wylacznik", wylacznik.pk).status_code == 302
    akcja(klient_admina, model, "zdejmij_wylacznik", wylacznik.pk)
    adres = reverse(f"admin:teraz_{model}_change", args=[wylacznik.pk])
    assert klient_admina.post(adres, {"warstwa": Warstwa.PSP, "aktywny": "", "powod": "Aktualizacja"}).status_code == 302
    wylacznik.refresh_from_db()
    assert wylacznik.aktywny and wylacznik.warstwa == Warstwa.RCB

    redaktor.user_permissions.add(Permission.objects.get(content_type__app_label="teraz", codename="zdejmij_wylacznik"))
    assert akcja(klient_admina, model, "zdejmij_wylacznik", wylacznik.pk).status_code == 302
    wylacznik.refresh_from_db()
    assert not wylacznik.aktywny and wylacznik.zmienil == redaktor


@pytest.mark.django_db
def test_retencja_wpisu_osobowego_uzywa_wlasnego_terminu(zrob_zrodlo, zrob_wpis, settings):
    settings.TERAZ_RETENCJA_ZRZUTOW_DNI = 10
    settings.TERAZ_RETENCJA_OSOBOWE_DNI = 30
    zrodlo = zrob_zrodlo()
    teraz = timezone.now()
    stary = zrob_wpis(zrodlo, klasa=Klasa.OSOBA_POSZUKIWANA, pobrano_at=teraz - timedelta(days=31))
    mlody = zrob_wpis(zrodlo, klasa=Klasa.OSOBA_POSZUKIWANA, pobrano_at=teraz - timedelta(days=29))
    zwykly = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, pobrano_at=stary.pobrano_at)
    tasks.usun_stare_zrzuty()
    stary.refresh_from_db()
    assert not stary.tytul and not stary.tresc and not stary.link
    assert stary.usunieto_at and stary.hash_zewnetrznego_id
    assert stary.ukryty_powod == "Upłynął termin retencji danych osobowych."
    assert stary.pobranie.hash_tresci == "a" * 64
    assert stary.zrodlo == zrodlo and stary.pobrano_at == zwykly.pobrano_at
    for wpis in (mlody, zwykly):
        wpis.refresh_from_db()
        assert wpis.tytul and wpis.tresc and wpis.link and not wpis.usunieto_at


@pytest.mark.django_db
def test_usun_na_zadanie_zachowuje_rejestr_i_zleca_usuniecie_zrzutow(
    klient_admina, django_user_model, zrob_zrodlo, zrob_wpis, monkeypatch, django_capture_on_commit_callbacks,
):
    redaktor = django_user_model.objects.create_superuser(username="wydawca")
    klient_admina.force_login(redaktor)
    zrodlo = zrob_zrodlo(tryb=Zrodlo.Tryb.PUBLICZNY)
    wpis = zrob_wpis(zrodlo, klasa=Klasa.ZWYKLY, zewnetrzny_id="identyfikator-osobowy", teryt=["0264011"])
    zrzut = wpis.pobranie
    kolejny = Pobranie.objects.create(zrodlo=zrodlo, pobrano_at=timezone.now())
    kolejny.wpisy_w_zrzucie.add(wpis)
    zrzut.zrzut.save("pierwszy.bin", ContentFile(b"Dane osobowe"))
    kolejny.zrzut.save("powtorzony.bin", ContentFile(b"Dane osobowe"))
    zdarzenie = Zdarzenie.objects.create(tytul_roboczy=wpis.tytul, pierwszy_wpis_at=wpis.pobrano_at,
                                         ostatni_wpis_at=wpis.pobrano_at)
    zdarzenie.wpisy.add(wpis)
    dziennik = [
        LogEntry.objects.create(user=redaktor, content_type=ContentType.objects.get_for_model(obiekt),
                                object_id=str(obiekt.pk), object_repr=wpis.tytul, action_flag=CHANGE)
        for obiekt in (wpis, zdarzenie)
    ]
    adres = reverse("teraz:wpisy")
    assert klient_admina.get(adres).json()["count"] == 1
    zlec = Mock()
    monkeypatch.setattr(tasks.usun_zrzuty_na_zadanie, "delay", zlec)
    with django_capture_on_commit_callbacks(execute=True):
        assert akcja(klient_admina, "wpis", "usun_na_zadanie", wpis.pk).status_code == 302
    zlec.assert_called_once_with()
    wpis.refresh_from_db()
    zdarzenie.refresh_from_db()
    assert not wpis.tytul and not wpis.tresc and not wpis.link and not wpis.teryt
    assert wpis.zewnetrzny_id != "identyfikator-osobowy" and len(wpis.hash_zewnetrznego_id) == 64
    assert wpis.usunieto_at and wpis.usunal == redaktor and wpis.ukryty_powod == "Żądanie usunięcia danych."
    assert not zdarzenie.tytul_roboczy
    for zapis in dziennik:
        zapis.refresh_from_db()
        assert zapis.object_repr.startswith("Usunięto tytuł")
        assert zapis.user == redaktor and zapis.action_flag == CHANGE
    assert akcja(klient_admina, "wpis", "dopusc", wpis.pk).status_code == 302
    wpis.refresh_from_db()
    assert wpis.status_przegladu == StatusPrzegladu.WSTRZYMANY
    assert klient_admina.get(adres).json()["count"] == 0
    pliki = {pobranie.pk: pobranie.zrzut.name for pobranie in (zrzut, kolejny)}
    for pobranie in (zrzut, kolejny):
        pobranie.refresh_from_db()
        assert pobranie.usunac_zrzut
        podglad = klient_admina.get(reverse("admin:teraz_pobranie_change", args=[pobranie.pk]))
        assert pliki[pobranie.pk] not in podglad.content.decode()
    magazyn = zrzut.zrzut.storage
    with monkeypatch.context() as awaria:
        awaria.setattr(magazyn, "delete", Mock(side_effect=OSError("Testowa awaria magazynu")))
        tasks.usun_zrzuty_na_zadanie()
    zrzut.refresh_from_db()
    assert zrzut.usunac_zrzut and zrzut.zrzut
    tasks.usun_stare_zrzuty()
    for pobranie in (zrzut, kolejny):
        pobranie.refresh_from_db()
        assert not pobranie.zrzut and not pobranie.usunac_zrzut
        assert not magazyn.exists(pliki[pobranie.pk])
    assert zrzut.hash_tresci == "a" * 64


def test_compose_montuje_prywatne_zrzuty_tylko_w_workerze():
    plik = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.production.yml"
    if not plik.is_file():
        pytest.skip("Plik Compose jest dostępny w pełnym repozytorium.")
    yaml = pytest.importorskip("yaml")
    konfiguracja = yaml.safe_load(plik.read_text(encoding="utf-8"))
    uslugi = {
        nazwa for nazwa, usluga in konfiguracja["services"].items()
        if any(wolumen.split(":")[0] == "teraz_zrzuty" for wolumen in usluga.get("volumes", ()))
    }
    assert uslugi == {"worker-teraz"}
