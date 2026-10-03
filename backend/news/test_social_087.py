import base64
import hashlib
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from news.account_models import AccountIdentity, PersonalContextThread, UserXConnection
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis
from news.community_models import CommunityLink
from news.daily_schedule import check_narrative, at, BEAT_PLAN
from news.narrative_threads import build_narratives, candidates
from news.notification_models import Notification
from news.political_models import PoliticalAccount, PoliticalPost
from news.test_thread_social import user, setup
from news.thread_social_models import ThreadComment, ThreadCommentReaction
from news.x_accounts import SESSION
from news.x_link_cards import x_post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offline(settings, monkeypatch):
    settings.THREADS_ENABLED = settings.ACCOUNTS_ENABLED = True
    settings.X_OAUTH_CLIENT_ID, settings.X_OAUTH_CLIENT_SECRET = 'client', 'secret'
    cache.clear()
    def forbidden(*args, **kwargs):
        pytest.fail('Network/AI is forbidden in 087 tests')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('news.clinic_ai._free_chat', forbidden)
    monkeypatch.setattr('news.clinic_ai.diagnose', forbidden)
    monkeypatch.setattr('news.account_lifecycle.queue_verification', lambda *a: None)


def test_reaction_unique_undo_grouped_and_private(setup):
    client, thread, reader, author, base = setup
    row = ThreadComment.objects.create(thread=thread, author=author, body='Komentarz')
    url = base + f'comments/{row.pk}/reaction/'
    for _ in range(2):
        response = client.post(url, {})
        assert response.status_code == 200 and response.data['reactions_count'] == 1 and response.data['reacted']
    assert ThreadCommentReaction.objects.count() == 1
    client.force_authenticate(user('second'))
    client.post(url, {})
    notification = Notification.objects.get(user=author, kind='comment_reaction')
    assert notification.title.startswith('2 ')
    assert client.delete(url).data['reactions_count'] == 1
    assert Notification.objects.filter(user=author).count() == 1
    client.force_authenticate(reader)
    assert client.delete(url).data['reactions_count'] == 0
    assert not Notification.objects.filter(user=author).exists()
    client.force_authenticate(None)
    assert client.post(url, {}).status_code == 403
    client.force_authenticate(reader)
    row.hidden_at = timezone.now()
    row.save()
    assert client.post(url, {}).status_code == 404


def test_comments_grouped_and_best_freshness(setup):
    client, thread, reader, author, base = setup
    for _ in range(3):
        assert client.post(base+'comments/', {'body': 'Kontekst'}).status_code == 201
    assert Notification.objects.filter(user=author, kind='thread_reply').count() == 1
    from news.notification_tasks import process_notification_events
    process_notification_events()
    assert Notification.objects.filter(user=author, kind='thread_reply').count() == 1
    assert Notification.objects.get(user=author).title.endswith('3')
    rows = list(thread.comments.all())
    rows[0].created_at = timezone.now() - timedelta(days=30)
    rows[0].save()
    for row in rows[:2]:
        ThreadCommentReaction.objects.create(user=author, comment=row)
    best = client.get(base+'comments/').data['results']
    assert best[0]['id'] == rows[1].pk
    assert client.get(base+'comments/?sort=new').data['results'][0]['id'] == rows[2].pk
    assert client.get(base+'comments/?sort=invalid').status_code == 400


def mock_x(monkeypatch, x_id='123', handle='reader_x'):
    token, profile = Mock(), Mock()
    token.json.return_value = {'access_token': 'never-store'}
    profile.json.return_value = {'data': {'id': x_id, 'username': handle}}
    post, get = Mock(return_value=token), Mock(return_value=profile)
    monkeypatch.setattr('news.x_accounts.requests.post', post)
    monkeypatch.setattr('news.x_accounts.requests.get', get)
    return post, get


def start(client, mode='login', consent=True):
    response = client.get('/api/account/x/start/', {'mode': mode,
        'accepted_terms': str(consent).lower(), 'adult': str(consent).lower()})
    assert response.status_code == 302
    return parse_qs(urlsplit(response['Location']).query)


def callback(client, state):
    return client.get('/api/account/x/callback/', {'state': state, 'code': 'code'})


