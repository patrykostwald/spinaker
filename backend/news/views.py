from collections import defaultdict
from datetime import datetime, time, timedelta
from hashlib import sha256
import re
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers
from news.models import Article, ArticleCategory, Ballot, EvidenceLink, Thread, ThreadItem
from news.serializers import ArticleSerializer, BallotSerializer, SearchTimelineSerializer, ThreadListSerializer, ThreadSerializer

def voting_question_tokens(query):
    """Recognize explicit Polish questions; ordinary keyword search stays unchanged."""
    words = re.findall(r'\w+', query.casefold())[:20]
    normalized = [word.translate(str.maketrans('ąćęłńóśźż', 'acelnoszz')) for word in words]
    if 'jak' not in normalized or not any(word in {'glosowal', 'glosowala', 'glosowali', 'glosowaly'} for word in normalized):
        return None
    stop = {'jak', 'glosowal', 'glosowala', 'glosowali', 'glosowaly', 'posel', 'poslanka', 'poslowie',
            'poslanki', 'pan', 'pani', 'w', 'sprawie', 'nad', 'na', 'przy', 'czy', 'sie', 'i'}
    return [word for word, normalized_word in zip(words, normalized) if normalized_word not in stop]


class SearchViewSet(viewsets.ViewSet):
    serializer_class = SearchTimelineSerializer

    @extend_schema(parameters=[OpenApiParameter('q', str, required=True), OpenApiParameter('categories', str),
        OpenApiParameter('from_date', OpenApiTypes.DATE), OpenApiParameter('to_date', OpenApiTypes.DATE)], responses=SearchTimelineSerializer)
    def list(self, request):
        query = request.query_params.get('q', '').strip()
        from scraper.utils import safe_url
        url_query = safe_url(query) if query.startswith(('https://', 'http://')) else ''
        if not query or len(query) > (1024 if url_query else 200):
            raise ValidationError({'q': 'Podaj frazę do 200 znaków lub URL do 1024 znaków.'})
        categories = [x.strip() for x in request.query_params.get('categories', '').split(',') if x.strip()]
        if set(categories) - set(ArticleCategory.values):
            raise ValidationError({'categories': 'Nieznana kategoria.'})
        dates = {}
        for key in ('from_date', 'to_date'):
            raw = request.query_params.get(key)
            if raw:
                try:
                    dates[key] = parse_date(raw)
                except ValueError:
                    dates[key] = None
                if dates[key] is None:
                    raise ValidationError({key: 'Użyj poprawnej daty YYYY-MM-DD.'})
        if dates.get('from_date') and dates.get('to_date') and dates['from_date'] > dates['to_date']:
            raise ValidationError({'to_date': 'Koniec zakresu poprzedza początek.'})
        try:
            page = int(request.query_params.get('page', '1'))
            if page < 1: raise ValueError
        except ValueError:
            raise ValidationError({'page': 'Podaj dodatni numer strony.'})
        page_size = 100
        key = 'search:' + sha256(repr(('live-search-v2', cache.get('search-generation', 1), query, categories, dates, page)).encode()).hexdigest()
        payload = cache.get(key)
        if payload is not None:
            return Response(payload)
        tokens = [] if url_query else re.findall(r'\w+', query)[:20]
        if not tokens and not url_query:
            raise ValidationError({'q': 'Podaj słowo lub nazwisko.'})
        voting_tokens = voting_question_tokens(query)
        name_tokens = []
        if voting_tokens is not None:
            tokens = voting_tokens
            # Match all identified name tokens against one ballot, not different MPs.
            name_tokens = [token for token in tokens if Ballot.objects.filter(name__icontains=token).exists()]
        member_query = Q()
        for token in tokens:
            member_query |= Q(name__icontains=token)
        if voting_tokens is not None:
            member_query = Q()
            for token in name_tokens:
                member_query &= Q(name__icontains=token)
        qs = Article.objects.exclude(category='tweet').exclude(source__source_type='twitter').select_related('source', 'voting', 'official_record', 'content').prefetch_related('evidence_links',
            Prefetch('voting__ballots', queryset=Ballot.objects.filter(member_query)))
        if url_query:
            qs = qs.filter(url=url_query.split('#', 1)[0])
        if voting_tokens is not None:
            matching = Ballot.objects.filter(member_query) if name_tokens else Ballot.objects.none()
            qs = qs.filter(category=ArticleCategory.VOTING, pk__in=matching.values('voting__article_id'))
        # Each word must have evidence in text, a member identity, or a sourced editorial link.
        for token in tokens:
            motion_match = Q(voting__motion__icontains=token) if voting_tokens is not None else Q(pk__in=[])
            qs = qs.filter(Q(title__icontains=token) | Q(description__icontains=token) | Q(content__text__icontains=token)
                | motion_match
                | Q(pk__in=Ballot.objects.filter(name__icontains=token).values('voting__article_id'))
                | Q(pk__in=EvidenceLink.objects.filter(phrase__icontains=token).values('article_id')))
        if categories:
            qs = qs.filter(category__in=categories)
        for name, day in dates.items():
            if name == 'from_date':
                qs = qs.filter(published_date__gte=timezone.make_aware(datetime.combine(day, time.min)))
            else:
                qs = qs.filter(published_date__lt=timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min)))
        total = qs.count()
        timeline = defaultdict(list)
        for article in qs.order_by(F('published_date').desc(nulls_last=True), '-pk')[(page - 1) * page_size:page * page_size]:
            day = timezone.localtime(article.published_date).date().isoformat() if article.published_date else 'undated'
            timeline[day].append(ArticleSerializer(article, context={'search_tokens': tokens}).data)
        payload = {'total': total, 'returned': sum(map(len, timeline.values())), 'truncated': False, 'page': page, 'next_page': page + 1 if page * page_size < total else None, 'timeline': dict(timeline)}
        if voting_tokens is not None:
            payload['direct_results'] = ArticleSerializer(
                list(qs.order_by(F('published_date').desc(nulls_last=True), '-pk')[:3]), many=True,
                context={'search_tokens': name_tokens}).data
            payload['query_intent'] = 'member_votes'
        # Local importers and the web server do not share LocMemCache generations.
        # A short TTL also reveals bulk imports without adding a DB write per article.
        cache.set(key, payload, 5)
        return Response(payload)

class ArticleViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.filter(source__is_active=True).exclude(source__catalog_stage='excluded').select_related('source', 'voting', 'official_record', 'content').prefetch_related('evidence_links')

    @extend_schema(parameters=[OpenApiParameter('q', str)], responses=BallotSerializer(many=True))
    @action(detail=True, methods=['get'])
    def ballots(self, request, pk=None):
        voting = getattr(self.get_object(), 'voting', None)
        if voting is None:
            return Response({'detail': 'Ten materiał nie jest głosowaniem.'}, status=404)
        qs = voting.ballots.all()
        name = request.query_params.get('q', '').strip()
        if len(name) > 200:
            raise ValidationError({'q': 'Maksymalnie 200 znaków.'})
        for token in name.split():
            qs = qs.filter(name__icontains=token)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(BallotSerializer(page, many=True).data)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'])
    def official(self, request, pk=None):
        record = getattr(self.get_object(), 'official_record', None)
        if record is None:
            return Response({'detail': 'Brak urzędowego rekordu.'}, status=404)
        return Response({'provider': record.provider, 'api_url': record.api_url, 'fetched_at': record.fetched_at, 'data': record.raw_data})

    @extend_schema(responses=inline_serializer(name='RelatedArticles', fields={'related': ArticleSerializer(many=True)}))
    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        article = self.get_object()
        if not article.published_date:
            return Response({'related': []})
        keywords = {w for w in re.findall(r'\w+', article.title.lower()) if len(w) > 4}
        candidates = self.get_queryset().exclude(pk=article.pk).filter(published_date__range=(
            article.published_date - timedelta(days=7), article.published_date + timedelta(days=7)))
        scored = []
        for candidate in candidates.order_by('-published_date')[:200]:
            score = len(keywords & set(re.findall(r'\w+', candidate.title.lower())))
            if score:
                scored.append((score, candidate))
        scored.sort(key=lambda pair: (pair[0], pair[1].published_date), reverse=True)
        return Response({'related': ArticleSerializer([a for _, a in scored[:10]], many=True).data})

class ThreadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_field = 'slug'

    def get_serializer_class(self):
        return ThreadSerializer if self.action == 'retrieve' else ThreadListSerializer

    def get_queryset(self):
        visible = Article.objects.all()
        items = ThreadItem.objects.filter(Q(article__in=visible) | ~Q(external_url="")).select_related('thread__created_by', 'article__source', 'article__voting', 'article__official_record', 'article__content').prefetch_related('article__evidence_links').order_by('position', 'id')
        qs = Thread.objects.filter(published=True).prefetch_related(Prefetch('thread_items', queryset=items, to_attr='visible_items'))
        if self.request.query_params.get('featured') in {'1', 'true', 'True'}:
            qs = qs.filter(is_featured=True)
        return qs.order_by('-is_featured', '-updated_at', '-pk')

    def retrieve(self, request, *args, **kwargs):
        thread = self.get_object()
        Thread.objects.filter(pk=thread.pk).update(views_count=F('views_count') + 1)
        thread.views_count += 1
        return Response(self.get_serializer(thread).data)

@extend_schema(responses=inline_serializer(name='Health', fields={'status': serializers.CharField()}))
@api_view(['GET'])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('health-check', 1, 10)
        if cache.get('health-check') != 1:
            raise RuntimeError('Cache unavailable')
        return Response({'status': 'ok'})
    except Exception:
        return Response({'status': 'unavailable'}, status=503)

