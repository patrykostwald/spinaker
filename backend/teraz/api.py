from datetime import timedelta
from urllib.parse import urlencode

from django.core.cache import caches
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import BooleanField, Count, FloatField, Func, Prefetch, Q
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .cache import BLEDY_CACHE, CZAS_CACHE, klucz_odpowiedzi
from .models import Klasa, Warstwa, Wpis, WylacznikKategorii, Zdarzenie, Zrodlo, sprawdz_bbox

NIEPEWNOSC = "nie mamy pewności, sprawdź Alert RCB i 112"
MAKSYMALNY_PREFIKS = {
    Klasa.WOJSKO_GRANICA: 2,
    Klasa.INFRASTRUKTURA: 2,
    Klasa.OSOBA_POSZUKIWANA: 4,
    Klasa.WRAZLIWY: 4,
    Klasa.NIEZNANA: 4,
}


class PrefiksTeryt(Func):
    output_field = BooleanField()

    def __init__(self, prefiks):
        super().__init__("teryt")
        self.prefiks = prefiks

    def as_postgresql(self, compiler, connection):
        pole, parametry = compiler.compile(self.source_expressions[0])
        return (
            f"EXISTS (SELECT 1 FROM jsonb_array_elements_text({pole}) AS kod(wartosc) "
            "WHERE LEFT(kod.wartosc, %s) = %s)",
            (*parametry, len(self.prefiks), self.prefiks),
        )

    def as_sqlite(self, compiler, connection):
        pole, parametry = compiler.compile(self.source_expressions[0])
        return (
            f"EXISTS (SELECT 1 FROM json_each({pole}) AS kod WHERE SUBSTR(kod.value, 1, %s) = %s)",
            (*parametry, len(self.prefiks), self.prefiks),
        )


class FiltryWpisow(serializers.Serializer):
    warstwa = serializers.ChoiceField(choices=Warstwa.choices, required=False)
    od = serializers.DateTimeField(required=False)
    do = serializers.DateTimeField(required=False)
    teryt = serializers.RegexField(r"\A[0-9]{1,7}\Z", required=False)
    bbox = serializers.CharField(required=False, max_length=100)

    def validate_bbox(self, value):
        try:
            bbox = [float(wartosc) for wartosc in value.split(",")]
            sprawdz_bbox(bbox)
        except (ValueError, DjangoValidationError) as exc:
            raise serializers.ValidationError("Podaj bbox w kolejności zachód, południe, wschód, północ.") from exc
        return bbox

    def validate(self, attrs):
        if "od" in attrs and "do" in attrs and attrs["od"] > attrs["do"]:
            raise serializers.ValidationError("Początek zakresu musi poprzedzać jego koniec.")
        return attrs


class WpisSerializer(serializers.ModelSerializer):
    zrodlo = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    warstwa = serializers.CharField(source="zrodlo.warstwa")
    atrybucja = serializers.CharField(source="zrodlo.atrybucja")

    class Meta:
        model = Wpis
        fields = (
            "id", "zrodlo", "warstwa", "tytul", "tresc", "link", "opublikowano_at", "pobrano_at",
            "atrybucja", "miejsce", "czas_zrodlowy_at", "dokladna_godzina_publikacji", "klasa", "teryt", "szerokosc", "dlugosc", "bbox", "dokladnosc", "pewnosc_lokalizacji",
        )

    def to_representation(self, instance):
        dane = super().to_representation(instance)
        prefiks = MAKSYMALNY_PREFIKS.get(instance.klasa)
        if prefiks:
            kody = sorted({kod[:prefiks] for kod in instance.teryt if len(kod) >= 2})
            dokladnosc = Wpis.Dokladnosc.BRAK
            if kody:
                dokladnosc = Wpis.Dokladnosc.POWIAT if all(len(kod) == 4 for kod in kody) else Wpis.Dokladnosc.WOJEWODZTWO
            dane.update(teryt=kody, szerokosc=None, dlugosc=None, bbox=None,
                        dokladnosc=dokladnosc, pewnosc_lokalizacji=0)
            dane["miejsce"] = ""
        if instance.zrodlo.slug == "rcb" and instance.dokladna_godzina_publikacji:
            godzina = timezone.localtime(instance.opublikowano_at)
            dane["atrybucja"] += f" o godz. {godzina:%H:%M}"
        return dane


