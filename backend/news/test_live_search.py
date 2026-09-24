from datetime import timedelta
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from news.models import Article, Source, ImportState


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_cross_process_import_visible_after_short_cache_expiry():
    client = APIClient()
    source = Source.objects.create(name='Test', url='https://example.org')
    with patch('django.core.cache.backends.base.time.time', return_value=1000):
        assert client.get('/api/search/', {'q': 'Archiwum'}).json()['total'] == 0
    # bulk_create intentionally bypasses local signals, like another process's cache.
    Article.objects.bulk_create([Article(source=source, title='Archiwum', url='https://example.org/a')])
    with patch('django.core.cache.backends.base.time.time', return_value=1006):
        assert client.get('/api/search/', {'q': 'Archiwum'}).json()['total'] == 1


@pytest.mark.django_db
def test_long_source_url_finds_exact_record_without_keyword_match():
    client = APIClient()
    source = Source.objects.create(name='Test', url='https://example.org')
    url = 'https://example.org/' + 'a' * 220
    record = Article.objects.create(source=source, title='Dokument', url=url)
    body = client.get('/api/search/', {'q': url + '#fragment'}).json()
    assert body['total'] == 1
    assert body['timeline']['undated'][0]['id'] == record.pk
    assert client.get('/api/search/', {'q': 'a' * 201}).status_code == 400


@pytest.mark.django_db
def test_public_status_does_not_claim_dead_worker_is_running_or_leak_job_errors():
    client = APIClient()
    ImportState.objects.create(name='local:heartbeat', last_success=timezone.now() - timedelta(minutes=4), last_error='PRIVATE')
    body = client.get('/api/archive/status/').json()
    assert body['worker_status'] == 'unconfirmed'
    assert body['complete'] is False
    assert 'PRIVATE' not in str(body)
    ImportState.objects.filter(name='local:heartbeat').update(last_success=timezone.now())
    cache.clear()
    assert client.get('/api/archive/status/').json()['worker_status'] == 'running'