def test_oauth_pkce_register_login_replay_and_no_tokens(monkeypatch):
    client = APIClient()
    post, get = mock_x(monkeypatch)
    query = start(client)
    flow = client.session[SESSION]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(flow['verifier'].encode()).digest()).rstrip(b'=').decode()
    assert query['code_challenge'] == [challenge] and query['code_challenge_method'] == ['S256']
    assert set(query['scope'][0].split()) == {'users.read', 'tweet.read'}
    assert query['redirect_uri'][0].endswith('/api/account/x/callback/')
    assert not callback(client, flow['state'])['Location'].endswith('failed')
    connection = UserXConnection.objects.get()
    assert client.session['_auth_user_id'] == str(connection.user_id)
    assert not connection.user.account_identity.email_verified and connection.user.account_identity.email is None
    assert 'never-store' not in str(connection.__dict__) + str(dict(client.session))
    assert post.call_args.kwargs['data']['code_verifier'] == flow['verifier']
    assert post.call_args.kwargs['auth'] == ('client', 'secret')
    assert callback(client, flow['state'])['Location'].endswith('failed')
    assert post.call_count == 1
    client.logout()
    query = start(client, consent=False)
    callback(client, query['state'][0])
    assert client.session['_auth_user_id'] == str(connection.user_id)
    assert UserXConnection.objects.count() == 1


@pytest.mark.parametrize('bad', ['state', 'expired', 'cancel', 'session'])
def test_oauth_rejects_without_network(bad):
    client = APIClient()
    query = start(client)
    state = query['state'][0]
    if bad == 'state':
        state = 'wrong'
    if bad == 'expired':
        session = client.session
        flow = session[SESSION]
        flow['created'] -= 601
        session[SESSION] = flow
        session.save()
    if bad == 'session':
        client = APIClient()
    response = client.get('/api/account/x/callback/', {'state': state, 'code': 'code', **({'error': 'denied'} if bad == 'cancel' else {})})
    assert response['Location'].endswith('failed')
    assert not UserXConnection.objects.exists()


def test_oauth_unique_disconnect_display_and_first_email(monkeypatch, settings, setup):
    client, thread, reader, author, base = setup
    reader.set_password('valid-password-987')
    reader.save()
    client.force_authenticate(None)
    client.force_login(reader)
    mock_x(monkeypatch)
    state = start(client, 'connect')['state'][0]
    assert callback(client, state)['Location'].endswith('connected')
    assert client.patch('/api/account/x-connection/', {'use_x_name': True}, format='json').status_code == 200
    row = client.post(base+'comments/', {'body': 'Kontekst'}).data
    assert row['author'] == '@reader_x' and row['x_profile'] == 'https://x.com/reader_x'
    second = APIClient()
    second.force_login(author)
    assert callback(second, start(second, 'connect')['state'][0])['Location'].endswith('failed')
    assert UserXConnection.objects.count() == 1
    assert client.delete('/api/account/x-connection/').status_code == 204
    assert not UserXConnection.objects.exists()
    settings.X_OAUTH_CLIENT_SECRET = ''
    assert not client.get('/api/account/me/').data['x_enabled']
    assert not client.get('/api/account/x-connection/').data['oauth_enabled']
    assert client.get('/api/account/x/start/').status_code == 404


def test_x_account_can_add_email_and_cannot_lock_itself_out(monkeypatch):
    client = APIClient()
    mock_x(monkeypatch)
    callback(client, start(client)['state'][0])
    assert client.delete('/api/account/x-connection/').status_code == 400
    assert client.patch('/api/account/me/', {'email': 'new@example.org'}, format='json').status_code == 200
    assert AccountIdentity.objects.get().email == 'new@example.org'
    assert not AccountIdentity.objects.get().email_verified


def message(camp='government', count=3, author_count=2, tone=True):
    today = timezone.localdate()
    obj = ClinicDailyMessage.objects.create(day=today, camp=camp, status='approved', message='Podatki i budżet')
    accounts = [PoliticalAccount.objects.create(user_id=str(1000 + i + (100 if camp == 'opposition' else 0)),
        handle=f'{camp}{i}', display_name=f'Autor {i}', camp=camp) for i in range(author_count)]
    posts = [PoliticalPost.objects.create(account=accounts[i % author_count], post_id=str(10000+obj.pk*100+i),
        url=f'https://x.com/autor/status/{10000+obj.pk*100+i}', text='Budżet obejmuje podatki i wspólne wydatki 120 mln zł.',
        published_at=timezone.now(), camp_at_collection=camp) for i in range(count)]
    obj.posts.set(posts)
    obj.points = [{'title': 'Podatki i budżet', 'summary': 'Podatki obejmują wydatki.', 'post_ids': [str(p.pk) for p in posts], 'authors': ['Autor 0', 'Autor 1']}]
    obj.tone = [{'post_id': str(p.pk), 'label': 'atak'} for p in posts] if tone else []
    obj.save()
    return obj, posts


