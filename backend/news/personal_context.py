"""Owner-scoped APIs for private context threads and comment reports."""
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_models import (
    ArticleFavorite, ArticleOpinion, CommentReport, PersonalContextThread,
    PersonalContextThreadItem, ThreadOpinion,
)
from news.accounts import AccountWriteThrottle
from news.community_models import CommunityLink
from news.models import Article, ArticleCategory, Source
from news.topics import TOPICS
from news.schema import json_view
from drf_spectacular.utils import extend_schema, extend_schema_view


def article_favorite_data(row):
    article = row.article
    return {
        'id': row.pk,
        'article': {'id': article.pk, 'title': article.title, 'url': article.url,
                    'category': article.category, 'published_date': article.published_date},
        'created_at': row.created_at,
    }


class ArticleFavoriteInput(serializers.Serializer):
    article_id = serializers.IntegerField(min_value=1)


@json_view("Ulubione materiały", tags=["konto"])
class ArticleFavoritesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def get(self, request):
        rows = ArticleFavorite.objects.filter(user=request.user, article__source__is_active=True).exclude(
            article__source__catalog_stage='excluded').select_related('article')[:100]
        return Response({'results': [article_favorite_data(row) for row in rows]})

    def post(self, request):
        serializer = ArticleFavoriteInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = get_object_or_404(Article, pk=serializer.validated_data['article_id'], source__is_active=True)
        row, created = ArticleFavorite.objects.get_or_create(user=request.user, article=article)
        return Response(article_favorite_data(row), status=201 if created else 200)


@json_view("Ulubiony materiał", tags=["konto"])
class ArticleFavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def delete(self, request, article_id):
        ArticleFavorite.objects.filter(user=request.user, article_id=article_id).delete()
        return Response(status=204)


