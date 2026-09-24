import pytest
from rest_framework.test import APIClient
from django.core.cache import cache
from news.models import Article

@pytest.mark.django_db
def test_youtube_disabled_without_network(monkeypatch, settings):
    settings.YOUTUBE_ENABLED = False
    monkeypatch.setattr('news.youtube.requests.get', lambda *a, **k: pytest.fail('Unexpected network'))
    assert APIClient().post('/api/youtube/search/', {'q': 'test'}, format='json').json()['status'] == 'not_configured'
    assert Article.objects.count() == 0

@pytest.mark.django_db
def test_youtube_import_cache_and_budget(monkeypatch, settings):
    cache.clear()
    settings.YOUTUBE_ENABLED = True; settings.YOUTUBE_API_KEY = 'test-only'; settings.YOUTUBE_DAILY_REQUEST_LIMIT = 1
    class Result:
        def raise_for_status(self): pass
        def json(self):
            return {'items': [{'id': {'videoId': 'abcdefghijk'}, 'snippet': {'title': 'Dokument', 'channelId': 'UCtest', 'channelTitle': 'Test channel', 'publishedAt': '2020-01-01T10:00:00Z'}}], 'nextPageToken': 'page2'}
    monkeypatch.setattr('news.youtube.requests.get', lambda *a, **k: Result())
    client = APIClient()
    first = client.post('/api/youtube/search/', {'q': 'Dokument'}, format='json')
    assert first.status_code == 200
    assert Article.objects.get().category == 'video'
    assert first.json()['next_token'] == 'page2'
    assert client.post('/api/youtube/search/', {'q': 'Dokument'}, format='json').status_code == 200
    assert client.post('/api/youtube/search/', {'q': 'Inna fraza'}, format='json').status_code == 429
    assert Article.objects.count() == 1
    cache.clear()
