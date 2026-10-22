from datetime import timedelta
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from news.account_models import AccountIdentity, ProfilePreference, MutedUser
from news.thread_social_models import ThreadComment, ThreadModerationReport
from news.community_models import CommunityThreadOpinion
from news.interview_vote_models import InterviewBallot, InterviewCandidate, InterviewVote
from news.test_notifications import public_thread

pytestmark = pytest.mark.django_db
PASSWORD = 'Str0ng~unique~086!'

@pytest.fixture(autouse=True)
def offline(settings, monkeypatch):
    settings.ACCOUNTS_ENABLED = settings.THREADS_ENABLED = True
    settings.PUSH_ENABLED = False
    cache.clear()
    def forbidden(*args, **kwargs):
        pytest.fail('Real external calls are forbidden')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('news.account_lifecycle.queue_verification', lambda email: None)
    monkeypatch.setattr('news.thread_moderation.deliver_mail', lambda *a: None)

def user(name):
    row = get_user_model().objects.create_user(name, email=f'{name}@example.org', password=PASSWORD)
    AccountIdentity.objects.create(user=row, email=row.email, email_verified=True)
    return row

@pytest.fixture
def setup():
    owner, other = user('owner'), user('other')
    client = APIClient()
    client.force_authenticate(owner)
    return client, owner, other

def test_nick_cooldown_and_boundary(setup):
    client, owner, other = setup
    url = '/api/account/profile/'
    assert client.patch(url, {'username': 'Fresh_Nick', 'bio': 'Moje bio'}, format='json').status_code == 200
    owner.refresh_from_db()
    assert owner.username == 'fresh_nick'
    assert client.patch(url, {'username': 'another'}, format='json').status_code == 400
    assert client.patch(url, {'bio': 'Nowe bio'}, format='json').status_code == 200
    now = timezone.now()
    ProfilePreference.objects.filter(user=owner).update(nick_changed_at=now-timedelta(days=30))
    with patch('news.profiles.timezone.now', return_value=now):
        assert client.patch(url, {'username': 'OTHER'}, format='json').status_code == 400
        assert client.patch(url, {'username': 'another'}, format='json').status_code == 200
    assert client.patch(url, {'username': 'bad/nick'}, format='json').status_code == 400
    assert client.patch(url, {'bio': 'x'*161}, format='json').status_code == 400

def test_public_profile_visibility_and_private_drafts(setup):
    client, owner, other = setup
    thread = public_thread(owner)
    draft = public_thread(owner)
    draft.is_public = False
    draft.save()
    ThreadComment.objects.create(thread=thread, author=owner, body='@boks 2 treść')
    ThreadComment.objects.create(thread=draft, author=owner, body='tajne')
    public = APIClient()
    data = public.get('/api/profiles/owner/').data
    assert [row['id'] for row in data['threads']['results']] == [thread.pk]
    assert data['comments']['results'] == []
    assert not {'email', 'nick_change_available_at'} & data.keys()
    client.patch('/api/account/profile/', {'public_activity': True}, format='json')
    data = public.get('/api/profiles/owner/').data
    assert len(data['comments']['results']) == 1
    assert data['comments']['results'][0]['box_references'] == [2]
    client.patch('/api/account/profile/', {'public_activity': False}, format='json')
    assert public.get('/api/profiles/owner/').data['comments']['results'] == []

def test_mute_feed_comments_profile_and_unmute(setup):
    client, owner, other = setup
    other_thread = public_thread(other)
    mine = public_thread(owner)
    ThreadComment.objects.create(thread=mine, author=other, body='hidden for owner')
    ThreadComment.objects.create(thread=mine, author=owner, body='visible')
    assert client.post('/api/account/mutes/', {'user_id': owner.pk}).status_code == 400
    for _ in range(2):
        assert client.post('/api/account/mutes/', {'user_id': other.pk}).status_code == 200
    assert MutedUser.objects.count() == 1
    assert other_thread.pk not in [r['id'] for r in client.get('/api/community/threads/').data['results']]
    assert len(client.get(f'/api/community/threads/{mine.pk}/comments/').data['results']) == 1
    assert client.get('/api/profiles/other/').data['muted']
    assert len(APIClient().get(f'/api/community/threads/{mine.pk}/comments/').data['results']) == 2
    assert client.delete(f'/api/account/mutes/{other.pk}/').status_code == 204
    assert not client.get('/api/profiles/other/').data['muted']

