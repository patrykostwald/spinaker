"""Publiczne paski: wyłącznie metadane już zebranych materiałów."""
import re
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from news.models import Article
from news.political_models import OfficialVideoChannel
from news.przeszlosc import KIND_LABELS, SOURCE_LABELS
from news.public_records_models import PublicRecord
from news.schema import json_view
from news.serializers import ArticleSerializer

CACHE_KEY = 'przeszlosc:paski:v1'
LIMIT = 20


class VideoMetadataSerializer(ArticleSerializer):
    """Wąska projekcja istniejącego serializera, bez treści i relacji diagnoz."""
    date = serializers.DateTimeField(source='published_date', allow_null=True)
    source = serializers.CharField(source='source.name')
    category = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='source.name')
    image_url = serializers.SerializerMethodField()

    class Meta(ArticleSerializer.Meta):
        fields = ('id', 'title', 'date', 'source', 'url', 'category', 'category_label', 'image_url')

    def get_category(self, obj):
        return obj.source.url.rsplit('/', 1)[-1]

    def get_image_url(self, obj):
        # Kanoniczny URL miniatury, bez przekazywania dowolnego hosta z bazy.
        parsed = urlparse(obj.url)
        video = parse_qs(parsed.query).get('v', [''])[0]
        if parsed.scheme == 'https' and parsed.hostname in {'www.youtube.com', 'youtube.com'} and re.fullmatch(r'[\w-]{11}', video, re.ASCII):
            return f'https://i.ytimg.com/vi/{video}/mqdefault.jpg'
        return ''

    def to_representation(self, instance):
        # ArticleSerializer dodaje opis i sprawdza prawa do pełnej treści.
        # Paski mają osobny, zamknięty kontrakt samych metadanych.
        return serializers.ModelSerializer.to_representation(self, instance)


class PublicMetadataSerializer(serializers.ModelSerializer):
    source = serializers.SerializerMethodField()
    url = serializers.CharField(source='source_url')
    category = serializers.CharField(source='kind')
    category_label = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()

    class Meta:
        model = PublicRecord
        fields = ('id', 'title', 'date', 'source', 'url', 'category', 'category_label', 'kind')

    def get_source(self, obj):
        return {'kprm': 'KPRM', 'ted': 'TED', 'bzp': 'BZP', 'votes': 'Sejm', 'statements': 'Sejm',
                'interpellations': 'Sejm', 'questions': 'Sejm', 'committees': 'Sejm',
                'assets': 'Sejm', 'processes': 'Sejm'}.get(obj.source) or SOURCE_LABELS.get(obj.source, obj.source)

    def get_category_label(self, obj):
        return KIND_LABELS.get(obj.kind) or {
            'statement': 'Wystąpienie', 'speech': 'Wystąpienie', 'document': 'Dokument',
            'press_release': 'Komunikat', 'procurement': 'Zamówienie',
            'notice': 'Zamówienie', 'committee_speech': 'Wystąpienie w komisji',
            'committee': 'Komisja', 'ep_vote': 'Głosowanie PE', 'committee_sitting': 'Posiedzenie komisji',
        }.get(obj.kind, 'Dokument')

    def get_kind(self, obj):
        return self.get_category_label(obj)


class GovernmentMetadataSerializer(VideoMetadataSerializer):
    category_label = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()

    class Meta(VideoMetadataSerializer.Meta):
        fields = ('id', 'title', 'date', 'source', 'url', 'category', 'category_label', 'kind')

    def get_category(self, obj):
        return 'press_release'

    def get_category_label(self, obj):
        return 'Komunikat'

    def get_kind(self, obj):
        return self.get_category_label(obj)


def strip_data():
    channel_urls = (OfficialVideoChannel.objects.filter(status='confirmed', collection_enabled=True)
                    .exclude(channel_id='').annotate(source_url=Concat(Value('https://www.youtube.com/channel/'), 'channel_id'))
                    .values('source_url'))
    videos = (Article.objects.filter(ingestion_method='youtube', source__is_active=True, source__url__in=channel_urls)
              .exclude(title='').filter(url__startswith='https://www.youtube.com/watch?v=')
              .select_related('source').only('id', 'title', 'url', 'published_date', 'source__name', 'source__url')
              .order_by(F('published_date').desc(nulls_last=True), '-pk')[:LIMIT])
    records = (PublicRecord.objects.exclude(title='').exclude(source_url='')
               .only('id', 'title', 'date', 'source', 'source_url', 'kind')
               .order_by(F('date').desc(nulls_last=True), '-fetched_at', '-pk')[:LIMIT])
    # KPRM trafia przez istniejący kolektor RSS/HTML do Article, nie PublicRecord.
    government = (Article.objects.filter(source__is_active=True, source__url__startswith='https://www.gov.pl/web/premier')
                  .exclude(title='').exclude(ingestion_method='youtube').select_related('source')
                  .only('id', 'title', 'url', 'published_date', 'source__name')
                  .order_by(F('published_date').desc(nulls_last=True), '-pk')[:LIMIT])
    public = list(PublicMetadataSerializer(records, many=True).data)
    public.extend(GovernmentMetadataSerializer(government, many=True).data)
    public.sort(key=lambda row: (row['date'] or '', row['id']), reverse=True)
    # Ten sam dokument bywa dostępny w obu istniejących magazynach.
    seen_urls = set()
    unique_public = []
    for row in public:
        if row['url'] not in seen_urls:
            unique_public.append(row)
            seen_urls.add(row['url'])
    # P2-5: różne rodzaje o tej samej etykiecie ('Dokument', 'Dokument') łączymy w jedną kategorię filtra
    for row in unique_public:
        row['category'] = slugify(row['category_label']) or row['category']
    data = {'youtube': VideoMetadataSerializer(videos, many=True).data,
            'publiczne': unique_public[:LIMIT], 'media': []}
    data['kategorie'] = {
        name: [{'id': key, 'label': label} for key, label in sorted(
            {row['category']: row['category_label'] for row in rows}.items(), key=lambda pair: pair[1])]
        for name, rows in data.items()
    }
    data['generated_at'] = timezone.now().isoformat()
    return data


@json_view('Najnowsze filmy i źródła publiczne', tags=['przeszlosc'])
@api_view(['GET'])
@permission_classes([AllowAny])
def strips_view(request):
    data = cache.get(CACHE_KEY)
    if data is None:
        data = strip_data()
        cache.set(CACHE_KEY, data, 300)
    return Response(data)