class ThreadItemInput(serializers.Serializer):
    article_id = serializers.IntegerField(min_value=1, required=False)
    link_id = serializers.IntegerField(min_value=1, required=False)
    note = serializers.CharField(max_length=280, required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if bool(attrs.get('article_id')) == bool(attrs.get('link_id')):
            raise serializers.ValidationError('Element nitki to materiał z Bazy albo link — dokładnie jedno z nich.')
        return attrs


MIN_PUBLIC_ITEMS = 2


class PersonalContextThreadSerializer(serializers.ModelSerializer):
    source_ids = serializers.PrimaryKeyRelatedField(source='sources', many=True,
        queryset=Source.objects.filter(is_active=True).exclude(catalog_stage='excluded'), required=False)
    article_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    articles = serializers.SerializerMethodField(read_only=True)
    items = ThreadItemInput(many=True, required=False, write_only=True)
    elements = serializers.SerializerMethodField(read_only=True)
    categories = serializers.ListField(child=serializers.ChoiceField(choices=ArticleCategory.choices), max_length=40, required=False)
    topics = serializers.ListField(child=serializers.ChoiceField(choices=list(TOPICS)), max_length=13, required=False)

    class Meta:
        model = PersonalContextThread
        fields = ['id', 'title', 'description', 'query', 'categories', 'topics', 'source_ids', 'article_ids',
                  'articles', 'items', 'elements', 'is_public', 'published_at', 'hidden_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'articles', 'elements', 'published_at', 'hidden_at', 'created_at', 'updated_at']

    def get_articles(self, instance):
        return [
            {'id': item.article_id, 'title': item.article.title, 'url': item.article.url,
             'category': item.article.category, 'published_date': item.article.published_date,
             'position': item.position}
            for item in instance.items.select_related('article').filter(article__isnull=False)
        ]

    def get_elements(self, instance):
        """Wszystkie elementy w kolejności: materiały z Bazy i linki, z notatkami."""
        from news.community import item_data
        return [item_data(item) for item in instance.items.select_related('article__source', 'link').all()]

    def validate_items(self, value):
        if len(value) > 100:
            raise serializers.ValidationError('Nitka może mieć najwyżej 100 elementów.')
        articles = [row['article_id'] for row in value if row.get('article_id')]
        links = [row['link_id'] for row in value if row.get('link_id')]
        if len(articles) != len(set(articles)) or len(links) != len(set(links)):
            raise serializers.ValidationError('Jeden materiał może wystąpić w nitce tylko raz.')
        if set(Article.objects.filter(pk__in=articles, source__is_active=True).values_list('pk', flat=True)) != set(articles):
            raise serializers.ValidationError('Co najmniej jeden materiał nie jest dostępny.')
        if set(CommunityLink.objects.filter(pk__in=links, hidden_at__isnull=True).values_list('pk', flat=True)) != set(links):
            raise serializers.ValidationError('Co najmniej jeden link nie jest dostępny.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('is_public'):
            if 'items' in attrs:
                count = len(attrs['items'])
            elif 'article_ids' in attrs:
                count = len(attrs['article_ids'])
            else:
                count = self.instance.items.count() if self.instance else 0
            if count < MIN_PUBLIC_ITEMS:
                raise serializers.ValidationError({'is_public': f'Opublikować można nitkę z co najmniej {MIN_PUBLIC_ITEMS} elementami.'})
        return attrs

    def validate_article_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Jeden materiał może wystąpić w nitce tylko raz.')
        existing = set(Article.objects.filter(pk__in=value, source__is_active=True).values_list('pk', flat=True))
        if existing != set(value):
            raise serializers.ValidationError('Co najmniej jeden materiał nie jest dostępny.')
        return value

    def validate_categories(self, value):
        return list(dict.fromkeys(value))

    def validate_topics(self, value):
        return list(dict.fromkeys(value))

    def _replace_items(self, instance, rows):
        PersonalContextThreadItem.objects.filter(thread=instance).delete()
        PersonalContextThreadItem.objects.bulk_create([
            PersonalContextThreadItem(thread=instance, article_id=row.get('article_id'), link_id=row.get('link_id'),
                                      note=row.get('note', ''), position=position)
            for position, row in enumerate(rows)
        ])

    @staticmethod
    def _rows(validated_data):
        items = validated_data.pop('items', None)
        article_ids = validated_data.pop('article_ids', None)
        if items is not None:
            return items
        if article_ids is not None:
            return [{'article_id': article_id} for article_id in article_ids]
        return None

    @staticmethod
    def _publication(validated_data, instance=None):
        if validated_data.get('is_public') and not (instance and instance.published_at):
            validated_data['published_at'] = timezone.now()

    def create(self, validated_data):
        rows = self._rows(validated_data) or []
        self._publication(validated_data)
        instance = PersonalContextThread.objects.create(**validated_data)
        self._replace_items(instance, rows)
        return instance

    def update(self, instance, validated_data):
        rows = self._rows(validated_data)
        self._publication(validated_data, instance)
        instance = super().update(instance, validated_data)
        if rows is not None:
            self._replace_items(instance, rows)
        return instance


@json_view("Prywatne nitki kontekstowe", tags=["konto"])
class PersonalContextThreadsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def get(self, request):
        rows = PersonalContextThread.objects.filter(owner=request.user).prefetch_related('items__article', 'sources')[:100]
        return Response({'results': PersonalContextThreadSerializer(rows, many=True).data})

    def post(self, request):
        serializer = PersonalContextThreadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            instance = serializer.save(owner=request.user)
        return Response(PersonalContextThreadSerializer(instance).data, status=201)


@json_view("Prywatna nitka kontekstowa", tags=["konto"])
@extend_schema_view(get=extend_schema(operation_id="account_context_threads_detail_retrieve"))
class PersonalContextThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def _get(self, request, thread_id):
        return get_object_or_404(PersonalContextThread, pk=thread_id, owner=request.user)

    def get(self, request, thread_id):
        return Response(PersonalContextThreadSerializer(self._get(request, thread_id)).data)

    def patch(self, request, thread_id):
        instance = self._get(request, thread_id)
        serializer = PersonalContextThreadSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            instance = serializer.save()
        return Response(PersonalContextThreadSerializer(instance).data)

    def delete(self, request, thread_id):
        self._get(request, thread_id).delete()
        return Response(status=204)


class CommentReportInput(serializers.Serializer):
    article_opinion_id = serializers.IntegerField(min_value=1, required=False)
    thread_opinion_id = serializers.IntegerField(min_value=1, required=False)
    reason = serializers.ChoiceField(choices=CommentReport.REASONS)
    details = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if bool(attrs.get('article_opinion_id')) == bool(attrs.get('thread_opinion_id')):
            raise serializers.ValidationError('Wskaż dokładnie jeden komentarz do zgłoszenia.')
        return attrs


@json_view("Zgłoszenia komentarzy", tags=["reakcje"])
class CommentReportsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def post(self, request):
        serializer = CommentReportInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        target = {}
        if values.get('article_opinion_id'):
            target['article_opinion'] = get_object_or_404(ArticleOpinion, pk=values['article_opinion_id'])
        else:
            target['thread_opinion'] = get_object_or_404(ThreadOpinion, pk=values['thread_opinion_id'])
        try:
            with transaction.atomic():
                report = CommentReport.objects.create(reporter=request.user, reason=values['reason'],
                    details=values['details'], **target)
        except IntegrityError:
            return Response({'detail': 'To zgłoszenie zostało już zapisane.'}, status=409)
        return Response({'id': report.pk, 'status': report.status}, status=201)
