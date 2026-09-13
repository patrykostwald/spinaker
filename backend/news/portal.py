"""Public news feeds and explainable topic links from stored source records.

Genre counts are exact for the lexical match, not an assertion of causation,
truth, popularity, or archive completeness. No provider call is made here.
"""
from collections import OrderedDict
from datetime import datetime, time, timedelta
from hashlib import sha256
import re
import json
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connection
from django.db.models import Q, Count, Prefetch, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from news.models import Article, ArticleCategory, Source, Thread, ThreadItem
from news.serializers import ArticleSerializer, SourceSerializer, ThreadSerializer

from news.topics import TOPICS, topic_choices, topic_clause

WARSAW = ZoneInfo('Europe/Warsaw')
# This is an editable editorial selection, not a measured audience ranking.
TOP_TEN = ('Onet Wiadomości', 'Wirtualna Polska', 'Interia', 'TVN24',
           'Polsat News', 'RMF24', 'Radio ZET', 'TVP Info', 'Gazeta.pl', 'Rzeczpospolita')
STOP = set('a aby ale albo ani aż bez będzie będą być był była było byli być co czy dla do i ich jego jej jest jeszcze już jak jako kiedy które który która którzy ma mają miał między mimo może można mu na nad nam nas nie nowa nowe nowy nowego nowym nową oraz od o on ona oni po pod przez przy przed się są tak także tam tego tej ten te to tym tu tę u w we więc więcej wszystko wszystkie wy z za ze że tylko dziś dzisiaj sprawie sprawa sprawy mówi powiedział powiedziała polska polski polskie polsce kraju kraj świat świata wiadomości polityka aktualności news informacja informacje'.split())


def visible_articles():
    return Article.objects.filter(source__is_active=True).exclude(source__catalog_stage='excluded').exclude(
        category='tweet').exclude(source__source_type__in=('twitter', 'politician'))


def hydrated(qs):
    return qs.select_related('source', 'voting', 'official_record', 'content').prefetch_related('evidence_links')


def top_sources():
    rows = {source.name: source for source in Source.objects.filter(name__in=TOP_TEN,
        is_active=True).exclude(catalog_stage='excluded')}
    return [rows[name] for name in TOP_TEN if name in rows]


def _integer(value, label, default, maximum):
    if value is None:
        return default
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise ValidationError({label: 'Podaj poprawną liczbę.'})
    if not 1 <= number <= maximum:
        raise ValidationError({label: f'Dozwolony zakres: 1–{maximum}.'})
    return number


def _filters(request, qs):
    topics = list(dict.fromkeys(filter(None, request.query_params.get('topics', '').split(','))))
    if set(topics) - set(TOPICS):
        raise ValidationError({'topics': 'Nieznany temat.'})
    if topics:
        qs = qs.filter(topic_clause(topics))
    categories = list(dict.fromkeys(filter(None, request.query_params.get('categories', '').split(','))))
    if set(categories) - set(ArticleCategory.values):
        raise ValidationError({'categories': 'Nieznana kategoria.'})
    if categories:
        qs = qs.filter(category__in=categories)
    raw_sources = request.query_params.get('sources', '')
    if raw_sources:
        parts = raw_sources.split(',')
        if len(parts) > 100 or any(not part.isdigit() for part in parts):
            raise ValidationError({'sources': 'Nieprawidłowy wybór źródeł.'})
        qs = qs.filter(source_id__in=[int(part) for part in parts])
    query = request.query_params.get('q', '').strip()
    if len(query) > 200:
        raise ValidationError({'q': 'Maksymalnie 200 znaków.'})
    match = request.query_params.get('match', 'substring')
    if match not in ('substring', 'words'):
        raise ValidationError({'match': 'Nieznany sposób dopasowania.'})
    for word in query.split()[:20]:
        if match == 'words':
            qs = qs.filter(Q(title__iregex=r'(?<!\w)' + re.escape(word) + r'(?!\w)') | _tag_clause(word, whole_word=True))
        else:
            qs = qs.filter(_text_clause('title', word) | _tag_clause(word))
    return qs


