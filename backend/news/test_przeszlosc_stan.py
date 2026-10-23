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


def test_endpoint(monkeypatch):
    cache.clear()
    client = APIClient()
    assert client.get('/api/przeszlosc/stan-danych/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert client.get('/api/przeszlosc/stan-danych/').json()['sources']
