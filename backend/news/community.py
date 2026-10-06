"""Spinki czytelników (faza II): publiczne spinki kontekstowe, linki spoza Bazy, reakcje i zgłoszenia."""
import os
from datetime import timedelta
from django.utils import timezone
from news.features import threads_enabled, accounts_enabled
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Max, F
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from news.account_models import PersonalContextThread
from news.community_models import CommunityLink, CommunityThreadOpinion
from news.models import Article

TRACKING_PARAMS = ('utm_', 'fbclid', 'gclid', 'mc_', 'igshid', 'ref_src', 'dclid', 'yclid', '_ga')
MIN_PUBLIC_ITEMS = 2


def _disabled():
    return Response({'detail': 'Spinki czytelników będą dostępne wkrótce.'}, status=404)


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
    from news.media_rights import article_media_allowed
    return {'kind': 'article', 'id': article.pk, 'title': article.title, 'url': article.url,
            'category': article.category, 'published_date': article.published_date,
            'source_name': article.source.name if article.source_id else '',
            # miniatura w boksie tylko ze źródeł, które na to pozwalają
            'image_url': article.image_url if article.image_url and article_media_allowed(article) else ''}


def _link_ref(link):
    from news.x_link_cards import card_data
    return {'kind': 'link', 'id': link.pk, 'title': link.title, 'url': link.canonical_url, 'domain': link.domain,
            'title_origin': link.title_origin, **card_data(link)}


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


@extend_schema(summary='Dodaj materiał do spinki przez link (bez kopiowania treści)', tags=['nitki'],
               request=LinkInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LinkThrottle])
def resolve_link(request):
    if not threads_enabled() or not accounts_enabled():
        return _disabled()
    serializer = LinkInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data['url'].strip()
    from news.x_link_cards import resolve_x
    x_result = resolve_x(url, request.user, serializer.validated_data['title'].strip())
    if x_result:
        if x_result.get('blocked'):
            return Response({'detail': 'Ten link jest ukryty.'}, status=409)
        if x_result.get('needs_title'):
            return Response({'detail': 'Nie udało się pobrać wpisu z X. Podaj tytuł linku.', 'needs_title': True}, status=422)
        return Response({'item': _link_ref(x_result['link']), 'status': 'existing_link'})
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

def public_threads(user=None):
    from news.clinic import published_diagnoses
    from news.thread_review import visible_statuses
    from news.account_models import MutedUser
    from news.diagnosis_threads import min_intensity as diagnosis_min_intensity
    muted = MutedUser.objects.filter(user=user).values('target_id') if user and user.is_authenticated else []
    return (PersonalContextThread.objects.filter(is_public=True, hidden_at__isnull=True)
            .filter(Q(owner__isnull=False) | Q(publication_review__status__in=visible_statuses()))
            .exclude(owner_id__in=muted)
            .filter(Q(diagnosis__isnull=True) | Q(diagnosis__in=published_diagnoses()))
            # spinki z diagnoz tylko od 70/100 (właściciel 5.10); inne rodzaje spinek Dr. Spina bez zmian
            .exclude(diagnosis__intensity__lt=diagnosis_min_intensity())
            .filter(Q(narrative_message__isnull=True) | Q(narrative_message__status='approved'))
            .annotate(items_count=Count('items', distinct=True), visible_comments_count=Count('comments', filter=Q(comments__deleted_at__isnull=True, comments__hidden_at__isnull=True) & ~Q(comments__author_id__in=muted), distinct=True)).filter(items_count__gte=MIN_PUBLIC_ITEMS))


def item_data(item):
    if item.box_data is not None:
        data = {**item.box_data, 'id': item.pk, 'box': True}
        if data.get('political_post_id'):
            from news.political_models import PoliticalPost
            if not PoliticalPost.objects.filter(pk=data['political_post_id'], available=True).exists():
                data.update(title='Wpis niedostępny', body='', source_name='', x_handle='')
        if data.get('box_type') == 'diagnosis' and data.get('diagnosis_id'):
            from news.clinic import published_diagnoses
            if not published_diagnoses().filter(pk=data['diagnosis_id']).exists():
                data.update(title='Diagnoza niedostępna', body='')
    elif item.article_id:
        data = _article_ref(item.article)
    else:
        data = _link_ref(item.link)
        data['hidden'] = bool(item.link.hidden_at)
    data.update({'note': item.note, 'link_note': item.link_note if item.position else '', 'position': item.position, 'item_id': item.pk,
                 'role': item.role, 'link_kind': item.link_kind if item.position else ''})
    return data


def _counts(thread_ids):
    result = {pk: {'positive': 0, 'doubt': 0, 'negative': 0} for pk in thread_ids}
    for row in CommunityThreadOpinion.objects.filter(thread_id__in=thread_ids).values('thread_id', 'polarity').annotate(n=Count('id')):
        result[row['thread_id']][row['polarity']] = row['n']
    return result


def source_key(item):
    if item.article_id:
        return f'a:{item.article.source_id or item.article.url}'
    if item.link_id:
        return f'l:{item.link.domain}'
    data = item.box_data or {}
    return f"b:{data.get('source_name') or data.get('url') or ''}" if (data.get('source_name') or data.get('url')) else ''


