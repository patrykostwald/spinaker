from unittest.mock import patch
from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from news.account_models import AccountIdentity, PersonalContextThread, PersonalContextThreadItem
from news.community_models import CommunityLink, CommunityThreadOpinion
from news.notification_api import FollowsView, FollowDetailView, NotificationsView, NotificationReadView, NotificationSettingsView
from news.notification_models import Follow, Notification, NotificationEvent, NotificationSettings
from news.notification_tasks import process_notification_events, send_notification_digests
from news.notify import notify

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enabled(settings, monkeypatch):
    settings.ACCOUNTS_ENABLED = True
    settings.PUSH_ENABLED = False
    monkeypatch.setattr('django.conf.settings.THREADS_ENABLED', True)


@pytest.fixture
def users():
    result = [get_user_model().objects.create_user(f'person{i}', email=f'person{i}@example.org', password='test-password') for i in range(3)]
    for user in result:
        AccountIdentity.objects.create(user=user, email=user.email, email_verified=True)
    return result


def request(view, user, method='get', data=None, **kwargs):
    req = getattr(APIRequestFactory(), method)('/', data=data or {}, format='json')
    force_authenticate(req, user)
    return view.as_view()(req, **kwargs)


def public_thread(owner):
    thread = PersonalContextThread.objects.create(owner=owner, title='Moja spinka')
    for i in range(2):
        link = CommunityLink.objects.create(canonical_url=f'https://example.org/{thread.pk}/{i}', domain='example.org', title=f'Materiał {i}', submitted_by=owner)
        PersonalContextThreadItem.objects.create(thread=thread, link=link, position=i)
    thread.is_public, thread.published_at = True, timezone.now()
    thread.save()
    return thread


def test_follows_are_idempotent_and_owner_scoped(users):
    first = request(FollowsView, users[0], 'post', {'kind': 'user', 'target_id': users[1].pk})
    assert first.status_code == 201
    again = request(FollowsView, users[0], 'post', {'kind': 'user', 'target_id': users[1].pk})
    assert again.status_code == 200
    assert first.data == again.data
    assert first.data['url'] == '/profile/person1'
    assert request(FollowsView, users[2]).data == []
    assert request(FollowDetailView, users[2], 'delete', follow_id=first.data['id']).status_code == 404
    assert request(FollowDetailView, users[0], 'delete', follow_id=first.data['id']).status_code == 204


def test_private_thread_cannot_be_followed(users):
    thread = PersonalContextThread.objects.create(owner=users[1], title='Prywatna')
    assert request(FollowsView, users[0], 'post', {'kind': 'thread', 'target_id': thread.pk}).status_code == 404
    assert request(FollowsView, users[0], 'post', {'kind': 'user', 'target_id': users[0].pk}).status_code == 400


def test_notification_read_is_owner_scoped(users):
    mine = notify(users[0], 'thread_reply', 'Nowa opinia', '/nitki/1')
    other = notify(users[1], 'thread_reply', 'Inna opinia', '/nitki/2')
    assert request(NotificationsView, users[0]).data['unread'] == 1
    assert request(NotificationReadView, users[0], 'post', {'ids': [other.pk]}).data['unread'] == 1
    assert request(NotificationReadView, users[0], 'post', {'all': True}).data['unread'] == 0
    other.refresh_from_db()
    assert other.read_at is None
    assert request(NotificationReadView, users[0], 'post', {'ids': 'wrong'}).status_code == 400


def test_settings_default_and_validation(users):
    assert request(NotificationSettingsView, users[0]).data == {'email_digest': 'off', 'push_spin_of_day': False, 'push_followed': False, 'push_thread_replies': False, 'service_enabled': True, 'social_enabled': False}
    assert request(NotificationSettingsView, users[0], 'patch', {'email_digest': 'hourly'}).status_code == 400
    assert request(NotificationSettingsView, users[0], 'patch', {'email_digest': 'weekly', 'push_followed': True}).data['push_followed'] is True
    assert request(NotificationSettingsView, users[1]).data['email_digest'] == 'off'


def test_feature_flag_disables_api_hooks_and_delivery(users, settings):
    settings.ACCOUNTS_ENABLED = False
    assert request(FollowsView, users[0]).status_code == 404
    assert notify(users[0], 'thread_reply', 'Test', '/') is None
    public_thread(users[0])
    assert not NotificationEvent.objects.exists()
    assert process_notification_events() == 0


def test_publication_outbox_is_idempotent_and_replies_reach_owner_and_followers(users):
    NotificationSettings.objects.create(user=users[0], social_enabled=True)
    Follow.objects.create(user=users[0], target_user=users[1])
    thread = public_thread(users[1])
    thread.save()
    assert NotificationEvent.objects.filter(kind='thread').count() == 1
    assert process_notification_events() == 1
    assert Notification.objects.filter(user=users[0], kind='followed_thread').count() == 1
    Follow.objects.create(user=users[0], thread=thread)
    CommunityThreadOpinion.objects.create(user=users[2], thread=thread, polarity='positive', body='Opinia')
    assert process_notification_events() == 1
    assert Notification.objects.filter(kind='thread_reply').count() == 2
    assert not Notification.objects.filter(user=users[2]).exists()
    assert process_notification_events() == 0