@api_view(['GET'])
def feed(request):
    mode = request.query_params.get('mode', 'latest')
    if mode not in ('latest', 'top'):
        raise ValidationError({'mode': 'Nieznany rodzaj paska.'})
    page = _integer(request.query_params.get('page'), 'page', 1, 100000)
    size = _integer(request.query_params.get('page_size'), 'page_size', 20, 40)
    now = timezone.now()
    sources = top_sources()
    qs = visible_articles().filter(Q(published_date__lte=now) | Q(published_date__isnull=True))
    if mode == 'top':
        day = now.astimezone(WARSAW).date()
        start = datetime.combine(day, time.min, tzinfo=WARSAW)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=WARSAW)
        qs = qs.filter(source_id__in=[source.pk for source in sources],
                       published_date__gte=start, published_date__lt=end)
    qs = _filters(request, qs)
    # Null publication dates stay last; import time never impersonates publication.
    qs = qs.order_by(F('published_date').desc(nulls_last=True), '-pk')
    total = qs.count()
    rows = list(hydrated(qs)[(page - 1) * size:page * size])
    payload = {'mode': mode, 'results': ArticleSerializer(rows, many=True).data,
        'total': total, 'next_page': page + 1 if page * size < total else None,
        'checked_at': now.isoformat(), 'latest_published_at': rows[0].published_date.isoformat()
            if rows and rows[0].published_date else None,
        'top_sources': SourceSerializer(sources, many=True).data,
        'selection_note': 'Dzisiejsze materiały z redakcyjnego wyboru dziesięciu źródeł; kolejność według daty publikacji.'
            if mode == 'top' else 'Materiały dostępne w bazie, od najnowszej znanej daty publikacji. Braki danych pozostają jawne.'}
    return Response(payload)


@api_view(['GET'])
def portal_config(request):
    visible = ThreadItem.objects.select_related('thread__created_by', 'article__source',
        'article__voting', 'article__official_record', 'article__content').prefetch_related(
        'article__evidence_links').order_by('position', 'id')
    editions = Thread.objects.filter(published=True, editorial_slot__in=('government', 'opposition')).prefetch_related(
        Prefetch('thread_items', queryset=visible, to_attr='visible_items')).order_by('-updated_at', '-pk')
    slots = {'government': None, 'opposition': None}
    for slot in slots:
        thread = editions.filter(editorial_slot=slot).first()
        if thread is not None:
            slots[slot] = ThreadSerializer(thread).data
    from news.political_polling import configuration, PoliticalReadError
    try:
        configured = bool(configuration())
    except PoliticalReadError:
        configured = False
    return Response({'categories': [{'value': value, 'label': label} for value, label in ArticleCategory.choices
        if value not in ('tweet', 'context')], 'top_sources': SourceSerializer(top_sources(), many=True).data,
        'topics': topic_choices(), 'sources': SourceSerializer(Source.objects.filter(is_active=True).exclude(catalog_stage='excluded').order_by('name', 'pk'), many=True).data,
        'editorial': slots, 'x_editorial': {'configured': configured,
            'status': 'configured' if configured else 'not_configured'}})


def _terms(article):
    declared = [tag.strip() for tag in article.tags if isinstance(tag, str)
                and 3 <= len(tag.strip()) <= 80 and tag.casefold().strip() not in STOP]
    words = [word.casefold() for word in re.findall(r'[^\W\d_]+', article.title, re.UNICODE)
        if len(word) >= 4 and word.casefold() not in STOP]
    # Keep source keywords intact; no invented aliases, entities, dates or claims.
    terms = list(dict.fromkeys(declared[:4] + words))
    return terms[:8]


def _tag_clause(term, whole_word=False):
    if whole_word or connection.vendor == 'sqlite' and not term.isascii():
        # SQLite LIKE does not case-fold Polish letters. Match each Unicode
        # character in literal or JSON-escaped form without decoding 12 indices
        # per row. Escaping makes user input data, never regex instructions.
        pattern = ''.join('(?:' + '|'.join(re.escape(value) for value in sorted({
            variant for char in {letter, letter.lower(), letter.upper()}
            for variant in (char, json.dumps(char, ensure_ascii=True)[1:-1])})) + ')'
            for letter in term)
        if whole_word:
            pattern = r'(?<!\w)' + pattern + r'(?!\w)'
        return Q(tags__iregex=pattern)
    # SQLite stores Django JSON using escaped Unicode; PostgreSQL may expose
    # literal Unicode. Match both serializations without modifying source tags.
    escaped = json.dumps(term, ensure_ascii=True)[1:-1]
    clause = Q(tags__icontains=term)
    if escaped != term:
        clause |= Q(tags__icontains=escaped)
    return clause


