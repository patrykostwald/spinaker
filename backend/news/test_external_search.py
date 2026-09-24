import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from news.models import Source, Article, ArchiveJob, ImportState

@pytest.mark.django_db
def test_external_disabled_never_calls_provider(monkeypatch):
    monkeypatch.setattr('news.external_search.requests.get', lambda *a, **k: pytest.fail('network'))
    with override_settings(EXTERNAL_SEARCH_ENABLED=False):
        assert APIClient().get('/api/search/external/', {'q':'test'}).json()['status'] == 'disabled'

@pytest.mark.django_db
def test_external_enforces_sources_and_does_not_invent_dates(monkeypatch):
    Source.objects.create(name='Publisher', url='https://example.org')
    class Result:
        def raise_for_status(self): pass
        def json(self): return {'web': {'results': [
            {'url':'https://example.org/story', 'title':'<b>Publisher title</b>', 'page_age':'2020-01-01'},
            {'url':'https://example.org.evil.org/story', 'title':'Spoof'},
            {'url':'https://unknown.org/story', 'title':'Unknown'},
            {'url':'https://example.org/story', 'title':'Duplicate'}]}}
    calls=[]
    monkeypatch.setattr('news.external_search.requests.get', lambda *a, **k: calls.append(k) or Result())
    with override_settings(EXTERNAL_SEARCH_ENABLED=True, BRAVE_SEARCH_API_KEY='test', EXTERNAL_SEARCH_DAILY_LIMIT=1, EXTERNAL_SEARCH_CACHE_SECONDS=0):
        client=APIClient()
        result=client.get('/api/search/external/', {'q':'test'}).json()
        assert len(result['results']) == 1
        assert result['results'][0]['published_date'] is None
        assert result['results'][0]['title'] == 'Publisher title'
        assert Article.objects.count() == 0
        assert ArchiveJob.objects.get().url == 'https://example.org/story'
        assert client.get('/api/search/external/', {'q':'next'}).json()['status'] == 'daily_limit'
        assert len(calls) == 1
        assert 'site=example.org' in calls[0]['params']['goggles']

@pytest.mark.django_db
def test_external_filters_never_guess_genre_or_publication_date(monkeypatch):
    monkeypatch.setattr('news.external_search.requests.get', lambda *a, **k: pytest.fail('network'))
    with override_settings(EXTERNAL_SEARCH_ENABLED=True, BRAVE_SEARCH_API_KEY='test'):
        assert APIClient().get('/api/search/external/', {'q':'test','categories':'voting'}).json()['status'] == 'filtered'
        assert ImportState.objects.count() == 0
