from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from django.apps import apps
from django.db import connection
from django.utils import timezone

from teraz.models import Zrodlo
from teraz.retencja import wyczysc_wpisy
from teraz.zrodla import rcb

from .test_zrodla import SCOPE, karta_rcb, link_rcb, odpowiedz

migracja = import_module("teraz.migrations.0005_decyzje_archiwum_i_pomiary")


@pytest.mark.django_db
def test_migracja_odroznia_rekomendacje_od_podstawy_wydawcy():
    zrodlo_rcb = Zrodlo.objects.get(slug="rcb")
    Zrodlo.objects.filter(pk=zrodlo_rcb.pk).update(podstawa_prawna=zrodlo_rcb.podstawa_rekomendowana, tryb="publiczny")
    Zrodlo.objects.filter(slug="gios").update(tryb="publiczny", podstawa_prawna="Zweryfikowana decyzja wydawcy.")
    Zrodlo.objects.filter(slug="mon").update(tryb="publiczny", rekomendowany_tryb="publiczny",
                                            podstawa_prawna="Zweryfikowana decyzja wydawcy.")
    migracja.przenies_rekomendacje(apps, SimpleNamespace(connection=connection))
    zrodlo_rcb.refresh_from_db()
    gios = Zrodlo.objects.get(slug="gios")
    mon = Zrodlo.objects.get(slug="mon")
    assert zrodlo_rcb.tryb == "wewnetrzny" and not zrodlo_rcb.podstawa_prawna and zrodlo_rcb.podstawa_rekomendowana
    assert gios.tryb == "publiczny" and gios.podstawa_prawna == "Zweryfikowana decyzja wydawcy."
    assert mon.tryb == mon.rekomendowany_tryb == "wewnetrzny" and mon.podstawa_prawna == gios.podstawa_prawna


@pytest.mark.django_db
def test_migracja_redukuje_stare_pomiary(zrob_wpis):
    gios = Zrodlo.objects.get(slug="gios")
    czas = timezone.now()
    gios.stan_adaptera = {"indeksy": {"52": [czas.isoformat(), 3]}}
    gios.save(update_fields=["stan_adaptera"])
    zrob_wpis(gios, zewnetrzny_id="52:stary:4", opublikowano_at=czas - timedelta(hours=2))
    aktualny = zrob_wpis(gios, zewnetrzny_id="52:nowszy:5", opublikowano_at=czas - timedelta(hours=1), wersje=[{}])
    hydro = Zrodlo.objects.get(slug="imgw_hydro")
    pomiar = zrob_wpis(hydro, zewnetrzny_id="stan:101", wersje=[{}])
    ostrzezenie = zrob_wpis(hydro, zewnetrzny_id="ostrzezenie-1", wersje=[{}])
    migracja.uporzadkuj_wpisy(apps, SimpleNamespace(connection=connection))
    aktualny.refresh_from_db()
    pomiar.refresh_from_db()
    ostrzezenie.refresh_from_db()
    assert gios.wpisy.count() == 1 and aktualny.zewnetrzny_id == "indeks:52"
    assert not aktualny.pomiar_aktywny and aktualny.opublikowano_at == czas
    assert not aktualny.wersje and not pomiar.wersje and ostrzezenie.wersje == [{}]


@pytest.mark.django_db
@pytest.mark.parametrize("usuniety", [False, True])
def test_migracja_i_import_rcb_z_dotychczasowym_id(zrob_wpis, monkeypatch, usuniety):
    zrodlo = Zrodlo.objects.get(slug="rcb")
    adres = link_rcb("10")
    adapter = rcb.ArchiwumRCB(zrodlo)
    karta = odpowiedz(karta_rcb("10"))
    _, aktualizacja = rcb.parsuj_karte(karta, adres)
    stary_id = f"{urlsplit(adres).path}:aktualizacja:10:55:1"
    stary = zrob_wpis(zrodlo, zewnetrzny_id=stary_id, tresc=aktualizacja["tresc"],
                     miejsce="ul. Leśna 12", wersje=[{"miejsce": "ul. Leśna 12"}])
    stary.pobranie.wersja_parsera = "2"
    stary.pobranie.odcisk_adresu = adapter.odcisk_adresu(adres)
    stary.pobranie.save(update_fields=["wersja_parsera", "odcisk_adresu"])
    if usuniety:
        wyczysc_wpisy(zrodlo.wpisy.all(), "Żądanie usunięcia danych.")
    migracja.uporzadkuj_wpisy(apps, SimpleNamespace(connection=connection))
    stary.refresh_from_db()
    assert not stary.miejsce
    if not usuniety:
        assert stary.zewnetrzny_id == aktualizacja["zewnetrzny_id"] and stary.wersje == [{"miejsce": ""}]
    zrodlo.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [adres]}}
    zrodlo.save(update_fields=["stan_adaptera"])
    monkeypatch.setattr(rcb.ArchiwumRCB, "pobierz", lambda *args: (karta, SCOPE))
    adapter.zbierz()
    assert zrodlo.wpisy.count() == 2
    assert zrodlo.wpisy.filter(tresc=aktualizacja["tresc"]).exists() is not usuniety
