import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.community_models import CommunityLink, CommunityThreadOpinion
from news.models import Article, Source
from news.political_models import PublicFigure, PublicFigureArticleReference
from news.topics import TOPICS


@pytest.fixture
def fixture(monkeypatch):
    monkeypatch.setenv('THREADS_ENABLED', 'true')
    owner = get_user_model().objects.create_user('author')
    source = Source.objects.create(name='Source', url='https://example.org', is_active=True)
    article = Article.objects.create(source=source, title='Material', url='https://example.org/material')
    link = CommunityLink.objects.create(canonical_url='https://example.org/link', domain='example.org', title='Link')
    def thread(title, **kwargs):
        row = PersonalContextThread.objects.create(owner=owner, title=title, is_public=True, published_at=timezone.now(), **kwargs)
        PersonalContextThreadItem.objects.create(thread=row, article=article, position=0)
        PersonalContextThreadItem.objects.create(thread=row, link=link, position=1)
        return row
    return owner, article, link, thread


@pytest.mark.django_db
def test_global_opinion_order_and_topic_filter(fixture):
    owner, article, link, create = fixture
    topic = next(iter(TOPICS))
    first = create('Older with opinion', topics=[topic])
    second = create('Newer without opinion')
    CommunityThreadOpinion.objects.create(thread=first, user=owner, polarity='positive')
    client = APIClient()
    rows = client.get('/api/community/threads/?sort=best').json()['results']
    assert [row['id'] for row in rows] == [first.pk, second.pk]
    assert rows[0]['author_id'] == owner.pk
    assert rows[0]['items_count'] == 2
    assert rows[0]['opinions']['positive'] == 1
    assert client.get('/api/community/threads/?sort=new').json()['results'][0]['id'] == second.pk
    assert [row['id'] for row in client.get('/api/community/threads/', {'topic': topic}).json()['results']] == [first.pk]


@pytest.mark.django_db
def test_context_membership_and_private_hidden_exclusion(fixture):
    owner, article, link, create = fixture
    visible = create('Public')
    private = create('Private')
    private.is_public = False
    private.save()
    hidden = create('Hidden', hidden_at=timezone.now())
    client = APIClient()
    for params in ({'article_id': article.pk}, {'url': article.url}, {'url': link.canonical_url + '?utm_source=test'}):
        response = client.get('/api/community/threads/', params).json()
        assert response['context_filtered'] is True
        assert [row['id'] for row in response['results']] == [visible.pk]
    assert client.get('/api/community/threads/', {'article_id': article.pk + 100}).json()['results'] == []
    link.hidden_at = timezone.now()
    link.save()
    assert client.get('/api/community/threads/', {'url': link.canonical_url}).json()['results'] == []


@pytest.mark.django_db
def test_figure_uses_confirmed_references_only(fixture):
    owner, article, link, create = fixture
    row = create('Context')
    figure = PublicFigure.objects.create(canonical_name='Public Person', role_category='parliamentary', role_title='MP', evidence_url='https://example.org/person')
    ref = PublicFigureArticleReference.objects.create(public_figure=figure, article=article, reference_kind='mentioned')
    client = APIClient()
    assert client.get('/api/community/threads/', {'figure_id': figure.pk}).json()['results'] == []
    ref.verification_status = 'confirmed'
    ref.save()
    result = client.get('/api/community/threads/', {'figure_id': figure.pk}).json()['results']
    assert [item['id'] for item in result] == [row.pk]


@pytest.mark.django_db
def test_filters_validate_and_feature_flag_still_gates(fixture, monkeypatch):
    client = APIClient()
    for params in ({'article_id': '-1'}, {'figure_id': 'x'}, {'topic': 'not-a-topic'}, {'sort': 'invented'}, {'url': 'file:///etc/hosts'}):
        assert client.get('/api/community/threads/', params).status_code == 400
    monkeypatch.setenv('THREADS_ENABLED', 'false')
    assert client.get('/api/community/threads/?sort=best').status_code == 404