def test_activity_filter_and_export_all_contents(setup):
    client, owner, other = setup
    thread = public_thread(other)
    own = public_thread(owner)
    own.items.filter(position=1).update(link_note='Powiązanie')
    ThreadComment.objects.create(thread=thread, author=owner, body='@boks 2 komentarz')
    CommunityThreadOpinion.objects.create(thread=thread, user=owner, polarity='doubt')
    ballot = InterviewBallot.objects.create(day=timezone.now().date())
    candidate = InterviewCandidate.objects.create(ballot=ballot, video_id='abcdefghijk', title='Wywiad')
    InterviewVote.objects.create(ballot=ballot, candidate=candidate, user=owner)
    ThreadModerationReport.objects.create(thread=thread, reporter=owner, target_author=other, reason='spam', snapshot='treść')
    for kind in ('ratings', 'comments', 'votes'):
        data = client.get(f'/api/account/activity/?kind={kind}').data
        assert len(data['results']) == 1
        assert data['results'][0]['kind'] == kind
    assert len(client.get('/api/account/activity/').data['results']) == 3
    assert client.get('/api/account/activity/?page=bad').status_code == 400
    exported = client.get('/api/account/export/').json()
    assert len(exported['thread_comments']) == len(exported['interview_votes']) == len(exported['moderation_reports']) == 1
    assert exported['opinions']['community'][0]['polarity'] == 'doubt'
    assert exported['threads'][0]['items'][1]['link_note'] == 'Powiązanie'
    assert 'email' not in client.get('/api/profiles/other/').data

def test_adult_required_and_newsletter_optional():
    client = APIClient()
    data = {'username': 'adultuser', 'email': 'new@example.org', 'password': PASSWORD, 'accepted_terms': True}
    for value in (None, False):
        response = client.post('/api/account/register/', data | ({'adult': value} if value is not None else {}), format='json')
        assert response.status_code == 400
    assert client.post('/api/account/register/', data | {'adult': True}, format='json').status_code == 201
    identity = AccountIdentity.objects.get(email=data['email'])
    assert identity.adult_declared_at and identity.newsletter_consent_at is None
    assert client.post('/api/account/register/', data | {'username': 'newsuser', 'email': 'news@example.org', 'adult': True, 'newsletter': True}, format='json').status_code == 201
    assert AccountIdentity.objects.get(email='news@example.org').newsletter_consent_at

def test_reports_access_and_single_appeal(setup):
    client, owner, other = setup
    moderator = user('moderator')
    moderator.is_staff = moderator.is_superuser = True
    moderator.save()
    report = ThreadModerationReport.objects.create(thread=public_thread(other), reporter=owner, target_author=other, reason='spam', details='private reporter text', snapshot='text')
    from news.thread_moderation import decide
    decide(report.pk, moderator, 'hide', 'N4', 'Powtarzany spam')
    row = client.get('/api/account/reports/').data['results'][0]
    assert row['status'] == 'removed' and row['can_appeal']
    client.force_authenticate(moderator)
    assert client.get('/api/account/reports/').data['results'] == []
    client.force_authenticate(other)
    assert 'details' not in client.get('/api/account/reports/').data['results'][0]
    url = f'/api/community/reports/{report.pk}/'
    assert client.post(url, {'body': 'Proszę sprawdzić ponownie'}).status_code == 200
    assert client.post(url, {'body': 'Drugi raz'}).status_code == 400

