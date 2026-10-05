import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from news.political_models import PoliticalAccount, PoliticalPost
from news.przeszlosc import terms, topic_graph

pytestmark = pytest.mark.django_db


def post(key, camp, text):
    account = PoliticalAccount.objects.create(user_id=key, handle=f'konto{key}', display_name=f'Konto {key}', camp=camp)
    return PoliticalPost.objects.create(account=account, post_id=key, url=f'https://x.com/konto{key}/status/{key}', text=text,
                                        published_at=timezone.now(), camp_at_collection=camp)


def test_terms():
    assert terms('CPK, lotnisko; a') == ['CPK', 'lotnisko']
    assert terms('') == []


def test_same_measure_for_both_camps():
    post('1', 'government', 'CPK ruszy w terminie.')
    post('2', 'opposition', 'Rząd opóźnia CPK.')
    post('3', 'opposition', 'Inny temat.')
    data = topic_graph('CPK')
    statements = [n for n in data['nodes'] if n['kind'] == 'statement']
    assert {n['camp'] for n in statements} == {'government', 'opposition'}
    assert data['counts']['statement'] == 2 and len(data['edges']) == 2


def test_endpoint_off_by_default(monkeypatch):
    client = APIClient()
    assert client.get('/api/przeszlosc/temat/?q=CPK').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/temat/?q=a').status_code == 400
    assert client.get('/api/przeszlosc/temat/?q=CPK').json()['terms'] == ['CPK']


def test_start_counts_and_latest():
    post('9', 'government', 'CPK ruszy.')
    data = APIClient().get('/api/przeszlosc/start/').json()
    assert data['counts']['posts'] == 1 and data['latest'] == [] and data['topics_enabled'] is False


def test_inflection_and_acronym_expansion():
    post('21', 'government', 'Ceny energii spadną.')
    post('22', 'opposition', 'Budowa Centralnego Portu Komunikacyjnego stoi.')
    assert topic_graph('ceny energia')['counts']['statement'] == 1
    assert topic_graph('CPK')['counts']['statement'] == 1


def test_pick_topics_ranks_richest():
    from news.przeszlosc import auto_topics, pick_topics
    for i in range(4):
        post(str(30 + i), 'government' if i % 2 else 'opposition', 'KPO znowu opóźnione, KPO.')
    rows = pick_topics()
    assert all(r['edges'] >= 3 for r in rows) and auto_topics() == rows


def test_topic_votes_by_club_and_name(monkeypatch):
    from news.models import Article, Ballot, ParliamentaryVoting, Source
    from news.przeszlosc import topic_votes
    source = Source.objects.create(name='Sejm', url='https://sejm.example')
    article = Article.objects.create(source=source, title='Pkt 3. Projekt ustawy o podatku VAT', url='https://sejm.example/v',
                                     published_date='2026-09-20T10:00:00Z')
    voting = ParliamentaryVoting.objects.create(article=article, term=10, sitting=40, number=7, motion='wniosek o odrzucenie',
                                                kind='ELECTRONIC', counts={'yes': 2, 'no': 1})
    for n, (name, club, vote) in enumerate([('Anna A', 'KO', 'YES'), ('Jan B', 'KO', 'YES'), ('Ewa C', 'PiS', 'NO'), ('Piotr D', 'PiS', 'ABSENT')]):
        Ballot.objects.create(voting=voting, mp_id=n + 1, name=name, club=club, vote=vote)
    rows = topic_votes('VAT')
    assert len(rows) == 1 and rows[0]['result'] == {'yes': 2, 'no': 1}
    assert {c['club']: c['votes'] for c in rows[0]['clubs']} == {'KO': {'za': 2}, 'PiS': {'przeciw': 1, 'nieobecny': 1}}
    assert ['Ewa C', 'PiS', 'przeciw'] in rows[0]['members'] and 'NrGlosowania=7' in rows[0]['url']
    assert topic_votes('lotnisko') == []
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    data = APIClient().get('/api/przeszlosc/temat/?q=VAT').json()
    assert data['counts']['vote'] == 1 and data['votes'][0]['id'] == '10/40/7'


def test_topic_rss(settings):
    """Kanał RSS tematu: poprawny XML z elementami tematu, wyłączony razem z przeszłością."""
    from unittest import mock
    from django.test import Client
    from news import przeszlosc
    graph = {'nodes': [{'id': 'post:1', 'kind': 'statement', 'label': 'VAT & akcyza <test>', 'date': '2026-10-03', 'url': 'https://x.com/a/1', 'sub': 'Ktoś'},
                       {'id': 'figure:1', 'kind': 'person', 'label': 'Osoba'}]}
    with mock.patch.object(przeszlosc, 'enabled', return_value=True), mock.patch.object(przeszlosc, 'topic_graph', return_value=graph):
        r = Client().get('/api/przeszlosc/rss/', {'q': 'VAT'})
    assert r.status_code == 200 and r['Content-Type'].startswith('application/rss+xml')
    body = r.content.decode()
    assert '<item>' in body and 'VAT &amp; akcyza &lt;test&gt;' in body and 'Osoba' not in body
    with mock.patch.object(przeszlosc, 'enabled', return_value=False):
        assert Client().get('/api/przeszlosc/rss/', {'q': 'VAT'}).status_code == 404
