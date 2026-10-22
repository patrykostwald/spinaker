"""Synthetic fixtures only; run with -p offline_test_guard."""
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from news.clinic_models import SpinDiagnosis
from news.followed_posts import quiet_hours
from news.models import ImportState
from news.notification_api import FollowsView, FollowDetailView, NotificationsView
from news.notification_models import Follow, Notification, NotificationEvent, NotificationPost, NotificationSettings
from news.notification_tasks import process_notification_events
from news.political_admin import PublicFigureAdmin
from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead, PublicFigure
from news.political_polling import configuration, political_poll_cycle, PoliticalReadError, followed_account_ids
from news.test_notifications import request
from news.test_political_intake import account, staff, config, page, item

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings):
    settings.ACCOUNTS_ENABLED = True
    settings.PUSH_ENABLED = True


@pytest.fixture
def clock():
    with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 3, 10, tzinfo=dt_timezone.utc)) as mocked:
        yield mocked


@pytest.fixture
def figure(account):
    from django.contrib.contenttypes.models import ContentType
    from news.political_models import PoliticalAccountCandidate, SocialHandleEvidence
    row = PublicFigure.objects.create(canonical_name='Anna Testowa', role_category='politician',
        role_title='Posłanka', evidence_url='https://example.org/fixture')
    candidate = PoliticalAccountCandidate.objects.create(handle=account.handle, display_name='Anna Testowa',
        classification='government', resolved_account=account)
    SocialHandleEvidence.objects.create(subject_content_type=ContentType.objects.get_for_model(PublicFigure),
        subject_object_id=row.pk, handle=account.handle, evidence_url='https://example.org/fixture',
        extracted_url=f'https://x.com/{account.handle}', candidate=candidate, status='candidate_created')
    return row


@pytest.fixture
def reader(figure):
    user = get_user_model().objects.create_user('reader-088')
    Follow.objects.create(user=user, figure=figure, mode='posts')
    NotificationSettings.objects.create(user=user, push_followed=True)
    return user


def post(account, number=100, **extra):
    return PoliticalPost.objects.create(**{'account': account, 'post_id': str(number),
        'text': f'Wpis testowy {number}', 'url': f'https://x.com/{account.handle}/status/{number}',
        'published_at': timezone.now() - timedelta(minutes=1), 'camp_at_collection': 'government', **extra})


def process(callbacks):
    with callbacks(execute=True):
        return process_notification_events()


@pytest.mark.parametrize('mode', ['posts', 'diagnoses', 'strong_spin'])
def test_mode_create_update_validation_and_owner_scope(figure, staff, mode):
    response = request(FollowsView, staff, 'post', {'kind': 'figure', 'target_id': figure.pk, 'mode': mode})
    assert response.status_code == 201 and response.data['mode'] == mode
    assert request(FollowDetailView, staff, 'patch', {'mode': 'strong_spin'}, follow_id=response.data['id']).data['mode'] == 'strong_spin'
    assert request(FollowDetailView, staff, 'patch', {'mode': 'bad'}, follow_id=response.data['id']).status_code == 400
    outsider = get_user_model().objects.create_user('outsider')
    assert request(FollowDetailView, outsider, 'patch', {'mode': 'posts'}, follow_id=response.data['id']).status_code == 404
    assert request(FollowsView, staff, 'post', {'kind': 'user', 'target_id': outsider.pk, 'mode': mode}).status_code == 400
    other = Follow.objects.create(user=staff, target_user=outsider)
    assert request(FollowDetailView, staff, 'patch', {'mode': 'posts'}, follow_id=other.pk).status_code == 400
    with pytest.raises(IntegrityError), transaction.atomic():
        Follow.objects.filter(pk=other.pk).update(mode='posts')


def test_default_and_repeated_follow_preserve_mode(figure, staff):
    data = {'kind': 'figure', 'target_id': figure.pk}
    assert request(FollowsView, staff, 'post', data).data['mode'] == 'diagnoses'
    Follow.objects.filter(user=staff).update(mode='posts')
    assert request(FollowsView, staff, 'post', data).data['mode'] == 'posts'