class ZdarzenieSerializer(serializers.ModelSerializer):
    wpisy = WpisSerializer(source="publiczne_wpisy", many=True)
    zweryfikowal = serializers.SerializerMethodField()

    class Meta:
        model = Zdarzenie
        fields = ("id", "status", "tytul_roboczy", "pierwszy_wpis_at", "ostatni_wpis_at",
                  "przygotowane_automatycznie", "zweryfikowal", "zweryfikowano_at", "wpisy")

    def get_zweryfikowal(self, obj) -> str | None:
        return (obj.zweryfikowal.first_name or None) if obj.zweryfikowal else None


class SwiezoscSerializer(serializers.Serializer):
    ostatnie_pobranie_at = serializers.DateTimeField(allow_null=True)
    ostatni_sukces_at = serializers.DateTimeField(allow_null=True)
    liczba_wpisow_24h = serializers.IntegerField()
    luka = serializers.BooleanField()
    blad = serializers.BooleanField()


class ZrodloSerializer(SwiezoscSerializer):
    slug = serializers.CharField()
    nazwa = serializers.CharField()
    instytucja = serializers.CharField()
    atrybucja = serializers.CharField()
    czestotliwosc_s = serializers.IntegerField()


class WarstwaSerializer(SwiezoscSerializer):
    warstwa = serializers.CharField()
    nazwa = serializers.CharField()
    wylaczona = serializers.BooleanField()
    zrodla = ZrodloSerializer(many=True)
    atrybucja = serializers.ListField(child=serializers.CharField())


class LiniaStanuSerializer(serializers.Serializer):
    warstwa = serializers.CharField()
    ostatnie_pobranie = serializers.CharField()
    komunikaty = serializers.CharField()
    komunikat = serializers.CharField(allow_blank=True)


class StanSerializer(serializers.Serializer):
    informacja = serializers.CharField()
    warstwy = LiniaStanuSerializer(many=True)


def stan_warstw():
    teraz = timezone.now()
    wylaczone = set(WylacznikKategorii.objects.filter(
        aktywny=True, warstwa__isnull=False,
    ).values_list("warstwa", flat=True))
    liczby = dict(Wpis.objects.publiczne().filter(
        opublikowano_at__range=(teraz - timedelta(hours=24), teraz),
    ).values_list("zrodlo_id").annotate(liczba=Count("pk")))
    grupy = {warstwa: [] for warstwa in Warstwa.values}
    zrodla = Zrodlo.objects.filter(tryb=Zrodlo.Tryb.PUBLICZNY).exclude(warstwa__in=wylaczone).order_by("slug")
    for zrodlo in zrodla:
        sukces = zrodlo.ostatni_sukces_at
        prog_luki_s = max(2 * zrodlo.czestotliwosc_s, 300)
        grupy[zrodlo.warstwa].append({
            "slug": zrodlo.slug,
            "nazwa": zrodlo.nazwa,
            "instytucja": zrodlo.instytucja,
            "atrybucja": zrodlo.atrybucja,
            "czestotliwosc_s": zrodlo.czestotliwosc_s,
            "ostatnie_pobranie_at": zrodlo.ostatnie_pobranie_at,
            "ostatni_sukces_at": sukces,
            "liczba_wpisow_24h": liczby.get(zrodlo.pk, 0),
            "luka": sukces is None or (teraz - sukces).total_seconds() > prog_luki_s,
            "blad": bool(zrodlo.ostatni_blad or zrodlo.kolejne_bledy),
        })
    return [
        {"warstwa": warstwa, "nazwa": nazwa, "wylaczona": warstwa in wylaczone, "zrodla": grupy[warstwa],
         "atrybucja": list(dict.fromkeys(z["atrybucja"] for z in grupy[warstwa] if z["atrybucja"])),
         "ostatnie_pobranie_at": max((z["ostatnie_pobranie_at"] for z in grupy[warstwa] if z["ostatnie_pobranie_at"]), default=None),
         "ostatni_sukces_at": max((z["ostatni_sukces_at"] for z in grupy[warstwa] if z["ostatni_sukces_at"]), default=None),
         "liczba_wpisow_24h": sum(z["liczba_wpisow_24h"] for z in grupy[warstwa]),
         "luka": any(z["luka"] for z in grupy[warstwa]), "blad": any(z["blad"] for z in grupy[warstwa])}
        for warstwa, nazwa in Warstwa.choices
    ]


