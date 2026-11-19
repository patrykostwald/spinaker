import json
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone as utc_timezone
from hashlib import sha256
from time import monotonic, sleep
from urllib.parse import urlsplit
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from news.models import SourceAccessInstruction
from scraper.access_gate import AccessDenied, require_approved_instruction
from scraper.utils import reserve_daily_fetch_budget

from .cache import uniewaznij_po_zapisie
from .models import Klasa, Pobranie, StatusPrzegladu, Wpis, Zdarzenie, Zrodlo
from .retencja import hash_id_wpisu
from .transport import BladKonfiguracji, BladFormatu, BladPobrania, LimitHosta, OdpowiedzHTTP, budzet_czasu, kanoniczny_adres, pobierz_http

log = logging.getLogger(__name__)
Scope = SourceAccessInstruction.Scope
KANALY = {
    Zrodlo.SposobDostepu.API: SourceAccessInstruction.Channel.API,
    Zrodlo.SposobDostepu.RSS: SourceAccessInstruction.Channel.RSS,
    Zrodlo.SposobDostepu.HTML: SourceAccessInstruction.Channel.HTML,
    Zrodlo.SposobDostepu.WEBSOCKET: "websocket",
}
POLA_WERSJI = (
    "tytul", "tresc", "link", "opublikowano_at", "czas_zrodlowy_at", "dokladna_godzina_publikacji",
    "miejsce", "teryt", "szerokosc", "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji",
)
POLA_PARSERA = frozenset((*POLA_WERSJI, "zewnetrzny_id", "klasa", "pomiar_aktywny", "zdarzenie_id", "status_zdarzenia"))
POLA_LOKALIZACJI = ("miejsce", "teryt", "szerokosc", "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji")
POLA_DO_PRZEGLADU = ("tytul", "tresc", *POLA_LOKALIZACJI)
LIMIT_WERSJI = 20
POZIOMY_DOKLADNOSCI = tuple(reversed(Wpis.Dokladnosc.values))
OCHRONA_KLAS = {
    Klasa.ZWYKLY: 0,
    Klasa.NIEZNANA: 1,
    Klasa.WRAZLIWY: 1,
    Klasa.WOJSKO_GRANICA: 2,
    Klasa.INFRASTRUKTURA: 2,
    Klasa.OSOBA_POSZUKIWANA: 3,
}
WYZWANIE_BOTA = re.compile(
    rb"_incapsula_resource\?swkmtfsr|id=[\"'](?:challenge-form|cf-challenge-running|captcha-box)[\"']",
    re.IGNORECASE,
)
TYTUL_WYZWANIA = re.compile(
    rb"<title>[^<]*(?:just a moment|attention required|request blocked|access denied|403 forbidden)", re.IGNORECASE,
)
POCZATEK_HTML = re.compile(rb"(?:<!doctype\s+html\b|<html[\s>])", re.IGNORECASE)
POCZATEK_KANALU = re.compile(rb"(?:<\?[^?]*\?>\s*|<!--(?:(?!-->).)*-->\s*)*<(?:[\w.-]+:)?(?:rss|feed)\b", re.I | re.S)


class PrzerwijCykl(Exception):
    """Zachowaj wykonane pobrania i wróć podczas następnego cyklu."""


# Kody HTTP, po których ta sama prośba może się udać przy ponowieniu (Z6P7a pkt 9): limit, przeterminowanie, zbyt wczesne
# żądanie i każdy błąd serwera (w tym 502 i 504). Element kolejki z takim błędem wraca do ponowienia, nie jest pomijany.
PRZEJSCIOWE_HTTP = frozenset({408, 425, 429})


def blad_przejsciowy(status):
    return status in PRZEJSCIOWE_HTTP or (status is not None and status >= 500)


def hash_tresci(tresc, kodowanie=None):
    try:
        tekst = tresc.decode(kodowanie or "utf-8")
    except (LookupError, UnicodeError) as exc:
        raise BladPobrania("Nie można odczytać kodowania odpowiedzi.") from exc
    tekst = tekst.replace("\r\n", "\n").replace("\r", "\n")
    tekst = unicodedata.normalize("NFC", "\n".join(wiersz.rstrip() for wiersz in tekst.split("\n")))
    return sha256(tekst.encode("utf-8")).hexdigest()