@pytest.mark.parametrize('extra', [{'available': False}, {'published_at': datetime(2020, 1, 1, tzinfo=dt_timezone.utc)},
    {'source_data': {'referenced_tweets': [{'type': 'retweeted'}]}}, {'text': 'RT @fixture: powtórka'}])
def test_ineligible_posts_do_not_queue(account, extra):
    post(account, **extra)
    assert not NotificationEvent.objects.filter(kind='post').exists()


def test_replies_flags_created_only_and_two_hour_boundary(account, clock):
    account.include_replies = False
    account.save()
    post(account, source_data={'referenced_tweets': [{'type': 'replied_to'}]})
    post(account, 101, published_at=timezone.now() - timedelta(hours=2, microseconds=1))
    valid = post(account, 102, published_at=timezone.now() - timedelta(hours=2))
    valid.save()
    assert list(NotificationEvent.objects.filter(kind='post').values_list('target_id', flat=True)) == [valid.pk]
    account.include_replies = account.include_reposts = True
    account.save()
    post(account, 103, source_data={'referenced_tweets': [{'type': 'replied_to'}, {'type': 'retweeted'}]})
    assert NotificationEvent.objects.filter(kind='post').count() == 2


def test_three_posts_one_push_and_rolling_window(clock, reader, account, django_capture_on_commit_callbacks):
    with patch('news.push.send_to_user') as send:
        for n in range(3):
            post(account, 100 + n)
            process(django_capture_on_commit_callbacks)
            clock.return_value += timedelta(minutes=1)
        assert send.call_count == 1
        row = Notification.objects.get()
        assert row.title == 'Testowa: 3 nowe wpisy' and row.posts.count() == 3
        clock.return_value = row.push_sent_at + timedelta(minutes=15)
        post(account, 104)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 2 and Notification.objects.count() == 2
        assert process(django_capture_on_commit_callbacks) == 0 and send.call_count == 2


@pytest.mark.parametrize('utc_hour,minute,expected', [(20, 59, False), (21, 0, True), (4, 59, True), (5, 0, False)])
def test_warsaw_quiet_boundaries(utc_hour, minute, expected):
    assert quiet_hours(datetime(2026, 10, 3, utc_hour, minute, tzinfo=dt_timezone.utc)) is expected


def test_night_group_delivered_at_seven_and_no_second_push(clock, reader, account, django_capture_on_commit_callbacks):
    clock.return_value = datetime(2026, 10, 3, 21, tzinfo=dt_timezone.utc)
    with patch('news.push.send_to_user') as send:
        post(account)
        process(django_capture_on_commit_callbacks)
        clock.return_value += timedelta(hours=4)
        post(account, 101)
        process(django_capture_on_commit_callbacks)
        assert Notification.objects.get().posts.count() == 2
        send.assert_not_called()
        clock.return_value = datetime(2026, 10, 4, 5, tzinfo=dt_timezone.utc)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1
        assert send.call_args.args[1]['title'] == 'Testowa: 2 nowe wpisy'
        clock.return_value += timedelta(minutes=1)
        post(account, 102)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1 and Notification.objects.get().posts.count() == 3


@pytest.mark.parametrize('mode,intensity,expected', [('posts', 80, 0), ('diagnoses', 10, 1), ('strong_spin', 69, 0), ('strong_spin', 70, 1)])
def test_diagnosis_modes(clock, reader, account, mode, intensity, expected, django_capture_on_commit_callbacks):
    Follow.objects.filter(user=reader).update(mode=mode)
    source = post(account)
    SpinDiagnosis.objects.create(post=source, status='approved', intensity=intensity)
    with patch('news.push.send_to_user') as send:
        process(django_capture_on_commit_callbacks)
    assert Notification.objects.filter(kind='followed_diagnosis').count() == expected
    assert send.call_count == (1 if mode == 'posts' else expected)