class StronicowanieTeraz(PageNumberPagination):
    def paginate_queryset(self, queryset, request, view=None):
        self.widok = view
        return super().paginate_queryset(queryset, request, view)

    def get_page_number(self, request, paginator):
        strona = self.widok.strona
        return paginator.num_pages if strona in self.last_page_strings else strona

    def _link(self, numer):
        parametry = self.widok.parametry_url.copy()
        if numer != 1:
            parametry[self.page_query_param] = numer
        query = urlencode(sorted(parametry.items()))
        return f"{self.widok.adres}?{query}" if query else self.widok.adres

    def get_next_link(self):
        return self._link(self.page.next_page_number()) if self.page.has_next() else None

    def get_previous_link(self):
        return self._link(self.page.previous_page_number()) if self.page.has_previous() else None


class PublicznyOdczyt(GenericAPIView):
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]
    http_method_names = ["get"]
    filtry_class = serializers.Serializer
    pagination_class = None
    cache_dostepny = True

    def get_throttles(self):
        throttles = super().get_throttles()
        for throttle in throttles:
            if isinstance(throttle, SimpleRateThrottle):
                throttle.cache = caches["teraz"]
        return throttles

    def check_throttles(self, request):
        try:
            super().check_throttles(request)
        except BLEDY_CACHE:
            self.cache_dostepny = False

    def przygotuj_parametry(self, request):
        filtry = self.filtry_class(data=request.query_params)
        filtry.is_valid(raise_exception=True)
        self.filtry = filtry.validated_data
        self.parametry_url = self.filtry.copy()
        for pole in ("od", "do"):
            if pole in self.filtry:
                self.parametry_url[pole] = self.filtry[pole].isoformat()
        if "bbox" in self.filtry:
            self.parametry_url["bbox"] = ",".join(str(punkt) for punkt in self.filtry["bbox"])
        self.adres = request.build_absolute_uri(request.path)

        parametry_cache = self.parametry_url.copy()
        if self.paginator is not None:
            pole = self.paginator.page_query_param
            strona = request.query_params.get(pole) or "1"
            if strona not in self.paginator.last_page_strings:
                try:
                    strona = int(strona)
                except ValueError:
                    raise NotFound("Nieprawidłowa strona.") from None
                if strona < 1:
                    raise NotFound("Nieprawidłowa strona.")
            self.strona = strona
            parametry_cache[pole] = strona
        return parametry_cache

    def get(self, request, *args, **kwargs):
        parametry = self.przygotuj_parametry(request)
        klucz = None
        if self.cache_dostepny:
            try:
                cache = caches["teraz"]
                klucz = klucz_odpowiedzi(self.adres, parametry)
                dane = cache.get(klucz)
                if dane is not None:
                    return Response(dane, headers={"Cache-Control": "no-store"})
            except BLEDY_CACHE:
                klucz = None

        odpowiedz = self.odczytaj()
        if klucz is not None and odpowiedz.status_code == 200:
            try:
                cache.set(klucz, odpowiedz.data, timeout=CZAS_CACHE)
            except BLEDY_CACHE:
                pass
        odpowiedz["Cache-Control"] = "no-store"
        return odpowiedz

    def lista(self, queryset):
        strona = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(strona, many=True).data)