def _walidator_http(odpowiedz, nazwa, dlugosc):
    wartosc = odpowiedz.naglowki.get(nazwa, "")
    return wartosc if len(wartosc) <= dlugosc and "\r" not in wartosc and "\n" not in wartosc else ""


def _sprawdz_czas(wartosc):
    if not isinstance(wartosc, datetime) or timezone.is_naive(wartosc):
        raise ValidationError("Czas publikacji musi zawierać strefę czasową.")


def _dane_wersji(wpis):
    dane = {pole: getattr(wpis, pole) for pole in POLA_WERSJI}
    return {pole: wartosc.astimezone(utc_timezone.utc).isoformat() if isinstance(wartosc, datetime) else wartosc for pole, wartosc in dane.items()}


def _hash_wersji(dane):
    return hash_tresci(json.dumps(dane, ensure_ascii=False, sort_keys=True).encode())


def _aktualizuj_wpis(obecny, nowy, zakres, czas, *, pomiar=False):
    if pomiar and nowy.opublikowano_at < obecny.opublikowano_at:
        return False
    poprzednie = _dane_wersji(obecny)
    dane = _dane_wersji(nowy)
    ponowny_przeglad = any(poprzednie[pole] != dane[pole] for pole in POLA_DO_PRZEGLADU)
    # Karta metadanych nie upoważnia do przywrócenia starszej treści w bieżącej wersji.
    skrot = _hash_wersji(dane)
    zmiana_wersji = skrot != (obecny.hash_wersji or _hash_wersji(poprzednie))
    pola = []
    if zmiana_wersji:
        if zakres == Scope.METADATA:
            poprzednie["tresc"] = ""
        if not pomiar:
            wersja = {"zastapiono_at": czas.isoformat(), **poprzednie}
            if obecny.klasa == nowy.klasa == Klasa.ZWYKLY and (
                POZIOMY_DOKLADNOSCI.index(nowy.dokladnosc) > POZIOMY_DOKLADNOSCI.index(obecny.dokladnosc)
                or obecny.szerokosc is None and nowy.szerokosc is not None
            ):
                wersja["zwiekszono_dokladnosc"] = True
            obecny.wersje = [*obecny.wersje[-(LIMIT_WERSJI - 1):], wersja]
            pola.append("wersje")
        for pole in POLA_WERSJI:
            setattr(obecny, pole, getattr(nowy, pole))
        obecny.hash_wersji = skrot
        pola.extend((*POLA_WERSJI, "hash_wersji"))
    if pomiar and obecny.wersje:
        obecny.wersje = []
        pola.append("wersje")
    if obecny.pomiar_aktywny != nowy.pomiar_aktywny:
        obecny.pomiar_aktywny = nowy.pomiar_aktywny
        pola.append("pomiar_aktywny")
    wyzsza_ochrona = OCHRONA_KLAS[nowy.klasa] > OCHRONA_KLAS[obecny.klasa]
    if wyzsza_ochrona:
        obecny.klasa = nowy.klasa
        pola.append("klasa")
    if obecny.klasa != Klasa.ZWYKLY and (
        zmiana_wersji and ponowny_przeglad
        or wyzsza_ochrona and obecny.status_przegladu == StatusPrzegladu.DOPUSZCZONY
    ):
        obecny.status_przegladu = StatusPrzegladu.DO_PRZEGLADU
        obecny.przeglad_zmienil = None
        obecny.przeglad_zmiana_at = None
        pola.extend(("status_przegladu", "przeglad_zmienil", "przeglad_zmiana_at"))
    if pola:
        obecny.save(update_fields=pola)
    return bool(pola)


