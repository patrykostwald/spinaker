from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from rest_framework.test import APIClient

from news.voting_anomalies import EXCESS_PP, MIN_VOTES, analyse, club_majority, refresh

START = datetime(2026, 6, 1, 10, tzinfo=dt_timezone.utc)


def voting(n, ballots, day=0):
    return {'term': 10, 'sitting': 1, 'number': n, 'title': f'Głosowanie {n}', 'date': (START + timedelta(days=day)).isoformat(),
            'ballots': ballots}


def club_rows(club, base_id, votes):
    return [(base_id + i, f'{club} Poseł {i}', club, v) for i, v in enumerate(votes)]


def mirrored(count=25, rebels_every=5):
    """Dwa kluby z identycznym wzorem głosowania: ten sam wynik musi wyjść dla obu (ta sama miara)."""
    rows = []
    for n in range(count):
        rebel = n % rebels_every == 0
        a = ['YES'] * 4 + (['NO'] if rebel else ['YES'])
        b = ['NO'] * 4 + (['YES'] if rebel else ['NO'])
        rows.append(voting(n + 1, club_rows('KO', 100, a) + club_rows('PiS', 200, b), day=n))
    return rows


def test_club_majority_ties_small_clubs_and_absences():
    assert club_majority([(1, 'YES'), (2, 'YES'), (3, 'NO'), (4, 'ABSENT')])[0] == 'YES'
    assert club_majority([(1, 'YES'), (2, 'NO'), (3, 'ABSTAIN'), (4, 'YES'), (5, 'NO')]) == (None, 0.0)  # remis
    assert club_majority([(1, 'YES'), (2, 'ABSENT'), (3, 'ABSENT')]) == (None, 0.0)  # mniej niż 3 oddane głosy
    top, unity = club_majority([(1, 'YES'), (2, 'YES'), (3, 'YES'), (4, 'NO'), (5, 'ABSENT')])
    assert top == 'YES' and unity == 0.75


def test_same_measure_for_mirrored_clubs():
    result = analyse(mirrored())
    clubs = {c['club']: c for c in result['clubs']}
    assert set(clubs) == {'KO', 'PiS'}
    for club in clubs.values():
        assert club['median'] == 0.0 and club['mps'] == 5
        assert [m['mp_id'] % 100 for m in club['flagged']] == [4]
        assert club['flagged'][0]['share'] == 20.0 and club['flagged'][0]['excess'] == 20.0
        assert club['rebellions_total'] == 5 and club['rebellions'][0]['unity'] == 80
    assert clubs['KO']['rebellions'][0]['vote'] == 'przeciw' and clubs['PiS']['rebellions'][0]['vote'] == 'za'
    assert result['votings'] == 25 and result['range'] == {'from': '2026-06-01', 'to': '2026-06-25'}
    assert 'NrGlosowania=' in clubs['KO']['rebellions'][0]['url']


def test_low_unity_is_deviation_but_not_rebellion():
    rows = [voting(n + 1, club_rows('Lewica', 300, ['YES', 'YES', 'YES', 'NO', 'NO'])) for n in range(MIN_VOTES)]
    result = analyse(rows)
    club = result['clubs'][0]
    assert club['rebellions_total'] == 0
    members = {m['mp_id']: m for m in result['members'].values()}
    assert members[303]['deviations'] == MIN_VOTES and members[303]['share'] == 100.0


def test_small_sample_and_threshold_edge_not_flagged():
    # 19 głosów: za mało, żeby porównywać, nawet przy samych odstępstwach
    rows = [voting(n + 1, club_rows('PSL', 400, ['YES'] * 4 + ['NO'])) for n in range(MIN_VOTES - 1)]
    assert analyse(rows)['clubs'][0]['flagged'] == []
    # dokładnie +5 pkt proc. ponad medianę: bez wyróżnienia (próg ostry); 1 odstępstwo na 20 głosów = 5%
    rows = [voting(n + 1, club_rows('PSL', 400, ['YES'] * 4 + (['NO'] if n == 0 else ['YES']))) for n in range(20)]
    club = analyse(rows)['clubs'][0]
    member = [m for m in analyse(rows)['members'].values() if m['mp_id'] == 404][0]
    assert member['excess'] == EXCESS_PP and not member['flagged'] and club['flagged'] == []


def test_unaffiliated_and_absence_are_not_deviations():
    ballots = club_rows('KO', 100, ['YES', 'YES', 'YES', 'ABSENT', 'NO_VOTE']) + [(900, 'Niezrzeszony', 'niez.', 'NO'), (901, 'Bez klubu', '', 'NO')]
    result = analyse([voting(1, ballots)])
    assert [c['club'] for c in result['clubs']] == ['KO']
    assert all(m['deviations'] == 0 for m in result['members'].values())
    assert {m['mp_id'] for m in result['members'].values()} == {100, 101, 102}


def test_empty_input():
    result = analyse([])
    assert result['clubs'] == [] and result['votings'] == 0 and result['range'] == {'from': None, 'to': None}


@pytest.mark.django_db
def test_refresh_and_api(monkeypatch):
    from news.models import Article, Ballot, ParliamentaryVoting, Source
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    for v in mirrored():
        article = Article.objects.create(source=source, title=v['title'], url=f"https://sejm.example/{v['number']}", published_date=v['date'])
        pv = ParliamentaryVoting.objects.create(article=article, term=10, sitting=1, number=v['number'], motion='wniosek', kind='ELECTRONIC')
        Ballot.objects.bulk_create([Ballot(voting=pv, mp_id=mp, name=name, club=club, vote=vote) for mp, name, club, vote in v['ballots']])
    client = APIClient()
    monkeypatch.delenv('PRZESZLOSC_ENABLED', raising=False)
    assert client.get('/api/przeszlosc/odstepstwa/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/odstepstwa/').json()['clubs'] == []  # przed pierwszym przeliczeniem
    out = refresh()
    assert out['term'] == 10 and out['periods']['90d'] == {'votings': 25, 'flagged': 2, 'rebellions': 10}
    body = client.get('/api/przeszlosc/odstepstwa/?okres=kadencja').json()
    assert body['period'] == 'term' and 'members' not in body and len(body['clubs']) == 2
    assert body['method'].startswith('Liczymy oddane głosy')
    one = client.get('/api/przeszlosc/odstepstwa/?posel=104&okres=kadencja').json()
    assert one['clubs'][0]['flagged'] and len(one['clubs'][0]['rebellions']) == 5
    assert client.get('/api/przeszlosc/odstepstwa/?posel=999').status_code == 404
    assert client.get('/api/przeszlosc/odstepstwa/?okres=rok').status_code == 400
    assert client.get('/api/przeszlosc/odstepstwa/?posel=abc').status_code == 400
