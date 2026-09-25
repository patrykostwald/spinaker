import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from news.community import canonical_url
from news.community_models import CommunityLink
from news.models import Article, Source


def user(name='czytelnik'):
    return get_user_model().objects.create_user(name, password='x')


def article(url='https://www.gov.pl/web/premier/komunikat'):
    source = Source.objects.create(name='KPRM', url='https://www.gov.pl/web/premier', is_active=True)
    return Article.objects.create(source=source, title='Komunikat KPRM', url=url, published_date=timezone.now())


def test_canonical_url_drops_tracking_www_fragment_and_slash():
    assert canonical_url('http://WWW.Onet.pl/news/abc/?utm_source=x&b=2&a=1#top') == 'https://onet.pl/news/abc?a=1&b=2'
    assert canonical_url('https://onet.pl/news/abc') == canonical_url('https://www.onet.pl/news/abc/?fbclid=1')


@pytest.mark.django_db
def test_link_already_in_base_returns_the_existing_box():
    item = article()
    client = APIClient()
    client.force_authenticate(user())
    response = client.post('/api/community/links/', {'url': 'https://gov.pl/web/premier/komunikat/?utm_medium=x'}, format='json')
    assert response.status_code == 200
    assert response.json()['item'] == {**response.json()['item'], 'kind': 'article', 'id': item.pk}


@pytest.mark.django_db
def test_new_link_needs_a_title_and_is_deduplicated():
    client = APIClient()
    client.force_authenticate(user())
    url = '/api/community/links/'
    missing = client.post(url, {'url': 'https://www.onet.pl/wiadomosci/sprawa'}, format='json')
    assert missing.status_code == 422 and missing.json()['needs_title'] is True
    created = client.post(url, {'url': 'https://www.onet.pl/wiadomosci/sprawa', 'title': 'Tytuł ze strony'}, format='json')
    assert created.status_code == 201 and created.json()['item']['kind'] == 'link'
    again = client.post(url, {'url': 'https://onet.pl/wiadomosci/sprawa/?utm_source=fb', 'title': 'Inny tytuł'}, format='json')
    assert again.json()['status'] == 'existing_link'
    assert CommunityLink.objects.count() == 1
    assert CommunityLink.objects.get().title == 'Tytuł ze strony' and CommunityLink.objects.get().title_origin == 'reader'
    assert not Article.objects.filter(url__icontains='onet.pl').exists()


@pytest.mark.django_db
def test_publish_thread_with_article_and_link_then_react():
    owner = user('autorka')
    base = article()
    link = CommunityLink.objects.create(canonical_url='https://onet.pl/a', domain='onet.pl', title='Artykuł spoza bazy')
    client = APIClient()
    client.force_authenticate(owner)
    too_short = client.post('/api/account/context-threads/', {'title': 'Sprawa', 'is_public': True,
                                                              'items': [{'article_id': base.pk}]}, format='json')
    assert too_short.status_code == 400
    response = client.post('/api/account/context-threads/', {
        'title': 'Sprawa mostu', 'is_public': True,
        'items': [{'article_id': base.pk, 'note': 'tu się zaczyna'}, {'link_id': link.pk}],
    }, format='json')
    assert response.status_code == 201
    thread_id = response.json()['id']
    assert response.json()['published_at'] is not None
    assert [row['kind'] for row in response.json()['elements']] == ['article', 'link']

    public = APIClient()
    listed = public.get('/api/community/threads/').json()['results']
    assert [row['id'] for row in listed] == [thread_id] and listed[0]['author'] == 'autorka'
    detail = public.get(f'/api/community/threads/{thread_id}/').json()
    assert detail['items'][0]['note'] == 'tu się zaczyna'

    reader = APIClient()
    reader.force_authenticate(user('czytelnik2'))
    opinions = f'/api/community/threads/{thread_id}/opinions/'
    assert reader.post(opinions, {'body': 'sam komentarz'}, format='json').status_code == 400
    assert reader.post(opinions, {'polarity': 'positive', 'body': 'Dobre zestawienie'}, format='json').status_code == 201
    assert public.get(opinions).json()['counts'] == {'positive': 1, 'negative': 0}
    assert reader.post(f'/api/community/threads/{thread_id}/report/', {'reason': 'spam'}, format='json').status_code == 201


@pytest.mark.django_db
def test_private_and_hidden_threads_are_not_public():
    owner = user('autor')
    base = article()
    link = CommunityLink.objects.create(canonical_url='https://onet.pl/b', domain='onet.pl', title='B')
    client = APIClient()
    client.force_authenticate(owner)
    private = client.post('/api/account/context-threads/', {'title': 'Prywatna', 'items': [{'article_id': base.pk}, {'link_id': link.pk}]}, format='json').json()
    assert APIClient().get(f'/api/community/threads/{private["id"]}/').status_code == 404
    public = client.patch(f'/api/account/context-threads/{private["id"]}/', {'is_public': True}, format='json')
    assert public.status_code == 200
    assert APIClient().get(f'/api/community/threads/{private["id"]}/').status_code == 200
    from news.account_models import PersonalContextThread
    PersonalContextThread.objects.filter(pk=private['id']).update(hidden_at=timezone.now())
    assert APIClient().get(f'/api/community/threads/{private["id"]}/').status_code == 404


@pytest.mark.django_db
def test_legacy_article_ids_still_work():
    owner = user('stary')
    base = article()
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post('/api/account/context-threads/', {'title': 'Stara', 'article_ids': [base.pk]}, format='json')
    assert response.status_code == 201
    assert [row['id'] for row in response.json()['articles']] == [base.pk]


@pytest.mark.django_db
def test_my_reactions_collects_every_part_of_the_site():
    from news.account_models import ArticleOpinion
    reader = user('czytelniczka')
    base = article()
    ArticleOpinion.objects.create(user=reader, article=base, polarity='positive', body='Dobre źródło')
    client = APIClient()
    assert client.get('/api/account/reactions/').status_code in (401, 403)
    client.force_authenticate(reader)
    data = client.get('/api/account/reactions/').json()
    assert data['counts']['material'] == 1 and data['comments'] == 1
    assert data['results'][0]['target'] == {'title': 'Komunikat KPRM', 'href': f'/material/{base.pk}'}