def _text_clause(field, term):
    lookup = 'iregex' if connection.vendor == 'sqlite' and not term.isascii() else 'icontains'
    return Q(**{field + '__' + lookup: re.escape(term) if lookup == 'iregex' else term})


def _term_clause(term):
    return _text_clause('title', term) | _tag_clause(term) | _text_clause('evidence_links__phrase', term)


def context_summary(article):
    generation = cache.get('search-generation', 1)
    key = 'article-context:v2:' + sha256(f'{article.pk}:{article.updated_at.isoformat()}:{generation}'.encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    base = visible_articles().exclude(pk=article.pk)
    frequencies = []
    terms = _terms(article)
    # One shared scan/join instead of up to eight full-archive count queries.
    # DISTINCT remains necessary when one record has several evidence links.
    totals = base.aggregate(**{f'term_{index}': Count('pk', filter=_term_clause(term), distinct=True)
                              for index, term in enumerate(terms)}) if terms else {}
    for index, term in enumerate(terms):
        number = totals[f'term_{index}']
        if number:
            frequencies.append((number, term))
    # Rare useful terms reduce matches caused only by generic headline vocabulary.
    frequencies.sort(key=lambda pair: (pair[0], -len(pair[1])))
    keywords = [term for _, term in frequencies[:3]]
    clause = Q(pk__in=[])
    for term in keywords:
        clause |= _term_clause(term)
    matched = base.filter(clause).distinct()
    grouped = list(matched.order_by().values('category').annotate(count=Count('pk', distinct=True)))
    labels = dict(ArticleCategory.choices)
    counts = [{'category': item['category'], 'label': labels.get(item['category'], item['category']),
               'count': item['count']} for item in grouped]
    result = {'keywords': keywords, 'query': ' · '.join(keywords),
        'counts': counts, 'total': sum(item['count'] for item in counts),
        'match_basis': 'Wspólne hasła w tytułach, tagach wydawców lub udokumentowanych powiązaniach. To dopasowanie tematyczne, nie potwierdzenie związku przyczynowego.',
        'checked_at': timezone.now().isoformat(), 'complete': False}
    cache.set(key, result, 30)
    return result


@api_view(['GET'])
def article_context(request, article_id):
    article = get_object_or_404(visible_articles(), pk=article_id)
    page = _integer(request.query_params.get('page'), 'page', 1, 100000)
    summary = context_summary(article)
    clause = Q(pk__in=[])
    for term in summary['keywords']:
        clause |= _term_clause(term)
    matched = visible_articles().exclude(pk=article.pk).filter(clause).distinct().order_by(F('published_date').desc(nulls_last=True), '-pk')
    rows = list(hydrated(matched)[(page - 1) * 30:page * 30])
    timeline = OrderedDict()
    for row, data in zip(rows, ArticleSerializer(rows, many=True).data):
        date = row.published_date.astimezone(WARSAW).date().isoformat() if row.published_date else 'unknown'
        timeline.setdefault(date, []).append(data)
    return Response({**summary, 'timeline': timeline,
        'next_page': page + 1 if page * 30 < summary['total'] else None})


@api_view(['GET'])
def context_counts(request):
    raw = request.query_params.get('ids', '').split(',')
    if not raw or len(raw) > 4 or any(not value.isdigit() for value in raw):
        raise ValidationError({'ids': 'Podaj od 1 do 4 identyfikatorów.'})
    results = {}
    for article in visible_articles().filter(pk__in=[int(value) for value in raw]):
        data = context_summary(article)
        results[str(article.pk)] = {'total': data['total'], 'categories': data['counts'],
                                  'checked_at': data['checked_at'], 'complete': False}
    return Response({'counts': results})