class Cykl:
    def __init__(self, adapter, zrodlo, start):
        self.adapter = adapter
        self.stan = deepcopy(zrodlo.stan_adaptera)
        self.kontynuacja_at = zrodlo.kontynuacja_at
        self.start = start
        self.termin = monotonic() + adapter.limit_czasu_s
        self.zadania = 0
        self.ostatnie = None
        self.status = None
        self.odcisk = ""
        self.blokada = False
        self.blad_kolejki = False
        self.termin_hosta = {}

    def wykonaj(self, adres, *, parser=None, zawsze_parsuj=False, po_odczycie=None, zrzut=True, warunkowo=True):
        if self.zadania >= self.adapter.limit_zadan or monotonic() >= self.termin:
            raise PrzerwijCykl
        self.status = None
        self.odcisk = ""
        adres = kanoniczny_adres(adres)
        self.odcisk = self.adapter.odcisk_adresu(adres)
        poprzednie = self.adapter._ostatnie_udane(self.odcisk)
        naglowki = {}
        ta_sama_wersja = poprzednie and poprzednie.wersja_parsera == self.adapter.wersja_parsera
        if warunkowo and ta_sama_wersja and poprzednie.etag:
            naglowki["If-None-Match"] = poprzednie.etag
        if warunkowo and ta_sama_wersja and poprzednie.last_modified:
            naglowki["If-Modified-Since"] = poprzednie.last_modified

        self.zadania += 1
        with budzet_czasu(self.termin):
            odpowiedz, zakres = self.adapter.pobierz(adres, naglowki)
        self.status = odpowiedz.status
        typ = odpowiedz.naglowki.get("Content-Type", "").partition(";")[0].strip().lower()
        poczatek = odpowiedz.tresc[:65536]
        dokument = poczatek.removeprefix(b"\xef\xbb\xbf").lstrip()
        html = not POCZATEK_KANALU.match(dokument) and (
            typ in {"text/html", "application/xhtml+xml"} or
            not typ and (POCZATEK_HTML.match(dokument) or
                         self.adapter.zrodlo.sposob_dostepu == Zrodlo.SposobDostepu.HTML)
        )
        self.blokada = (
            self.status == 403 or odpowiedz.naglowki.get("cf-mitigated") == "challenge"
            or bool(WYZWANIE_BOTA.search(poczatek) or html and TYTUL_WYZWANIA.search(poczatek))
        )
        if self.blokada:
            raise BladPobrania("Odmowa dostępu lub wyzwanie bota.", status_http=self.status)
        if self.status == 304 and naglowki:
            skrot, wpisy = poprzednie.hash_tresci, []
        elif not 200 <= self.status < 300 or self.status == 206:
            raise BladPobrania(f"http_{self.status}", status_http=self.status)
        else:
            skrot = hash_tresci(odpowiedz.tresc, odpowiedz.kodowanie)
            wpisy = []
            if zawsze_parsuj or not (ta_sama_wersja and poprzednie.hash_tresci == skrot):
                wpisy = self.adapter._parsuj(parser or self.adapter.parsuj, odpowiedz)
        if po_odczycie:
            po_odczycie()
        self.ostatnie = self.adapter._zapisz(self, odpowiedz, zakres, skrot, wpisy, poprzednie, zrzut)
        if self.ostatnie is None:
            raise PrzerwijCykl
        return self.ostatnie

    def wykonaj_element_kolejki(self, adres, *, przesun, odloz=None, **opcje):
        """Jeden element kolejki. Błąd trwały (np. 404) pomija element (`przesun`). Błąd przejściowy (408, 425, 429, 5xx), gdy kolejka
        podaje `odloz`, nie pomija go po cichu: element wraca do ponowienia (R38d, Z6P6 pkt 7)."""
        try:
            return self.wykonaj(adres, po_odczycie=przesun, **opcje)
        except BladPobrania as exc:
            status = exc.status_http
            if self.blokada or status is None or not 400 <= status < 600 or status == 403:
                raise
            if odloz is not None and blad_przejsciowy(status):
                odloz()
            else:
                przesun()
            self.stan["bledy_kolejki"] = self.stan.get("bledy_kolejki", 0) + 1
            self.blad_kolejki = True
            self.ostatnie = self.adapter._zapisz_blad(self, exc, blad_elementu=True)
            if self.ostatnie is None or status == 429:
                raise PrzerwijCykl
            return self.ostatnie