def test_diagnosis_updates_existing_alert_and_link_without_push(clock, reader, account, django_capture_on_commit_callbacks):
    source = post(account)
    with patch('news.push.send_to_user') as send:
        process(django_capture_on_commit_callbacks)
        assert send.call_args.args[1]['url'] == source.url
        row = Notification.objects.get()
        row.read_at = timezone.now(); row.save()
        diagnosis = SpinDiagnosis.objects.create(post=source, status='approved', intensity=74)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1 and Notification.objects.count() == 1
    data = request(NotificationsView, reader).data['results'][0]
    assert data['read_at'] is None and data['url'] == f'/klinika/{diagnosis.pk}'
    assert data['posts'][0]['score'] == 74
    diagnosis.hidden_at = timezone.now(); diagnosis.save()
    assert request(NotificationsView, reader).data['results'][0]['posts'][0]['score'] is None


@pytest.mark.parametrize('change', ['push_off', 'service_off', 'inactive', 'unfollow', 'unavailable'])
def test_pending_push_rechecks_preferences_and_visibility(clock, reader, account, change, django_capture_on_commit_callbacks):
    clock.return_value = datetime(2026, 10, 3, 21, tzinfo=dt_timezone.utc)
    source = post(account)
    process(django_capture_on_commit_callbacks)
    if change == 'push_off': NotificationSettings.objects.filter(user=reader).update(push_followed=False)
    if change == 'service_off': NotificationSettings.objects.filter(user=reader).update(service_enabled=False)
    if change == 'inactive': get_user_model().objects.filter(pk=reader.pk).update(is_active=False)
    if change == 'unfollow': Follow.objects.filter(user=reader).delete()
    if change == 'unavailable': PoliticalPost.objects.filter(pk=source.pk).update(available=False)
    clock.return_value += timedelta(hours=8)
    with patch('news.push.send_to_user') as send:
        process(django_capture_on_commit_callbacks)
    send.assert_not_called()
    assert Notification.objects.count() == 1


def test_followed_due_account_precedes_older_due_and_shortens_interval(clock, reader, account, staff, config):
    other = PoliticalAccount.objects.create(user_id='9999', handle='OtherFixture', display_name='Other', camp='government',
        enabled=True, confirmation_url='https://example.org/other', next_poll_at=timezone.now() - timedelta(hours=1))
    other.confirm(staff)
    PoliticalAccount.objects.filter(pk=account.pk).update(poll_interval_minutes=60,
        last_polled_at=timezone.now() - timedelta(minutes=16), next_poll_at=timezone.now() + timedelta(minutes=44))
    with patch('news.political_polling.fetch_x_timeline', return_value=page([])) as fetch:
        result = political_poll_cycle()
    assert result['account_id'] == account.pk and fetch.call_count == 1
    account.refresh_from_db()
    assert account.next_poll_at == timezone.now() + timedelta(minutes=15)
    assert PoliticalRead.objects.count() == 1


