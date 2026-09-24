from urllib.parse import urlparse
from django.db import transaction
from django.db.models import F, Prefetch
from rest_framework import serializers, viewsets
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from news.models import Article, Source, Thread, ThreadItem, ThreadType
from news.serializers import ArticleSerializer, ThreadSerializer
from news.editorial_roles import can_author_threads


class IsThreadAuthor(BasePermission):
    def has_permission(self, request, view):
        return can_author_threads(request.user)

    def has_object_permission(self, request, view, obj):
        return can_author_threads(request.user) and (request.user.is_staff or obj.created_by_id == request.user.pk)

class WriteItemSerializer(serializers.Serializer):
    article_id = serializers.PrimaryKeyRelatedField(queryset=Article.objects.exclude(category='tweet'), required=False)
    external_url = serializers.URLField(required=False)
    def validate(self, attrs):
        if bool(attrs.get('article_id')) == bool(attrs.get('external_url')):
            raise serializers.ValidationError('Wybierz materiał z bazy albo adres posta X.')
        if attrs.get('external_url'):
            from news.x_reference import normalize_x_url
            attrs['external_url'] = normalize_x_url(attrs['external_url'])
        return attrs
    editorial_note = serializers.CharField(required=False, allow_blank=True, max_length=5000)

class WriteThreadSerializer(serializers.ModelSerializer):
    items = WriteItemSerializer(many=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    class Meta:
        model = Thread
        fields = ('title', 'description', 'published', 'is_featured', 'editorial_slot', 'is_sponsored', 'sponsor_name', 'items')
    def validate_items(self, items):
        if not 1 <= len(items) <= 100:
            raise serializers.ValidationError('Dodaj od 1 do 100 materiałów.')
        ids = [('article', i['article_id'].pk) if i.get('article_id') else ('url', i['external_url']) for i in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Ten sam materiał nie może występować dwukrotnie.')
        return items
    def validate(self, attrs):
        if not self.context['request'].user.is_staff:
            protected = {'published', 'is_featured', 'editorial_slot', 'is_sponsored', 'sponsor_name', 'created_by', 'thread_type'}
            supplied = protected.intersection(self.initial_data)
            if supplied:
                raise serializers.ValidationError({key: 'To pole ustala wyłącznie redakcja.' for key in sorted(supplied)})
            # Content edits of an approved story must be reviewed again.
            attrs['published'] = False
            attrs['is_featured'] = False
        effective = lambda field, default: attrs.get(field, getattr(self.instance, field, default))
        if effective('is_featured', False) and not effective('published', False):
            raise serializers.ValidationError('Wyróżnić można wyłącznie opublikowaną nitkę.')
        sponsored = effective('is_sponsored', False)
        if self.instance and self.instance.thread_type == ThreadType.SPONSORED and 'is_sponsored' not in attrs:
            sponsored = True
        name = effective('sponsor_name', '').strip()
        if sponsored and not name:
            raise serializers.ValidationError({'sponsor_name': 'Podaj nazwę sponsora.'})
        if 'is_sponsored' in attrs and not attrs['is_sponsored']:
            if attrs.get('sponsor_name'):
                raise serializers.ValidationError({'sponsor_name': 'Nazwa sponsora wymaga oznaczenia materiału sponsorowanego.'})
            attrs['sponsor_name'] = ''
            if self.instance and self.instance.thread_type == ThreadType.SPONSORED:
                attrs['thread_type'] = ThreadType.CONTEXT
        elif not sponsored and name:
            raise serializers.ValidationError({'sponsor_name': 'Oznacz nitkę jako materiał sponsorowany.'})
        return attrs
    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('items')
        thread = Thread.objects.create(created_by=self.context['request'].user, **validated_data)
        self.save_items(thread, items)
        return thread
    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop('items', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        # Do not write stale approval/sponsor fields from an earlier read when
        # another editor changed them while this author was editing content.
        instance.save(update_fields=[*validated_data, 'updated_at'])
        if items is not None:
            instance.thread_items.all().delete()
            self.save_items(instance, items)
        return instance
    def save_items(self, thread, items):
        # Timeline order follows source publication dates; undated items stay last.
        def publication(item):
            article = item.get('article_id')
            return article.published_date if article else None
        anchor = list(enumerate(items[:1])) if thread.editorial_slot else []
        remaining = list(enumerate(items))[len(anchor):]
        items = anchor + sorted(remaining, key=lambda x: (publication(x[1]) is None, publication(x[1]).isoformat() if publication(x[1]) else '', x[0]))
        ThreadItem.objects.bulk_create([ThreadItem(thread=thread, article=item.get('article_id'), external_url=item.get('external_url', ''), position=index,
            editorial_note=item.get('editorial_note', '')) for index, (_, item) in enumerate(items)])

class EditorialThreadViewSet(viewsets.ModelViewSet):
    permission_classes = [IsThreadAuthor]
    lookup_field = 'slug'
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    def get_queryset(self):
        qs = Thread.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(created_by=self.request.user)
        return qs.select_related('created_by').prefetch_related('created_by__groups', Prefetch('thread_items', queryset=ThreadItem.objects.select_related('thread__created_by', 'article__source', 'article__voting', 'article__official_record', 'article__content').prefetch_related('article__evidence_links', 'thread__created_by__groups').order_by('position', 'id'), to_attr='visible_items'))
    def get_serializer_class(self):
        return ThreadSerializer if self.action in ('list', 'retrieve') else WriteThreadSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = serializer.save()
        return Response({'slug': thread.slug, 'published': thread.published}, status=201)
    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        thread = serializer.save()
        return Response({'slug': thread.slug, 'published': thread.published})

class WriteArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(max_length=255, write_only=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    evidence_note = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    class Meta:
        model = Article
        fields = ('title', 'url', 'published_date', 'category', 'author', 'description', 'source_name', 'evidence_note')
    def validate_url(self, value):
        parsed = urlparse(value)
        if parsed.hostname in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
            raise serializers.ValidationError('Dodaj post X jako odnośnik w nitce, poza bazą artykułów.')
        if parsed.scheme not in ('http', 'https') or parsed.username:
            raise serializers.ValidationError('Podaj adres HTTP lub HTTPS źródła.')
        return value
    @transaction.atomic
    def create(self, data):
        parsed = urlparse(data['url'])
        source, _ = Source.objects.get_or_create(url=f'{parsed.scheme}://{parsed.netloc}', defaults={
            'name': data.pop('source_name'), 'source_type': 'portal', 'scrape_enabled': False})
        article = Article.objects.create(source=source, ingestion_method='manual', category_reviewed=True, **data)
        Source.objects.filter(pk=source.pk).update(total_articles=F('total_articles') + 1)
        return article

class EditorialArticleViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = WriteArticleSerializer
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = serializer.save()
        return Response(ArticleSerializer(article).data, status=201)
