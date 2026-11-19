from datetime import timedelta
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.forms import modelform_factory
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.access_gate import AccessDenied, approved_instruction
from teraz import tasks
from teraz.management.commands import teraz_karty_dostepu as polecenie
from teraz.models import Zrodlo
from teraz.transport import BAZA_FIRMS, SEGMENT_KLUCZA_FIRMS
from teraz.zrodla import cert_pl, emsc, gdacs, gios, imgw_meteo, pse_osp, rcb, usgs
from teraz.zrodla.rejestr import ADAPTERY

Status = SourceAccessInstruction.Status
KLUCZ = "A" * 32
OCZEKIWANE = set(polecenie.zrodla_z_rejestru())
PUBLICZNIE_TAK = {"rcb", "imgw_meteo", "gios", "firms", "emsc", "usgs", "gdacs", "cert_pl", "pse_osp"}

# Adresy, o które adaptery faktycznie proszą bramkę (stałe z kodu adapterów).
ADRESY_ZADAN = {
    "rcb": [rcb.LISTA, f"{rcb.LISTA}?page=2&size=10",
            rcb.adres_karty("/web/rcb/alert-rcb---zagrozenie-z-powietrza-0311")],
    "imgw_meteo": [imgw_meteo.URL_METEO],
    "gios": [gios.URL_STACJI + "?page=0&size=500", f"{gios.URL_INDEKSU}/114"],
    "firms": [f"{BAZA_FIRMS}/{KLUCZ}/{sensor}/{polecenie.OBSZAR_FIRMS}/1" for sensor in ("VIIRS_NOAA20_NRT", "MODIS_NRT")],
    "emsc": [emsc.URL_EMSC],
    "usgs": [usgs.URL_USGS],
    "gdacs": [gdacs.URL_GDACS],
    "cert_pl": [cert_pl.URL_CERT],
    "pse_osp": [pse_osp.URL_PSE],
}


def uruchom(*argumenty):
    wyjscie = StringIO()
    call_command("teraz_karty_dostepu", *argumenty, stdout=wyjscie)
    return wyjscie.getvalue()


def migawka():
    return sorted(SourceAccessInstruction.objects.values_list(
        "source__url", "version", "status", "channel", "allowed_scope", "endpoint", "daily_request_cap"))


def zatwierdz(karta):
    karta.status = Status.APPROVED
    karta.reviewed_at = timezone.now()
    karta.reviewed_by = "Test"
    karta.valid_until = timezone.now() + timedelta(days=5)
    karta.save()


@pytest.mark.django_db
def test_idempotencja_dwa_uruchomienia_te_same_wiersze():
    uruchom()
    pierwsze = migawka()
    zrodla = sorted(Source.objects.values_list("pk", "url", "name", "is_active", "catalog_stage"))
    uruchom()
    assert migawka() == pierwsze
    assert sorted(Source.objects.values_list("pk", "url", "name", "is_active", "catalog_stage")) == zrodla
    assert len(pierwsze) == len(OCZEKIWANE)


@pytest.mark.django_db
def test_nigdy_nie_zatwierdza_i_nie_wypelnia_przegladu():
    uruchom()
    uruchom("--powiaz")
    karty = SourceAccessInstruction.objects.all()
    assert karty.count() == len(OCZEKIWANE)
    assert not karty.filter(status=Status.APPROVED).exists()
    assert set(karty.values_list("status", flat=True)) <= {Status.DRAFT, Status.CONTACT_REQUIRED}
    assert all(karta.reviewed_at is None and karta.reviewed_by == "" and karta.version == 1 for karta in karty)


@pytest.mark.django_db
def test_dry_run_nic_nie_zapisuje():
    wynik = uruchom("--dry-run")
    assert not SourceAccessInstruction.objects.exists()
    assert not Source.objects.exists()
    assert not Zrodlo.objects.filter(zrodlo_dostepu__isnull=False).exists()
    assert "nic nie zapisano" in wynik
    for slug in OCZEKIWANE:
        assert slug in wynik


@pytest.mark.django_db
def test_wszystkie_zrodla_z_rejestru_maja_wiersz_w_wyniku():
    wynik = uruchom()
    wiersze = {linia.split()[0] for linia in wynik.splitlines()[1:-1]}
    assert wiersze == OCZEKIWANE
    assert "teraz-testowy" not in wiersze
    assert set(ADAPTERY) - OCZEKIWANE == {"teraz-testowy"}
    assert OCZEKIWANE <= set(polecenie.KARTY)
    assert set(polecenie.KARTY) <= set(ADAPTERY)


@pytest.mark.django_db
def test_clean_przechodzi_dla_szkicow_i_kontaktu():
    uruchom()
    for karta in SourceAccessInstruction.objects.select_related("source"):
        karta.full_clean()
        karta.source.full_clean(exclude={"catalog_seed_key"})