def test_narratives_both_camps_idempotent_schedule_and_featured():
    gov, posts = message()
    opp, _ = message('opposition', count=4)
    SpinDiagnosis.objects.create(post=posts[0], status='approved', headline='Diagnoza podatków', intensity=85, verdict='spin')
    result = build_narratives()
    assert set(result['threads']) == {'government', 'opposition'}
    threads = PersonalContextThread.objects.filter(narrative_message__isnull=False)
    assert threads.count() == 2
    before = list(threads.values_list('id', flat=True))
    for thread in threads:
        rows = list(thread.items.all())
        assert 3 <= len(rows) <= 8 and rows[-1].box_data['box_type'] == 'message'
        assert all(row.link_note and len(row.link_note) <= 200 for row in rows[1:])
        if thread.narrative_message_id == gov.pk:
            assert rows[-2].box_data['box_type'] == 'diagnosis'
    build_narratives()
    assert set(before) == set(threads.values_list('id', flat=True))
    assert check_narrative(at(timezone.now(), 22, 30))[0] == 'done'
    assert BEAT_PLAN['narrative-thread-daily'][1] == {'hour': 21, 'minute': 45}
    featured = APIClient().get('/api/community/threads/?featured=1').data['results'][0]
    assert featured['id'] == opp.narrative_thread.pk
    gov.status = opp.status = 'rejected'
    gov.save(); opp.save()
    assert APIClient().get('/api/community/threads/?featured=1').data['results'][0]['diagnosis_id'] is not None


@pytest.mark.parametrize('count,authors,tone', [(2, 2, True), (3, 1, True), (3, 2, False)])
def test_narrative_criterion_and_na(count, authors, tone):
    obj, _ = message(count=count, author_count=authors, tone=tone)
    assert not candidates(obj)
    assert build_narratives()['status'] == 'not_applicable'
    assert check_narrative(at(timezone.now(), 22, 30))[0] == 'na'
    assert not PersonalContextThread.objects.filter(narrative_message__isnull=False).exists()


def test_narrative_one_side_and_unavailable_posts():
    obj, posts = message()
    result = build_narratives()
    assert list(result['threads']) == ['government']
    posts[0].available = False
    posts[0].save()
    assert not candidates(obj)
    build_narratives()
    assert not PersonalContextThread.objects.get(narrative_message=obj).is_public


@pytest.mark.parametrize('host', ['x.com', 'twitter.com', 'mobile.twitter.com'])
def test_x_urls(host):
    assert x_post(f'https://{host}/Example/status/123456?s=20&ref_src=foo') == ('123456', 'https://x.com/Example/status/123456')
    assert not x_post(f'https://{host}.evil.test/Example/status/123456')


def test_x_card_from_database_diagnosis_no_budget(setup):
    client, *_ = setup
    obj, posts = message()
    post = posts[0]
    d = SpinDiagnosis.objects.create(post=post, status='approved', headline='Diagnoza', intensity=70, verdict='spin')
    before = SpinDiagnosis.objects.count()
    response = client.post('/api/community/links/', {'url': post.url}, format='json')
    assert response.status_code == 200
    assert response.data['item']['diagnosis_id'] == d.pk
    assert response.data['item']['intensity'] == 70 and response.data['item']['box_type'] == 'post'
    assert SpinDiagnosis.objects.count() == before
    post.available = False
    post.save()
    response = client.post('/api/community/links/', {'url': post.url}, format='json')
    assert 'body' not in response.data['item'] and 'diagnosis_id' not in response.data['item']


def test_oembed_mock_cache_error_no_ai(setup, monkeypatch):
    client, *_ = setup
    response = Mock()
    response.json.return_value = {'author_name': 'Autorka', 'author_url': 'https://twitter.com/autorka',
        'html': '<blockquote><p>Tekst &amp; dane<br>ze źródła.</p><a href="https://x.com/autorka/status/777">October 3, 2026</a></blockquote><script>evil()</script>'}
    get = Mock(return_value=response)
    monkeypatch.setattr('news.x_link_cards.requests.get', get)
    for host in ('x.com', 'twitter.com', 'mobile.twitter.com'):
        data = client.post('/api/community/links/', {'url': f'https://{host}/autorka/status/777?s=20'}, format='json').data['item']
        assert data['body'] == 'Tekst & dane ze źródła.'
        assert data['x_handle'] == 'autorka' and data['published_date'].startswith('2026-10-03')
    assert get.call_count == 1 and CommunityLink.objects.count() == 4  # three setup links + one cached post
    assert get.call_args.args[0] == 'https://publish.twitter.com/oembed'
    assert not SpinDiagnosis.objects.exists()
    get.side_effect = requests.RequestException('offline')
    assert client.post('/api/community/links/', {'url': 'https://x.com/a/status/888'}, format='json').status_code == 422
    result = client.post('/api/community/links/', {'url': 'https://x.com/a/status/888', 'title': 'Mój tytuł'}, format='json')
    assert result.status_code == 200 and result.data['item']['title'] == 'Mój tytuł'
    assert 'box_type' not in result.data['item']


