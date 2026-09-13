import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from news.models import Source, Article, Thread
from news.account_models import ProfilePreference, ArticleOpinion, ThreadFavorite

pytestmark = pytest.mark.django_db


@pytest.fixture
def accounts():
    cache.clear()
    return [get_user_model().objects.create_user(username=name, email=name + '@example.org') for name in ['one', 'two']]


@pytest.fixture
def source():
    return Source.objects.create(name='Independent publisher', url='https://example.org', is_active=True)


def test_private_default_explicit_opt_in_and_no_email(accounts, source):
    owner, other = accounts
    article = Article.objects.create(source=source, title='News', url='https://example.org/a')
    ArticleOpinion.objects.create(user=owner, article=article, polarity='positive', body='Public comment')
    client = APIClient()
    assert client.get('/api/profiles/one/activity/').status_code == 404
    assert client.get('/api/account/history/').status_code == 403
    client.force_authenticate(owner)
    assert client.get('/api/account/profile/').data == {'username': 'one', 'public_activity': False}
    assert client.get('/api/account/history/').data['results'][0]['body'] == 'Public comment'
    assert client.patch('/api/account/profile/', {'public_activity': True, 'user': other.pk, 'is_staff': True}, format='json').status_code == 200
    owner.refresh_from_db()
    assert not owner.is_staff and not ProfilePreference.objects.filter(user=other).exists()
    client.force_authenticate(None)
    response = client.get('/api/profiles/one/activity/')
    assert response.status_code == 200 and 'email' not in str(response.data)
    assert 'favorites' not in response.data and 'topics' not in response.data
    client.force_authenticate(owner)
    client.patch('/api/account/profile/', {'public_activity': False}, format='json')
    assert client.get('/api/profiles/one/activity/').status_code == 404


def test_history_is_always_owner_scoped(accounts, source):
    owner, other = accounts
    article = Article.objects.create(source=source, title='News', url='https://example.org/a')
    ArticleOpinion.objects.create(user=owner, article=article, polarity='negative', body='Owner opinion')
    client = APIClient()
    client.force_authenticate(other)
    assert client.get('/api/account/history/', {'user': owner.pk}).data['results'] == []


def test_favorites_private_idempotent_and_hidden_threads(accounts):
    owner, other = accounts
    published = Thread.objects.create(title='Published', published=True)
    draft = Thread.objects.create(title='Draft', published=False)
    client = APIClient()
    client.force_authenticate(owner)
    assert client.post('/api/account/favorites/', {'thread_id': draft.pk}, format='json').status_code == 404
    data = {'thread_id': published.pk, 'user': other.pk}
    assert client.post('/api/account/favorites/', data, format='json').status_code == 201
    assert client.post('/api/account/favorites/', data, format='json').status_code == 200
    assert len(client.get('/api/account/favorites/', {'thread_id': published.pk}).data['results']) == 1
    assert client.get('/api/account/favorites/', {'thread_id': draft.pk}).data['results'] == []
    with pytest.raises(IntegrityError), transaction.atomic():
        ThreadFavorite.objects.create(user=owner, thread=published)
    client.force_authenticate(other)
    assert client.get('/api/account/favorites/').data['results'] == []
    client.delete(f'/api/account/favorites/{published.pk}/')
    assert ThreadFavorite.objects.filter(user=owner, thread=published).exists()
    client.force_authenticate(owner)
    published.published = False
    published.save()
    assert client.get('/api/account/favorites/').data['results'] == []
    assert client.delete(f'/api/account/favorites/{published.pk}/').status_code == 204


def test_profile_and_favorites_csrf(accounts):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(accounts[0])
    assert client.patch('/api/account/profile/', {'public_activity': True}, format='json').status_code == 403
    assert client.post('/api/account/favorites/', {'thread_id': 1}, format='json').status_code == 403
    assert client.delete('/api/account/favorites/1/').status_code == 403


