import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from news.account_models import ArticleFavorite, ArticleOpinion, CommentReport, PersonalContextThread
from news.models import Article, Source


pytestmark = pytest.mark.django_db


@pytest.fixture
def people():
    return [get_user_model().objects.create_user(username=name) for name in ('owner', 'other')]


@pytest.fixture
def articles():
    source = Source.objects.create(name='Publisher', url='https://example.org', is_active=True)
    return [
        Article.objects.create(source=source, title='First', url='https://example.org/first', tags=['zdrowie']),
        Article.objects.create(source=source, title='Second', url='https://example.org/second', tags=['zdrowie']),
    ]


def test_article_favorites_are_private_and_idempotent(people, articles):
    client = APIClient()
    client.force_authenticate(people[0])
    url = '/api/account/article-favorites/'
    assert client.post(url, {'article_id': articles[0].pk}, format='json').status_code == 201
    assert client.post(url, {'article_id': articles[0].pk}, format='json').status_code == 200
    assert len(client.get(url).data['results']) == 1
    client.force_authenticate(people[1])
    assert client.get(url).data['results'] == []
    client.force_authenticate(people[0])
    assert client.delete(f'{url}{articles[0].pk}/').status_code == 204
    assert not ArticleFavorite.objects.exists()


def test_personal_context_thread_keeps_owner_order_and_cannot_be_read_by_others(people, articles):
    client = APIClient()
    client.force_authenticate(people[0])
    response = client.post('/api/account/context-threads/', {
        'title': 'Mój kontekst', 'query': 'zdrowie', 'topics': ['zdrowie'],
        'article_ids': [articles[1].pk, articles[0].pk],
    }, format='json')
    assert response.status_code == 201
    thread_id = response.data['id']
    assert [row['id'] for row in response.data['articles']] == [articles[1].pk, articles[0].pk]
    client.force_authenticate(people[1])
    assert client.get(f'/api/account/context-threads/{thread_id}/').status_code == 404
    client.force_authenticate(people[0])
    assert client.patch(f'/api/account/context-threads/{thread_id}/', {
        'article_ids': [articles[0].pk, articles[1].pk],
    }, format='json').data['articles'][0]['id'] == articles[0].pk
    assert PersonalContextThread.objects.get(pk=thread_id).owner == people[0]


def test_personal_context_rejects_duplicate_or_inaccessible_articles(people, articles):
    client = APIClient()
    client.force_authenticate(people[0])
    assert client.post('/api/account/context-threads/', {
        'title': 'Bad', 'article_ids': [articles[0].pk, articles[0].pk],
    }, format='json').status_code == 400
    articles[1].source.is_active = False
    articles[1].source.save()
    assert client.post('/api/account/context-threads/', {
        'title': 'Hidden', 'article_ids': [articles[1].pk],
    }, format='json').status_code == 400


def test_comment_report_has_one_target_and_is_deduplicated(people, articles):
    opinion = ArticleOpinion.objects.create(user=people[1], article=articles[0], polarity='positive', body='Komentarz')
    client = APIClient()
    client.force_authenticate(people[0])
    url = '/api/comments/reports/'
    assert client.post(url, {'article_opinion_id': opinion.pk, 'reason': 'spam'}, format='json').status_code == 201
    assert client.post(url, {'article_opinion_id': opinion.pk, 'reason': 'spam'}, format='json').status_code == 409
    assert client.post(url, {'article_opinion_id': opinion.pk, 'thread_opinion_id': 1, 'reason': 'spam'}, format='json').status_code == 400
    assert CommentReport.objects.count() == 1
