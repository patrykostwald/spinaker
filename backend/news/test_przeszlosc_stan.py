"""Stan danych (Śledczy G4): każde źródło ze stanem, licznikiem i datą; zaległe po 48 h."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_stan
from news.public_records_models import PublicCollectionState
from news.test_drzewo_pieniedzy import rec

pytestmark = pytest.mark.django_db


def test_statuses(monkeypatch):
    cache.clear()
    monkeypatch.setenv('PUBLIC_RECORDS_TED_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_RECORDS_FTS_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    rec('ted', 'notice', '1-2026', {})
    PublicCollectionState.objects.create(source='fts', last_success_at=timezone.now() - timedelta(hours=72))
    rows = {r['key']: r for r in przeszlosc_stan.sources()}
    assert rows['ted']['status'] == 'ok' and rows['ted']['records'] == 1 and rows['ted']['gaps']
    assert rows['fts']['status'] == 'stale'
    assert rows['votes']['status'] == 'empty'
    assert rows['pkw']['status'] == 'off'
    assert rows['niw']['enabled'] and rows['bzp']['status'] == 'off'
    data = przeszlosc_stan.payload()
    assert data['counts']['stale'] == 1 and 'people_total' in data['krs']
    # P0-13: zbiory spoza PublicRecord mają własne wiersze; bez opisu braków nie twierdzimy, że ich nie ma
    keys = {r['key'] for r in data['sources']}
    assert {'glosowania', 'oswiadczenia', 'rcl', 'wpisy_x', 'krs_podmioty', 'wzmianki', 'druki'} <= keys
    assert all(r['gaps'] for r in data['sources']) and not any('Brak znanych braków' in r['gaps'] for r in data['sources'])


def test_dataset_counts_votes_and_worker_state_wins(monkeypatch):
    from news.models import Article, ParliamentaryVoting, Source
    cache.clear()
    source = Source.objects.create(name='Sejm', url='https://api.sejm.gov.pl')
    article = Article.objects.create(source=source, title='Głosowanie nr 1', url='https://api.sejm.gov.pl/sejm/term10/votings/1/1',
                                     published_date=timezone.now())
    ParliamentaryVoting.objects.create(article=article, term=10, sitting=1, number=1, motion='m', kind='ELECTRONIC')
    rows = {r['key']: r for r in przeszlosc_stan.datasets()}
    assert rows['glosowania']['records'] == 1 and rows['glosowania']['status'] == 'ok'
    assert rows['rcl']['status'] == 'empty'
    # env procesu web mówi „wyłączone”, ale worker pobrał dane w ostatnich 48 h
    monkeypatch.setenv('PUBLIC_RECORDS_PKW_ENABLED', 'false')
    PublicCollectionState.objects.update_or_create(source='pkw', defaults={'last_success_at': timezone.now() - timedelta(hours=2)})
    assert {r['key']: r for r in przeszlosc_stan.sources()}['pkw']['status'] != 'off'


def test_endpoint(monkeypatch):
    cache.clear()
    client = APIClient()
    assert client.get('/api/przeszlosc/stan-danych/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/stan-danych/').json()['sources']
