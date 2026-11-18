from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from .cache import uniewaznij_po_zapisie
from .models import Pobranie, StatusPrzegladu, Wpis, WylacznikKategorii, Zdarzenie, Zrodlo
from .retencja import wyczysc_wpisy
from .tasks import usun_zrzuty_na_zadanie


@admin.register(Zrodlo)
class ZrodloAdmin(admin.ModelAdmin):
    list_display = ("nazwa", "warstwa", "tryb", "ostatnie_pobranie_at", "ostatni_sukces_at", "kolejne_bledy")
    list_filter = ("warstwa", "tryb", "sposob_dostepu")
    search_fields = ("slug", "nazwa", "instytucja")
    raw_id_fields = ("zrodlo_dostepu",)
    readonly_fields = ("tryb_zmienil", "tryb_zmiana_at", "ostatnie_pobranie_at", "ostatni_sukces_at",
                       "ostatni_blad", "kolejne_bledy", "podstawa_rekomendowana",
                       "wyjatek_podpisal", "ostatnia_proba_archiwum_at")
    actions = ("przelacz_na_publiczne",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.method == "POST" and getattr(request.resolver_match, "url_name", "") == "teraz_zrodlo_change":
            return queryset.select_for_update()
        return queryset

    def get_readonly_fields(self, request, obj=None):
        pola = self.readonly_fields
        if not request.user.is_superuser:
            pola = (*pola, "blokada_dostepu", "podstawa_prawna", "rejestr_podstaw_url",
                    "rekomendowany_tryb", "wyjatek_decyzja")
        if obj and obj.tryb == Zrodlo.Tryb.PUBLICZNY:
            return (*pola, "slug", "nazwa", "instytucja", "warstwa", "sposob_dostepu", "adres",
                    "zrodlo_dostepu", "podstawa_prawna", "rejestr_podstaw_url", "czestotliwosc_s",
                    "atrybucja", "redystrybucja_pro", "rekomendowany_tryb", "wyjatek_decyzja")
        if obj and obj.podstawa_rekomendowana and request.user.is_superuser:
            return (*pola, "rekomendowany_tryb")
        return pola

    def get_form(self, request, obj=None, **kwargs):
        formularz = super().get_form(request, obj, **kwargs)
        if "tryb" in formularz.base_fields and (not obj or obj.tryb != Zrodlo.Tryb.PUBLICZNY):
            formularz.base_fields["tryb"].choices = [
                para for para in Zrodlo.Tryb.choices if para[0] != Zrodlo.Tryb.PUBLICZNY
            ]
        return formularz

    def save_model(self, request, obj, form, change):
        if request.user.is_superuser and "wyjatek_decyzja" in form.changed_data:
            obj.wyjatek_podpisal = request.user if obj.wyjatek_decyzja.strip() else None
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        akcje = super().get_actions(request)
        if not request.user.is_superuser:
            akcje.pop("przelacz_na_publiczne", None)
        return akcje

    @admin.action(permissions=["change"], description="Przełącz źródło na publiczne")
    def przelacz_na_publiczne(self, request, queryset):
        if not request.user.is_superuser:
            return
        liczba = odmowy = 0
        with transaction.atomic(using=queryset.db):
            for zrodlo in queryset.exclude(tryb=Zrodlo.Tryb.PUBLICZNY).select_for_update():
                podstawa = zrodlo.podstawa_prawna.strip()
                if (not podstawa or podstawa == zrodlo.podstawa_rekomendowana.strip()
                        or not zrodlo.rejestr_podstaw_url
                        or (zrodlo.rekomendowany_tryb != Zrodlo.Tryb.PUBLICZNY
                            and not (zrodlo.wyjatek_decyzja.strip() and zrodlo.wyjatek_podpisal_id))):
                    odmowy += 1
                    continue
                zrodlo.tryb = Zrodlo.Tryb.PUBLICZNY
                zrodlo.tryb_zmienil = request.user
                zrodlo.tryb_zmiana_at = timezone.now()
                zrodlo.save(update_fields=["tryb", "tryb_zmienil", "tryb_zmiana_at"])
                liczba += 1
        self.message_user(request, f"Źródła dopuszczone do publikacji: {liczba}.")
        if odmowy:
            self.message_user(request, f"Odmowy publikacji z powodu braku podstawy, odnośnika lub wymaganego podpisanego wyjątku: {odmowy}.", level="warning")


@admin.register(Pobranie)
class PobranieAdmin(admin.ModelAdmin):
    list_display = ("zrodlo", "pobrano_at", "status_http", "bez_zmian", "wersja_parsera", "ma_zrzut")
    list_filter = ("status_http", "bez_zmian", "dane_osobowe")
    search_fields = ("zrodlo__slug", "hash_tresci")
    fields = ("zrodlo", "pobrano_at", "opublikowano_at", "status_http", "etag", "last_modified", "hash_tresci",
              "plik", "wersja_parsera", "bez_zmian", "dane_osobowe", "usunac_zrzut")
    readonly_fields = fields

    @admin.display(description="Prywatny plik zrzutu")
    def plik(self, obj):
        return None if obj.usunac_zrzut else obj.zrzut.name or None

    @admin.display(boolean=True, description="Zrzut")
    def ma_zrzut(self, obj):
        return bool(obj.zrzut) and not obj.usunac_zrzut

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wpis)
class WpisAdmin(admin.ModelAdmin):
    list_display = ("tytul", "zrodlo", "opublikowano_at", "klasa", "status_przegladu")
    list_filter = ("klasa", "status_przegladu", "zrodlo__warstwa")
    search_fields = ("tytul", "zewnetrzny_id")
    readonly_fields = tuple(pole.name for pole in Wpis._meta.fields if not pole.primary_key)
    actions = ("dopusc", "wstrzymaj", "usun_na_zadanie")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request)

    @admin.action(permissions=["change"], description="Dopuść")
    def dopusc(self, request, queryset):
        liczba = queryset.filter(usunieto_at__isnull=True).update(
            status_przegladu=StatusPrzegladu.DOPUSZCZONY, ukryty_powod="",
            przeglad_zmienil=request.user, przeglad_zmiana_at=timezone.now(),
        )
        if liczba:
            uniewaznij_po_zapisie(queryset.db)
        self.message_user(request, f"Wpisy dopuszczone przez redakcję: {liczba}.")

    @admin.action(permissions=["change"], description="Wstrzymaj")
    def wstrzymaj(self, request, queryset):
        liczba = queryset.filter(usunieto_at__isnull=True).update(
            status_przegladu=StatusPrzegladu.WSTRZYMANY,
            przeglad_zmienil=request.user, przeglad_zmiana_at=timezone.now(),
        )
        if liczba:
            uniewaznij_po_zapisie(queryset.db)
        self.message_user(request, f"Wstrzymane wpisy: {liczba}.")

    @admin.action(permissions=["change"], description="Usuń na żądanie")
    def usun_na_zadanie(self, request, queryset):
        with transaction.atomic(using=queryset.db):
            liczba = wyczysc_wpisy(queryset, "Żądanie usunięcia danych.", request.user)
            if liczba:
                transaction.on_commit(usun_zrzuty_na_zadanie.delay, using=queryset.db, robust=True)
        self.message_user(request, f"Wpisy wyczyszczone na żądanie: {liczba}.")