def test_thread_api_limits_continuation_and_old_records(setup):
    client, thread, reader, author, base = setup
    client.force_authenticate(author)
    links = [CommunityLink.objects.create(canonical_url=f'https://example.org/limit/{i}', domain='example.org', title=str(i)) for i in range(11)]
    endpoint = '/api/account/context-threads/'
    payload = {'title': 'Nowa', 'items': [{'link_id': link.pk} for link in links], 'is_public': True}
    assert client.post(endpoint, payload, format='json').status_code == 400
    payload['items'] = payload['items'][:10]
    assert client.post(endpoint, payload, format='json').status_code == 201
    # Existing long threads remain readable and metadata can still be edited.
    from news.account_models import PersonalContextThreadItem
    for i, link in enumerate(links, start=3):
        PersonalContextThreadItem.objects.create(thread=thread, link=link, position=i)
    assert client.get(endpoint+f'{thread.pk}/').status_code == 200
    assert client.patch(endpoint+f'{thread.pk}/', {'title': 'Starsza długa nitka'}, format='json').status_code == 200
    last = thread.items.last()
    payload = {'title': 'Kontynuacja', 'continues': thread.pk, 'items': [{'link_id': last.link_id}]}
    result = client.post(endpoint, payload, format='json')
    assert result.status_code == 201 and result.data['continues'] == thread.pk
    payload['items'] = [{'link_id': links[0].pk}]
    assert client.post(endpoint, payload, format='json').status_code == 400
    client.force_authenticate(reader)
    payload['items'] = [{'link_id': last.link_id}]
    assert client.post(endpoint, payload, format='json').status_code == 400


def test_diagnosis_rebuild_command_idempotent():
    from news.test_diagnosis_threads import diagnosis
    row = diagnosis(claims=[])
    thread = row.context_thread
    thread.items.filter(box_data__box_type='technique').delete()
    out = StringIO()
    call_command('drspin_diagnosis_threads', stdout=out)
    ids = list(thread.items.values_list('pk', flat=True))
    assert len(ids) == 3
    call_command('drspin_diagnosis_threads', stdout=out)
    assert list(thread.items.values_list('pk', flat=True)) == ids


def test_oauth_provider_failure_and_no_consent(monkeypatch):
    client = APIClient()
    post, _ = mock_x(monkeypatch)
    assert callback(client, start(client, consent=False)['state'][0])['Location'].endswith('failed')
    assert not UserXConnection.objects.exists()
    post.side_effect = requests.RequestException('provider unavailable')
    assert callback(client, start(client)['state'][0])['Location'].endswith('failed')
    assert not UserXConnection.objects.exists()


def test_continuation_links_respect_publication(setup):
    client, thread, _, author, base = setup
    client.force_authenticate(author)
    links = list(thread.items.values_list('link_id', flat=True))
    response = client.post('/api/account/context-threads/', {'title': 'Dalszy kontekst', 'continues': thread.pk,
        'items': [{'link_id': links[-1]}, {'link_id': links[0]}], 'is_public': True}, format='json')
    assert response.status_code == 201
    pk = response.data['id']
    assert client.get(base).data['continuations'] == [pk]
    assert client.get(f'/api/community/threads/{pk}/').data['continues'] == thread.pk
    PersonalContextThread.objects.filter(pk=pk).update(is_public=False)
    assert client.get(base).data['continuations'] == []


def test_narrative_strongest_and_limits():
    obj, posts = message(count=8, author_count=5)
    for i, post in enumerate(posts[:2]):
        SpinDiagnosis.objects.create(post=post, status='approved', headline='Podatki', intensity=60+i*20, verdict='spin')
    build_narratives()
    rows = list(obj.narrative_thread.items.all())
    assert len(rows) == 6
    assert len({row.box_data['source_name'] for row in rows[:4]}) == 4
    assert rows[-2].box_data['diagnosis_id'] == SpinDiagnosis.objects.get(intensity=80).pk
    assert all(len(row.box_data['body']) <= 400 and len(row.box_data['title']) <= 80 and len(row.link_note) <= 200 for row in rows)


def test_account_export_includes_x_and_comment_reactions(monkeypatch, setup):
    client, thread, reader, author, base = setup
    UserXConnection.objects.create(user=reader, x_user_id='111', username='reader_x', use_x_name=True)
    row = ThreadComment.objects.create(thread=thread, author=author, body='Tekst')
    client.post(base+f'comments/{row.pk}/reaction/', {})
    result = client.get('/api/account/export/').json()
    assert result['x_connection']['username'] == 'reader_x'
    assert result['comment_reactions'][0]['comment_id'] == row.pk
