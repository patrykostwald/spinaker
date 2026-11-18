import math
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import Count, Exists, OuterRef, Q

from .storage import PrywatnyMagazynZrzutow


class Warstwa(models.TextChoices):
    RCB = "rcb", "Alert RCB"
    IMGW_METEO = "imgw_meteo", "Ostrzeżenia meteorologiczne"
    IMGW_HYDRO = "imgw_hydro", "Ostrzeżenia hydrologiczne"
    POWIETRZE = "powietrze", "Jakość powietrza"
    POZARY = "pozary", "Pożary"
    WSTRZASY = "wstrzasy", "Wstrząsy"
    KATASTROFY = "katastrofy", "Katastrofy"
    POLICJA = "policja", "Policja"
    PSP = "psp", "Państwowa Straż Pożarna"
    SG = "sg", "Straż Graniczna"
    WOJSKO = "wojsko", "Wojsko"
    DROGI = "drogi", "Drogi"
    KOLEJ = "kolej", "Kolej"
    PRZESTRZEN = "przestrzen", "Przestrzeń powietrzna"
    ENERGETYKA = "energetyka", "Energetyka"
    CYBER = "cyber", "Cyberbezpieczeństwo"
    MEDIA = "media", "Media"
    URZEDY = "urzedy", "Urzędy"


class Klasa(models.TextChoices):
    ZWYKLY = "zwykly", "Zwykły"
    WRAZLIWY = "wrazliwy", "Wrażliwy"
    WOJSKO_GRANICA = "wojsko_granica", "Wojsko lub granica"
    OSOBA_POSZUKIWANA = "osoba_poszukiwana", "Osoba poszukiwana"
    INFRASTRUKTURA = "infrastruktura", "Infrastruktura"
    NIEZNANA = "nieznana", "Nieznana"


class StatusPrzegladu(models.TextChoices):
    DO_PRZEGLADU = "do_przegladu", "Do przeglądu"
    DOPUSZCZONY = "dopuszczony", "Dopuszczony"
    WSTRZYMANY = "wstrzymany", "Wstrzymany"


http_url = URLValidator(schemes=["http", "https"])


def sprawdz_teryt(kody):
    if not isinstance(kody, list) or not all(
        isinstance(kod, str) and re.fullmatch(r"[0-9]{1,7}", kod) for kod in kody
    ):
        raise ValidationError("Podaj listę kodów TERYT jako ciągi cyfr.")


def sprawdz_bbox(bbox):
    if not isinstance(bbox, list) or len(bbox) != 4 or not all(
        type(wartosc) in (int, float) and -180 <= wartosc <= 180 for wartosc in bbox
    ):
        raise ValidationError("Podaj cztery współrzędne prostokąta.")
    zachod, poludnie, wschod, polnoc = bbox
    if zachod > wschod or not -90 <= poludnie <= polnoc <= 90:
        raise ValidationError("Podaj prostokąt w kolejności zachód, południe, wschód, północ.")


