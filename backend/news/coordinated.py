"""Wspólny przekaz (plan Architekta 6.10, spin.clinic): prawie identyczne zdania we wpisach polityków na X.

Metoda (bez AI, bez nowych pakietów, ta sama dla każdego obozu i partii):
- tekst wpisu sprowadzamy do małych liter bez linków, oznaczeń @, znaków # i interpunkcji;
- porównujemy zbiory kolejnych pięciu słów (5-gramy); podobieństwo Jaccarda co najmniej 0,8 łączy dwa wpisy,
  jeśli dzieli je najwyżej 6 godzin;
- połączone wpisy tworzą klaster; pokazujemy go, gdy w jednym 6-godzinnym oknie napisały go co najmniej 3 różne konta;
- podania dalej (RT) i wpisy krótsze niż 8 słów pomijamy; usunięte wpisy znikają z klastra razem z treścią.
Wspólny przekaz to obserwacja, nie dowód zmowy: zdarza się przy komunikatach partii, apelach i cytatach.
"""
import re
from collections import defaultdict
from datetime import timedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

NGRAM = 5
MIN_TOKENS = 8
SIMILARITY = 0.8
WINDOW = timedelta(hours=6)
MIN_ACCOUNTS = 3
MAX_POSTING = 300  # 5-gram obecny w tylu wpisach to formułka (np. stopka), nie przekaz
LOOKBACK_HOURS = 48
NIGHT_LOOKBACK_HOURS = 7 * 24
PHRASE_CHARS = 280

METHOD = ('Szukamy wpisów polityków na X, które mają co najmniej 80% wspólnych pięciowyrazowych fragmentów i powstały '
          'w ciągu 6 godzin. Pokazujemy je, gdy napisały je co najmniej 3 różne konta. Te same progi dla wszystkich obozów. '
          'Wspólny przekaz to obserwacja, nie dowód zmowy.')