@pytest.mark.parametrize('variable,value', [('X_POLITICAL_DAILY_REQUEST_LIMIT', '1'), ('X_POLITICAL_DAILY_POST_LIMIT', '5'), ('X_POLITICAL_MONTHLY_USD_LIMIT', '0.025')])
def test_followed_cannot_exceed_any_budget(clock, reader, account, config, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    with patch('news.political_polling.fetch_x_timeline', side_effect=PoliticalReadError('timeout')) as fetch:
        assert political_poll_cycle()['status'] == 'error'
        PoliticalAccount.objects.filter(pk=account.pk).update(next_poll_at=timezone.now())
        assert political_poll_cycle()['status'] == 'budget_limit'
        assert fetch.call_count == 1
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert Decimal(budget['spent_upper_usd']) == Decimal('0.025')
    assert budget['daily_requests'] == 1 and budget['daily_posts'] == 5


def test_minimum_interval_and_no_shortening_backoff(clock, reader, account, config, monkeypatch):
    monkeypatch.setenv('X_FOLLOWED_POLL_MINUTES', '1')
    assert configuration()['followed_minutes'] == 5
    PoliticalAccount.objects.filter(pk=account.pk).update(last_error='x_http_429',
        last_polled_at=timezone.now() - timedelta(hours=1), next_poll_at=timezone.now() + timedelta(hours=1))
    with patch('news.political_polling.fetch_x_timeline') as fetch:
        assert political_poll_cycle()['status'] == 'idle'
    fetch.assert_not_called()


def test_admin_counts_active_followers_and_posts_mode(reader, figure, staff):
    Follow.objects.create(user=staff, figure=figure)
    model_admin = PublicFigureAdmin(PublicFigure, admin.site)
    obj = model_admin.get_queryset(APIRequestFactory().get('/')).get(pk=figure.pk)
    assert model_admin.follower_count(obj) == 2 and model_admin.post_follower_count(obj) == 1


def test_no_priority_without_posts_follow(reader, figure, account):
    assert followed_account_ids([account.pk]) == {account.pk}
    Follow.objects.filter(user=reader).update(mode='strong_spin')
    assert followed_account_ids([account.pk]) == set()


def test_late_follower_and_withdrawal_before_delivery(clock, reader, account, figure):
    source = post(account)
    late = get_user_model().objects.create_user('late-reader')
    clock.return_value += timedelta(seconds=1)
    Follow.objects.create(user=late, figure=figure, mode='posts')
    process_notification_events()
    assert not Notification.objects.filter(user=late).exists()
    second = post(account, 101)
    PoliticalPost.objects.filter(pk=second.pk).update(available=False)
    process_notification_events()
    assert NotificationPost.objects.count() == 1


def test_disabled_push_preserves_centre_but_disabled_service_does_not(clock, reader, account):
    NotificationSettings.objects.filter(user=reader).update(push_followed=False)
    post(account)
    with patch('news.push.send_to_user') as send:
        process_notification_events()
    send.assert_not_called()
    assert Notification.objects.count() == 1
    NotificationSettings.objects.filter(user=reader).update(service_enabled=False)
    post(account, 101)
    process_notification_events()
    assert NotificationPost.objects.count() == 1


def test_delayed_outbox_still_delivers_recent_at_intake(clock, reader, account):
    post(account)
    clock.return_value += timedelta(hours=3)
    process_notification_events()
    assert NotificationPost.objects.count() == 1


def test_diagnosis_during_quiet_hours_waits(clock, reader, account, django_capture_on_commit_callbacks):
    Follow.objects.filter(user=reader).update(mode='diagnoses')
    clock.return_value = datetime(2026, 10, 3, 21, tzinfo=dt_timezone.utc)
    SpinDiagnosis.objects.create(post=post(account), status='approved', intensity=74)
    with patch('news.push.send_to_user') as send:
        process(django_capture_on_commit_callbacks)
        assert Notification.objects.get().push_pending
        send.assert_not_called()
        clock.return_value += timedelta(hours=8)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1


def test_failed_push_keeps_centre_and_does_not_retry(clock, reader, account, django_capture_on_commit_callbacks):
    post(account)
    with patch('news.push.send_to_user', side_effect=RuntimeError('synthetic outage')) as send:
        process(django_capture_on_commit_callbacks)
        process(django_capture_on_commit_callbacks)
    assert send.call_count == 1 and Notification.objects.count() == 1


def test_mode_change_cannot_bypass_fifteen_minute_push_limit(clock, reader, account, django_capture_on_commit_callbacks):
    post(account)
    with patch('news.push.send_to_user') as send:
        process(django_capture_on_commit_callbacks)
        first = Notification.objects.get()
        Follow.objects.filter(user=reader).update(mode='diagnoses')
        clock.return_value += timedelta(minutes=1)
        SpinDiagnosis.objects.create(post=post(account, 102), status='approved', intensity=74)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1
        assert Notification.objects.filter(push_pending=True).count() == 1
        clock.return_value = first.push_sent_at + timedelta(minutes=15)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 2