class Zrodlo(models.Model):
    class Tryb(models.TextChoices):
        PUBLICZNY = "publiczny", "Publiczny"
        WEWNETRZNY = "wewnetrzny", "Wewnętrzny"
        WYLACZONY = "wylaczony", "Wyłączony"

    class SposobDostepu(models.TextChoices):
        API = "api", "API"
        RSS = "rss", "RSS"
        HTML = "html", "Strona WWW"
        X = "x", "X"
        WEBSOCKET = "websocket", "WebSocket"

    class Redystrybucja(models.TextChoices):
        ALLOW = "allow", "Dozwolona"
        DENY = "deny", "Zabroniona"
        PENDING = "pending", "Do wyjaśnienia"

    slug = models.SlugField(unique=True, help_text="Stały identyfikator źródła i klucz adaptera.")
    nazwa = models.CharField(max_length=200, help_text="Nazwa źródła widoczna na liście warstw.")
    instytucja = models.CharField(max_length=200, help_text="Instytucja publikująca komunikaty.")
    warstwa = models.CharField(max_length=16, choices=Warstwa.choices, db_index=True, help_text="Warstwa mapy.")
    sposob_dostepu = models.CharField(max_length=9, choices=SposobDostepu.choices, help_text="Kanał pobierania komunikatów.")
    adres = models.CharField(max_length=2048, help_text="Adres używany przez adapter.")
    czestotliwosc_s = models.PositiveIntegerField(default=300, validators=[MinValueValidator(1)], help_text="Odstęp między pobraniami w sekundach.")
    tryb = models.CharField(max_length=12, choices=Tryb.choices, default=Tryb.WEWNETRZNY, db_index=True, help_text="Tryb publikacji i pobierania.")
    tryb_zmienil = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Wydawca, który dopuścił źródło do publikacji.")
    tryb_zmiana_at = models.DateTimeField(null=True, blank=True, help_text="Czas dopuszczenia źródła przez wydawcę.")
    podstawa_prawna = models.TextField(blank=True, help_text="Opis podstawy dostępu i publikacji.")
    podstawa_rekomendowana = models.TextField(blank=True, editable=False)
    wyjatek_decyzja = models.TextField(blank=True, help_text="Uzasadnienie wyjątku od rekomendowanego trybu.")
    wyjatek_podpisal = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", editable=False)
    atrybucja = models.TextField(blank=True)
    redystrybucja_pro = models.CharField(max_length=7, choices=Redystrybucja.choices, default=Redystrybucja.PENDING)
    rekomendowany_tryb = models.CharField(max_length=12, choices=Tryb.choices, default=Tryb.WEWNETRZNY)
    stan_adaptera = models.JSONField(default=dict, editable=False)
    kontynuacja_at = models.DateTimeField(null=True, blank=True, editable=False)
    blokada_dostepu = models.BooleanField(default=False, help_text="Wstrzymuje pobieranie po odmowie lub wyzwaniu bota.")
    rejestr_podstaw_url = models.URLField(max_length=1024, blank=True, validators=[http_url], help_text="Odnośnik do wpisu w rejestrze podstaw.")
    zrodlo_dostepu = models.ForeignKey("news.Source", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Źródło w katalogu spinakera z zatwierdzoną instrukcją dostępu.")
    ostatnie_pobranie_at = models.DateTimeField(null=True, blank=True, help_text="Czas rozpoczęcia ostatniej próby pobrania.")
    ostatnia_proba_archiwum_at = models.DateTimeField(null=True, blank=True, editable=False)
    ostatni_sukces_at = models.DateTimeField(null=True, blank=True, help_text="Czas ostatniego udanego pobrania, także bez zmian.")
    ostatni_blad = models.CharField(max_length=200, blank=True, help_text="Wewnętrzny kod ostatniego błędu.")
    kolejne_bledy = models.PositiveIntegerField(default=0, help_text="Liczba nieudanych prób od ostatniego sukcesu.")

    class Meta:
        verbose_name = "źródło"
        verbose_name_plural = "źródła"

    def clean(self):
        super().clean()
        if self.slug == "firms":
            from .transport import BAZA_FIRMS
            if self.adres != BAZA_FIRMS:
                raise ValidationError({"adres": "FIRMS wymaga bazowego adresu bez klucza."})
        schematy = ["wss"] if self.sposob_dostepu == self.SposobDostepu.WEBSOCKET else ["http", "https"]
        try:
            URLValidator(schemes=schematy)(self.adres)
        except ValidationError as exc:
            raise ValidationError({"adres": exc}) from exc

    def __str__(self):
        return self.nazwa


class Pobranie(models.Model):
    zrodlo = models.ForeignKey(Zrodlo, on_delete=models.PROTECT, related_name="pobrania", help_text="Źródło odpowiedzi.")
    pobrano_at = models.DateTimeField(db_index=True, help_text="Czas pobrania odpowiedzi.")
    opublikowano_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Czas publikacji podany dla całej odpowiedzi.")
    status_http = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Kod HTTP, jeżeli odebrano odpowiedź.")
    etag = models.CharField(max_length=1024, blank=True, help_text="Nagłówek ETag do następnego pobrania.")
    last_modified = models.CharField(max_length=128, blank=True, help_text="Nagłówek Last-Modified do następnego pobrania.")
    hash_tresci = models.CharField(max_length=64, blank=True, help_text="SHA-256 poprawnie pobranej treści po normalizacji.")
    odcisk_adresu = models.CharField(max_length=64, blank=True, help_text="Odcisk adresu przypisujący walidatory HTTP do właściwego zasobu.")
    zrzut = models.FileField(storage=PrywatnyMagazynZrzutow(), max_length=200, blank=True, help_text="Plik w prywatnym magazynie zrzutów.")
    wersja_parsera = models.CharField(max_length=64, help_text="Wersja parsera użyta do odczytu odpowiedzi.")
    bez_zmian = models.BooleanField(default=False, help_text="Odpowiedź zgodna z poprzednią treścią źródła.")
    dane_osobowe = models.BooleanField(default=False, help_text="Zrzut zawiera komunikat o osobie poszukiwanej i podlega krótszej retencji.")
    usunac_zrzut = models.BooleanField(default=False, help_text="Zrzut czeka na usunięcie przez worker.")
    wpisy_w_zrzucie = models.ManyToManyField("Wpis", blank=True, related_name="zrzuty_z_wpisem",
        help_text="Wpisy obecne w pliku, w tym już znane przy tym pobraniu.")

    class Meta:
        verbose_name = "pobranie"
        verbose_name_plural = "pobrania"
        indexes = [
            models.Index(fields=["zrodlo", "-pobrano_at"], name="teraz_pobranie_zrodlo_czas"),
            models.Index(fields=["zrodlo", "odcisk_adresu", "-pobrano_at"], name="teraz_pobranie_adres_czas"),
        ]

    def __str__(self):
        return f"{self.zrodlo} ({self.pobrano_at:%Y-%m-%d %H:%M})"


class WpisQuerySet(models.QuerySet):
    def publiczne(self):
        wylaczniki = WylacznikKategorii.objects.filter(aktywny=True).filter(
            Q(warstwa=OuterRef("zrodlo__warstwa")) | Q(klasa=OuterRef("klasa"))
        )
        return (self.filter(zrodlo__tryb=Zrodlo.Tryb.PUBLICZNY)
                .filter(pomiar_aktywny=True)
                .filter(Q(klasa=Klasa.ZWYKLY) | Q(status_przegladu=StatusPrzegladu.DOPUSZCZONY))
                .exclude(status_przegladu=StatusPrzegladu.WSTRZYMANY)
                .filter(usunieto_at__isnull=True)
                .filter(~Exists(wylaczniki)))


class Wpis(models.Model):
    class Dokladnosc(models.TextChoices):
        PUNKT = "punkt", "Punkt"
        GMINA = "gmina", "Gmina"
        POWIAT = "powiat", "Powiat"
        WOJEWODZTWO = "wojewodztwo", "Województwo"
        KRAJ = "kraj", "Kraj"
        BRAK = "brak", "Brak danych"

    zrodlo = models.ForeignKey(Zrodlo, on_delete=models.CASCADE, related_name="wpisy", help_text="Źródło komunikatu.")
    pobranie = models.ForeignKey(Pobranie, on_delete=models.RESTRICT, related_name="wpisy", help_text="Pierwsza odpowiedź zawierająca komunikat.")
    zewnetrzny_id = models.CharField(max_length=255, help_text="Identyfikator komunikatu, unikalny w źródle.")
    tytul = models.CharField(max_length=500, help_text="Tytuł komunikatu.")
    tresc = models.TextField(blank=True, help_text="Treść komunikatu dopuszczona przez kartę dostępu.")
    link = models.URLField(max_length=2048, validators=[http_url], help_text="Odnośnik do komunikatu u źródła.")
    opublikowano_at = models.DateTimeField(db_index=True, help_text="Czas publikacji podany przez źródło.")
    pobrano_at = models.DateTimeField(help_text="Czas pierwszego pobrania komunikatu.")
    klasa = models.CharField(max_length=20, choices=Klasa.choices, default=Klasa.NIEZNANA, help_text="Klasa wrażliwości publikacji.")
    miejsce = models.TextField(blank=True)
    czas_zrodlowy_at = models.DateTimeField(null=True, blank=True, help_text="Godzina komunikatu podana w treści źródła.")
    dokladna_godzina_publikacji = models.BooleanField(default=True)
    wersje = models.JSONField(default=list, blank=True, editable=False)
    pomiar_aktywny = models.BooleanField(default=True, editable=False)
    hash_wersji = models.CharField(max_length=64, blank=True, editable=False)
    teryt = models.JSONField(default=list, blank=True, validators=[sprawdz_teryt], help_text="Lista kodów TERYT z zachowaniem początkowych zer.")
    szerokosc = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)], help_text="Szerokość geograficzna w stopniach.")
    dlugosc = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)], help_text="Długość geograficzna w stopniach.")
    bbox = models.JSONField(null=True, blank=True, validators=[sprawdz_bbox], help_text="Zasięg w kolejności zachód, południe, wschód, północ.")
    dokladnosc = models.CharField(max_length=12, choices=Dokladnosc.choices, default=Dokladnosc.BRAK, help_text="Poziom dokładności lokalizacji.")
    pewnosc_lokalizacji = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)], help_text="Ocena pewności lokalizacji od 0 do 1.")
    status_przegladu = models.CharField(max_length=16, choices=StatusPrzegladu.choices,
        default=StatusPrzegladu.DO_PRZEGLADU, db_index=True, help_text="Decyzja redakcji o publikacji.")
    ukryty_powod = models.TextField(blank=True, help_text="Wewnętrzne uzasadnienie ukrycia wpisu.")
    przeglad_zmienil = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Redaktor, który ostatnio dopuścił lub wstrzymał wpis.")
    przeglad_zmiana_at = models.DateTimeField(null=True, blank=True, help_text="Czas ostatniej decyzji o publikacji.")
    usunieto_at = models.DateTimeField(null=True, blank=True, help_text="Czas wyczyszczenia danych wpisu.")
    usunal = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Redaktor, który zlecił usunięcie danych.")
    hash_zewnetrznego_id = models.CharField(max_length=64, blank=True, db_index=True,
        help_text="Odcisk identyfikatora wyczyszczonego wpisu do rozpoznawania ponownych pobrań.")

    objects = WpisQuerySet.as_manager()

    class Meta:
        verbose_name = "wpis"
        verbose_name_plural = "wpisy"
        constraints = [
            models.UniqueConstraint(fields=["zrodlo", "zewnetrzny_id"], name="teraz_unikalny_wpis_zrodla"),
            models.CheckConstraint(condition=Q(pewnosc_lokalizacji__gte=0, pewnosc_lokalizacji__lte=1), name="teraz_pewnosc_od_0_do_1"),
        ]
        indexes = [models.Index(fields=["zrodlo", "-opublikowano_at"], name="teraz_wpis_zrodlo_czas")]

    def clean(self):
        super().clean()
        if self.pobranie_id and self.zrodlo_id != self.pobranie.zrodlo_id:
            raise ValidationError({"pobranie": "Wybierz pobranie należące do źródła wpisu."})
        if (self.szerokosc is None) != (self.dlugosc is None):
            raise ValidationError("Podaj obie współrzędne punktu.")
        if any(value is not None and not math.isfinite(value) for value in (self.szerokosc, self.dlugosc)):
            raise ValidationError("Współrzędne muszą być skończonymi liczbami.")

    def __str__(self):
        return self.tytul


