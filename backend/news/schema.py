"""OpenAPI response shapes for function views and APIViews without a serializer.

drf-spectacular cannot infer bodies built by hand in ``Response({...})``.  The
public portal endpoints (used by the spin.clinic frontend and documented for
outside readers) get explicit shapes below; account, editorial and staff views
are documented as JSON objects with a summary (``json_view``).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers

from news.serializers import ArticleSerializer, SourceSerializer

class PortalChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class ContextCategoryCountSerializer(serializers.Serializer):
    category = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()

FEED_PARAMETERS = [
    OpenApiParameter("mode", str, enum=["latest", "top"], description="`latest` — wszystkie źródła; `top` — dzisiejsze materiały wiodących mediów."),
    OpenApiParameter("q", str, description="Hasło (dopasowanie w tytule i opisie)."),
    OpenApiParameter("match", str, enum=["substring", "words"], description="`words` — dopasowanie całych słów."),
    OpenApiParameter("categories", str, description="Kategorie `ArticleCategory`, rozdzielone przecinkami."),
    OpenApiParameter("topics", str, description="Tematy portalu (np. `polityka,swiat`), rozdzielone przecinkami."),
    OpenApiParameter("sources", str, description="Identyfikatory źródeł, rozdzielone przecinkami."),
    OpenApiParameter("platforms", str, enum=["youtube"], description="Ograniczenie do platformy."),
    OpenApiParameter("page", int, description="Numer strony (od 1)."),
    OpenApiParameter("page_size", int, description="Rozmiar strony (1–40, domyślnie 20)."),
]

FeedResponse = inline_serializer("FeedResponse", {
    "mode": serializers.ChoiceField(choices=["latest", "top"]),
    "results": ArticleSerializer(many=True),
    "total": serializers.IntegerField(),
    "next_page": serializers.IntegerField(allow_null=True),
    "checked_at": serializers.DateTimeField(),
    "latest_published_at": serializers.DateTimeField(allow_null=True),
    "top_sources": SourceSerializer(many=True),
    "selection_note": serializers.CharField(),
})

PortalConfigResponse = inline_serializer("PortalConfigResponse", {
    "categories": PortalChoiceSerializer(many=True),
    "topics": PortalChoiceSerializer(many=True),
    "sources": SourceSerializer(many=True, help_text="Katalog źródeł (bez wykluczonych); `portal_group`: top / publiczne / media."),
    "top_sources": SourceSerializer(many=True),
    "source_stats": serializers.DictField(child=serializers.IntegerField()),
    "editorial": serializers.DictField(help_text="Nitki redakcyjne „Przekaz dnia” (rząd / opozycja) albo null."),
    "x_editorial": serializers.DictField(),
    "platforms": serializers.DictField(),
})

TopicOfDayResponse = inline_serializer("TopicOfDayResponse", {
    "query": serializers.CharField(allow_null=True),
    "label": serializers.CharField(allow_null=True),
    "mode": serializers.ChoiceField(choices=["automatic", "unavailable"]),
    "source_count": serializers.IntegerField(),
    "article_count": serializers.IntegerField(),
})

ArticleContextResponse = inline_serializer("ArticleContextResponse", {
    "query": serializers.CharField(),
    "keywords": serializers.ListField(child=serializers.CharField()),
    "match_basis": serializers.CharField(),
    "counts": ContextCategoryCountSerializer(many=True),
    "total": serializers.IntegerField(),
    "timeline": serializers.DictField(child=ArticleSerializer(many=True), help_text="Materiały powiązane pogrupowane według daty publikacji (YYYY-MM-DD lub `unknown`)."),
    "next_page": serializers.IntegerField(allow_null=True),
    "checked_at": serializers.DateTimeField(),
})

ContextCountsResponse = inline_serializer("ContextCountsResponse", {
    "counts": serializers.DictField(child=serializers.DictField(), help_text="Klucz: id materiału; wartość: total, categories, checked_at, complete."),
})

PublicFigureListResponse = inline_serializer("PublicFigureListResponse", {
    "count": serializers.IntegerField(),
    "page": serializers.IntegerField(),
    "page_size": serializers.IntegerField(),
    "results": serializers.ListField(child=serializers.DictField(), help_text="Profil: id, name, role_category, role_title, organisation, status, official_profile_url, evidence_url, source_checked_at."),
})

PUBLIC_FIGURE_LIST_PARAMETERS = [
    OpenApiParameter("q", str, description="Imię, nazwisko, funkcja lub instytucja."),
    OpenApiParameter("role_category", str, description="government / party / parliamentary / european / local / political."),
    OpenApiParameter("status", str, description="current / former."),
    OpenApiParameter("page", int),
    OpenApiParameter("page_size", int, description="1–100, domyślnie 50."),
]


def json_view(summary, tags=None):
    """Widok bez serializera: treść opisana jako obiekt JSON (żądanie i odpowiedź)."""
    return extend_schema(summary=summary, tags=tags, request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
