import logging
import random
import re
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import caches
from django.db import transaction
from django.db.models import DurationField, ExpressionWrapper, F, IntegerField, Q
from django.db.models.functions import Cast, Now
from django.utils import timezone

from .models import Klasa, Pobranie, Wpis, Zrodlo
from .retencja import wyczysc_wpisy
from .zbieranie import AdapterTestowy
from .zrodla.rejestr import ADAPTERY

log = logging.getLogger(__name__)
WAZNOSC_POBRANIA = 10
LIMIT_CZASU_POBRANIA = 50
MIEKKI_LIMIT_CZASU_POBRANIA = 40


def nalezne_zrodla():
    testowe = [slug for slug, adapter in ADAPTERY.items() if adapter is AdapterTestowy]
    return (Zrodlo.objects.exclude(tryb=Zrodlo.Tryb.WYLACZONY)
            .exclude(sposob_dostepu=Zrodlo.SposobDostepu.WEBSOCKET)
            .filter(slug__in=ADAPTERY, blokada_dostepu=False)
            .filter(Q(zrodlo_dostepu__isnull=False) | Q(slug__in=testowe))
            .alias(czas_od_proby=Now() - F("ostatnie_pobranie_at"),
                   interwal=ExpressionWrapper(Cast("czestotliwosc_s", IntegerField()) * timedelta(seconds=1),
                                              output_field=DurationField()))
            .filter(Q(kontynuacja_at__lte=Now()) | Q(kontynuacja_at__isnull=True) & (
                Q(ostatnie_pobranie_at__isnull=True) | Q(czas_od_proby__gte=F("interwal"))
            )))


@shared_task(ignore_result=True)
def zbierz_nalezne_zrodla():
    for pk in nalezne_zrodla().values_list("pk", flat=True).iterator():
        zbierz_zrodlo.apply_async((pk,), countdown=random.uniform(0, 5), expires=WAZNOSC_POBRANIA)


@shared_task(ignore_result=True, acks_late=False,
             soft_time_limit=MIEKKI_LIMIT_CZASU_POBRANIA, time_limit=LIMIT_CZASU_POBRANIA)
def zbierz_zrodlo(pk):
    cache = caches["teraz"]
    blokada = f"zbieranie:zrodlo:{pk}"
    if not cache.add(blokada, True, timeout=LIMIT_CZASU_POBRANIA + 5):
        return
    try:
        zrodlo = nalezne_zrodla().select_related("zrodlo_dostepu").filter(pk=pk).first()
        if zrodlo:
            ADAPTERY[zrodlo.slug](zrodlo).zbierz()
    finally:
        cache.delete(blokada)


@shared_task(ignore_result=True)
def usun_stare_zrzuty():
    teraz = timezone.now()
    dni = settings.TERAZ_RETENCJA_ZRZUTOW_DNI
    dni_osobowe = settings.TERAZ_RETENCJA_OSOBOWE_DNI
    prog = teraz - timedelta(days=dni)
    prog_osobowy = teraz - timedelta(days=dni_osobowe)
    wyczysc_wpisy(
        Wpis.objects.filter(klasa=Klasa.OSOBA_POSZUKIWANA, pobrano_at__lt=prog_osobowy),
        "Upłynął termin retencji danych osobowych.",
    )
    osobowe = (Q(dane_osobowe=True) | Q(wpisy__klasa=Klasa.OSOBA_POSZUKIWANA)
               | Q(wpisy_w_zrzucie__klasa=Klasa.OSOBA_POSZUKIWANA))
    _usun_zrzuty(Pobranie.objects.filter(
        Q(usunac_zrzut=True) | Q(pobrano_at__lt=prog) | (Q(pobrano_at__lt=prog_osobowy) & osobowe)
    ))
    _usun_osierocone_zrzuty(max(prog, prog_osobowy))


@shared_task(ignore_result=True)
def usun_zrzuty_na_zadanie():
    _usun_zrzuty(Pobranie.objects.filter(usunac_zrzut=True))


def _usun_zrzuty(queryset):
    identyfikatory = queryset.exclude(zrzut="").values_list("pk", flat=True).distinct()
    for pk in identyfikatory.iterator():
        with transaction.atomic():
            pobranie = Pobranie.objects.select_for_update().filter(pk=pk).exclude(zrzut="").first()
            if pobranie:
                try:
                    pobranie.zrzut.delete(save=False)
                except OSError:
                    log.warning("Nie udało się usunąć zrzutu Teraz, pobranie %s.", pk)
                    continue
                pobranie.usunac_zrzut = False
                pobranie.save(update_fields=["zrzut", "usunac_zrzut"])


def _usun_osierocone_zrzuty(prog):
    magazyn = Pobranie._meta.get_field("zrzut").storage
    try:
        _, pliki = magazyn.listdir("")
    except FileNotFoundError:
        return
    for nazwa in pliki:
        if not re.fullmatch(r"[a-f0-9]{32}\.bin", nazwa):
            continue
        try:
            if magazyn.get_modified_time(nazwa) < prog and not Pobranie.objects.filter(zrzut=nazwa).exists():
                magazyn.delete(nazwa)
        except FileNotFoundError:
            continue
        except OSError:
            log.warning("Nie udało się sprawdzić osieroconego zrzutu Teraz.")