class Adapter(ABC):
    wersja_parsera = "2"
    limit_zadan = 1
    limit_czasu_s = 35
    minimalny_odstep = 3
    pole_proby = "ostatnie_pobranie_at"
    pola_stanu_bledu = ()

    def __init__(self, zrodlo):
        self.zrodlo = zrodlo
        self.cykl = None

    def odcisk_adresu(self, adres):
        return sha256(adres.encode()).hexdigest()

    def karta_dostepu(self, adres):
        kanal = KANALY.get(self.zrodlo.sposob_dostepu)
        if kanal is None:
            raise AccessDenied("nieobslugiwany_kanal")
        instrukcja = require_approved_instruction(self.zrodlo.zrodlo_dostepu, kanal, request_url=adres)
        if instrukcja.allowed_scope not in Scope.values:
            raise AccessDenied("nieznany_zakres_instrukcji")
        return instrukcja

    def pobierz(self, adres, naglowki):
        instrukcja = self.karta_dostepu(adres)
        kanoniczny_adres(instrukcja.endpoint)
        odstep = max(self.minimalny_odstep, instrukcja.minimum_interval_seconds)
        host = urlsplit(adres).hostname
        poprzedni_termin = self.cykl.termin_hosta.get(host, 0)
        czekaj = poprzedni_termin - monotonic()
        if czekaj > 0:
            if poprzedni_termin >= self.cykl.termin:
                raise PrzerwijCykl
            sleep(czekaj)

        def zarezerwuj_budzet():
            if not reserve_daily_fetch_budget(instrukcja):
                raise AccessDenied("limit_dzienny_instrukcji")
            self.cykl.termin_hosta[host] = monotonic() + odstep

        odpowiedz = self._transport(
            adres, naglowki, instrukcja=instrukcja, minimalny_odstep=odstep, przed_zadaniem=zarezerwuj_budzet,
        )
        return odpowiedz, instrukcja.allowed_scope

    def _transport(self, adres, naglowki, *, instrukcja, **opcje):
        return pobierz_http(adres, naglowki, **opcje)

    @abstractmethod
    def parsuj(self, odpowiedz):
        """Zwróć listę słowników wpisów zgodnych z POLA_PARSERA."""

    def przeprowadz(self, cykl):
        cykl.wykonaj(self.zrodlo.adres)

    def czas_publikacji(self, odpowiedz):
        return None

    def _otworz_cykl(self):
        start = timezone.now()
        with transaction.atomic():
            zrodlo = Zrodlo.objects.select_for_update().filter(pk=self.zrodlo.pk).first()
            if not self._dostepne(zrodlo):
                return None, None
            poprzednia_proba = getattr(zrodlo, self.pole_proby)
            setattr(zrodlo, self.pole_proby, start)
            zrodlo.save(update_fields=[self.pole_proby])
        return Cykl(self, zrodlo, start), poprzednia_proba

    def _dostepne(self, zrodlo):
        return (zrodlo and zrodlo.tryb != Zrodlo.Tryb.WYLACZONY and not zrodlo.blokada_dostepu
                and zrodlo.adres == self.zrodlo.adres and zrodlo.zrodlo_dostepu_id == self.zrodlo.zrodlo_dostepu_id
                and zrodlo.sposob_dostepu == self.zrodlo.sposob_dostepu)

    def zbierz(self):
        cykl, poprzednia_proba = self._otworz_cykl()
        if cykl is None:
            return None
        self.cykl = cykl
        try:
            self.przeprowadz(cykl)
        except LimitHosta:
            if cykl.ostatnie is None:
                Zrodlo.objects.filter(pk=self.zrodlo.pk, **{self.pole_proby: cykl.start}).update(
                    **{self.pole_proby: poprzednia_proba},
                )
        except PrzerwijCykl:
            pass
        except (AccessDenied, BladPobrania, ValidationError, SoftTimeLimitExceeded) as exc:
            return self._zapisz_blad(cykl, exc)
        else:
            if cykl.ostatnie is not None and not cykl.blad_kolejki:
                Zrodlo.objects.filter(pk=self.zrodlo.pk, blokada_dostepu=False,
                                      **{self.pole_proby: cykl.start}).update(ostatni_blad="", kolejne_bledy=0)
        finally:
            self.cykl = None
        return cykl.ostatnie

    def _parsuj(self, parser, odpowiedz):
        try:
            wpisy = parser(odpowiedz)
        except (TypeError, ValueError, LookupError, SyntaxError, AttributeError, RecursionError) as exc:
            raise BladFormatu("Nie udało się odczytać wpisów. Sprawdź format danych źródła.") from exc
        if not isinstance(wpisy, list):
            raise BladFormatu("Parser musi zwrócić listę wpisów.")
        return wpisy

    def _ostatnie_udane(self, odcisk):
        return (self.zrodlo.pobrania.filter(odcisk_adresu=odcisk).exclude(hash_tresci="")
                .order_by("-pobrano_at", "-pk").first())

    def _zablokuj_zrodlo(self, cykl):
        zrodlo = Zrodlo.objects.select_for_update().filter(pk=self.zrodlo.pk).first()
        return zrodlo if self._dostepne(zrodlo) and getattr(zrodlo, self.pole_proby) == cykl.start else None

    def _zapisz_blad(self, cykl, exc, *, blad_elementu=False):
        status = getattr(exc, "status_http", None)
        if status is None:
            status = cykl.status
        blad = str(exc) if isinstance(exc, (BladKonfiguracji, BladFormatu)) else type(exc).__name__
        cykl.blokada |= status == 403
        if cykl.blokada:
            blad = "Dostęp wstrzymany: HTTP 403 lub wyzwanie bota."
        elif isinstance(exc, BladPobrania) and status and str(exc) == f"http_{status}":
            blad = str(exc)
        with transaction.atomic():
            zrodlo = self._zablokuj_zrodlo(cykl)
            if zrodlo is None:
                return None
            pobranie = Pobranie.objects.create(zrodlo=zrodlo, pobrano_at=timezone.now(), status_http=status,
                odcisk_adresu=cykl.odcisk, wersja_parsera=self.wersja_parsera)
            zrodlo.ostatni_blad = blad[:200]
            zrodlo.kolejne_bledy += 1
            zrodlo.blokada_dostepu = cykl.blokada
            if blad_elementu:
                zrodlo.stan_adaptera = cykl.stan
            else:
                for pole in self.pola_stanu_bledu:
                    if pole in cykl.stan:
                        zrodlo.stan_adaptera[pole] = cykl.stan[pole]
                    else:
                        zrodlo.stan_adaptera.pop(pole, None)
            zrodlo.kontynuacja_at = cykl.kontynuacja_at if blad_elementu else None
            zrodlo.save(update_fields=["ostatni_blad", "kolejne_bledy", "blokada_dostepu", "kontynuacja_at", "stan_adaptera"])
        return pobranie

    def _zapisz(self, cykl, odpowiedz, zakres, skrot, wpisy, poprzednie, zrzut=True):
        czas = timezone.now()
        etag = _walidator_http(odpowiedz, "ETag", 1024)
        last_modified = _walidator_http(odpowiedz, "Last-Modified", 128)
        status = odpowiedz.status
        if status == 304:
            etag = etag or poprzednie.etag
            last_modified = last_modified or poprzednie.last_modified
            opublikowano = poprzednie.opublikowano_at
        else:
            opublikowano = self.czas_publikacji(odpowiedz)
            if opublikowano is not None:
                _sprawdz_czas(opublikowano)

        pobranie = Pobranie(pobrano_at=czas, opublikowano_at=opublikowano, status_http=status, etag=etag,
            last_modified=last_modified, hash_tresci=skrot, odcisk_adresu=cykl.odcisk, wersja_parsera=self.wersja_parsera)
        try:
            with transaction.atomic():
                zrodlo = self._zablokuj_zrodlo(cykl)
                if zrodlo is None:
                    return None
                pobranie.zrodlo = zrodlo
                pobranie.bez_zmian = bool(poprzednie and poprzednie.hash_tresci == skrot)
                pobranie.dane_osobowe = pobranie.bez_zmian and poprzednie.dane_osobowe
                pobranie.save()
                zapisane, osobowe, usuniete, zmiana = self._zapisz_wpisy(pobranie, wpisy, zakres)
                pobranie.dane_osobowe |= osobowe
                if zrzut and zakres == Scope.SNAPSHOT and status != 304 and not pobranie.bez_zmian and not usuniete:
                    pobranie.zrzut.save(f"{uuid4().hex}.bin", ContentFile(odpowiedz.tresc), save=False)
                    pobranie.wpisy_w_zrzucie.add(*zapisane)
                pobranie.save(update_fields=["dane_osobowe", "zrzut"])
                if zmiana:
                    uniewaznij_po_zapisie(zrodlo._state.db)
                zrodlo.ostatni_sukces_at = czas
                zrodlo.stan_adaptera = cykl.stan
                zrodlo.kontynuacja_at = cykl.kontynuacja_at
                zrodlo.save(update_fields=["ostatni_sukces_at", "stan_adaptera", "kontynuacja_at"])
        except Exception:
            if pobranie.zrzut and pobranie.zrzut._committed:
                try:
                    if not Pobranie.objects.filter(zrzut=pobranie.zrzut.name).exists():
                        pobranie.zrzut.delete(save=False)
                except OSError:
                    log.warning("Nie udało się usunąć niedokończonego zrzutu Teraz.")
            raise
        return pobranie

    def _zapisz_wpisy(self, pobranie, wpisy, zakres):
        kandydaci = {}
        for dane in wpisy:
            if not isinstance(dane, dict) or not dane.keys() <= POLA_PARSERA:
                raise BladFormatu("Parser zwrócił wpis z nieobsługiwanymi polami.")
            dane = dane.copy()
            grupa = dane.pop("zdarzenie_id", "")
            status = dane.pop("status_zdarzenia", None)
            _sprawdz_czas(dane.get("opublikowano_at"))
            if dane.get("czas_zrodlowy_at") is not None:
                _sprawdz_czas(dane["czas_zrodlowy_at"])
            wpis = Wpis(**dane, zrodlo=pobranie.zrodlo, pobranie=pobranie, pobrano_at=pobranie.pobrano_at)
            if zakres == Scope.METADATA:
                wpis.tresc = ""
                wpis.miejsce = ""
            wpis.full_clean(exclude={"zrodlo", "pobranie"}, validate_unique=False, validate_constraints=False)
            kandydaci.setdefault(wpis.zewnetrzny_id, (wpis, grupa, status))

        odciski = {hash_id_wpisu(identyfikator): identyfikator for identyfikator in kandydaci}
        usuniete = set(Wpis.objects.filter(zrodlo=pobranie.zrodlo, hash_zewnetrznego_id__in=odciski)
                      .values_list("hash_zewnetrznego_id", flat=True))
        for odcisk in usuniete:
            kandydaci.pop(odciski[odcisk])
        istniejace = {wpis.zewnetrzny_id: wpis for wpis in Wpis.objects.select_for_update().filter(
            zrodlo=pobranie.zrodlo, zewnetrzny_id__in=kandydaci)}
        zapisane = []
        osobowe = zmiana = False
        for identyfikator, (nowy, grupa, status) in kandydaci.items():
            wpis = istniejace.get(identyfikator)
            if wpis is None:
                wpis = nowy
                wpis.hash_wersji = _hash_wersji(_dane_wersji(wpis))
                wpis.save()
                zmiana = True
            else:
                pomiar = (pobranie.zrodlo.slug == "gios" or
                          pobranie.zrodlo.slug == "imgw_hydro" and identyfikator.startswith("stan:"))
                zmiana |= _aktualizuj_wpis(wpis, nowy, zakres, pobranie.pobrano_at, pomiar=pomiar)
            if grupa:
                zmiana |= _dolacz_zdarzenie(wpis, grupa, status)
            osobowe |= wpis.klasa == Klasa.OSOBA_POSZUKIWANA
            zapisane.append(wpis.pk)
        return zapisane, osobowe, bool(usuniete), zmiana


