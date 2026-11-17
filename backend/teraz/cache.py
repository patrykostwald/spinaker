import logging
from hashlib import sha256
from urllib.parse import urlencode
from uuid import uuid4

from django.core.cache import caches
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver
from redis.exceptions import RedisError

from .models import Wpis, WylacznikKategorii, Zdarzenie, Zrodlo

log = logging.getLogger(__name__)
GENERACJA = "api:generacja"
CZAS_CACHE = 20
BLEDY_CACHE = (RedisError, OSError)
PUBLICZNE_POLA_ZRODLA = ("slug", "nazwa", "instytucja", "warstwa", "czestotliwosc_s", "tryb")


def uniewaznij_po_zapisie(using=None):
    def uniewaznij():
        try:
            caches["teraz"].set(GENERACJA, uuid4().hex, timeout=None)
        except BLEDY_CACHE:
            log.warning("Nie udało się unieważnić pamięci API Teraz.")

    transaction.on_commit(uniewaznij, using=using)


@receiver(pre_save, sender=Zrodlo)
def sprawdz_zmiane_zrodla(sender, instance, update_fields, using, raw, **kwargs):
    if raw or update_fields is not None or instance.pk is None:
        return
    poprzednie = sender.objects.using(using).filter(pk=instance.pk).values_list(*PUBLICZNE_POLA_ZRODLA).first()
    instance._zmiana_publicznych_pol = poprzednie != tuple(getattr(instance, pole) for pole in PUBLICZNE_POLA_ZRODLA)


@receiver(post_save, sender=Zrodlo)
def zmiana_zrodla(instance, created, update_fields, using, raw, **kwargs):
    if raw:
        return
    zmiana = (getattr(instance, "_zmiana_publicznych_pol", False) if update_fields is None
              else not update_fields.isdisjoint(PUBLICZNE_POLA_ZRODLA))
    if created or zmiana:
        uniewaznij_po_zapisie(using)


for model in (Wpis, Zdarzenie, WylacznikKategorii):
    post_save.connect(lambda using, **kwargs: uniewaznij_po_zapisie(using), sender=model, weak=False)
for model in (Zrodlo, Wpis, Zdarzenie, WylacznikKategorii):
    post_delete.connect(lambda using, **kwargs: uniewaznij_po_zapisie(using), sender=model, weak=False)


@receiver(m2m_changed, sender=Zdarzenie.wpisy.through)
def zmiana_wpisow_zdarzenia(action, using, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        uniewaznij_po_zapisie(using)


def klucz_odpowiedzi(adres, parametry):
    cache = caches["teraz"]
    generacja = cache.get_or_set(GENERACJA, lambda: uuid4().hex, timeout=None)
    query = urlencode(sorted(parametry.items()))
    adres_hash = sha256(f"{adres}?{query}".encode()).hexdigest()
    return f"api:{generacja}:{adres_hash}"
