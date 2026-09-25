"""Nitki czytelników (faza II): publiczne nitki kontekstowe, linki spoza Bazy, reakcje i zgłoszenia."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from news.account_models import PersonalContextThread
from news.accounts import AccountWriteThrottle, OpinionInput, OpinionReadThrottle
from news.community_models import CommunityLink, CommunityThreadOpinion, CommunityThreadReport
from news.models import Article
from news.schema import json_view

TRACKING_PARAMS = ('utm_', 'fbclid', 'gclid', 'mc_', 'igshid', 'ref_src', 'dclid', 'yclid', '_ga')
MIN_PUBLIC_ITEMS = 2


def canonical_url(value: str) -> str:
    """Jeden adres = jeden box: bez śledzących parametrów, fragmentu, „www.” i końcowego ukośnika."""
    parts = urlsplit(value.strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise ValueError('url')
    host = parts.hostname.lower().removeprefix('www.')
    if parts.port and parts.port not in (80, 443):
        host = f'{host}:{parts.port}'
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith(TRACKING_PARAMS)]
    path = parts.path.rstrip('/') or '/'
    return urlunsplit(('https', host, path, urlencode(sorted(query)), ''))


def _article_ref(article):
    return {'kind': 'article', 'id': article.pk, 'title': article.title, 'url': article.url,
            'category': article.category, 'published_date': article.published_date,
            'source_name': article.source.name if article.source_id else ''}


def _link_ref(link):
    return {'kind': 'link', 'id': link.pk, 'title': link.title, 'url': link.canonical_url, 'domain': link.domain,
            'title_origin': link.title_origin}


def find_article(url: str, canonical: str):
    candidates = {url, canonical, canonical.replace('https://', 'https://www.', 1), canonical + '/'}
    return (Article.objects.filter(url__in=candidates, source__is_active=True).exclude(source__catalog_stage='excluded')
            .select_related('source').first())


def fetch_publisher_title(url: str) -> str:
    """Tytuł z metadanych strony — tylko gdy włączone (jedno pobranie na prośbę czytelnika)."""
    if os.environ.get('COMMUNITY_LINK_PREVIEW_ENABLED', '').lower() != 'true':
        return ''
    try:
        from news.metadata import extract_metadata
        from scraper.utils import fetch_feed, safe_url
        if not safe_url(url):
            return ''
        return str(extract_metadata(fetch_feed(url), url).get('title') or '')[:300]
    except Exception:
        return ''


class LinkInput(serializers.Serializer):
    url = serializers.URLField(max_length=1024)
    title = serializers.CharField(max_length=300, required=False, allow_blank=True, default='')


class LinkThrottle(UserRateThrottle):
    scope = 'community_link'
    rate = '60/hour'


@extend_schema(summary='Dodaj materiał do nitki przez link (bez kopiowania treści)', tags=['nitki'],
               request=LinkInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LinkThrottle])
def resolve_link(request):
    serializer = LinkInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data['url'].strip()
    try:
        canonical = canonical_url(url)
    except ValueError:
        raise serializers.ValidationError({'url': 'Podaj adres zaczynający się od http:// albo https://.'})
    article = find_article(url, canonical)
    if article:
        return Response({'item': _article_ref(article), 'status': 'in_base'})
    existing = CommunityLink.objects.filter(canonical_url=canonical, hidden_at__isnull=True).first()
    if existing:
        return Response({'item': _link_ref(existing), 'status': 'existing_link'})
    if CommunityLink.objects.filter(canonical_url=canonical).exists():
        return Response({'detail': 'Ten link został usunięty przez zespół i nie może być ponownie dodany.'}, status=409)
    title, origin = fetch_publisher_title(url), 'publisher'
    if not title:
        title, origin = serializer.validated_data['title'].strip(), 'reader'
    if not title:
        return Response({'detail': 'Podaj tytuł materiału — przepisz go ze strony źródła.', 'needs_title': True}, status=422)
    try:
        with transaction.atomic():
            link = CommunityLink.objects.create(canonical_url=canonical, domain=urlsplit(canonical).hostname or '',
                                                title=title, title_origin=origin, submitted_by=request.user)
    except IntegrityError:
        link = CommunityLink.objects.get(canonical_url=canonical)
    return Response({'item': _link_ref(link), 'status': 'created'}, status=201)


# --- publiczne nitki ------------------------------------------------------------------------

def public_threads():
    return (PersonalContextThread.objects.filter(is_public=True, hidden_at__isnull=True)
            .annotate(items_count=Count('items', distinct=True)).filter(items_count__gte=MIN_PUBLIC_ITEMS))


def item_data(item):
    if item.article_id:
        data = _article_ref(item.article)
    else:
        data = _link_ref(item.link)
        data['hidden'] = bool(item.link.hidden_at)
    data.update({'note': item.note, 'position': item.position})
    return data


def _counts(thread_ids):
    result = {pk: {'positive': 0, 'negative': 0} for pk in thread_ids}
    for row in CommunityThreadOpinion.objects.filter(thread_id__in=thread_ids).values('thread_id', 'polarity').annotate(n=Count('id')):
        result[row['thread_id']][row['polarity']] = row['n']
    return result


def thread_summary(thread, counts):
    items = [item for item in thread.items.all() if not (item.link_id and item.link.hidden_at)]
    return {'id': thread.pk, 'title': thread.title, 'description': thread.description,
            'author': thread.owner.username, 'published_at': thread.published_at, 'updated_at': thread.updated_at,
            'items_count': len(items), 'preview': [item_data(item) for item in items[:3]],
            'opinions': counts.get(thread.pk, {'positive': 0, 'negative': 0})}


@extend_schema(summary='Publiczne nitki kontekstowe czytelników', tags=['nitki'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def community_threads(request):
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        return Response({'detail': 'Nieprawidłowy numer strony.'}, status=400)
    rows = public_threads().select_related('owner').prefetch_related('items__article__source', 'items__link')
    query = request.query_params.get('q', '').strip()
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(description__icontains=query))
    author = request.query_params.get('author', '').strip()
    if author:
        rows = rows.filter(owner__username=author)
    size = 20
    batch = list(rows.order_by('-published_at', '-pk')[(page - 1) * size:page * size + 1])
    counts = _counts([row.pk for row in batch])
    return Response({'results': [thread_summary(row, counts) for row in batch[:size]],
                     'next_page': page + 1 if len(batch) > size else None})


@extend_schema(summary='Publiczna nitka czytelnika', tags=['nitki'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def community_thread_detail(request, thread_id):
    thread = get_object_or_404(public_threads().select_related('owner'), pk=thread_id)
    items = [item for item in thread.items.select_related('article__source', 'link') if not (item.link_id and item.link.hidden_at)]
    data = thread_summary(thread, _counts([thread.pk]))
    data.update({'items': [item_data(item) for item in items], 'preview': None,
                 'is_owner': request.user.is_authenticated and request.user.pk == thread.owner_id})
    return Response(data)


class CommunityOpinionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = CommunityThreadOpinion
        fields = ['id', 'author', 'polarity', 'body', 'created_at']

    def get_author(self, opinion):
        return {'id': opinion.user_id, 'username': opinion.user.username}


@json_view('Reakcje i komentarze do publicznej nitki czytelnika', tags=['nitki'])
class CommunityOpinionsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method in ('POST', 'PATCH') else super().get_permissions()

    def _thread(self, thread_id):
        return get_object_or_404(public_threads(), pk=thread_id)

    def get(self, request, thread_id):
        rows = self._thread(thread_id).opinions.select_related('user')
        counts = {'positive': 0, 'negative': 0}
        counts.update({row['polarity']: row['n'] for row in rows.values('polarity').annotate(n=Count('id'))})
        mine = rows.filter(user=request.user).first() if request.user.is_authenticated else None
        return Response({
            'counts': counts,
            'mine': CommunityOpinionSerializer(mine).data if mine else None,
            'positive': CommunityOpinionSerializer(rows.filter(polarity='positive').exclude(body='')[:50], many=True).data,
            'negative': CommunityOpinionSerializer(rows.filter(polarity='negative').exclude(body='')[:50], many=True).data,
        })

    def post(self, request, thread_id):
        thread = self._thread(thread_id)
        serializer = OpinionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                opinion = CommunityThreadOpinion.objects.create(user=request.user, thread=thread, **serializer.validated_data)
        except IntegrityError:
            return Response({'detail': 'Twoja reakcja na tę nitkę jest już zapisana.'}, status=409)
        return Response(CommunityOpinionSerializer(opinion).data, status=201)

    def patch(self, request, thread_id):
        if not isinstance(request.data, dict) or set(request.data) - {'body'}:
            raise serializers.ValidationError('Możesz jedynie dopisać komentarz; reakcja pozostaje bez zmian.')
        serializer = OpinionInput(data={'polarity': 'positive', **request.data})
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']
        if not body:
            raise serializers.ValidationError({'body': 'Podaj treść komentarza.'})
        self._thread(thread_id)
        with transaction.atomic():
            opinion = get_object_or_404(CommunityThreadOpinion.objects.select_for_update().select_related('user'),
                                        thread_id=thread_id, user=request.user)
            if opinion.body or not CommunityThreadOpinion.objects.filter(pk=opinion.pk, body='').update(body=body):
                return Response({'detail': 'Komentarz został już zapisany i nie można go zastąpić.'}, status=409)
            opinion.body = body
        return Response(CommunityOpinionSerializer(opinion).data)


class ReportInput(serializers.Serializer):
    reason = serializers.ChoiceField(choices=[value for value, _ in CommunityThreadReport.REASONS])
    details = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


@extend_schema(summary='Zgłoś publiczną nitkę do moderacji', tags=['nitki'], request=ReportInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AccountWriteThrottle])
def report_thread(request, thread_id):
    thread = get_object_or_404(public_threads(), pk=thread_id)
    serializer = ReportInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    _, created = CommunityThreadReport.objects.get_or_create(reporter=request.user, thread=thread, defaults=serializer.validated_data)
    return Response({'status': 'received' if created else 'already_reported'}, status=201 if created else 200)
