from datetime import timedelta
import pytest
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from news.models import Article, Source, Thread

@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def editor(db):
    return get_user_model().objects.create_user(username='editor', password='test-only-password', is_staff=True)

@pytest.fixture
def articles(db):
    source = Source.objects.create(name='Test', url='https://example.org')
    return [Article.objects.create(source=source, title=f'Source {i}', url=f'https://example.org/{i}', published_date=timezone.now() - timedelta(days=i)) for i in range(2)]

@pytest.mark.django_db
def test_editor_requires_staff(editor):
    client = APIClient()
    assert client.post('/api/editor/threads/', {}, format='json').status_code == 403
    regular = get_user_model().objects.create_user(username='reader')
    client.force_authenticate(regular)
    assert client.post('/api/editor/threads/', {}, format='json').status_code == 403
    client.force_authenticate(editor)
    assert client.get('/api/editor/threads/').status_code == 200

@pytest.mark.django_db
def test_create_edit_publish(editor, articles):
    client = APIClient()
    client.force_authenticate(editor)
    response = client.post('/api/editor/threads/', {'title': 'Historia', 'published': False, 'items': [{'article_id': a.pk, 'editorial_note': 'Komentarz'} for a in articles]}, format='json')
    assert response.status_code == 201, response.data
    slug = response.json()['slug']
    thread = Thread.objects.get(slug=slug)
    assert thread.created_by == editor
    assert list(thread.thread_items.values_list('article_id', flat=True)) == [articles[1].pk, articles[0].pk]
    assert client.get(f'/api/threads/{slug}/').status_code == 404
    assert client.patch(f'/api/editor/threads/{slug}/', {'published': True, 'is_featured': True}, format='json').status_code == 200
    assert client.get(f'/api/threads/{slug}/').status_code == 200
    response = client.post('/api/editor/threads/', {'title': 'Duplicate', 'items': [{'article_id': articles[0].pk}, {'article_id': articles[0].pk}]}, format='json')
    assert response.status_code == 400 and Thread.objects.count() == 1

@pytest.mark.django_db
def test_manual_source_has_no_invented_date(editor):
    client = APIClient()
    client.force_authenticate(editor)
    data = {'title': 'Wypowiedź', 'url': 'https://example.org/statement', 'source_name': 'Example', 'category': 'statement', 'published_date': None}
    response = client.post('/api/editor/articles/', data, format='json')
    assert response.status_code == 201, response.data
    a = Article.objects.get()
    assert a.published_date is None and a.author == '' and a.ingestion_method == 'manual'
    assert a.source.total_articles == 1
    assert client.post('/api/editor/articles/', data, format='json').status_code == 400
    data['url'] = 'javascript:alert(1)'
    assert client.post('/api/editor/articles/', data, format='json').status_code == 400

@pytest.mark.django_db
def test_session_csrf_login_logout(editor):
    client = APIClient(enforce_csrf_checks=True)
    data = {'username': 'editor', 'password': 'test-only-password'}
    assert client.post('/api/auth/login/', data, format='json').status_code == 403
    csrf = client.get('/api/auth/csrf/').json()['csrfToken']
    response = client.post('/api/auth/login/', data, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert client.get('/api/me/').json()['is_editor'] is True
    assert client.post('/api/editor/threads/', {}, format='json').status_code == 403
    csrf = client.get('/api/auth/csrf/').json()['csrfToken']
    assert client.post('/api/auth/logout/', {}, format='json', HTTP_X_CSRFTOKEN=csrf).status_code == 200
    assert client.get('/api/me/').json()['authenticated'] is False

@pytest.mark.django_db
def test_x_reference_is_thread_only(editor, monkeypatch):
    client = APIClient()
    client.force_authenticate(editor)
    def forbidden(*args, **kwargs):
        raise AssertionError('X must not be fetched')
    monkeypatch.setattr('news.metadata.fetch_feed', forbidden)
    url = 'https://x.com/example/status/123456?s=20'
    preview = client.post('/api/editor/preview-url/', {'url': url}, format='json')
    assert preview.status_code == 200
    assert preview.json()['reference']['published_date'] is None
    result = client.post('/api/editor/threads/', {'title': 'Odnośnik', 'published': True, 'items': [{'external_url': url, 'editorial_note': 'Komentarz autora'}]}, format='json')
    assert result.status_code == 201, result.data
    slug = result.json()['slug']
    item = client.get(f'/api/threads/{slug}/').json()['items'][0]
    assert item['article']['reference_only'] is True
    assert item['article']['url'] == 'https://x.com/example/status/123456'
    assert Article.objects.count() == 0
    assert client.patch(f'/api/editor/threads/{slug}/', {'items': [{'external_url': item['article']['url']}]}, format='json').status_code == 200
    bad = client.post('/api/editor/threads/', {'title': 'Bad', 'items': [{'external_url': 'https://x.com.evil.org/example/status/123'}]}, format='json')
    assert bad.status_code == 400
