import pytest
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import include, path
from rest_framework.test import APIClient
from news.account_models import SavedTopic, ArticleOpinion, ThreadOpinion, UserXConnection
from news.models import Article, Source, Thread

urlpatterns = [path('api/', include('news.account_urls')), path('api/', include('news.urls'))]
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_urls():
    cache.clear()
    with override_settings(ROOT_URLCONF=__name__):
        yield


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username='reader', password='A8!quite-strong-secret')


@pytest.fixture
def article():
    source = Source.objects.create(name='Publisher', url='https://example.org', is_active=True)
    return Article.objects.create(source=source, title='Publisher title', url='https://example.org/a')


def token(client):
    return client.get('/api/account/me/').data['csrfToken']


def test_register_csrf_password_and_no_privilege_escalation():
    client = APIClient(enforce_csrf_checks=True)
    data = {'username': 'Reader', 'password': 'Str0ng~unique~zxcv!', 'is_staff': True, 'is_superuser': True}
    assert client.post('/api/account/register/', data, format='json').status_code == 403
    csrf = token(client)
    response = client.post('/api/account/register/', data, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 201
    created = get_user_model().objects.get(username='reader')
    assert not created.is_staff and not created.is_superuser
    assert created.check_password(data['password'])
    assert response.data['csrfToken'] != csrf
    assert client.get('/api/account/me/').data['authenticated']
    assert client.post('/api/editor/threads/', {}, format='json', HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code == 403
    assert client.patch('/api/editor/sources/1/', {}, format='json', HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code == 403


def test_weak_password_and_duplicate_handle_rejected(user):
    client = APIClient()
    assert client.post('/api/account/register/', {'username': 'newreader', 'password': '123'}, format='json').status_code == 400
    assert client.post('/api/account/register/', {'username': 'READER', 'password': 'Something!99long'}, format='json').status_code == 400


def test_public_login_logout_csrf_and_editor_login_still_rejects(user):
    client = APIClient(enforce_csrf_checks=True)
    data = {'username': 'reader', 'password': 'A8!quite-strong-secret'}
    assert client.post('/api/account/login/', data, format='json').status_code == 403
    csrf = token(client)
    assert client.post('/api/auth/login/', data, format='json', HTTP_X_CSRFTOKEN=csrf).status_code == 403
    response = client.post('/api/account/login/', data, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert client.post('/api/account/logout/', {}, format='json').status_code == 403
    assert client.post('/api/account/logout/', {}, format='json', HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code == 200
    assert client.get('/api/account/me/').data['authenticated'] is False


def test_login_rate_limit(user):
    client = APIClient()
    for _ in range(10):
        assert client.post('/api/account/login/', {'username': 'reader', 'password': 'bad'}, format='json').status_code == 403
    assert client.post('/api/account/login/', {'username': 'reader', 'password': 'bad'}, format='json').status_code == 429


def test_x_connection_is_opt_in_and_can_be_removed(user):
    client = APIClient()
    assert client.get('/api/account/x-connection/').status_code == 403
    client.force_authenticate(user)
    assert client.get('/api/account/x-connection/').data == {
        'connected': False, 'username': '', 'oauth_enabled': False, 'connect_url': None,
    }
    assert client.get('/api/account/x-connection/start/').status_code == 503
    UserXConnection.objects.create(user=user, x_user_id='123', username='reader_on_x')
    assert client.get('/api/account/x-connection/').data['connected'] is True
    assert client.delete('/api/account/x-connection/').status_code == 204
    assert not UserXConnection.objects.filter(user=user).exists()


@override_settings(X_USER_OAUTH_ENABLED=True, X_USER_OAUTH_CLIENT_ID='client-id',
                   X_USER_OAUTH_REDIRECT_URI='https://portal.example/api/account/x-connection/callback/',
                   X_USER_OAUTH_SUCCESS_PATH='/konto')
def test_x_connection_uses_pkce_and_discards_oauth_token(user):
    client = APIClient()
    client.force_login(user)
    start = client.get('/api/account/x-connection/start/')
    assert start.status_code == 302
    assert 'code_challenge=' in start['Location'] and 'scope=users.read' in start['Location']
    state = client.session['x_oauth_state']
    token_response = Mock()
    token_response.json.return_value = {'access_token': 'must-not-be-persisted'}
    identity_response = Mock()
    identity_response.json.return_value = {'data': {'id': '765', 'username': 'reader_x'}}
    with patch('news.accounts.requests.post', return_value=token_response) as post, \
         patch('news.accounts.requests.get', return_value=identity_response):
        callback = client.get('/api/account/x-connection/callback/', {'state': state, 'code': 'code-from-x'})
    assert callback.status_code == 302 and callback['Location'] == '/konto?x=connected'
    connection = UserXConnection.objects.get(user=user)
    assert connection.x_user_id == '765' and connection.username == 'reader_x'
    assert post.call_args.kwargs['data']['code_verifier']
    assert 'must-not-be-persisted' not in str(connection.__dict__)
    # The state was consumed; reusing the redirect is rejected without a second exchange.
    assert client.get('/api/account/x-connection/callback/', {'state': state, 'code': 'code-from-x'})['Location'] == '/konto?x=failed'


def test_topics_owner_only_max_ten_and_db_cap(user, article):
    client = APIClient()
    assert client.get('/api/account/topics/').status_code == 403
    client.force_authenticate(user)
    payload = {'label': 'Temat', 'query': 'temat', 'source_ids': [article.source_id], 'categories': ['article']}
    ids = []
    for _ in range(10):
        response = client.post('/api/account/topics/', payload, format='json')
        assert response.status_code == 201
        ids.append(response.data['id'])
    assert client.post('/api/account/topics/', payload, format='json').status_code == 409
    with pytest.raises(IntegrityError), transaction.atomic():
        SavedTopic.objects.create(owner=user, label='Bad', query='bad', slot=10)
    with pytest.raises(IntegrityError), transaction.atomic():
        SavedTopic.objects.create(owner=user, label='Race', query='race', slot=0)
    other = get_user_model().objects.create_user(username='other')
    client.force_authenticate(other)
    url = f'/api/account/topics/{ids[0]}/'
    assert client.get(url).status_code == 404
    assert client.patch(url, {'query': 'changed'}, format='json').status_code == 404
    assert client.delete(url).status_code == 404
    assert client.get('/api/account/topics/').data['topics'] == []


def test_topic_validation_and_csrf(user, article):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.post('/api/account/topics/', {'label': 'T', 'query': 't'}, format='json').status_code == 403
    csrf = token(client)
    for extra in [{'categories': ['unknown']}, {'query': 'x' * 201}, {'position': 10}, {'source_ids': [999999]}]:
        response = client.post('/api/account/topics/', {'label': 'T', 'query': 't', **extra}, format='json', HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == 400


def test_one_immutable_opinion_counts_and_no_ownership_input(user, article):
    client = APIClient()
    url = f'/api/articles/{article.pk}/opinions/'
    assert client.post(url, {'polarity': 'positive', 'body': 'Komentarz'}, format='json').status_code == 403
    client.force_authenticate(user)
    response = client.post(url, {'polarity': 'positive', 'body': 'Komentarz', 'user': 999}, format='json')
    assert response.status_code == 201 and response.data['author']['id'] == user.pk
    assert client.post(url, {'polarity': 'negative', 'body': 'Zmiana'}, format='json').status_code == 409
    assert client.patch(url, {'body': 'Zmiana'}, format='json').status_code == 409
    assert client.delete(url).status_code == 405
    with pytest.raises(IntegrityError), transaction.atomic():
        ArticleOpinion.objects.create(article=article, user=user, polarity='negative', body='Race')
    result = client.get(url).data
    assert result['counts'] == {'positive': 1, 'negative': 0}
    assert result['mine']['body'] == 'Komentarz'


def test_opinion_unicode_budget_csrf_and_pagination(user, article):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    url = f'/api/articles/{article.pk}/opinions/'
    assert client.post(url, {'polarity': 'positive', 'body': 'Komentarz'}, format='json').status_code == 403
    csrf = token(client)
    for body in ['x' * 241, '😀' * 121, 'bad\u0000text']:
        assert client.post(url, {'polarity': 'positive', 'body': body}, format='json', HTTP_X_CSRFTOKEN=csrf).status_code == 400
    for n in range(23):
        author = get_user_model().objects.create_user(username=f'commenter{n}')
        ArticleOpinion.objects.create(user=author, article=article, body='Real record', polarity='positive')
    data = client.get(url + '?page_size=100').data
    assert data['counts']['positive'] == 23 and len(data['positive']['results']) == 20
    assert data['positive']['next_page'] == 2
    assert len(client.get(url + '?positive_page=2').data['positive']['results']) == 3


def test_one_opinion_per_user_on_published_thread(user):
    published = Thread.objects.create(title='Published', slug='published', published=True)
    draft = Thread.objects.create(title='Draft', slug='draft', published=False)
    client = APIClient()
    published_url = '/api/threads/published/opinions/'
    assert client.get('/api/threads/draft/opinions/').status_code == 404
    assert client.post(published_url, {'polarity': 'positive'}, format='json').status_code == 403
    client.force_authenticate(user)
    response = client.post(published_url, {'polarity': 'negative', 'body': ''}, format='json')
    assert response.status_code == 201
    assert client.post(published_url, {'polarity': 'positive'}, format='json').status_code == 409
    response = client.patch(published_url, {'body': 'Brakuje ważnego źródła.'}, format='json')
    assert response.status_code == 200
    assert client.patch(published_url, {'body': 'Zmiana'}, format='json').status_code == 409
    assert ThreadOpinion.objects.get(user=user, thread=published).polarity == 'negative'
    data = client.get(published_url).data
    assert data['counts'] == {'positive': 0, 'negative': 1}
    assert data['negative'][0]['body'] == 'Brakuje ważnego źródła.'
    assert not ThreadOpinion.objects.filter(thread=draft).exists()