THRESHOLDS = {'similarity': SIMILARITY, 'window_hours': int(WINDOW.total_seconds() // 3600), 'min_accounts': MIN_ACCOUNTS,
              'ngram': NGRAM, 'min_tokens': MIN_TOKENS}

_URL = re.compile(r'https?://\S+|www\.\S+')
_MENTION = re.compile(r'(^|\s)@\w+')
_NON_WORD = re.compile(r'[^\w\s]|_', re.UNICODE)


def normalize(text):
    text = _URL.sub(' ', text or '')
    text = _MENTION.sub(' ', text)
    text = text.replace('#', ' ').lower()
    text = _NON_WORD.sub(' ', text)
    return text.split()


def shingles(tokens, n=NGRAM):
    if len(tokens) < max(n, MIN_TOKENS):
        return frozenset()
    return frozenset(' '.join(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_repost(text):
    return (text or '').lstrip().startswith('RT @')


def _max_accounts_in_window(items):
    """items: [(czas, konto)] → największa liczba różnych kont w jednym oknie WINDOW."""
    items = sorted(items)
    best, start = 0, 0
    counts = defaultdict(int)
    for end, (at, account) in enumerate(items):
        counts[account] += 1
        while at - items[start][0] > WINDOW:
            old = items[start][1]
            counts[old] -= 1
            if not counts[old]:
                del counts[old]
            start += 1
        best = max(best, len(counts))
    return best


def find_clusters(posts):
    """posts: [{'id', 'account', 'at' (datetime), 'text'}] → [{'ids': [...], 'similarity': najniższa krawędź}].
    Czysta funkcja: wynik zależy tylko od tekstu, czasu i liczby kont, nigdy od obozu czy partii."""
    rows = []
    for post in posts:
        if is_repost(post['text']):
            continue
        sh = shingles(normalize(post['text']))
        if sh:
            rows.append((post, sh))
    index = defaultdict(list)
    for i, (_, sh) in enumerate(rows):
        for gram in sh:
            index[gram].append(i)
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edge_sim = {}
    for i, (post, sh) in enumerate(rows):
        candidates = set()
        for gram in sh:
            posting = index[gram]
            if len(posting) <= MAX_POSTING:
                candidates.update(j for j in posting if j > i)
        for j in candidates:
            other, osh = rows[j]
            if abs(other['at'] - post['at']) > WINDOW:
                continue
            sim = jaccard(sh, osh)
            if sim >= SIMILARITY:
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
                edge_sim[(i, j)] = sim
    groups = defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)
    clusters = []
    for members in groups.values():
        if len(members) < MIN_ACCOUNTS:
            continue
        if _max_accounts_in_window([(rows[i][0]['at'], rows[i][0]['account']) for i in members]) < MIN_ACCOUNTS:
            continue
        member_set = set(members)
        sims = [s for (i, j), s in edge_sim.items() if i in member_set and j in member_set]
        clusters.append({'ids': [rows[i][0]['id'] for i in sorted(members, key=lambda k: (rows[k][0]['at'], str(rows[k][0]['id'])))],
                         'similarity': round(min(sims), 3) if sims else 1.0})
    clusters.sort(key=lambda c: c['ids'][0])
    return clusters


CAMP_LABELS = {'government': 'rządzący', 'opposition': 'opozycja', 'public': 'instytucja'}


def describe(posts):
    """Podsumowanie klastra z dostępnych wpisów: konta, partie, obozy, czas. Partia tylko z potwierdzonego dowodu konta."""
    from news.clinic import figures_by_account, party_data
    posts = sorted((p for p in posts if p.available), key=lambda p: (p.published_at, p.pk))
    figures = figures_by_account({p.account_id for p in posts})
    accounts = {}
    for p in posts:
        if p.account_id in accounts:
            continue
        figure = figures.get(p.account_id)
        party = party_data(figure) if figure else None
        accounts[p.account_id] = {'handle': p.account.handle, 'name': figure.canonical_name if figure else p.account.display_name,
                                  'party': party['short'] if party else None, 'camp': p.camp_at_collection}
    parties = sorted({a['party'] for a in accounts.values() if a['party']})
    camps = sorted({a['camp'] for a in accounts.values() if a['camp']})
    return {
        'posts': posts, 'accounts': list(accounts.values()), 'parties': parties, 'camps': camps,
        'accounts_count': len(accounts), 'posts_count': len(posts),
        'cross_party': len(parties) >= 2, 'cross_camp': len({c for c in camps if c in ('government', 'opposition')}) >= 2,
        'first_at': posts[0].published_at if posts else None, 'last_at': posts[-1].published_at if posts else None,
        'phrase': (posts[0].text or '')[:PHRASE_CHARS] if posts else '',
    }


def refresh(hours=LOOKBACK_HOURS, now=None):
    """Szuka klastrów we wpisach z ostatnich `hours` godzin i zapisuje je (klaster, który już był, rośnie zamiast się dublować)."""
    from django.db import transaction
    from django.utils import timezone
    from news.analysis_models import CoordinatedCluster
    from news.political_models import PoliticalPost
    now = now or timezone.now()
    qs = (PoliticalPost.objects.filter(available=True, published_at__gte=now - timedelta(hours=hours), published_at__lte=now)
          .values('pk', 'account_id', 'published_at', 'text'))
    found = find_clusters([{'id': r['pk'], 'account': r['account_id'], 'at': r['published_at'], 'text': r['text']} for r in qs])
    created = updated = 0
    for cluster in found:
        with transaction.atomic():
            existing = list(CoordinatedCluster.objects.filter(posts__in=cluster['ids']).distinct().order_by('pk'))
            ids = set(cluster['ids'])
            for old in existing:
                ids.update(old.posts.values_list('pk', flat=True))
            info = describe(PoliticalPost.objects.filter(pk__in=ids).select_related('account'))
            if info['accounts_count'] < MIN_ACCOUNTS:
                continue
            fields = {k: info[k] for k in ('phrase', 'first_at', 'last_at', 'accounts_count', 'posts_count', 'accounts', 'parties',
                                           'camps', 'cross_party', 'cross_camp')}
            fields['similarity'] = min([cluster['similarity'], *(o.similarity for o in existing if o.similarity)])
            if existing:
                target = existing[0]
                for key, value in fields.items():
                    setattr(target, key, value)
                target.save()
                for extra in existing[1:]:
                    extra.delete()
                updated += 1
            else:
                target = CoordinatedCluster.objects.create(**fields)
                created += 1
            target.posts.set(list(ids))
    return {'status': 'ok', 'clusters': len(found), 'created': created, 'updated': updated, 'hours': hours}


def payload(cluster):
    info = describe(cluster.posts.select_related('account'))
    if info['accounts_count'] < MIN_ACCOUNTS:
        return None  # po usunięciu wpisów zostało za mało kont
    span = info['last_at'] - info['first_at']
    return {
        'id': cluster.pk, 'phrase': info['phrase'], 'accounts_count': info['accounts_count'], 'posts_count': info['posts_count'],
        'parties': info['parties'], 'camps': [CAMP_LABELS.get(c, c) for c in info['camps']],
        'cross_party': info['cross_party'], 'cross_camp': info['cross_camp'],
        'first_at': info['first_at'].isoformat(), 'last_at': info['last_at'].isoformat(), 'span_minutes': int(span.total_seconds() // 60),
        'similarity': cluster.similarity,
        'accounts': [{**a, 'camp': CAMP_LABELS.get(a['camp'], a['camp'])} for a in info['accounts']],
        'posts': [{'url': p.url, 'handle': p.account.handle, 'published_at': p.published_at.isoformat()} for p in info['posts']],
    }


def public():
    """Strona publiczna dopiero po sprawdzeniu wyników na prawdziwych danych (właściciel 6.10); liczenie działa zawsze."""
    import os
    return os.environ.get('WSPOLNY_PRZEKAZ_PUBLIC', '').strip().lower() in ('1', 'true', 'yes')


@api_view(['GET'])
@permission_classes([AllowAny])
def clusters_view(request):
    """GET /api/clinic/wspolny-przekaz/?limit=30 - klastry od najnowszego, wszystkie obozy na jednej liście.
    Przy WSPOLNY_PRZEKAZ_PUBLIC=false tylko podgląd dla redakcji (staff); dla pozostałych 404."""
    from news.analysis_models import CoordinatedCluster
    staff = bool(getattr(request.user, 'is_staff', False))
    if not public() and not staff:
        return Response({'detail': 'Nie znaleziono.'}, status=404)
    try:
        limit = max(1, min(int(request.query_params.get('limit', 30)), 100))
    except ValueError:
        return Response({'detail': 'limit to liczba.'}, status=400)
    results = []
    for cluster in CoordinatedCluster.objects.order_by('-first_at', '-pk')[:limit * 2]:
        row = payload(cluster)
        if row:
            results.append(row)
        if len(results) >= limit:
            break
    return Response({'method': METHOD, 'thresholds': THRESHOLDS, 'public': public(), 'results': results})