def test_password_and_logout_all_sessions(setup):
    _, owner, other = setup
    first, second, third = APIClient(), APIClient(), APIClient()
    for client, person in [(first, owner), (second, owner), (third, other)]:
        assert client.login(username=person.username, password=PASSWORD)
    assert first.post('/api/account/password-change/', {'current_password': 'wrong', 'password': 'New~Strong~086!'}).status_code == 400
    assert first.post('/api/account/password-change/', {'current_password': PASSWORD, 'password': 'New~Strong~086!'}).status_code == 200
    assert not second.get('/api/account/me/').data['authenticated']
    assert first.get('/api/account/me/').data['authenticated']
    assert second.login(username=owner.username, password='New~Strong~086!')
    assert first.post('/api/account/logout-all/', {}).status_code == 200
    assert not second.get('/api/account/me/').data['authenticated']
    assert not first.get('/api/account/me/').data['authenticated']
    assert third.get('/api/account/me/').data['authenticated']

def test_notifications_defaults_and_outbox(setup):
    client, owner, other = setup
    from news.notification_models import Notification, NotificationEvent
    from news.notify import notify
    settings = client.get('/api/account/notification-settings/').data
    assert settings['service_enabled'] and not settings['social_enabled']
    assert notify(owner, 'followed_thread', 'Nowa spinka', '/nitki') is None
    assert notify(owner, 'report_status', 'Decyzja', '/konto') is not None
    client.patch('/api/account/notification-settings/', {'social_enabled': True}, format='json')
    assert notify(owner, 'followed_thread', 'Nowa spinka', '/nitki') is not None

def test_profile_report_and_delete_comments(setup):
    client, owner, other = setup
    assert client.post('/api/profiles/other/report/', {'reason': 'privacy'}).status_code == 201
    assert client.post('/api/profiles/other/report/', {'reason': 'privacy'}).status_code == 200
    row = ThreadComment.objects.create(author=owner, thread=public_thread(other), body='Osobiste dane')
    assert client.post('/api/account/delete/', {'password': PASSWORD, 'confirm': 'USUŃ'}).status_code == 200
    row.refresh_from_db()
    assert row.author_id is None and row.body == '' and row.deleted_at


def test_vote_result_and_moderation_notifications_are_idempotent(setup):
    client, owner, other = setup
    from news.clinic_models import ClinicInterview
    from news.notify import queue_event
    from news.notification_tasks import process_notification_events
    from news.notification_models import Notification
    ballot = InterviewBallot.objects.create(day=timezone.now().date()-timedelta(days=1))
    candidate = InterviewCandidate.objects.create(ballot=ballot, video_id='abcdefghijk', title='Rozmowa')
    InterviewVote.objects.create(user=owner, ballot=ballot, candidate=candidate)
    interview = ClinicInterview.objects.create(day=ballot.day, video_id=candidate.video_id,
        url='https://youtube.com/watch?v=abcdefghijk', selection_method='votes')
    assert client.get('/api/account/activity/?kind=votes').data['results'][0]['won'] is True
    queue_event('vote_result', interview.pk)
    process_notification_events()
    process_notification_events()
    assert Notification.objects.filter(user=owner, kind='vote_result').count() == 1
    other.is_staff = other.is_superuser = True
    other.save()
    report = ThreadModerationReport.objects.create(thread=public_thread(owner), target_author=owner,
        reporter=other, snapshot='tekst', reason='spam')
    from news.thread_moderation import decide
    decide(report.pk, other, 'hide', 'N4', 'Spam')
    process_notification_events()
    process_notification_events()
    assert Notification.objects.filter(kind='report_status').count() == 2