class WarstwyView(PublicznyOdczyt):
    serializer_class = WarstwaSerializer

    def odczytaj(self):
        return Response(self.get_serializer(stan_warstw(), many=True).data)


class StanView(PublicznyOdczyt):
    serializer_class = StanSerializer

    def odczytaj(self):
        linie = []
        for warstwa in stan_warstw():
            ostatnie = warstwa["ostatnie_pobranie_at"]
            linie.append({
                "warstwa": warstwa["warstwa"],
                "ostatnie_pobranie": (
                    f"ostatnie pobranie: {timezone.localtime(ostatnie):%H:%M}" if ostatnie else "brak w naszych danych"
                ),
                "komunikaty": f"komunikatów z 24 h: {warstwa['liczba_wpisow_24h']}",
                "komunikat": NIEPEWNOSC if warstwa["luka"] or warstwa["blad"] or not warstwa["zrodla"] else "",
            })
        return Response(self.get_serializer({"informacja": "To nie jest strona urzędowa", "warstwy": linie}).data)


class WpisyView(PublicznyOdczyt):
    serializer_class = WpisSerializer
    filtry_class = FiltryWpisow
    pagination_class = StronicowanieTeraz

    def get_queryset(self):
        dane = self.filtry
        wpisy = Wpis.objects.publiczne().select_related("zrodlo").order_by("-opublikowano_at", "-pk")
        for filtr, pole in (("warstwa", "zrodlo__warstwa"), ("od", "opublikowano_at__gte"), ("do", "opublikowano_at__lte")):
            if filtr in dane:
                wpisy = wpisy.filter(**{pole: dane[filtr]})
        if "teryt" in dane:
            prefiks = dane["teryt"]
            ukryte_klasy = [klasa for klasa, limit in MAKSYMALNY_PREFIKS.items() if len(prefiks) > limit]
            wpisy = wpisy.exclude(klasa__in=ukryte_klasy).filter(PrefiksTeryt(prefiks))
        if "bbox" in dane:
            zachod, poludnie, wschod, polnoc = dane["bbox"]
            wpisy = wpisy.exclude(klasa__in=MAKSYMALNY_PREFIKS).alias(
                bbox_zachod=Cast(KeyTextTransform("0", "bbox"), FloatField()),
                bbox_poludnie=Cast(KeyTextTransform("1", "bbox"), FloatField()),
                bbox_wschod=Cast(KeyTextTransform("2", "bbox"), FloatField()),
                bbox_polnoc=Cast(KeyTextTransform("3", "bbox"), FloatField()),
            ).filter(
                Q(dlugosc__range=(zachod, wschod), szerokosc__range=(poludnie, polnoc))
                | Q(bbox_zachod__lte=wschod, bbox_wschod__gte=zachod,
                    bbox_poludnie__lte=polnoc, bbox_polnoc__gte=poludnie)
            )
        return wpisy

    def odczytaj(self):
        return self.lista(self.get_queryset())


class ZdarzeniaView(PublicznyOdczyt):
    serializer_class = ZdarzenieSerializer
    pagination_class = StronicowanieTeraz

    def get_queryset(self):
        wpisy = (Wpis.objects.publiczne().select_related("zrodlo")
                 .alias(czas_osi=Coalesce("czas_zrodlowy_at", "opublikowano_at"))
                 .order_by("czas_osi", "pk"))
        return (Zdarzenie.objects.publiczne().select_related("zweryfikowal")
                .prefetch_related(Prefetch("wpisy", queryset=wpisy, to_attr="publiczne_wpisy"))
                .order_by("-ostatni_wpis_at", "-pk"))

    def odczytaj(self):
        return self.lista(self.get_queryset())


class ZdarzenieView(ZdarzeniaView):
    pagination_class = None

    def odczytaj(self):
        zdarzenie = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        return Response(self.get_serializer(zdarzenie).data)