@extend_schema(responses=inline_serializer(name='CurrentUser', fields={'authenticated': serializers.BooleanField(), 'is_editor': serializers.BooleanField(), 'is_journalist': serializers.BooleanField(), 'can_edit_threads': serializers.BooleanField(), 'can_create_threads': serializers.BooleanField(), 'can_publish': serializers.BooleanField(), 'can_manage_sponsorship': serializers.BooleanField(), 'role': serializers.CharField(), 'username': serializers.CharField(), 'patronite_url': serializers.CharField(), 'buycoffee_url': serializers.CharField()}))
@api_view(['GET'])
def me(request):
    from django.conf import settings
    from news.editorial_roles import role_data
    return Response({'authenticated': request.user.is_authenticated, **role_data(request.user), 'username': request.user.get_username(), 'patronite_url': settings.PATRONITE_URL, 'buycoffee_url': settings.BUYCOFFEE_URL})

@extend_schema(request=inline_serializer(name='GoogleNewsQuery', fields={'q': serializers.CharField(max_length=200)}), responses={202: OpenApiTypes.OBJECT})
@api_view(['POST'])
@permission_classes([IsAdminUser])
def google_news(request):
    query = str(request.data.get('q', '')).strip()
    if not query or len(query) > 200:
        raise ValidationError({'q': 'Podaj frazę od 1 do 200 znaków.'})
    from scraper.tasks import scrape_google_news
    task = scrape_google_news.delay(query)
    return Response({'task_id': task.id}, status=202)


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def editorial_status(request):
    from django.conf import settings
    from news.models import Source, ImportState, ArchiveJob
    feeds = Source.objects.exclude(rss_url='')
    return Response({'articles': Article.objects.count(), 'published_threads': Thread.objects.filter(published=True).count(),
        'rss_sources': feeds.count(), 'rss_with_errors': feeds.exclude(last_error='').count(),
        'source_errors': list(Source.objects.exclude(last_error='').values('id', 'name', 'last_error', 'last_scraped')),
        'jobs': list(ImportState.objects.values('name', 'last_started', 'last_success', 'last_error', 'imported')),
        'x_enabled': settings.TWITTER_ENABLED and bool(settings.TWITTER_BEARER_TOKEN),
        'newsapi_enabled': settings.NEWSAPI_ENABLED and bool(settings.NEWSAPI_KEY),
        'local_mode': connection.vendor == 'sqlite',
        'local_worker_active': ImportState.objects.filter(name='local:heartbeat', last_success__gte=timezone.now()-timedelta(seconds=90)).exists(),
        'archive_queue': list(ArchiveJob.objects.values('status').annotate(count=Count('id')))})

@extend_schema(request=None, responses={501: OpenApiTypes.OBJECT})
@api_view(['POST'])
def patronite_webhook(request):
    return Response({'detail': 'Integracja webhook nie jest jeszcze aktywna.'}, status=501)


@api_view(['GET'])
def source_coverage(request):
    from django.db.models import Count, Min, Max
    from news.models import Source, ArchiveJob
    sources = Source.objects.exclude(source_type__in=['twitter', 'politician']).filter(is_active=True).annotate(
        records=Count('articles'), oldest=Min('articles__published_date'), newest=Max('articles__published_date')).order_by('name')
    queue = {row['source_id']: row['count'] for row in ArchiveJob.objects.exclude(status='done').values('source_id').annotate(count=Count('id'))}
    return Response({'complete': False, 'notice': 'Zakres dat dotyczy zgromadzonych rekordów. Nie oznacza kompletnego archiwum wydawcy.',
        'sources': [{'id': row.pk, 'name': row.name, 'url': row.url, 'records': row.records,
            'oldest': row.oldest, 'newest': row.newest, 'last_checked': row.last_scraped,
            'status': 'requires_attention' if row.last_error else 'collected' if row.records else 'not_collected',
            'pending_archive_urls': queue.get(row.pk, 0)} for row in sources]})


@api_view(['GET'])
def archive_status(request):
    """Small public progress snapshot; no internal errors, jobs or credentials."""
    from news.models import Source, ImportState
    payload = cache.get('archive-public-status-v1')
    if payload is None:
        heartbeat = ImportState.objects.filter(name='local:heartbeat').values_list('last_success', flat=True).first()
        now = timezone.now()
        payload = {
            'records': Article.objects.exclude(category='tweet').exclude(source__source_type='twitter').count(),
            'active_sources': Source.objects.filter(is_active=True, scrape_enabled=True).exclude(source_type__in=['twitter', 'politician']).count(),
            'worker_status': 'running' if heartbeat and 0 <= (now - heartbeat).total_seconds() < 90 else 'unconfirmed',
            'last_heartbeat': heartbeat.isoformat() if heartbeat else None,
            'checked_at': now.isoformat(), 'complete': False,
        }
        cache.set('archive-public-status-v1', payload, 10)
    return Response(payload)
