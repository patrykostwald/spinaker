from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from rest_framework.test import APIClient

from news.coordinated import find_clusters, jaccard, normalize, refresh, shingles

T0 = datetime(2026, 10, 5, 8, tzinfo=dt_timezone.utc)
MESSAGE = 'Rząd podnosi podatki i zabiera Polakom pieniądze, a obiecywał zupełnie coś innego przed wyborami w zeszłym roku'
OTHER = 'Dziś w Sejmie rozmawialiśmy o ochronie zdrowia, szpitalach powiatowych i kolejkach do specjalistów w małych miastach'


def p(pid, account, text=MESSAGE, minutes=0):
    return {'id': pid, 'account': account, 'at': T0 + timedelta(minutes=minutes), 'text': text}


def test_normalize_and_shingles():
    assert normalize('RT? Zobacz: https://t.co/x @Jan #CPK, TAK!') == ['rt', 'zobacz', 'cpk', 'tak']
    assert shingles(normalize('za krótki wpis tylko siedem słów tu')) == frozenset()
    sh = shingles(normalize(MESSAGE))
    assert len(sh) == len(normalize(MESSAGE)) - 4
    assert jaccard(sh, sh) == 1.0 and jaccard(sh, frozenset()) == 0.0


def test_three_accounts_within_window_make_a_cluster():
    posts = [p(1, 'a', MESSAGE + ' https://t.co/1'), p(2, 'b', '@ktos ' + MESSAGE.upper(), 30), p(3, 'c', MESSAGE + '!!!', 300),
             p(4, 'd', OTHER, 10)]
    clusters = find_clusters(posts)
    assert [c['ids'] for c in clusters] == [[1, 2, 3]] and clusters[0]['similarity'] == 1.0


def test_two_accounts_or_same_account_repeated_is_not_enough():
    assert find_clusters([p(1, 'a'), p(2, 'b', minutes=5)]) == []
    assert find_clusters([p(1, 'a'), p(2, 'a', minutes=5), p(3, 'b', minutes=10)]) == []


def test_outside_window_and_reposts_and_low_similarity():
    assert find_clusters([p(1, 'a'), p(2, 'b', minutes=30), p(3, 'c', minutes=6 * 60 + 31)]) == []
    reposts = [p(1, 'a'), p(2, 'b', 'RT @a: ' + MESSAGE, 5), p(3, 'c', 'RT @a: ' + MESSAGE, 6)]
    assert find_clusters(reposts) == []
    half = ' '.join(MESSAGE.split()[:9]) + ' ' + ' '.join(OTHER.split()[:9])
    assert find_clusters([p(1, 'a'), p(2, 'b', minutes=1), p(3, 'c', half, 2)]) == []


def test_same_measure_independent_of_account_labels():
    """Wynik zależy tylko od tekstu, czasu i liczby kont: zamiana kont rządzących i opozycji nic nie zmienia."""
    gov = [p(1, 'gov1'), p(2, 'gov2', minutes=10), p(3, 'gov3', minutes=20)]
    opp = [p(11, 'opp1', OTHER, 0), p(12, 'opp2', OTHER, 10), p(13, 'opp3', OTHER, 20)]
    clusters = find_clusters(gov + opp)
    assert sorted(c['ids'] for c in clusters) == [[1, 2, 3], [11, 12, 13]]
    swapped = [dict(x, account=x['account'].replace('gov', 'tmp').replace('opp', 'gov').replace('tmp', 'opp')) for x in gov + opp]
    assert find_clusters(swapped) == clusters


@pytest.mark.django_db
def test_refresh_stores_cross_party_cluster_and_api(monkeypatch):
    from news.analysis_models import CoordinatedCluster
    from news.political_models import PoliticalAccount, PoliticalPost

    def post(n, camp, text=MESSAGE, minutes=0):
        account = PoliticalAccount.objects.get_or_create(user_id=str(100 + n), defaults={'handle': f'konto{n}', 'display_name': f'Konto {n}', 'camp': camp})[0]
        return PoliticalPost.objects.create(account=account, post_id=str(1000 + n + minutes), url=f'https://x.com/konto{n}/status/{1000 + n + minutes}',
                                            text=text, published_at=T0 + timedelta(minutes=minutes), camp_at_collection=camp)

    from types import SimpleNamespace
    parties = {'konto1': 'KO', 'konto2': 'PiS', 'konto3': 'PiS'}

    def figures(ids):
        accounts = PoliticalAccount.objects.filter(pk__in=ids, handle__in=parties)
        return {a.pk: SimpleNamespace(canonical_name=f'Osoba {a.handle}', party=parties[a.handle]) for a in accounts}

    monkeypatch.setattr('news.clinic.figures_by_account', figures)
    monkeypatch.setattr('news.clinic.party_data', lambda figure: {'short': figure.party})
    first = [post(1, 'government'), post(2, 'opposition', minutes=20), post(3, 'opposition', minutes=40)]
    post(4, 'government', OTHER, 5)
    now = T0 + timedelta(hours=1)
    assert refresh(now=now)['created'] == 1
    cluster = CoordinatedCluster.objects.get()
    assert cluster.accounts_count == 3 and cluster.posts_count == 3
    assert cluster.cross_party and cluster.cross_camp and cluster.parties == ['KO', 'PiS']
    # drugi przebieg z nowym wpisem: ten sam klaster rośnie, nie powstaje drugi
    post(5, 'opposition', MESSAGE, 50)
    out = refresh(now=now)
    assert out['created'] == 0 and out['updated'] == 1 and CoordinatedCluster.objects.count() == 1
    assert CoordinatedCluster.objects.get().accounts_count == 4
    body = APIClient().get('/api/clinic/wspolny-przekaz/').json()
    assert body['thresholds']['min_accounts'] == 3 and len(body['results']) == 1
    row = body['results'][0]
    assert row['accounts_count'] == 4 and row['cross_party'] and row['span_minutes'] == 50 and len(row['posts']) == 4
    assert set(row['camps']) == {'rządzący', 'opozycja'}
    # usunięte wpisy znikają; poniżej 3 kont klaster nie jest pokazywany
    PoliticalPost.objects.filter(pk__in=[first[1].pk, first[2].pk]).update(available=False)
    assert APIClient().get('/api/clinic/wspolny-przekaz/').json()['results'] == []
    assert APIClient().get('/api/clinic/wspolny-przekaz/?limit=x').status_code == 400