@admin.register(Zdarzenie)
class ZdarzenieAdmin(admin.ModelAdmin):
    list_display = ("tytul_roboczy", "status", "ostatni_wpis_at", "przygotowane_automatycznie", "zweryfikowal")
    list_filter = ("status", "przygotowane_automatycznie")
    search_fields = ("tytul_roboczy",)
    autocomplete_fields = ("wpisy",)
    readonly_fields = ("zweryfikowal", "zweryfikowano_at")

    def save_model(self, request, obj, form, change):
        if obj.status in {Zdarzenie.Status.POTWIERDZONE, Zdarzenie.Status.OCENA, Zdarzenie.Status.ODWOLANE}:
            obj.zweryfikowal = request.user
            obj.zweryfikowano_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(WylacznikKategorii)
class WylacznikKategoriiAdmin(admin.ModelAdmin):
    list_display = ("__str__", "aktywny", "zmienil", "zmiana_at")
    list_filter = ("aktywny",)
    readonly_fields = ("zmienil", "zmiana_at")
    actions = ("wlacz_wylacznik", "zdejmij_wylacznik")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (*self.readonly_fields, "warstwa", "klasa", "aktywny")
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    def has_zdejmij_wylacznik_permission(self, request):
        return self.has_change_permission(request) and request.user.has_perm("teraz.zdejmij_wylacznik")

    def save_model(self, request, obj, form, change):
        obj.zmienil = request.user
        obj.zmiana_at = timezone.now()
        if change:
            obj.save(update_fields=["powod", "zmienil", "zmiana_at"])
        else:
            super().save_model(request, obj, form, change)

    @admin.action(permissions=["change"], description="Włącz wyłącznik kategorii")
    def wlacz_wylacznik(self, request, queryset):
        liczba = queryset.filter(aktywny=False).update(aktywny=True, zmienil=request.user, zmiana_at=timezone.now())
        if liczba:
            uniewaznij_po_zapisie(queryset.db)
        self.message_user(request, f"Włączone wyłączniki: {liczba}.")

    @admin.action(permissions=["zdejmij_wylacznik"], description="Zdejmij wyłącznik kategorii")
    def zdejmij_wylacznik(self, request, queryset):
        liczba = queryset.filter(aktywny=True).update(aktywny=False, zmienil=request.user, zmiana_at=timezone.now())
        if liczba:
            uniewaznij_po_zapisie(queryset.db)
        self.message_user(request, f"Zdjęte wyłączniki: {liczba}.")
