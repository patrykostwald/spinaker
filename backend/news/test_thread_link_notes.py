import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.community_models import CommunityLink
from news.models import Article, Source


pytestmark = pytest.mark.django_db


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr('django.conf.settings.THREADS_ENABLED', True)
    owner = get_user_model().objects.create_user('thread-author')
    source = Source.objects.create(name='Źródło', url='https://example.org', is_active=True)
    article = Article.objects.create(source=source, title='Materiał', url='https://example.org/1')
    link = CommunityLink.objects.create(canonical_url='https://example.org/2', domain='example.org', title='Film')
    client = APIClient()
    client.force_authenticate(owner)
    return client, owner, article, link


def create_thread(context, **changes):
    client, _, article, link = context
    payload = {
        'title': 'Prosta nitka', 'description': '', 'query': '', 'categories': [], 'topics': [], 'source_ids': [],
        'items': [{'article_id': article.pk, 'note': 'Początek'},
                  {'link_id': link.pk, 'note': 'Komentarz', 'link_note': 'Film wyjaśnia opisane zdarzenie.'}],
        **changes,
    }
    return client.post('/api/account/context-threads/', payload, format='json')


def test_thread_link_note_create_read_update_and_public_preview(context):
    client, _, article, link = context
    response = create_thread(context, is_public=True)
    assert response.status_code == 201, response.data
    thread_id = response.data['id']
    url = f'/api/account/context-threads/{thread_id}/'
    assert response.data['elements'][0]['link_note'] == ''
    assert response.data['elements'][1]['link_note'] == 'Film wyjaśnia opisane zdarzenie.'
    assert PersonalContextThreadItem.objects.get(thread_id=thread_id, position=1).link_note == response.data['elements'][1]['link_note']
    assert client.get(url).data['elements'] == response.data['elements']
    updated = client.patch(url, {'items': [
        {'link_id': link.pk, 'link_note': 'Stare powiązanie po zmianie kolejności'},
        {'article_id': article.pk, 'note': 'Nowy komentarz', 'link_note': 'ą' * 280},
    ]}, format='json')
    assert updated.status_code == 200
    assert [item['link_note'] for item in updated.data['elements']] == ['', 'ą' * 280]
    assert PersonalContextThreadItem.objects.get(thread_id=thread_id, position=0).link_note == ''
    public = APIClient()
    detail = public.get(f'/api/community/threads/{thread_id}/').data
    assert [item['link_note'] for item in detail['items']] == ['', 'ą' * 280]
    assert detail['items'][1]['note'] == 'Nowy komentarz'
    assert public.get('/api/community/threads/').data['results'][0]['preview'][1]['link_note'] == 'ą' * 280


@pytest.mark.parametrize('position', [0, 1])
def test_thread_link_note_limit_is_validated_before_writing(context, position):
    client, _, article, link = context
    response = create_thread(context)
    url = f'/api/account/context-threads/{response.data["id"]}/'
    items = [{'article_id': article.pk}, {'link_id': link.pk}]
    items[position]['link_note'] = 'x' * 281
    invalid = client.patch(url, {'items': items}, format='json')
    assert invalid.status_code == 400
    assert 'link_note' in invalid.data['items'][position]
    assert client.get(url).data['elements'][1]['link_note'] == 'Film wyjaśnia opisane zdarzenie.'
    assert create_thread(context, items=items).status_code == 400
    assert PersonalContextThread.objects.count() == 1


def test_thread_link_note_legacy_items_and_article_ids(context):
    client, _, article, link = context
    for payload in ({'items': [{'article_id': article.pk}, {'link_id': link.pk}]}, {'article_ids': [article.pk]}):
        response = client.post('/api/account/context-threads/', {'title': 'Starsza nitka', **payload}, format='json')
        assert response.status_code == 201
        assert all(item['link_note'] == '' for item in response.data['elements'])
    response = create_thread(context)
    url = f'/api/account/context-threads/{response.data["id"]}/'
    # Updating only the title preserves existing connections.
    assert client.patch(url, {'title': 'Nowy tytuł'}, format='json').data['elements'][1]['link_note'] == 'Film wyjaśnia opisane zdarzenie.'
    legacy = client.patch(url, {'article_ids': [article.pk]}, format='json')
    assert legacy.data['elements'][0]['link_note'] == ''


def test_thread_link_note_first_item_cleared_and_database_guard(context):
    _, _, article, link = context
    response = create_thread(context, items=[{'link_id': link.pk, 'link_note': 'Nie ma poprzednika'}, {'article_id': article.pk}])
    assert response.status_code == 201
    first = PersonalContextThreadItem.objects.get(thread_id=response.data['id'], position=0)
    assert first.link_note == ''
    with pytest.raises(IntegrityError), transaction.atomic():
        PersonalContextThreadItem.objects.filter(pk=first.pk).update(link_note='Niedozwolone')


def test_thread_link_note_moderation_hides_thread_and_link(context):
    client, _, _, link = context
    response = create_thread(context, is_public=True)
    thread_id = response.data['id']
    public = APIClient()
    link.hidden_at = timezone.now()
    link.save(update_fields=['hidden_at'])
    detail = public.get(f'/api/community/threads/{thread_id}/').data
    assert len(detail['items']) == 1
    assert detail['items'][0]['link_note'] == ''
    PersonalContextThread.objects.filter(pk=thread_id).update(hidden_at=timezone.now())
    assert public.get(f'/api/community/threads/{thread_id}/').status_code == 404
    assert public.get('/api/community/threads/').data['results'] == []
    # The owner still has the text available, just like the item comment.
    assert client.get(f'/api/account/context-threads/{thread_id}/').data['elements'][1]['link_note'] == 'Film wyjaśnia opisane zdarzenie.'
