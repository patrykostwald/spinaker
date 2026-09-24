import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from news.editorial import WriteThreadSerializer
from news.models import Article, Source, Thread, ThreadItem

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def people():
    users = get_user_model()
    staff = users.objects.create_user(username='editor', password='Test-only-secret!47', is_staff=True)
    journalist = users.objects.create_user(username='journalist', password='Test-only-secret!47')
    other = users.objects.create_user(username='other-journalist')
    reader = users.objects.create_user(username='reader')
    group, _ = Group.objects.get_or_create(name='journalists')
    journalist.groups.add(group)
    other.groups.add(group)
    return staff, journalist, other, reader


@pytest.fixture
def article():
    source = Source.objects.create(name='Fixture publisher', url='https://example.org', is_active=True)
    return Article.objects.create(source=source, title='Original source title', url='https://example.org/source', category='article')


def payload(article):
    return {'title': 'Autorska nitka', 'items': [{'article_id': article.pk, 'editorial_note': 'Komentarz autora'}]}


def listed(response):
    data = response.json()
    return data if isinstance(data, list) else data['results']


def test_journalist_can_create_own_draft_staff_can_approve(people, article):
    staff, author, other, reader = people
    client = APIClient()
    for user in (None, reader):
        client.force_authenticate(user)
        assert client.post('/api/editor/threads/', payload(article), format='json').status_code == 403
    client.force_authenticate(author)
    response = client.post('/api/editor/threads/', payload(article), format='json')
    assert response.status_code == 201, response.data
    thread = Thread.objects.get(slug=response.data['slug'])
    assert thread.created_by_id == author.pk and not thread.published and not thread.is_featured
    assert client.get(f'/api/threads/{thread.slug}/').status_code == 404
    assert client.patch(f'/api/editor/threads/{thread.slug}/', {'description': 'Uzupełnienie'}, format='json').status_code == 200
    client.force_authenticate(staff)
    assert client.patch(f'/api/editor/threads/{thread.slug}/', {'published': True, 'is_featured': True}, format='json').status_code == 200
    client.force_authenticate(None)
    detail = client.get(f'/api/threads/{thread.slug}/').json()
    assert detail['author_name'] == author.username and detail['author_role'] == 'journalist'
    assert detail['items'][0]['author_role'] == 'journalist'
    assert detail['is_sponsored'] is False and detail['sponsorship_label'] == ''


def test_journalist_list_and_mutations_are_owner_scoped(people, article):
    staff, author, other, _ = people
    own = Thread.objects.create(title='My draft', created_by=author)
    foreign = Thread.objects.create(title='Other draft', created_by=other)
    editorial = Thread.objects.create(title='Staff draft', created_by=staff)
    published = Thread.objects.create(title='Other published', created_by=other, published=True)
    client = APIClient()
    client.force_authenticate(author)
    assert [row['id'] for row in listed(client.get('/api/editor/threads/'))] == [own.pk]
    for thread in (foreign, editorial, published):
        assert client.get(f'/api/editor/threads/{thread.slug}/').status_code == 404
        assert client.patch(f'/api/editor/threads/{thread.slug}/', {'title': 'Take over'}, format='json').status_code == 404
    client.force_authenticate(staff)
    assert len(listed(client.get('/api/editor/threads/'))) == 4
    assert client.patch(f'/api/editor/threads/{foreign.slug}/', {'description': 'Redakcja'}, format='json').status_code == 200
    foreign.refresh_from_db()
    assert foreign.created_by_id == other.pk


@pytest.mark.parametrize('key,value', [
    ('published', True), ('published', False), ('is_featured', False),
    ('editorial_slot', ''), ('editorial_slot', 'government'), ('is_sponsored', True),
    ('is_sponsored', False), ('sponsor_name', ''), ('sponsor_name', 'Firma testowa'),
    ('created_by', 1), ('thread_type', 'sponsored'),
])
def test_journalist_must_omit_staff_owned_fields(people, article, key, value):
    _, author, _, _ = people
    client = APIClient()
    client.force_authenticate(author)
    data = {**payload(article), key: value}
    response = client.post('/api/editor/threads/', data, format='json')
    assert response.status_code == 400, response.data
    assert Thread.objects.count() == 0
    thread = Thread.objects.create(title='Draft', created_by=author)
    assert client.patch(f'/api/editor/threads/{thread.slug}/', {key: value}, format='json').status_code == 400