def test_topics_are_publisher_tags_not_titles_or_material_type(accounts, source):
    tagged = Article.objects.create(source=source, title='Neutral title', url='https://example.org/a', category='interview', tags=['ŚWIAT'])
    Article.objects.create(source=source, title='Świat', url='https://example.org/b', category='article', tags=[])
    Article.objects.create(source=source, title='Neutral', url='https://example.org/c', tags=['Transport'])
    client = APIClient()
    result = client.get('/api/feed/', {'topics': 'swiat', 'categories': 'interview', 'sources': source.pk})
    assert result.status_code == 200 and [row['id'] for row in result.data['results']] == [tagged.pk]
    assert client.get('/api/feed/', {'topics': 'sport'}).data['total'] == 0
    assert client.get('/api/feed/', {'topics': 'invented'}).status_code == 400
    client.force_authenticate(accounts[0])
    saved = client.post('/api/account/topics/', {'label': 'Świat', 'query': 'wiadomości', 'topics': ['swiat'], 'categories': ['interview'], 'source_ids': [source.pk]}, format='json')
    assert saved.status_code == 201 and saved.data['topics'] == ['swiat']
    assert saved.data['categories'] == ['interview']
    assert client.post('/api/account/topics/', {'label': 'Bad', 'query': 'x', 'topics': ['article']}, format='json').status_code == 400


def test_source_selection_includes_beyond_top_ten_and_hides_inactive(source):
    Source.objects.create(name='Inactive', url='https://inactive.example', is_active=False)
    data = APIClient().get('/api/portal/config/').data
    assert source.pk in [row['id'] for row in data['sources']]
    assert 'Inactive' not in [row['name'] for row in data['sources']]
    assert len(data['topics']) == 13


def test_reaction_without_comment_append_once_and_owner_only(accounts, source):
    owner, other = accounts
    article = Article.objects.create(source=source, title='News', url='https://example.org/a')
    url = f'/api/articles/{article.pk}/opinions/'
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post(url, {'polarity': 'negative'}, format='json')
    assert response.status_code == 201 and response.data['body'] == ''
    initial = client.get(url).data
    assert initial['counts'] == {'positive': 0, 'negative': 1}
    assert initial['negative']['results'] == [] and initial['mine']['body'] == ''
    client.force_authenticate(other)
    assert client.patch(url, {'body': 'Hijack'}, format='json').status_code == 404
    client.force_authenticate(owner)
    assert client.patch(url, {'body': 'Comment', 'polarity': 'positive'}, format='json').status_code == 400
    assert client.patch(url, {'body': 'Comment'}, format='json').status_code == 200
    assert client.patch(url, {'body': 'Replacement'}, format='json').status_code == 409
    opinion = ArticleOpinion.objects.get(user=owner, article=article)
    assert opinion.body == 'Comment' and opinion.polarity == 'negative'
    assert len(client.get(url).data['negative']['results']) == 1


def test_append_compare_and_set_rejects_lost_race(accounts, source, monkeypatch):
    from django.db.models.query import QuerySet
    article = Article.objects.create(source=source, title='News', url='https://example.org/a')
    ArticleOpinion.objects.create(user=accounts[0], article=article, polarity='positive')
    client = APIClient()
    client.force_authenticate(accounts[0])
    original = QuerySet.update
    def lost_race(qs, **kwargs):
        if qs.model is ArticleOpinion and set(kwargs) == {'body'}:
            return 0
        return original(qs, **kwargs)
    monkeypatch.setattr(QuerySet, 'update', lost_race)
    assert client.patch(f'/api/articles/{article.pk}/opinions/', {'body': 'My comment'}, format='json').status_code == 409


def test_saved_topic_can_use_source_topic_without_search_phrase(accounts, source):
    client = APIClient()
    client.force_authenticate(accounts[0])
    response = client.post('/api/account/topics/', {'label': 'Zdrowie', 'topics': ['zdrowie'], 'source_ids': [source.pk]}, format='json')
    assert response.status_code == 201 and response.data['query'] == ''


def test_paused_import_source_remains_selectable(accounts, source):
    source.scrape_enabled = False
    source.catalog_stage = 'candidate'
    source.save()
    client = APIClient()
    assert source.pk in [row['id'] for row in client.get('/api/portal/config/').data['sources']]
    client.force_authenticate(accounts[0])
    response = client.post('/api/account/topics/', {'label': 'Manual', 'source_ids': [source.pk]}, format='json')
    assert response.status_code == 201