def test_profile_moderation_and_owner_scoped_endpoints(setup):
    client, owner, other = setup
    report = client.post('/api/profiles/other/report/', {'reason': 'privacy'}).data
    owner.is_staff = owner.is_superuser = True
    owner.save()
    from news.thread_moderation import decide
    decide(report['id'], owner, 'hide', 'N3', 'Ujawnione dane prywatne')
    assert APIClient().get('/api/profiles/other/').status_code == 404
    for endpoint in ('activity', 'reports', 'mutes', 'export'):
        assert APIClient().get(f'/api/account/{endpoint}/').status_code == 403


def test_auth_rate_limits_and_thread_creation_limit(setup, monkeypatch):
    client, owner, _ = setup
    from news.accounts import AccountIPThrottle, AccountWriteThrottle
    monkeypatch.setattr(AccountIPThrottle, 'rate', '1/hour')
    anonymous = APIClient()
    assert anonymous.post('/api/account/login/', {'username': 'none', 'password': 'bad'}).status_code == 403
    assert anonymous.post('/api/account/login/', {'username': 'none', 'password': 'bad'}).status_code == 429
    cache.clear()
    with patch('news.account_lifecycle.send_password_reset.apply_async'):
        assert anonymous.post('/api/account/password-reset/', {'email': 'none@example.org'}).status_code == 200
        assert anonymous.post('/api/account/password-reset/', {'email': 'none@example.org'}).status_code == 429
    cache.clear()
    monkeypatch.setattr(AccountWriteThrottle, 'rate', '1/hour')
    assert client.post('/api/account/context-threads/', {'title': 'Nowy szkic'}, format='json').status_code == 201
    assert client.post('/api/account/context-threads/', {'title': 'Drugi szkic'}, format='json').status_code == 429


def test_thread_pagination_and_public_feature_flag(setup, settings):
    from news.account_models import PersonalContextThread
    client, owner, other = setup
    PersonalContextThread.objects.bulk_create([PersonalContextThread(owner=owner, title=f'Szkic {i}') for i in range(21)])
    first = client.get('/api/account/context-threads/?status=draft&page=1').data
    second = client.get('/api/account/context-threads/?status=draft&page=2').data
    assert len(first['results']) == 20 and first['next_page'] == 2
    assert len(second['results']) == 1 and second['next_page'] is None
    assert not set(r['id'] for r in first['results']) & set(r['id'] for r in second['results'])
    public_thread(other)
    settings.THREADS_ENABLED = False
    assert client.get('/api/profiles/other/').data['threads']['results'] == []


def test_malformed_write_and_private_cache(setup):
    client, owner, other = setup
    assert client.post('/api/account/mutes/', [], format='json').status_code == 400
    assert client.post('/api/account/password-change/', [], format='json').status_code == 400
    public_thread(other)
    for path in ('/api/account/profile/', '/api/account/activity/', '/api/profiles/other/', '/api/community/threads/'):
        assert 'no-store' in client.get(path)['Cache-Control']


def test_optional_newsletter_uses_verified_address_and_retryable_confirmation(setup):
    client, owner, _ = setup
    from news.notification_models import NotificationEvent
    from news.notification_tasks import process_notification_events
    from news.newsletter_models import NewsletterSubscriber
    identity = owner.account_identity
    identity.email_verified = False
    identity.newsletter_consent_at = timezone.now()
    identity.save()
    assert not NotificationEvent.objects.filter(kind='account_newsletter').exists()
    identity.email_verified = True
    identity.save()
    with patch('news.newsletter.send_confirmation', return_value='no_smtp'):
        process_notification_events()
    assert NotificationEvent.objects.get(kind='account_newsletter').processed_at is None
    with patch('news.newsletter.send_confirmation', return_value='sent') as send:
        process_notification_events()
        process_notification_events()
        send.assert_called_once()
    assert NewsletterSubscriber.objects.get(email=owner.email).status == 'pending'
    assert client.post('/api/account/delete/', {'password': PASSWORD, 'confirm': 'USUŃ'}).status_code == 200
    assert not NewsletterSubscriber.objects.filter(email=owner.email).exists()
