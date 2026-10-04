"""Owner-scoped APIs for private context threads and comment reports."""
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission
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


class ThreadAccountsEnabled(BasePermission):
    def has_permission(self, request, view):
        from news.features import accounts_enabled, threads_enabled
        return accounts_enabled() and threads_enabled()


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
            article__source__catalog_stage='excluded').select_related('article')
        if 'page' in request.query_params:
            from news.profiles import paginate
            return Response(paginate(request, rows, article_favorite_data))
        return Response({'results': [article_favorite_data(row) for row in rows[:100]]})

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
    # przepięcie: boks z oryginalnej spinki (np. diagnoza albo wpis z X ułożony przez Dr. Spina) - materiał kopiowany 1:1
    box_item_id = serializers.IntegerField(min_value=1, required=False)
    # wyjaśnienie autora = „tytuł” boksu: dlaczego ten materiał jest w spince; może być długie (właściciel 3.10)
    note = serializers.CharField(max_length=4000, required=False, allow_blank=True, default='')
    link_note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    role = serializers.ChoiceField(choices=[c for c, _ in PersonalContextThreadItem.ROLES], required=False, allow_blank=True, default='')
    link_kind = serializers.ChoiceField(choices=[c for c, _ in PersonalContextThreadItem.LINK_KINDS], required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if sum(bool(attrs.get(key)) for key in ('article_id', 'link_id', 'box_item_id')) != 1:
            raise serializers.ValidationError('Element spinki to materiał z Bazy albo link - dokładnie jedno z nich.')
        return attrs


MIN_PUBLIC_ITEMS = 2


class PersonalContextThreadSerializer(serializers.ModelSerializer):
    opinions = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    # widoczne na liście: tytuł w jednym wierszu, podtytuł w dwóch (pomiar przy 1280 px, właściciel 4.10)
    title = serializers.CharField(max_length=65)
    description = serializers.CharField(max_length=170, required=False, allow_blank=True)
    source_ids = serializers.PrimaryKeyRelatedField(source='sources', many=True,
        queryset=Source.objects.filter(is_active=True).exclude(catalog_stage='excluded'), required=False)
    article_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=10, required=False)
    continues = serializers.PrimaryKeyRelatedField(queryset=PersonalContextThread.objects.all(), required=False, allow_null=True)
    repin_of = serializers.PrimaryKeyRelatedField(queryset=PersonalContextThread.objects.all(), required=False, allow_null=True)
    articles = serializers.SerializerMethodField(read_only=True)
    items = ThreadItemInput(many=True, required=False, write_only=True)
    elements = serializers.SerializerMethodField(read_only=True)
    categories = serializers.ListField(child=serializers.ChoiceField(choices=ArticleCategory.choices), max_length=40, required=False)
    topics = serializers.ListField(child=serializers.ChoiceField(choices=list(TOPICS)), max_length=13, required=False)

    class Meta:
        model = PersonalContextThread
        fields = ['id', 'continues', 'repin_of', 'title', 'description', 'query', 'categories', 'topics', 'source_ids', 'article_ids',
                  'articles', 'items', 'elements', 'is_public', 'published_at', 'hidden_at', 'created_at', 'updated_at', 'opinions', 'comments_count']
        read_only_fields = ['id', 'articles', 'elements', 'published_at', 'hidden_at', 'created_at', 'updated_at']

    def get_articles(self, instance):
        return [
            {'id': item.article_id, 'title': item.article.title, 'url': item.article.url,
             'category': item.article.category, 'published_date': item.article.published_date,
             'position': item.position}
            for item in instance.items.select_related('article').filter(article__isnull=False)
        ]

    def get_opinions(self, instance):
        from news.community import _counts
        return _counts([instance.pk])[instance.pk]

    def get_comments_count(self, instance):
        return instance.comments.filter(hidden_at__isnull=True, deleted_at__isnull=True).count()

    def get_elements(self, instance):
        """Wszystkie elementy w kolejności: materiały z Bazy i linki, z notatkami."""
        from news.community import item_data
        return [item_data(item) for item in instance.items.select_related('article__source', 'link').all()]

    def validate_items(self, value):
        if len(value) > 10:
            raise serializers.ValidationError('Spinka może mieć najwyżej 10 boksów.')
        articles = [row['article_id'] for row in value if row.get('article_id')]
        links = [row['link_id'] for row in value if row.get('link_id')]
        if len(articles) != len(set(articles)) or len(links) != len(set(links)):
            raise serializers.ValidationError('Jeden materiał może wystąpić w spince tylko raz.')
        if set(Article.objects.filter(pk__in=articles, source__is_active=True).values_list('pk', flat=True)) != set(articles):
            raise serializers.ValidationError('Co najmniej jeden materiał nie jest dostępny.')
        if set(CommunityLink.objects.filter(pk__in=links, hidden_at__isnull=True).values_list('pk', flat=True)) != set(links):
            raise serializers.ValidationError('Co najmniej jeden link nie jest dostępny.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'items' in attrs and 'article_ids' in attrs:
            raise serializers.ValidationError('Podaj jeden zestaw boksów.')
        previous = attrs.get('continues')
        if previous:
            request = self.context.get('request')
            if not request or previous.owner_id != request.user.pk or self.instance:
                raise serializers.ValidationError({'continues': 'Wybierz własną poprzednią spinkę przy tworzeniu kontynuacji.'})
            last = previous.items.last()
            rows = attrs.get('items') or [{'article_id': pk} for pk in attrs.get('article_ids', [])]
            if not last or not rows or (rows[0].get('article_id'), rows[0].get('link_id')) != (last.article_id, last.link_id):
                raise serializers.ValidationError({'continues': 'Pierwszy boks musi być ostatnim boksem poprzedniej spinki.'})
        original = attrs.get('repin_of')
        if original:
            from news.community import public_threads
            if self.instance and self.instance.repin_of_id != original.pk:
                raise serializers.ValidationError({'repin_of': 'Przepięcia nie można przenieść do innej spinki.'})
            if not public_threads().filter(pk=original.pk).exists():
                raise serializers.ValidationError({'repin_of': 'Przepiąć można tylko opublikowaną spinkę.'})
            request = self.context.get('request')
            if request and original.owner_id == request.user.pk:
                raise serializers.ValidationError({'repin_of': 'Własną spinkę możesz po prostu edytować.'})
            rows = attrs.get('items') or [{'article_id': pk} for pk in attrs.get('article_ids', [])]
            key = lambda article, link, box: ('a', article) if article else ('l', link) if link else ('b', box)
            mine = [key(row.get('article_id'), row.get('link_id'), row.get('box_item_id')) for row in rows]
            theirs = {key(item.article_id, item.link_id, item.pk if item.box_data is not None else None)
                      for item in original.items.all() if not (item.link_id and item.link.hidden_at)}
            if rows and (set(mine) != theirs or len(mine) != len(set(mine))):
                raise serializers.ValidationError({'repin_of': 'Przepięcie używa dokładnie tych samych boksów co spinka.'})
        if not original and any(row.get('box_item_id') for row in attrs.get('items') or []):
            raise serializers.ValidationError({'items': 'Boksy z cudzej spinki można użyć tylko w przepięciu.'})
        if attrs.get('is_public', self.instance.is_public if self.instance else False):
            from news.account_security import require_verified
            from news.community import threads_enabled
            if not threads_enabled():
                raise serializers.ValidationError({'is_public': 'Publikacja spinek nie jest jeszcze dostępna.'})
            request = self.context.get('request')
            require_verified(request.user if request else self.instance.owner if self.instance else None)
            if 'items' in attrs:
                count = len(attrs['items'])
            elif 'article_ids' in attrs:
                count = len(attrs['article_ids'])
            else:
                count = self.instance.items.count() if self.instance else 0
            if count < MIN_PUBLIC_ITEMS:
                raise serializers.ValidationError({'is_public': f'Opublikować można spinkę z co najmniej {MIN_PUBLIC_ITEMS} elementami.'})
        return attrs

    def validate_article_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Jeden materiał może wystąpić w spince tylko raz.')
        existing = set(Article.objects.filter(pk__in=value, source__is_active=True).values_list('pk', flat=True))
        if existing != set(value):
            raise serializers.ValidationError('Co najmniej jeden materiał nie jest dostępny.')
        return value

    def validate_categories(self, value):
        return list(dict.fromkeys(value))

    def validate_topics(self, value):
        return list(dict.fromkeys(value))

    def _replace_items(self, instance, rows):
        boxes = dict(PersonalContextThreadItem.objects.filter(pk__in=[row['box_item_id'] for row in rows if row.get('box_item_id')])
                     .values_list('pk', 'box_data'))
        PersonalContextThreadItem.objects.filter(thread=instance).delete()
        PersonalContextThreadItem.objects.bulk_create([
            PersonalContextThreadItem(thread=instance, article_id=row.get('article_id'), link_id=row.get('link_id'),
                                      box_data=boxes.get(row.get('box_item_id')), note=row.get('note', ''), role=row.get('role', ''),
                                      link_kind=row.get('link_kind', '') if position else '',
                                      link_note=row.get('link_note', '') if position else '', position=position)
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
        sources = validated_data.pop('sources', [])
        self._publication(validated_data)
        instance = PersonalContextThread.objects.create(**validated_data)
        instance.sources.set(sources)
        self._replace_items(instance, rows)
        return instance

    def update(self, instance, validated_data):
        rows = self._rows(validated_data)
        self._publication(validated_data, instance)
        instance = super().update(instance, validated_data)
        if rows is not None:
            self._replace_items(instance, rows)
        return instance


@json_view("Prywatne spinki kontekstowe", tags=["konto"])
class PersonalContextThreadsView(APIView):
    permission_classes = [IsAuthenticated, ThreadAccountsEnabled]
    throttle_classes = [AccountWriteThrottle]

    def get(self, request):
        rows = PersonalContextThread.objects.filter(owner=request.user).prefetch_related('items__article', 'sources')
        state = serializers.ChoiceField(choices=['all', 'draft', 'published', 'hidden']).run_validation(request.query_params.get('status', 'all'))
        if state == 'draft':
            rows = rows.filter(is_public=False, hidden_at__isnull=True)
        elif state == 'published':
            rows = rows.filter(is_public=True, hidden_at__isnull=True)
        elif state == 'hidden':
            rows = rows.filter(hidden_at__isnull=False)
        if 'page' in request.query_params:
            from news.profiles import paginate
            return Response(paginate(request, rows, lambda row: PersonalContextThreadSerializer(row).data))
        return Response({'results': PersonalContextThreadSerializer(rows[:100], many=True).data})

    def post(self, request):
        serializer = PersonalContextThreadSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            instance = serializer.save(owner=request.user)
        return Response(PersonalContextThreadSerializer(instance).data, status=201)


@json_view("Prywatna spinka kontekstowa", tags=["konto"])
@extend_schema_view(get=extend_schema(operation_id="account_context_threads_detail_retrieve"))
class PersonalContextThreadDetailView(APIView):
    permission_classes = [IsAuthenticated, ThreadAccountsEnabled]
    throttle_classes = [AccountWriteThrottle]

    def _get(self, request, thread_id):
        return get_object_or_404(PersonalContextThread, pk=thread_id, owner=request.user)

    def get(self, request, thread_id):
        return Response(PersonalContextThreadSerializer(self._get(request, thread_id)).data)

    def patch(self, request, thread_id):
        instance = self._get(request, thread_id)
        serializer = PersonalContextThreadSerializer(instance, data=request.data, partial=True, context={'request': request})
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
