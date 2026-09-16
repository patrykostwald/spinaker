import pytest
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from news.models import Article, Source, Thread, ThreadItem

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def source(db):
    return Source.objects.create(name='Źródło testowe', url='https://example.org')

@pytest.fixture
def client():
    return APIClient()

def article(source, title='Budżet państwa', **kwargs):
    return Article.objects.create(source=source, title=title, url=f'https://example.org/{Article.objects.count()}', published_date=kwargs.pop('published_date', timezone.now()), **kwargs)

@pytest.mark.django_db
def test_search_endpoint(client, source):
    a = article(source)
    response = client.get('/api/search/', {'q': 'Budżet'})
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert body['timeline'][timezone.localtime(a.published_date).date().isoformat()][0]['id'] == a.pk

@pytest.mark.django_db
@pytest.mark.parametrize('params', [{}, {'q': 'x', 'from_date': '2025-02-30'}, {'q': 'x', 'categories': 'unknown'}, {'q': 'x', 'from_date': '2026-02-02', 'to_date': '2026-01-01'}])
def test_invalid_search(client, params):
    assert client.get('/api/search/', params).status_code == 400

@pytest.mark.django_db
def test_date_end_includes_whole_local_day(client, source):
    from datetime import datetime
    article(source, published_date=timezone.make_aware(datetime(2025, 1, 20, 23, 59)))
    article(source, published_date=timezone.make_aware(datetime(2025, 1, 21, 0, 0)))
    response = client.get('/api/search/', {'q': 'Budżet', 'from_date': '2025-01-20', 'to_date': '2025-01-20'})
    assert response.json()['total'] == 1

@pytest.mark.django_db
def test_all_categories_are_public(client, source):
    for category in ('tweet', 'mention', 'sponsored', 'advertisement', 'reportage'):
        a = article(source, category=category)
        assert client.get(f'/api/articles/{a.pk}/').status_code == 200
    assert client.get('/api/search/', {'q': 'Budżet'}).json()['total'] == 4
    assert client.get('/api/search/', {'q': 'Budżet', 'categories': 'tweet'}).json()['total'] == 0

@pytest.mark.django_db
def test_unknown_publication_date(client, source):
    a = article(source, published_date=None)
    payload = client.get('/api/search/', {'q': 'Budżet'}).json()
    assert payload['timeline']['undated'][0]['published_date'] is None
    assert client.get(f'/api/articles/{a.pk}/related/').json() == {'related': []}

@pytest.mark.django_db
def test_related_overlap_and_date_window(client, source):
    original = article(source, 'Polityka energetyczna państwa')
    matching = article(source, 'Nowa polityka energetyczna')
    article(source, 'Niepowiązany materiał')
    article(source, 'Polityka energetyczna', published_date=timezone.now() - timedelta(days=10))
    response = client.get(f'/api/articles/{original.pk}/related/').json()
    assert [a['id'] for a in response['related']] == [matching.pk]

@pytest.mark.django_db
def test_drafts_domain_and_views(client, source):
    draft = Thread.objects.create(title='Szkic', thread_type='factcheck')
    fact = Thread.objects.create(title='Sprawdzenie', thread_type='factcheck', published=True)
    context = Thread.objects.create(title='Historia', thread_type='context', published=True)
    assert client.get(f'/api/threads/{draft.slug}/').status_code == 404
    assert {t['slug'] for t in client.get('/api/threads/', HTTP_X_FRONTEND_DOMAIN='spin.clinic').json()['results']} == {fact.slug, context.slug}
    assert client.get(f'/api/threads/{context.slug}/', HTTP_X_FRONTEND_DOMAIN='spin.clinic').status_code == 200
    assert client.get(f'/api/threads/{fact.slug}/').status_code == 200
    fact.refresh_from_db()
    assert fact.views_count == 1
    assert client.get('/api/threads/', HTTP_X_FRONTEND_DOMAIN='evilspin.clinic').json()['count'] == 2

@pytest.mark.django_db
def test_thread_positions_and_slug_collision(client, source):
    t = Thread.objects.create(title='Zażółć gęślą', thread_type='factcheck', published=True)
    other = Thread.objects.create(title=t.title, thread_type='factcheck')
    assert t.slug != other.slug
    a, b = article(source), article(source)
    ThreadItem.objects.create(thread=t, article=a, position=2)
    ThreadItem.objects.create(thread=t, article=b, position=0)
    assert [i['article']['id'] for i in client.get(f'/api/threads/{t.slug}/').json()['items']] == [b.pk, a.pk]

@pytest.mark.django_db
def test_rate_limit_before_cached_results(client, source):
    article(source)
    for _ in range(100):
        assert client.get('/api/search/', {'q': 'Budżet'}).status_code == 200
    assert client.get('/api/search/', {'q': 'Budżet'}).status_code == 429

@pytest.mark.django_db
def test_health_and_placeholder(client):
    assert client.get('/api/health/').json() == {'status': 'ok'}
    assert client.post('/api/patronite/webhook/', {}).status_code == 501
    assert client.post('/api/admin/google-news/', {'q': 'Polska'}).status_code == 403


def test_public_source_principles_page(client):
    response = client.get('/zasady-zrodel/')
    assert response.status_code == 200
    assert 'Nie uruchamiamy pobierania' in response.content.decode()

@pytest.mark.django_db
def test_pagination_reaches_old_and_undated(client, source):
    now = timezone.now()
    Article.objects.bulk_create([Article(source=source, title='Archiwum', url=f'https://example.org/archive/{i}', published_date=now - timedelta(days=i)) for i in range(505)])
    last = article(source, 'Archiwum', published_date=None)
    ids, page = [], 1
    while page:
        body = client.get('/api/search/', {'q': 'Archiwum', 'page': page}).json()
        ids.extend(a['id'] for rows in body['timeline'].values() for a in rows)
        page = body['next_page']
    assert len(ids) == len(set(ids)) == 506
    assert ids[-1] == last.pk
    assert client.get('/api/search/', {'q': 'Archiwum', 'page': '0'}).status_code == 400