def test_hidden_thread_does_not_deliver(users):
    Follow.objects.create(user=users[0], target_user=users[1])
    thread = public_thread(users[1])
    thread.hidden_at = timezone.now()
    thread.save()
    process_notification_events()
    assert not Notification.objects.exists()


def test_digest_opt_in_interval_verified_email_and_no_duplicate(users):
    preference = NotificationSettings.objects.create(user=users[0], email_digest='weekly', social_enabled=True)
    notify(users[0], 'followed_thread', 'Nowa spinka', '/nitki/1')
    notify(users[1], 'followed_thread', 'Brak zgody na mail', '/nitki/2')
    with patch('news.account_mail.send_account_mail', return_value=True) as mail:
        assert send_notification_digests() == 1
        assert mail.call_count == 1
        assert mail.call_args.args[0] == users[0].email
        assert '/nitki/1' in mail.call_args.args[2]
        assert send_notification_digests() == 0
    notify(users[0], 'followed_thread', 'Następna', '/nitki/3')
    preference.refresh_from_db()
    preference.last_digest_at = timezone.now() - timedelta(days=8)
    preference.save()
    AccountIdentity.objects.filter(user=users[0]).update(email_verified=False)
    with patch('news.account_mail.send_account_mail', return_value=True) as mail:
        assert send_notification_digests() == 0
        mail.assert_not_called()


def test_failed_digest_is_retried(users):
    NotificationSettings.objects.create(user=users[0], email_digest='daily', social_enabled=True)
    row = notify(users[0], 'followed_thread', 'Nowa spinka', '/nitki/1')
    with patch('news.account_mail.send_account_mail', return_value=False):
        assert send_notification_digests() == 0
    row.refresh_from_db()
    assert row.emailed_at is None
    with patch('news.account_mail.send_account_mail', return_value=True):
        assert send_notification_digests() == 1


def test_diagnosis_notifies_only_after_publication(users):
    from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure
    from news.clinic_models import SpinDiagnosis
    account = PoliticalAccount.objects.create(user_id='123', handle='osoba', display_name='Osoba', camp='government')
    post = PoliticalPost.objects.create(account=account, post_id='999', url='https://x.com/osoba/status/999', text='Publiczny wpis', published_at=timezone.now(), camp_at_collection='government')
    figure = PublicFigure.objects.create(canonical_name='Osoba publiczna', role_category='politician', role_title='Poseł', evidence_url='https://example.org')
    Follow.objects.create(user=users[0], figure=figure)
    diagnosis = SpinDiagnosis.objects.create(post=post, status='pending_review')
    assert not NotificationEvent.objects.filter(kind='diagnosis').exists()
    diagnosis.status = 'approved'
    diagnosis.save(update_fields=['status'])
    diagnosis.save(update_fields=['headline'])
    assert NotificationEvent.objects.filter(kind='diagnosis').count() == 1
    with patch('news.clinic.figures_by_account', return_value={account.pk: figure}):
        process_notification_events()
    row = Notification.objects.get(user=users[0])
    assert row.kind == 'followed_diagnosis'
    assert row.url == f'/klinika/{diagnosis.pk}'
    assert process_notification_events() == 0


def test_push_is_opt_in_and_failure_preserves_notification(users, settings, django_capture_on_commit_callbacks):
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    send = Mock(side_effect=RuntimeError('offline'))
    settings.PUSH_ENABLED = True
    preference = NotificationSettings.objects.create(user=users[0], push_followed=False, social_enabled=True)
    with patch.dict(sys.modules, {'news.push': SimpleNamespace(send_to_user=send)}):
        with django_capture_on_commit_callbacks(execute=True):
            notify(users[0], 'followed_thread', 'Pierwsza', '/nitki/1')
        send.assert_not_called()
        preference.push_followed = True
        preference.save()
        with django_capture_on_commit_callbacks(execute=True):
            row = notify(users[0], 'followed_thread', 'Druga', '/nitki/2')
        send.assert_called_once()
        assert send.call_args.args[1]['url'] == '/nitki/2'
        assert Notification.objects.filter(pk=row.pk).exists()


def test_hidden_follow_is_not_exposed(users):
    thread = public_thread(users[1])
    Follow.objects.create(user=users[0], thread=thread)
    assert len(request(FollowsView, users[0]).data) == 1
    thread.hidden_at = timezone.now()
    thread.save()
    assert request(FollowsView, users[0]).data == []


def test_large_digest_reports_remaining_notifications(users):
    NotificationSettings.objects.create(user=users[0], email_digest='daily')
    Notification.objects.bulk_create([Notification(user=users[0], kind='followed_thread', title=f'Nowa {i}', url=f'/spinki/{i}') for i in range(101)])
    with patch('news.account_mail.send_account_mail', return_value=True) as mail:
        assert send_notification_digests() == 1
        assert 'Pozostałe powiadomienia: 1.' in mail.call_args.args[2]
    assert not Notification.objects.filter(emailed_at__isnull=True).exists()