def test_journalist_edit_withdraws_publication_without_changing_sponsor_or_source(people, article):
    _, author, _, _ = people
    original = Article.objects.filter(pk=article.pk).values().get()
    thread = Thread.objects.create(title='Reviewed story', created_by=author, published=True, is_featured=True,
                                   is_sponsored=True, sponsor_name='Fixture sponsor')
    ThreadItem.objects.create(thread=thread, article=article)
    client = APIClient()
    client.force_authenticate(author)
    assert client.patch(f'/api/editor/threads/{thread.slug}/', {'description': 'New comment'}, format='json').status_code == 200
    thread.refresh_from_db()
    assert not thread.published and not thread.is_featured
    assert thread.is_sponsored and thread.sponsor_name == 'Fixture sponsor'
    assert client.get(f'/api/threads/{thread.slug}/').status_code == 404
    assert Article.objects.filter(pk=article.pk).values().get() == original


def test_author_save_does_not_overwrite_concurrent_staff_sponsorship(people):
    from types import SimpleNamespace
    _, author, _, _ = people
    thread = Thread.objects.create(title='Concurrent draft', created_by=author)
    serializer = WriteThreadSerializer(thread, data={'description': 'Author edit'}, partial=True,
                                       context={'request': SimpleNamespace(user=author)})
    assert serializer.is_valid(), serializer.errors
    Thread.objects.filter(pk=thread.pk).update(is_sponsored=True, sponsor_name='New staff label')
    serializer.save()
    thread.refresh_from_db()
    assert thread.is_sponsored and thread.sponsor_name == 'New staff label'


def test_staff_sponsorship_requires_label_and_is_exposed_on_every_box(people, article):
    staff, _, _, _ = people
    client = APIClient()
    client.force_authenticate(staff)
    for name in ('', '  '):
        assert client.post('/api/editor/threads/', {**payload(article), 'is_sponsored': True, 'sponsor_name': name}, format='json').status_code == 400
    data = {**payload(article), 'is_sponsored': True, 'sponsor_name': '  Fixture sponsor  '}
    response = client.post('/api/editor/threads/', data, format='json')
    assert response.status_code == 201, response.data
    slug = response.data['slug']
    assert client.get(f'/api/threads/{slug}/').status_code == 404
    assert client.patch(f'/api/editor/threads/{slug}/', {'published': True}, format='json').status_code == 200
    client.force_authenticate(None)
    detail = client.get(f'/api/threads/{slug}/').json()
    for obj in (detail, *detail['items']):
        assert obj['is_sponsored'] is True
        assert obj['sponsor_name'] == 'Fixture sponsor'
        assert obj['sponsorship_label'] == 'Materiał sponsorowany · Fixture sponsor'
    assert detail['items'][0]['article']['category'] == 'article'
    client.force_authenticate(staff)
    assert client.patch(f'/api/editor/threads/{slug}/', {'is_sponsored': False}, format='json').status_code == 200
    thread = Thread.objects.get(slug=slug)
    assert not thread.is_sponsored and thread.sponsor_name == ''


def test_database_and_admin_block_unnamed_published_sponsorship():
    for data in ({'is_sponsored': True}, {'thread_type': 'sponsored'}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Thread.objects.create(title='No sponsor label', published=True, **data)
    thread = Thread(title='Blank sponsor', published=True, is_sponsored=True, sponsor_name='   ')
    with pytest.raises(ValidationError):
        thread.clean()


@pytest.mark.parametrize('login_url', ['/api/auth/login/', '/api/account/login/'])
def test_journalist_login_me_and_separate_admin_rights(people, login_url):
    _, author, _, _ = people
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get('/api/auth/csrf/').json()['csrfToken']
    response = client.post(login_url, {'username': author.username, 'password': 'Test-only-secret!47'}, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200, response.content
    me = client.get('/api/me/').json()
    assert me['is_editor'] and me['is_journalist'] and me['can_edit_threads']
    assert not me['can_publish'] and not me['can_manage_sponsorship']
    assert me['role'] == 'journalist'
    csrf = client.get('/api/auth/csrf/').json()['csrfToken']
    for url in ('/api/editor/articles/', '/api/editor/sources/'):
        assert client.post(url, {}, format='json', HTTP_X_CSRFTOKEN=csrf).status_code == 403
    assert client.get('/admin/').status_code == 302
    author.groups.clear()
    assert client.get('/api/editor/threads/').status_code == 403
    assert not client.get('/api/me/').json()['is_editor']


def test_signup_cannot_self_grant_journalist_role():
    client = APIClient()
    response = client.post('/api/account/register/', {
        'username': 'self_appointed', 'password': 'SecreT~unique~942!',
        'groups': ['journalists'], 'role': 'journalist', 'is_journalist': True, 'is_staff': True,
    }, format='json')
    assert response.status_code == 201, response.data
    user = get_user_model().objects.get(username='self_appointed')
    assert not user.groups.exists() and not user.is_staff
    assert client.get('/api/editor/threads/').status_code == 403
