"""przeszłość.today v3 (docs/SPINA_V3_API.md): ogólna lista głosowań Sejmu i graf powiązań osoby.

Tylko dane, które już mamy (ParliamentaryVoting, Ballot, denominators profilu); zakres jawnie w polu `coverage`.
Flagi (domyślnie wyłączone): PRZESZLOSC_VOTES_LIST_ENABLED, PRZESZLOSC_NETWORK_ENABLED; obie wymagają też PRZESZLOSC_ENABLED.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from django.conf import settings
from django.db.models import Count, F, Max, Min, Q
from django.views.decorators.gzip import gzip_page
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

PER_PAGE, PAGE_MAX = 20, 50
OUTCOMES = ('przyjete', 'odrzucone', 'nieustalone')
COVERAGE_TTL = 3600
DISABLED = {'detail': 'Funkcja jeszcze wyłączona.'}
COVERAGE_NOTE = 'Głosowania imienne Sejmu zaimportowane do naszej bazy z API Sejmu. To nie jest pełne archiwum.'
NETWORK_NOTE = 'Współwystępowanie to wskazówka do sprawdzenia, nie dowód współpracy. Każda pozycja prowadzi do źródła.'


def _on(flag) -> bool:
    from news.przeszlosc import enabled
    from news.v3_flags import flag as site_flag
    return enabled() and site_flag(flag)


def _server_cache() -> bool:
    from news.przeszlosc_cache import active
    return active()


def outcome(counts) -> str:
    """przyjete / odrzucone z liczby głosów za i wymaganej większości z API Sejmu; bez danych - nieustalone (nie zgadujemy)."""
    counts = counts or {}
    yes, needed = counts.get('yes'), counts.get('majorityVotes')
    if isinstance(yes, int) and isinstance(needed, int) and needed > 0:
        return 'przyjete' if yes >= needed else 'odrzucone'
    return 'nieustalone'


def coverage() -> dict:
    from django.core.cache import cache
    from news.models import ParliamentaryVoting
    key = 'przeszlosc:v3:glosowania:coverage'
    data = cache.get(key) if _server_cache() else None
    if data is None:
        terms = []
        for row in (ParliamentaryVoting.objects.values('term')
                    .annotate(n=Count('id'), first=Min('article__published_date'), last=Max('article__published_date'))
                    .order_by('-term')):
            terms.append({'term': row['term'], 'votings': row['n'],
                          'first': row['first'].date().isoformat() if row['first'] else None,
                          'last': row['last'].date().isoformat() if row['last'] else None})
        data = {'scope': 'imported', 'complete': False, 'description': COVERAGE_NOTE,
                'total_votings': sum(t['votings'] for t in terms), 'terms': terms}
        if _server_cache():
            cache.set(key, data, COVERAGE_TTL)
    return data


def clubs(term=None) -> list[str]:
    from django.core.cache import cache
    from news.models import Ballot
    key = f'przeszlosc:v3:glosowania:kluby:{term or "all"}'
    data = cache.get(key) if _server_cache() else None
    if data is None:
        rows = Ballot.objects.exclude(club='')
        if term:
            rows = rows.filter(voting__term=term)
        sizes = Counter(dict(rows.values('club').annotate(n=Count('mp_id', distinct=True)).values_list('club', 'n')))
        data = [club for club, _ in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))]
        if _server_cache():
            cache.set(key, data, COVERAGE_TTL)
    return data


def _params(params):
    """Walidacja parametrów; ValueError z komunikatem dla 400."""
    def number(key, default=None):
        value = params.get(key)
        if value in (None, ''):
            return default
        if not str(value).isdigit():
            raise ValueError(f'Parametr {key} musi być liczbą.')
        return int(value)

    result = {'kadencja': number('kadencja'), 'strona': max(1, number('strona', 1)),
              'na_strone': max(1, min(PAGE_MAX, number('na_strone', PER_PAGE))),
              'klub': (params.get('klub') or '').strip()[:100] or None,
              'wynik': (params.get('wynik') or '').strip() or None, 'q': (params.get('q') or '').strip()[:120]}
    for key in ('od', 'do'):
        value = params.get(key) or None
        if value:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                raise ValueError('Daty w formacie YYYY-MM-DD.') from None
        result[key] = value
    if result['od'] and result['do'] and result['od'] > result['do']:
        raise ValueError('Data od nie może być późniejsza niż data do.')
    if result['wynik'] and result['wynik'] not in OUTCOMES:
        raise ValueError('Wynik: przyjete, odrzucone albo nieustalone.')
    if result['q'] and len(result['q']) < 3:
        raise ValueError('Szukaj: co najmniej 3 znaki.')
    return result


def outcome_q(value):
    """Filtr wyniku w zapytaniu (PostgreSQL i SQLite): liczby z JSON `counts` rzutowane na liczby całkowite."""
    if value == 'przyjete':
        return Q(v3_need__gt=0, v3_yes__isnull=False, v3_yes__gte=F('v3_need'))
    if value == 'odrzucone':
        return Q(v3_need__gt=0, v3_yes__isnull=False, v3_yes__lt=F('v3_need'))
    return Q(v3_need__isnull=True) | Q(v3_need__lte=0) | Q(v3_yes__isnull=True)


def votes_page(p: dict) -> dict:
    from django.db.models import IntegerField
    from django.db.models.fields.json import KeyTextTransform
    from django.db.models.functions import Cast
    from news.models import Ballot, ParliamentaryVoting
    from news.przeszlosc import VOTE_GROUP
    from news.przeszlosc_osoba import vote_url
    rows = ParliamentaryVoting.objects.all()
    if p['wynik']:
        rows = rows.annotate(v3_yes=Cast(KeyTextTransform('yes', 'counts'), IntegerField()),
                             v3_need=Cast(KeyTextTransform('majorityVotes', 'counts'), IntegerField()))
    if p['kadencja']:
        rows = rows.filter(term=p['kadencja'])
    if p['od']:
        rows = rows.filter(article__published_date__date__gte=p['od'])
    if p['do']:
        rows = rows.filter(article__published_date__date__lte=p['do'])
    if p['q']:
        rows = rows.filter(Q(article__title__icontains=p['q']) | Q(motion__icontains=p['q']))
    if p['klub']:
        rows = rows.filter(pk__in=Ballot.objects.filter(club=p['klub']).values('voting_id'))
    if p['wynik']:
        rows = rows.filter(outcome_q(p['wynik']))  # w bazie, ta sama reguła co outcome() (recenzja Codex 13.10)
    rows = rows.order_by(F('article__published_date').desc(nulls_last=True), '-term', '-sitting', '-number')
    total = rows.count()
    pages = max(1, -(-total // p['na_strone']))
    page = min(p['strona'], pages)
    start = (page - 1) * p['na_strone']
    batch = list(rows.select_related('article')[start:start + p['na_strone']])
    club_votes = {}
    if p['klub'] and batch:
        for voting_id, vote, n in (Ballot.objects.filter(voting__in=batch, club=p['klub'])
                                   .values_list('voting_id', 'vote').annotate(n=Count('id'))):
            label = VOTE_GROUP.get(vote, 'inne')
            club_votes.setdefault(voting_id, Counter())[label] += n
    results = []
    for v in batch:
        counts = v.counts or {}
        when = v.article.published_date
        item = {'id': f'{v.term}/{v.sitting}/{v.number}', 'term': v.term, 'sitting': v.sitting, 'number': v.number,
                'title': v.article.title[:300], 'motion': (v.motion or '')[:400],
                'date': when.date().isoformat() if when else None, 'kind': v.kind,
                'result': {k: counts.get(k) for k in ('yes', 'no', 'abstain', 'notParticipating') if k in counts},
                'majority': {'type': counts.get('majorityType'), 'votes': counts.get('majorityVotes')},
                'outcome': outcome(counts), 'url': vote_url(v)}
        if p['klub']:
            item['club_votes'] = {'club': p['klub'], 'votes': dict(club_votes.get(v.pk, {}))}
        results.append(item)
    return {'results': results, 'total': total, 'page': page, 'pages': pages, 'per_page': p['na_strone'],
            'filter': {key: p[key] for key in ('kadencja', 'klub', 'od', 'do', 'wynik', 'q')},
            'clubs': clubs(p['kadencja']), 'coverage': coverage()}


@api_view(['GET'])
@permission_classes([AllowAny])
def votes_list_view(request):
    """GET /api/przeszlosc/glosowania/?kadencja=10&klub=KO&od=&do=&wynik=przyjete&q=&strona=1&na_strone=20"""
    if not _on('PRZESZLOSC_VOTES_LIST_ENABLED'):
        return Response(DISABLED, status=404)
    try:
        params = _params(request.query_params)
    except ValueError as error:
        return Response({'detail': str(error)}, status=400)
    response = Response(votes_page(params))
    response['Cache-Control'] = 'public, max-age=300'
    return response


votes_list_view = gzip_page(votes_list_view)


def network(figure, denominators: dict) -> dict:
    """Graf osoby z `denominators` profilu (co_occurrence, shared_krs, vote_alignment): węzły osób i krawędzie z dowodami."""
    from news.przeszlosc_osoba import _person
    root = _person(figure)
    root_id = f'figure:{figure.pk}'
    nodes = {root_id: {'id': root_id, 'kind': 'osoba', 'label': root['name'], 'role': root['role'], 'root': True}}
    edges = []

    def node(person, club=None, term=None, mp_id=None):
        # Recenzja Fable (poprawka 10): węzeł tylko z identyfikatora (osoba z rejestru albo numer posła z Sejmu), nigdy z nazwiska.
        if person.get('id'):
            key = f"figure:{person['id']}"
        elif term and isinstance(mp_id, int):
            key = f'mp:{term}:{mp_id}'
        else:
            return None
        if key not in nodes:
            nodes[key] = {'id': key, 'kind': 'osoba', 'label': person.get('name'), 'role': person.get('role')}
            if person.get('slug'):
                nodes[key]['slug'] = person['slug']
        if club:
            nodes[key]['club'] = club
        return key

    denominators = denominators or {}
    profile = f"/przeszlosc/osoba/{root['slug']}"

    def edge(target, kind, weight, label, evidence, section, **extra):
        if target is None:
            return
        item = {'source': root_id, 'target': target, 'kind': kind, 'weight': weight, 'label': label, 'evidence': evidence or [],
                **extra}
        if not item['evidence']:  # każda krawędź prowadzi do źródła albo do sekcji profilu z pełną listą
            item['evidence_note'] = 'Źródła w sekcji profilu.'
            item['evidence_url'] = f'{profile}#{section}'
        edges.append(item)

    for p in denominators.get('people') or []:
        edge(node(p), 'wspolwystepowanie', p.get('score', 0), 'wspólne dokumenty, tematy lub przekazy', p.get('evidence'), 'mianowniki')
    for p in denominators.get('krs') or []:
        edge(node(p), 'krs', p.get('count', 0), 'te same podmioty w KRS', p.get('evidence'), 'krs')
    votes = denominators.get('votes') or {}
    seen = set()
    for group, suffix in (('aligned', ''), ('cross_club', ', spoza klubu')):
        for p in votes.get(group) or []:
            target = node(p, club=p.get('club'), term=votes.get('term'), mp_id=p.get('mp_id'))
            if target is None or target in seen:
                continue
            seen.add(target)
            shared = p.get('shared', 0)
            edge(target, 'glosowania', p.get('pct', 0),
                 f"zgodność głosów {p.get('pct', 0)}% w {shared} wspólnych głosowaniach (okno {votes.get('window', 0)}){suffix}",
                 p.get('evidence'), 'glosowania', shared=shared, window=votes.get('window', 0))
    return {'person': root, 'nodes': list(nodes.values()), 'edges': edges,
            'coverage': {'people': len(denominators.get('people') or []), 'krs': len(denominators.get('krs') or []),
                         'votes_window': votes.get('window', 0), 'votes_available': bool(votes.get('available'))},
            'note': denominators.get('note') or NETWORK_NOTE}


@api_view(['GET'])
@permission_classes([AllowAny])
def network_view(request, ident):
    """GET /api/przeszlosc/osoba/<id albo slug>/powiazania/ - graf z istniejących mianowników profilu (bramka Pro)."""
    if not _on('PRZESZLOSC_NETWORK_ENABLED'):
        return Response(DISABLED, status=404)
    from news.przeszlosc_cache import cached_person
    from news.przeszlosc_dostep import access, has, locked
    from news.przeszlosc_osoba import resolve
    figure = resolve(ident)
    if figure is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej w rejestrze.'}, status=404)
    if not has('denominators', request):
        return _per_user(locked('denominators'))
    data = network(figure, cached_person(figure).get('denominators'))
    return _per_user(Response({**data, 'access': access(request)}))


def _per_user(response):
    """Odpowiedź zależna od dostępu (bramka Pro): prywatny cache i Vary po sesji (recenzja Codex 13.10)."""
    from django.utils.cache import patch_vary_headers
    response['Cache-Control'] = 'private, max-age=300' if response.status_code == 200 else 'private, no-store'
    patch_vary_headers(response, ('Cookie', 'Authorization'))
    return response