def clip_counts(items):
    """Reakcje na każdą spinkę (połączenie kolejnych boksów) - kwadraty w wierszu listy."""
    from news.thread_social_models import ThreadStepReaction
    ids = [item.pk for item in items[1:]]
    out = {pk: {'positive': 0, 'doubt': 0, 'negative': 0} for pk in ids}
    for row in ThreadStepReaction.objects.filter(item_id__in=ids, part='context').values('item_id', 'polarity').annotate(n=Count('id')):
        out[row['item_id']][row['polarity']] = row['n']
    return [out[pk] for pk in ids]


def box_counts(items):
    """Reakcje na każdy boks - kolor kwadratów w miniaturze spinki na liście (właściciel 3.10)."""
    from news.thread_social_models import ThreadStepReaction
    ids = [item.pk for item in items]
    out = {pk: {'positive': 0, 'doubt': 0, 'negative': 0} for pk in ids}
    for row in ThreadStepReaction.objects.filter(item_id__in=ids, part='box').values('item_id', 'polarity').annotate(n=Count('id')):
        out[row['item_id']][row['polarity']] = row['n']
    return [out[pk] for pk in ids]


def top_comments(thread, limit=2):
    from news.thread_social_models import ThreadComment
    rows = (ThreadComment.objects.filter(thread=thread, deleted_at__isnull=True, hidden_at__isnull=True)
            .select_related('author').annotate(liked=Count('reactions', filter=Q(reactions__polarity='positive')))
            .order_by('-liked', '-created_at')[:limit])
    from news.x_accounts import public_identity
    return [{'id': row.pk, 'author': f'@{row.author.username}' if row.author_id else 'Czytelnik', 'body': row.body[:220],
             'author_color': public_identity(row.author)['color'] if row.author_id else '', 'created_at': row.created_at} for row in rows]


def _scores(thread_ids):
    from news.thread_steps import score_of
    return score_of(thread_ids)


def thread_summary(thread, counts):
    from news.x_accounts import public_identity
    ai = bool(thread.diagnosis_id or thread.narrative_message_id or thread.signal_kind)
    identity = public_identity(thread.owner)
    items = [item for item in thread.items.all() if not (item.link_id and item.link.hidden_at)]
    return {'id': thread.pk, 'title': thread.title, 'description': thread.description, 'topics': thread.topics,
            # rodzaj spinki w linii meta nagłówka (właściciel 6.10)
            'kind': thread.kind, 'kind_label': dict(thread.KINDS).get(thread.kind, ''),
            'author': 'Dr. Spin (AI)' if ai else thread.owner.username,
            'display_name': 'Dr. Spin (AI)' if ai else identity['display_name'], 'x_profile': identity['x_profile'],
            # kolor autora do rozjaśnienia wiersza z lewej (właściciel 6.10): Dr. Spin zawsze niebieski, czytelnik - kolor nicka
            'author_color': '' if ai else identity['color'],
            'is_ai': ai, 'diagnosis_id': thread.diagnosis_id,
            'narrative': bool(thread.narrative_message_id),
            'signal_kind': thread.signal_kind,
            'confidence': thread.signal_data.get('confidence'),
            'continues': thread.continues_id if thread.continues_id and public_threads().filter(pk=thread.continues_id).exists() else None,
            'continuations': list(public_threads().filter(continues=thread).values_list('pk', flat=True)),
            'repin_of': thread.repin_of_id if thread.repin_of_id and public_threads().filter(pk=thread.repin_of_id).exists() else None,
            'repins': list(public_threads().filter(repin_of=thread).values_list('pk', flat=True)[:50]),
            'author_id': thread.owner_id, 'published_at': thread.published_at, 'updated_at': thread.updated_at,
            'items_count': len(items), 'preview': [item_data(item) for item in items],
            'comments_count': getattr(thread, 'visible_comments_count', 0),
            'opinions': counts.get(thread.pk, {'positive': 0, 'doubt': 0, 'negative': 0}),
            'score': _scores([thread.pk]).get(thread.pk, {'percent': 0, 'reactions': 0}),
            # dane do wiersza na liście (właściciel 3.10): powiązania, źródła, dwa najlepsze komentarze
            'contexts_count': sum(1 for item in items if item.position and item.link_note),
            'sources_count': len({source_key(item) for item in items} - {''}),
            'top_comments': top_comments(thread, 5),  # rotacja w okienku na liście (właściciel 5.10)
            'clips': clip_counts(items),
            'boxes': box_counts(items),
            'admission': admission_progress(thread) if thread.owner_id and not thread.admitted_at else None}


def admission_progress(thread):
    from news.admission import progress
    return progress(thread)