class ZdarzenieQuerySet(models.QuerySet):
    def publiczne(self):
        powiazania = self.model.wpisy.through.objects.filter(zdarzenie_id=OuterRef("pk"))
        ukryte = powiazania.exclude(wpis_id__in=Wpis.objects.publiczne().values("pk"))
        return self.filter(Exists(powiazania), ~Exists(ukryte)).alias(
            liczba_instytucji=Count("wpisy__zrodlo__instytucja", distinct=True),
        ).filter(
            Q(status__in=[Zdarzenie.Status.KOMUNIKAT_OFICJALNY, Zdarzenie.Status.ZGLOSZONE])
            | Q(status=Zdarzenie.Status.ODWOLANE, zrodlo_automatu__isnull=False, przygotowane_automatycznie=True)
            | Q(zweryfikowal__isnull=False, zweryfikowano_at__isnull=False)
        ).filter(
            ~Q(status=Zdarzenie.Status.POTWIERDZONE) | Q(liczba_instytucji__gte=2)
        )


class Zdarzenie(models.Model):
    class Status(models.TextChoices):
        KOMUNIKAT_OFICJALNY = "komunikat_oficjalny", "Komunikat oficjalny"
        ZGLOSZONE = "zgloszone", "Zgłoszone"
        POTWIERDZONE = "potwierdzone", "Potwierdzone"
        OCENA = "ocena", "Ocena"
        ODWOLANE = "odwolane", "Odwołane"

    zrodlo_automatu = models.ForeignKey(Zrodlo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", editable=False)
    identyfikator_automatu = models.CharField(max_length=64, blank=True, editable=False)
    wpisy = models.ManyToManyField(Wpis, related_name="zdarzenia", help_text="Komunikaty pogrupowane w zdarzenie.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ZGLOSZONE, db_index=True, help_text="Status redakcyjny zdarzenia.")
    tytul_roboczy = models.CharField(max_length=500, help_text="Tytuł zdarzenia ustalony na podstawie powiązanych komunikatów.")
    pierwszy_wpis_at = models.DateTimeField(help_text="Czas pierwszego powiązanego komunikatu.")
    ostatni_wpis_at = models.DateTimeField(db_index=True, help_text="Czas ostatniego powiązanego komunikatu.")
    przygotowane_automatycznie = models.BooleanField(default=True, help_text="Zdarzenie przygotowano automatycznie.")
    zweryfikowal = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", help_text="Redaktor, który zweryfikował zdarzenie.")
    zweryfikowano_at = models.DateTimeField(null=True, blank=True, help_text="Czas weryfikacji redakcyjnej.")

    objects = ZdarzenieQuerySet.as_manager()

    class Meta:
        verbose_name = "zdarzenie"
        verbose_name_plural = "zdarzenia"
        constraints = [models.UniqueConstraint(fields=["zrodlo_automatu", "identyfikator_automatu"],
            condition=~Q(identyfikator_automatu=""), name="teraz_unikalne_zdarzenie_automatu")]

    def __str__(self):
        return self.tytul_roboczy


class WylacznikKategorii(models.Model):
    warstwa = models.CharField(max_length=16, choices=Warstwa.choices, null=True, blank=True, unique=True, help_text="Warstwa blokowana przez wyłącznik.")
    klasa = models.CharField(max_length=20, choices=Klasa.choices, null=True, blank=True, unique=True, help_text="Klasa blokowana przez wyłącznik.")
    aktywny = models.BooleanField(default=False, help_text="Blokuje publikację w wybranej kategorii.")
    powod = models.TextField(help_text="Uzasadnienie decyzji redakcyjnej.")
    zmienil = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Osoba, która ostatnio zmieniła wyłącznik.")
    zmiana_at = models.DateTimeField(null=True, blank=True, help_text="Czas ostatniej zmiany wyłącznika.")

    class Meta:
        verbose_name = "wyłącznik kategorii"
        verbose_name_plural = "wyłączniki kategorii"
        permissions = [("zdejmij_wylacznik", "Może zdjąć wyłącznik kategorii")]
        constraints = [models.CheckConstraint(
            condition=(Q(warstwa__isnull=False, klasa__isnull=True) | Q(warstwa__isnull=True, klasa__isnull=False)),
            name="teraz_wylacznik_jedna_kategoria",
        )]

    def __str__(self):
        return self.get_warstwa_display() or self.get_klasa_display()
