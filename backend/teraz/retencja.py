from hashlib import sha256
from uuid import uuid4

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .cache import uniewaznij_po_zapisie
from .models import Pobranie, StatusPrzegladu, Wpis, Zdarzenie, Zrodlo


def hash_id_wpisu(identyfikator):
    return sha256(identyfikator.encode()).hexdigest()


def wyczysc_wpisy(queryset, powod, uzytkownik=None):
    baza = queryset.db
    queryset = queryset.filter(usunieto_at__isnull=True)
    czas = timezone.now()
    with transaction.atomic(using=baza):
        # Zapis adaptera blokuje to samo źródło przed dołączeniem kolejnego zrzutu.
        zrodla = queryset.order_by().values("zrodlo_id")
        list(Zrodlo.objects.using(baza).filter(pk__in=zrodla).order_by("pk")
             .select_for_update().values_list("pk", flat=True))
        wpisy = list(queryset.select_for_update().order_by("pk"))
        if not wpisy:
            return 0
        for wpis in wpisy:
            wpis.hash_zewnetrznego_id = hash_id_wpisu(wpis.zewnetrzny_id)
            wpis.zewnetrzny_id = f"usuniety-{uuid4().hex}"
            wpis.tytul = wpis.tresc = wpis.link = ""
            wpis.teryt = []
            wpis.miejsce = wpis.hash_wersji = ""
            wpis.wersje = []
            wpis.czas_zrodlowy_at = None
            wpis.dokladna_godzina_publikacji = False
            wpis.szerokosc = wpis.dlugosc = wpis.bbox = None
            wpis.dokladnosc = Wpis.Dokladnosc.BRAK
            wpis.pewnosc_lokalizacji = 0
            wpis.status_przegladu = StatusPrzegladu.WSTRZYMANY
            wpis.ukryty_powod = powod
            wpis.usunieto_at = czas
            wpis.usunal = uzytkownik
        Wpis.objects.using(baza).bulk_update(wpisy, [
            "hash_zewnetrznego_id", "zewnetrzny_id", "tytul", "tresc", "link", "teryt", "szerokosc",
            "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji", "status_przegladu", "ukryty_powod",
            "usunieto_at", "usunal", "miejsce", "hash_wersji", "wersje", "czas_zrodlowy_at",
            "dokladna_godzina_publikacji",
        ])
        identyfikatory = [wpis.pk for wpis in wpisy]
        Pobranie.objects.using(baza).exclude(zrzut="").filter(
            Q(wpisy__in=identyfikatory) | Q(wpisy_w_zrzucie__in=identyfikatory),
        ).update(usunac_zrzut=True)
        zdarzenia = Zdarzenie.objects.using(baza).filter(wpisy__in=identyfikatory)
        identyfikatory_zdarzen = list(zdarzenia.values_list("pk", flat=True).distinct())
        zdarzenia.update(tytul_roboczy="")
        typy = ContentType.objects.db_manager(baza).get_for_models(Wpis, Zdarzenie)
        for model, obiekty in ((Wpis, identyfikatory), (Zdarzenie, identyfikatory_zdarzen)):
            LogEntry.objects.using(baza).filter(
                content_type=typy[model], object_id__in=map(str, obiekty),
            ).update(object_repr=f"Usunięto tytuł ({model._meta.verbose_name}).")
        uniewaznij_po_zapisie(baza)
    return len(wpisy)
