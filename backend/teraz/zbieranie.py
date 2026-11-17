import logging
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime
from hashlib import sha256
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
from .models import Klasa, Pobranie, Wpis, Zrodlo
from .retencja import hash_id_wpisu
from .transport import BladPobrania, LimitHosta, OdpowiedzHTTP, kanoniczny_adres, pobierz_http

log = logging.getLogger(__name__)
Scope = SourceAccessInstruction.Scope
KANALY = {
    Zrodlo.SposobDostepu.API: SourceAccessInstruction.Channel.API,
    Zrodlo.SposobDostepu.RSS: SourceAccessInstruction.Channel.RSS,
    Zrodlo.SposobDostepu.HTML: SourceAccessInstruction.Channel.HTML,
}
POLA_PARSERA = frozenset({"zewnetrzny_id", "tytul", "tresc", "link", "opublikowano_at", "klasa",
                          "teryt", "szerokosc", "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji"})


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


class Adapter(ABC):
    wersja_parsera = "1"

    def __init__(self, zrodlo):
        self.zrodlo = zrodlo

    def pobierz(self, adres, naglowki):
        kanal = KANALY.get(self.zrodlo.sposob_dostepu)
        if kanal is None:
            raise AccessDenied("nieobslugiwany_kanal")
        instrukcja = require_approved_instruction(self.zrodlo.zrodlo_dostepu, kanal, request_url=adres)
        # Sprawdź, czy zatwierdzony adres też odpowiada regułom transportu, w tym regułom portu.
        kanoniczny_adres(instrukcja.endpoint)
        if instrukcja.allowed_scope not in Scope.values:
            raise AccessDenied("nieznany_zakres_instrukcji")

        def zarezerwuj_budzet():
            if not reserve_daily_fetch_budget(instrukcja):
                raise AccessDenied("limit_dzienny_instrukcji")

        odpowiedz = pobierz_http(adres, naglowki, minimalny_odstep=instrukcja.minimum_interval_seconds,
                                 przed_zadaniem=zarezerwuj_budzet)
        return odpowiedz, instrukcja.allowed_scope

    @abstractmethod
    def parsuj(self, odpowiedz):
        """Zwróć listę słowników wpisów zgodnych z POLA_PARSERA."""

    def czas_publikacji(self, odpowiedz):
        """Zwróć czas publikacji całej odpowiedzi, jeśli źródło go podaje."""
        return None

    def zbierz(self):
        start = timezone.now()
        status = None
        odcisk = ""
        try:
            with transaction.atomic():
                zrodlo = Zrodlo.objects.select_for_update().filter(pk=self.zrodlo.pk).first()
                if not zrodlo or zrodlo.tryb == Zrodlo.Tryb.WYLACZONY or zrodlo.adres != self.zrodlo.adres:
                    return None
                poprzednia_proba = zrodlo.ostatnie_pobranie_at
                zrodlo.ostatnie_pobranie_at = start
                zrodlo.save(update_fields=["ostatnie_pobranie_at"])
            adres = kanoniczny_adres(self.zrodlo.adres)
            odcisk = sha256(adres.encode()).hexdigest()
            poprzednie = self._ostatnie_udane()
            ta_sama_wersja = poprzednie and poprzednie.wersja_parsera == self.wersja_parsera
            ten_sam_adres = poprzednie and poprzednie.odcisk_adresu == odcisk
            naglowki = {}
            if ta_sama_wersja and ten_sam_adres:
                if poprzednie.etag:
                    naglowki["If-None-Match"] = poprzednie.etag
                if poprzednie.last_modified:
                    naglowki["If-Modified-Since"] = poprzednie.last_modified
            odpowiedz, zakres = self.pobierz(adres, naglowki)
            status = odpowiedz.status
            if status == 304 and naglowki:
                return self._zapisz(start, odcisk, odpowiedz, zakres, poprzednie.hash_tresci, [], poprzednie)
            if not 200 <= status < 300 or status == 206:
                return self._zapisz_blad(start, odcisk, status, f"http_{status}")

            skrot = hash_tresci(odpowiedz.tresc, odpowiedz.kodowanie)
            parsuj = not (ta_sama_wersja and ten_sam_adres and poprzednie.hash_tresci == skrot)
            try:
                wpisy = self.parsuj(odpowiedz) if parsuj else []
            except (TypeError, ValueError, LookupError, SyntaxError) as exc:
                raise ValidationError("Nie udało się odczytać wpisów z odpowiedzi.") from exc
            if not isinstance(wpisy, list):
                raise ValidationError("Parser musi zwrócić listę wpisów.")
            return self._zapisz(start, odcisk, odpowiedz, zakres, skrot, wpisy, poprzednie)
        except LimitHosta:
            # Źródło pozostaje należne podczas kolejnego przebiegu harmonogramu.
            Zrodlo.objects.filter(pk=self.zrodlo.pk, ostatnie_pobranie_at=start).update(
                ostatnie_pobranie_at=poprzednia_proba,
            )
            return None
        except (AccessDenied, BladPobrania, ValidationError, SoftTimeLimitExceeded) as exc:
            if isinstance(exc, BladPobrania) and exc.status_http is not None:
                status = exc.status_http
            return self._zapisz_blad(start, odcisk, status, type(exc).__name__)

    def _ostatnie_udane(self):
        return self.zrodlo.pobrania.exclude(hash_tresci="").order_by("-pobrano_at", "-pk").first()

    def _zapisz_blad(self, start, odcisk, status, blad):
        with transaction.atomic():
            zrodlo = Zrodlo.objects.select_for_update().filter(pk=self.zrodlo.pk).first()
            if (not zrodlo or zrodlo.tryb == Zrodlo.Tryb.WYLACZONY or zrodlo.adres != self.zrodlo.adres
                    or zrodlo.ostatnie_pobranie_at != start):
                return None
            pobranie = Pobranie.objects.create(zrodlo=zrodlo, pobrano_at=timezone.now(), status_http=status,
                odcisk_adresu=odcisk, wersja_parsera=self.wersja_parsera)
            zrodlo.ostatni_blad = blad
            zrodlo.kolejne_bledy += 1
            zrodlo.save(update_fields=["ostatni_blad", "kolejne_bledy"])
        return pobranie

    def _zapisz(self, start, odcisk, odpowiedz, zakres, skrot, wpisy, poprzednie):
        status = odpowiedz.status
        czas = timezone.now()
        etag = _walidator_http(odpowiedz, "ETag", 1024)
        last_modified = _walidator_http(odpowiedz, "Last-Modified", 128)
        if status == 304:
            etag = etag or poprzednie.etag
            last_modified = last_modified or poprzednie.last_modified
            opublikowano = poprzednie.opublikowano_at
        else:
            opublikowano = self.czas_publikacji(odpowiedz)
            if opublikowano is not None:
                _sprawdz_czas(opublikowano)

        pobranie = Pobranie(pobrano_at=czas, opublikowano_at=opublikowano, status_http=status, etag=etag,
            last_modified=last_modified, hash_tresci=skrot, odcisk_adresu=odcisk, wersja_parsera=self.wersja_parsera)
        try:
            with transaction.atomic():
                zrodlo = Zrodlo.objects.select_for_update().filter(pk=self.zrodlo.pk).first()
                if (not zrodlo or zrodlo.tryb == Zrodlo.Tryb.WYLACZONY or zrodlo.adres != self.zrodlo.adres
                        or zrodlo.ostatnie_pobranie_at != start):
                    return None
                pobranie.zrodlo = zrodlo
                ostatnie = self._ostatnie_udane()
                pobranie.bez_zmian = bool(ostatnie and ostatnie.hash_tresci == skrot)
                pobranie.dane_osobowe = pobranie.bez_zmian and ostatnie.dane_osobowe
                do_zapisu, istniejace, zawiera_dane_osobowe, zawiera_usuniete = self._przygotuj_wpisy(
                    zrodlo, pobranie, wpisy, zakres,
                )
                pobranie.dane_osobowe |= zawiera_dane_osobowe
                if zakres == Scope.SNAPSHOT and status != 304 and not pobranie.bez_zmian and not zawiera_usuniete:
                    pobranie.zrzut.save(f"{uuid4().hex}.bin", ContentFile(odpowiedz.tresc), save=False)
                pobranie.save()
                nowe = Wpis.objects.bulk_create(do_zapisu)
                if nowe:
                    uniewaznij_po_zapisie(zrodlo._state.db)
                if pobranie.zrzut:
                    pobranie.wpisy_w_zrzucie.add(*istniejace, *(wpis.pk for wpis in nowe))
                zrodlo.ostatni_sukces_at = czas
                zrodlo.ostatni_blad = ""
                zrodlo.kolejne_bledy = 0
                zrodlo.save(update_fields=["ostatni_sukces_at", "ostatni_blad", "kolejne_bledy"])
        except Exception:
            if pobranie.zrzut and pobranie.zrzut._committed:
                try:
                    if not Pobranie.objects.filter(zrzut=pobranie.zrzut.name).exists():
                        pobranie.zrzut.delete(save=False)
                except OSError:
                    log.warning("Nie udało się usunąć niedokończonego zrzutu Teraz.")
            raise
        return pobranie

    def _przygotuj_wpisy(self, zrodlo, pobranie, dane_parsowania, zakres):
        do_zapisu = {}
        dane_osobowe = False
        for dane in dane_parsowania:
            if not isinstance(dane, dict) or not dane.keys() <= POLA_PARSERA:
                raise ValidationError("Parser zwrócił wpis z nieobsługiwanymi polami.")
            _sprawdz_czas(dane.get("opublikowano_at"))
            wpis = Wpis(**dane, zrodlo=zrodlo, pobranie=pobranie, pobrano_at=pobranie.pobrano_at)
            if zakres == Scope.METADATA:
                wpis.tresc = ""
            wpis.full_clean(exclude={"zrodlo", "pobranie"}, validate_unique=False, validate_constraints=False)
            do_zapisu.setdefault(wpis.zewnetrzny_id, wpis)
            dane_osobowe |= wpis.klasa == Klasa.OSOBA_POSZUKIWANA

        odciski = {hash_id_wpisu(identyfikator): identyfikator for identyfikator in do_zapisu}
        usuniete = set(Wpis.objects.filter(zrodlo=zrodlo, hash_zewnetrznego_id__in=odciski)
                      .values_list("hash_zewnetrznego_id", flat=True))
        for odcisk in usuniete:
            do_zapisu.pop(odciski[odcisk])
        istniejace = Wpis.objects.filter(zrodlo=zrodlo, zewnetrzny_id__in=do_zapisu).values_list("zewnetrzny_id", "klasa", "pk")
        identyfikatory = []
        for identyfikator, klasa, pk in istniejace:
            do_zapisu.pop(identyfikator)
            dane_osobowe |= klasa == Klasa.OSOBA_POSZUKIWANA
            identyfikatory.append(pk)
        return list(do_zapisu.values()), identyfikatory, dane_osobowe, bool(usuniete)


def _sprawdz_czas(wartosc):
    if not isinstance(wartosc, datetime) or timezone.is_naive(wartosc):
        raise ValidationError("Czas publikacji musi zawierać strefę czasową.")


class AdapterTestowy(Adapter):
    def pobierz(self, adres, naglowki):
        return OdpowiedzHTTP(200, {}, b"[]", "utf-8"), Scope.METADATA

    def parsuj(self, odpowiedz):
        return []


ADAPTERY = {"teraz-testowy": AdapterTestowy}
