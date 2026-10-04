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
