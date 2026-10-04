"""przeszłość.today, tydzień 1: drzewo powiązań tematu z danych, które już zbieramy (decyzja właściciela 5.10).

Tylko osoby publiczne i podmioty. Krawędzie wyłącznie z potwierdzonych źródeł: posłowie z oficjalnych danych Sejmu,
konta X przez sprawdzony dowód, KRS i artykuły po weryfikacji. Nic nie jest ustalane po samym nazwisku.
Ta sama miara: rządzący i opozycja przechodzą przez identyczne zapytania.
"""
import os
import re

from django.db.models import Q

PER_KIND = 30


def enabled():
    return os.environ.get('PRZESZLOSC_ENABLED', '').lower() == 'true'


def terms(query):
    """„CPK, lotnisko” → ['CPK', 'lotnisko']; pojedyncze słowa krótsze niż 3 znaki pomijamy."""
    return [t.strip() for t in re.split(r'[,;|]', query or '') if len(t.strip()) >= 3][:5]


def _match(fields, words):
    q = Q()
    for word in words:
        for field in fields:
            q |= Q(**{f'{field}__icontains': word})
    return q


def topic_graph(query):
    from news.clinic import figures_by_account, published_diagnoses
    from news.models import Article
    from news.political_models import (PoliticalPost, PublicFigure, PublicFigureArticleReference,
                                       PublicFigureOrganisationRelation)
    from news.public_records_models import PublicRecord

    words = terms(query)
    nodes, edges = {}, []
    if not words:
        return {'topic': query, 'terms': [], 'nodes': [], 'edges': [], 'counts': {}}

    def node(key, kind, label, **meta):
        nodes.setdefault(key, {'id': key, 'kind': kind, 'label': label[:160], **meta})
        return key

    def figure(f):
        return node(f'figure:{f.pk}', 'person', f.canonical_name, role=f.role_title, url=f.official_profile_url or f.evidence_url)

    # Sejm: druki, głosowania, konsultacje, lobbing - osoby tylko z oficjalnych identyfikatorów posłów
    records = (PublicRecord.objects.filter(_match(['title', 'text'], words))
               .order_by('-date', '-pk').prefetch_related('people__figure')[:PER_KIND])
    for record in records:
        key = node(f'record:{record.pk}', 'record', record.title or f'{record.kind} {record.external_id}',
                   date=record.date.isoformat() if record.date else None, url=record.source_url, sub=record.kind)
        for person in record.people.all():
            if person.figure_id and not person.figure.archived:
                edges.append({'source': figure(person.figure), 'target': key, 'label': 'w dokumencie'})

    # Wpisy polityków na X i diagnozy Dr. Spina
    posts = list(PoliticalPost.objects.filter(_match(['text'], words), available=True)
                 .select_related('account').order_by('-published_at')[:PER_KIND])
    people = figures_by_account({post.account_id for post in posts})
    diagnoses = {d.post_id: d for d in published_diagnoses().filter(post__in=posts)}
    for post in posts:
        key = node(f'post:{post.pk}', 'statement', post.text, date=post.published_at.date().isoformat(), url=post.url,
                   sub=post.account.display_name, camp=post.camp_at_collection)
        author = people.get(post.account_id)
        edges.append({'source': figure(author) if author else node(f'account:{post.account_id}', 'person', post.account.display_name),
                      'target': key, 'label': 'napisał(a)'})
        diagnosis = diagnoses.get(post.pk)
        if diagnosis:
            d = node(f'diagnosis:{diagnosis.pk}', 'diagnosis', diagnosis.headline, url=f'https://spin.clinic/klinika/{diagnosis.pk}',
                     date=post.published_at.date().isoformat(), intensity=diagnosis.intensity)
            edges.append({'source': key, 'target': d, 'label': 'diagnoza Dr. Spina'})

    # Media: artykuły z bazy; osoby tylko przez potwierdzone powiązanie
    articles = list(Article.objects.filter(_match(['title'], words)).select_related('source').order_by('-published_date')[:PER_KIND])
    for article in articles:
        node(f'article:{article.pk}', 'media', article.title, url=article.url, sub=article.source.name if article.source_id else '',
             date=article.published_date.date().isoformat() if article.published_date else None)
    for ref in (PublicFigureArticleReference.objects.filter(article__in=articles, verification_status='confirmed')
                .select_related('public_figure')):
        edges.append({'source': figure(ref.public_figure), 'target': f'article:{ref.article_id}', 'label': 'w artykule'})

    # KRS: spółki i fundacje osób, które pojawiły się w temacie (tylko zweryfikowane relacje)
    figure_ids = [int(k.split(':')[1]) for k in nodes if k.startswith('figure:')]
    relations = (PublicFigureOrganisationRelation.objects
                 .filter(public_figure_id__in=figure_ids, verification_status='confirmed', organisation__archived=False)
                 .select_related('organisation')[:PER_KIND * 2])
    for rel in relations:
        org = rel.organisation
        key = node(f'org:{org.pk}', 'organisation', org.name, url=org.official_register_url, sub=f'KRS {org.krs_number}')
        edges.append({'source': f'figure:{rel.public_figure_id}', 'target': key, 'label': rel.organ or rel.public_role})

    counts = {}
    for item in nodes.values():
        counts[item['kind']] = counts.get(item['kind'], 0) + 1
    # najpierw osoby z największą liczbą powiązań
    degree = {}
    for edge in edges:
        degree[edge['source']] = degree.get(edge['source'], 0) + 1
    for key, item in nodes.items():
        item['links'] = degree.get(key, 0) + sum(1 for e in edges if e['target'] == key)
    return {'topic': query, 'terms': words, 'nodes': sorted(nodes.values(), key=lambda n: (-n['links'], n.get('date') or '')),
            'edges': edges, 'counts': counts}


from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402


@api_view(['GET'])
@permission_classes([AllowAny])
def topic_view(request):
    """GET /api/przeszlosc/temat/?q=CPK - wyłączone, dopóki PRZESZLOSC_ENABLED nie jest true."""
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    query = request.query_params.get('q', '')[:120]
    if not terms(query):
        return Response({'detail': 'Podaj temat (co najmniej 3 znaki).'}, status=400)
    from django.core.cache import cache
    from django.db import connection
    key = 'przeszlosc:' + query.lower()
    data = cache.get(key) if connection.vendor == 'postgresql' else None
    if data is None:
        data = topic_graph(query)
        if connection.vendor == 'postgresql':
            cache.set(key, data, 600)
    return Response(data)