@pytest.mark.django_db
def test_limity_i_odstepy():
    uruchom()
    for slug in OCZEKIWANE:
        zrodlo = Zrodlo.objects.get(slug=slug)
        karta = SourceAccessInstruction.objects.get(source__name=zrodlo.nazwa)
        assert karta.minimum_interval_seconds >= 3
        if slug in PUBLICZNIE_TAK:
            assert karta.status == Status.DRAFT
            minimum = -(-86400 // zrodlo.czestotliwosc_s) * ADAPTERY[slug].limit_zadan
            assert karta.daily_request_cap >= max(1, minimum), slug
            assert karta.terms_url and karta.evidence["atrybucja"] and karta.evidence["werdykt"]
        else:
            assert karta.status == Status.CONTACT_REQUIRED and karta.daily_request_cap == 0
    assert SourceAccessInstruction.objects.get(source__url=gdacs.URL_GDACS).minimum_interval_seconds == 60
    assert SourceAccessInstruction.objects.get(source__url=rcb.LISTA).minimum_interval_seconds == 5


@pytest.mark.django_db
def test_kontakt_wymagany_dla_imgw_hydro_i_zakresy_zgodne_z_werdyktem():
    uruchom()
    karta = SourceAccessInstruction.objects.get(source__url=Zrodlo.objects.get(slug="imgw_hydro").adres)
    assert karta.status == Status.CONTACT_REQUIRED and karta.daily_request_cap == 0
    assert not karta.source.is_active and karta.source.catalog_stage == "candidate"
    metadane = {slug for slug in OCZEKIWANE if polecenie.KARTY[slug]["zakres"] == SourceAccessInstruction.Scope.METADATA}
    assert metadane == {"cert_pl", "pse_osp"}


@pytest.mark.django_db
def test_emsc_dostaje_kanal_websocket():
    uruchom()
    karta = SourceAccessInstruction.objects.get(endpoint=emsc.URL_EMSC)
    assert karta.channel == "websocket" == SourceAccessInstruction.Channel.WEBSOCKET
    assert karta.source.url == "https://www.seismicportal.eu/"
    karta.full_clean()


@pytest.mark.django_db
def test_atrybucje_z_werdyktu_prawnika_trafiaja_do_evidence():
    uruchom()
    oczekiwane = {
        "rcb": "Źródło: RCB, gov.pl",
        "imgw_meteo": "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej - Państwowy Instytut Badawczy",
        "gios": "Źródło: GIOŚ, Państwowy Monitoring Środowiska",
        "firms": "NASA FIRMS (ESDIS)",
        "emsc": "EMSC-CSEM SeismicPortal",
        "gdacs": "GDACS (ONZ, JRC)",
        "cert_pl": "CERT Polska / NASK",
        "pse_osp": "PSE S.A.",
    }
    for slug, fraza in oczekiwane.items():
        karta = SourceAccessInstruction.objects.get(source__name=Zrodlo.objects.get(slug=slug).nazwa)
        assert fraza in karta.evidence["atrybucja"], slug
        assert karta.evidence["url"] and karta.evidence["warunki"]
    karta_imgw = SourceAccessInstruction.objects.get(source__url=imgw_meteo.URL_METEO)
    assert "zostały przetworzone" in karta_imgw.evidence["atrybucja"]
    assert not any(chr(kod) in str(polecenie.KARTY) for kod in (0x2013, 0x2014))  # bez długich myślników


@pytest.mark.django_db
def test_wybrane_zrodla_i_nieznane_zrodlo():
    uruchom("--zrodlo", "cert_pl", "gdacs")
    assert SourceAccessInstruction.objects.count() == 2
    with pytest.raises(CommandError):
        uruchom("--zrodlo", "nieistniejace")
    uruchom()
    assert SourceAccessInstruction.objects.count() == len(OCZEKIWANE)


@pytest.mark.django_db
def test_istniejaca_karta_i_powiazane_zrodlo_nie_sa_ruszane():
    zrodlo = Zrodlo.objects.get(slug="cert_pl")
    wlasne = Source.objects.create(name="Własne CERT", url="https://cert.pl/", is_active=False, scrape_enabled=False,
                                   catalog_stage="candidate")
    zrodlo.zrodlo_dostepu = wlasne
    zrodlo.save(update_fields=["zrodlo_dostepu"])
    karta = SourceAccessInstruction.objects.create(
        source=wlasne, version=3, status=Status.SUSPENDED, channel="rss", endpoint=cert_pl.URL_CERT, daily_request_cap=7)
    uruchom()
    assert SourceAccessInstruction.objects.filter(source=wlasne).count() == 1
    karta.refresh_from_db()
    assert (karta.status, karta.version, karta.daily_request_cap) == (Status.SUSPENDED, 3, 7)
    assert Source.objects.filter(name="Własne CERT").count() == 1


@pytest.mark.django_db
def test_brak_wiersza_zrodla_teraz_jest_zgloszony():
    Zrodlo.objects.filter(slug="cert_pl").delete()
    wynik = uruchom()
    assert "brak wiersza źródła Teraz" in wynik
    assert SourceAccessInstruction.objects.count() == len(OCZEKIWANE) - 1


@pytest.mark.django_db
def test_powiaz_dziala_tylko_po_zatwierdzeniu_przez_czlowieka():
    uruchom("--powiaz")
    assert not Zrodlo.objects.filter(zrodlo_dostepu__isnull=False).exists()
    assert not Source.objects.filter(is_active=True).exists()
    assert not tasks.nalezne_zrodla().filter(slug="cert_pl").exists()

    karta = SourceAccessInstruction.objects.get(source__url=cert_pl.URL_CERT)
    zatwierdz(karta)
    wynik = uruchom("--powiaz")
    assert "włączono źródło" in wynik and "już powiązano" not in wynik
    zrodlo = Zrodlo.objects.get(slug="cert_pl")
    assert zrodlo.zrodlo_dostepu == karta.source and karta.source.is_active and karta.source.scrape_enabled
    assert Zrodlo.objects.filter(zrodlo_dostepu__isnull=False).count() == 1
    assert tasks.nalezne_zrodla().filter(slug="cert_pl").exists()
    assert "już powiązano" in uruchom("--powiaz")


@pytest.mark.django_db
@pytest.mark.parametrize("slug", sorted(PUBLICZNIE_TAK))
def test_po_zatwierdzeniu_bramka_przepuszcza_adresy_adaptera_i_tylko_je(slug):
    uruchom()
    zrodlo = Zrodlo.objects.get(slug=slug)
    karta = SourceAccessInstruction.objects.get(source__url=polecenie.KARTY[slug].get("strona", zrodlo.adres))
    for adres in ADRESY_ZADAN[slug]:
        assert approved_instruction(karta.source, karta.channel, adres) is None  # szkic nie przepuszcza niczego
    zatwierdz(karta)
    uruchom("--powiaz")
    zrodlo.refresh_from_db()
    karta = SourceAccessInstruction.objects.select_related("source").get(pk=karta.pk)
    for adres in ADRESY_ZADAN[slug]:
        assert approved_instruction(karta.source, karta.channel, adres) == karta, adres
    for obcy in ("https://example.org/", "https://www.gov.pl/web/gov/prawa-autorskie/inne", f"{karta.endpoint}/../x/y/z"):
        assert approved_instruction(karta.source, karta.channel, obcy) is None, obcy
    if slug not in ("firms", "emsc"):
        adapter = ADAPTERY[slug](zrodlo)
        assert adapter.karta_dostepu(ADRESY_ZADAN[slug][0]) == karta
        with pytest.raises(AccessDenied):
            adapter.karta_dostepu("https://example.org/")
    if slug == "emsc":
        assert emsc.AdapterEMSC(zrodlo).karta_dostepu(emsc.URL_EMSC) == karta


@pytest.mark.django_db
def test_klucz_firms_poza_wzorcem_jest_odrzucony():
    uruchom()
    karta = SourceAccessInstruction.objects.get(endpoint=BAZA_FIRMS)
    zatwierdz(karta)
    uruchom("--powiaz")
    karta = SourceAccessInstruction.objects.select_related("source").get(pk=karta.pk)
    sensor_zly =f"{BAZA_FIRMS}/{KLUCZ}/INNY_SENSOR/{polecenie.OBSZAR_FIRMS}/1"
    obszar_zly = f"{BAZA_FIRMS}/{KLUCZ}/MODIS_NRT/0,0,1,1/1"
    placeholder = f"{BAZA_FIRMS}/{SEGMENT_KLUCZA_FIRMS}/MODIS_NRT/{polecenie.OBSZAR_FIRMS}/1"
    assert approved_instruction(karta.source, karta.channel, sensor_zly) is None
    assert approved_instruction(karta.source, karta.channel, obszar_zly) is None
    assert approved_instruction(karta.source, karta.channel, placeholder) == karta


def test_formularz_karty_przyjmuje_wss_i_odrzuca_inne_schematy():
    """Panel administratora musi móc zapisać kartę EMSC (wss), ale nie karty z ftp lub ws."""
    formularz = modelform_factory(SourceAccessInstruction, fields=["endpoint"])
    assert formularz(data={"endpoint": emsc.URL_EMSC}).is_valid()
    assert formularz(data={"endpoint": "https://www.gov.pl/web/rcb"}).is_valid()
    assert not formularz(data={"endpoint": "ftp://example.org/x"}).is_valid()
    assert not formularz(data={"endpoint": "ws://example.org/x"}).is_valid()


@pytest.mark.django_db
def test_zatwierdzenie_bez_przegladu_nie_przechodzi_clean():
    """Zatwierdzenie bez daty i autora przeglądu jest odrzucane przez model: człowiek musi wypełnić przegląd."""
    uruchom()
    karta = SourceAccessInstruction.objects.get(source__url=cert_pl.URL_CERT)
    karta.status = Status.APPROVED
    with pytest.raises(ValidationError):
        karta.full_clean()
