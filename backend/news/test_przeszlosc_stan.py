"""Stan danych (Śledczy G4): każde źródło ze stanem, licznikiem i datą; zaległe po 2 x własnym interwale (min. 48 h)."""
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
    monkeypatch.setenv('PUBLIC_RECORDS_HOWTHEYVOTE_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    rec('ted', 'notice', '1-2026', {})
    PublicCollectionState.objects.create(source='howtheyvote', last_success_at=timezone.now() - timedelta(hours=72))
    rows = {r['key']: r for r in przeszlosc_stan.sources()}
    assert rows['ted']['status'] == 'ok' and rows['ted']['records'] == 1 and rows['ted']['gaps']
    assert rows['howtheyvote']['status'] == 'stale' and rows['howtheyvote']['stale_after_hours'] == 48
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


def test_stale_limit_follows_each_source_refresh_interval(monkeypatch):
    """Źródło tygodniowe/miesięczne nie jest „zaległe” po 48 h; zaległe dopiero po 2 x własnym interwale."""
    cache.clear()
    assert przeszlosc_stan.stale_limit(1) == timedelta(hours=48)       # godzinne: nie mniej niż 48 h
    assert przeszlosc_stan.stale_limit(24) == timedelta(hours=48)
    assert przeszlosc_stan.stale_limit(168) == timedelta(hours=336)    # tygodniowe
    assert przeszlosc_stan.stale_limit(720) == timedelta(hours=1440)   # miesięczne
    now = timezone.now()
    for key in ('pkw', 'mileage', 'lobby_mswia'):
        monkeypatch.setenv(f'PUBLIC_RECORDS_{key.upper()}_ENABLED', 'true')
    PublicCollectionState.objects.update_or_create(source='pkw', defaults={'last_success_at': now - timedelta(days=5)})            # tydzień: ok
    PublicCollectionState.objects.update_or_create(source='mileage', defaults={'last_success_at': now - timedelta(days=29)})       # miesiąc: ok
    PublicCollectionState.objects.update_or_create(source='lobby_mswia', defaults={'last_success_at': now - timedelta(days=15)})   # tydzień, 15 dni: zaległe
    rows = {r['key']: r for r in przeszlosc_stan.sources()}
    assert rows['pkw']['status'] == 'ok' and rows['pkw']['refresh_hours'] == 168
    assert rows['mileage']['status'] == 'ok' and rows['mileage']['stale_after_hours'] == 1440
    assert rows['lobby_mswia']['status'] == 'stale'
    assert rows['niw']['refresh_hours'] == 168 and rows['bzp']['refresh_hours'] == 24