def _dolacz_zdarzenie(wpis, grupa, status):
    if status not in (Zdarzenie.Status.KOMUNIKAT_OFICJALNY, Zdarzenie.Status.ODWOLANE, Zdarzenie.Status.ZGLOSZONE):
        raise BladFormatu("Nieobsługiwany status zdarzenia automatycznego.")
    czas = wpis.czas_zrodlowy_at if wpis.zrodlo.slug == "rcb" and wpis.czas_zrodlowy_at else wpis.opublikowano_at
    zdarzenie, nowe = Zdarzenie.objects.get_or_create(
        zrodlo_automatu=wpis.zrodlo, identyfikator_automatu=hash_id_wpisu(grupa),
        defaults=dict(tytul_roboczy=wpis.tytul, status=status, pierwszy_wpis_at=czas, ostatni_wpis_at=czas),
    )
    powiazanie = not zdarzenie.wpisy.filter(pk=wpis.pk).exists()
    if powiazanie:
        zdarzenie.wpisy.add(wpis)
    pola = {}
    if czas < zdarzenie.pierwszy_wpis_at:
        pola["pierwszy_wpis_at"] = czas
    if czas > zdarzenie.ostatni_wpis_at:
        pola["ostatni_wpis_at"] = czas
    if status == Zdarzenie.Status.ODWOLANE and zdarzenie.status != status:
        pola["status"] = status
    if pola:
        Zdarzenie.objects.filter(pk=zdarzenie.pk).update(**pola)
    return nowe or powiazanie or bool(pola)


class AdapterTestowy(Adapter):
    def pobierz(self, adres, naglowki):
        return OdpowiedzHTTP(200, {}, b"[]", "utf-8"), Scope.METADATA

    def parsuj(self, odpowiedz):
        return []