@extend_schema(summary='Publiczne spinki kontekstowe czytelników', tags=['nitki'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def community_threads(request):
    if not threads_enabled():
        return _disabled()
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        return Response({'detail': 'Nieprawidłowy numer strony.'}, status=400)
    rows = public_threads(request.user).select_related('owner').prefetch_related('items__article__source', 'items__link')
    if request.query_params.get('ai') == '1':
        rows = rows.filter(owner__isnull=True)
    if request.query_params.get('featured') == '1':
        selected = rows.filter(narrative_message__day=timezone.localdate()).order_by('-narrative_score', '-pk').first()
        selected = selected or rows.filter(diagnosis__isnull=False).order_by('-published_at', '-pk').first()
        return Response({'results': [thread_summary(selected, _counts([selected.pk]))] if selected else [], 'next_page': None})
    # Źródło listy: Wszystkie (Dr. Spin + przyjęte tropy czytelników), Dr. Spin, Czytelnicy (przyjęci), Izba przyjęć.
    source = request.query_params.get('source', '')
    if source:
        if source not in ('all', 'drspin', 'readers', 'izba'):
            return Response({'detail': 'Nieznane źródło.'}, status=400)
        from news.admission import WINDOW
        if source == 'all':
            rows = rows.filter(Q(owner__isnull=True) | Q(admitted_at__isnull=False))
        elif source == 'drspin':
            rows = rows.filter(owner__isnull=True)
        elif source == 'readers':
            rows = rows.filter(owner__isnull=False, admitted_at__isnull=False)
        else:
            rows = rows.filter(owner__isnull=False, admitted_at__isnull=True, published_at__gte=timezone.now() - WINDOW)
    query = request.query_params.get('q', '').strip()
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(description__icontains=query))
    author = request.query_params.get('author', '').strip()
    if author:
        rows = rows.filter(owner__username=author)
    topic = request.query_params.get('topic', '').strip()
    if topic:
        from news.topics import TOPICS
        if topic not in TOPICS:
            return Response({'detail': 'Nieznany temat.'}, status=400)
        # Indexed JSON lookups work on both SQLite (tests) and PostgreSQL.
        topic_filter = Q()
        for index in range(len(TOPICS)):
            topic_filter |= Q(**{f'topics__{index}': topic})
        rows = rows.filter(topic_filter)
    context_filtered = False
    for key in ('article_id', 'figure_id'):
        value = request.query_params.get(key)
        if value is not None:
            if not value.isdigit() or int(value) < 1:
                return Response({'detail': 'Nieprawidłowy identyfikator.'}, status=400)
            context_filtered = True
            if key == 'article_id':
                rows = rows.filter(items__article_id=int(value))
            else:
                from news.political_models import PublicFigureArticleReference
                articles = PublicFigureArticleReference.objects.filter(
                    public_figure_id=int(value), verification_status='confirmed').values('article_id')
                rows = rows.filter(items__article_id__in=articles)
    url = request.query_params.get('url')
    if url:
        try:
            canonical = canonical_url(url)
        except ValueError:
            return Response({'detail': 'Nieprawidłowy adres.'}, status=400)
        context_filtered = True
        base = find_article(url, canonical)
        match = Q(items__link__canonical_url=canonical, items__link__hidden_at__isnull=True)
        if base:
            match |= Q(items__article_id=base.pk)
        rows = rows.filter(match)
    sort = request.query_params.get('sort', 'best')
    if sort not in ('new', 'best', 'hot', 'comments'):
        return Response({'detail': 'Nieznana kolejność.'}, status=400)
    if sort == 'best':
        rows = rows.annotate(positive_count=Count('opinions', filter=Q(opinions__polarity='positive'), distinct=True))
        rows = rows.order_by('-positive_count', '-published_at', '-pk')
    elif sort == 'hot':
        now = timezone.now()
        rows = rows.annotate(recent_reactions=Count('opinions', distinct=True,
            filter=Q(opinions__created_at__gte=now - timedelta(days=7), opinions__created_at__lte=now)))
        rows = rows.order_by('-recent_reactions', '-published_at', '-pk')
    elif sort == 'comments':
        rows = rows.annotate(last_comment=Max('comments__created_at', filter=Q(comments__deleted_at__isnull=True, comments__hidden_at__isnull=True)))
        rows = rows.order_by(F('last_comment').desc(nulls_last=True), '-published_at', '-pk')
    else:
        rows = rows.order_by('-published_at', '-pk')
    size = 20
    batch = list(rows.distinct()[(page - 1) * size:page * size + 1])
    counts = _counts([row.pk for row in batch])
    return Response({'results': [thread_summary(row, counts) for row in batch[:size]],
                     'next_page': page + 1 if len(batch) > size else None, 'context_filtered': context_filtered}, headers={'Cache-Control': 'private, no-store'})


@extend_schema(summary='Publiczna spinka czytelnika', tags=['nitki'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def community_thread_detail(request, thread_id):
    if not threads_enabled():
        return _disabled()
    thread = get_object_or_404(public_threads(request.user).select_related('owner'), pk=thread_id)
    items = [item for item in thread.items.select_related('article__source', 'link') if not (item.link_id and item.link.hidden_at)]
    data = thread_summary(thread, _counts([thread.pk]))
    data.update({'items': [item_data(item) for item in items], 'preview': None,
                 'is_owner': request.user.is_authenticated and request.user.pk == thread.owner_id})
    return Response(data, headers={'Cache-Control': 'private, no-store'})
