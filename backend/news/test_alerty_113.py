"""Zlecenie 113: szybsze i pewniejsze alerty. Dane syntetyczne, bez sieci."""
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
import json
import sys
import types
import uuid
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.alerts_polling import budget_snapshot
from news.followed_posts import quiet_for
from news.notification_models import Notification, NotificationPost, NotificationSettings
from news.notification_tasks import process_notification_events
from news.political_polling import poll_minutes
from news.push_models import PushDelivery, PushSubscription
from news.test_followed_posts_088 import clock, figure, post, process, reader, setup  # noqa: F401
from news.test_political_intake import account, staff  # noqa: F401

pytestmark = pytest.mark.django_db


def at(hour, minute=0, second=0):
    # 2026-10-03 jest w czasie letnim: Warszawa = UTC+2.
    return datetime(2026, 10, 3, hour, minute, second=second, tzinfo=dt_timezone.utc)


@pytest.mark.parametrize('fast, gap_minutes, groups', [(False, 3, 1), (True, 3, 2), (True, 1, 1)])
def test_group_window_by_mode(settings, clock, reader, account, django_capture_on_commit_callbacks, fast, gap_minutes, groups):
    settings.ALERTS_FAST_MODE = fast
    post(account, 100)
    with patch('news.push.send_to_user', return_value=1):
        clock.return_value = at(10)
        process(django_capture_on_commit_callbacks)
        clock.return_value = at(10, 1, 5)
        process(django_capture_on_commit_callbacks)
        clock.return_value = at(10, 1, 5) + timedelta(minutes=gap_minutes)
        post(account, 101)
        process(django_capture_on_commit_callbacks)
    assert Notification.objects.count() == groups


def test_default_flag_is_off(settings):
    from django.conf import settings as real
    assert real.ALERTS_FAST_MODE is False


def test_fast_mode_holds_a_minute_then_sends_single_post(settings, clock, reader, account, django_capture_on_commit_callbacks):
    settings.ALERTS_FAST_MODE = True
    post(account)
    with patch('news.push.send_to_user', return_value=1) as send:
        process(django_capture_on_commit_callbacks)
        send.assert_not_called()
        clock.return_value += timedelta(seconds=61)
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1
        payload = send.call_args.args[1]
        assert payload['title'].startswith('Anna Testowa: ') and payload['body'] == 'Wpis testowy 100'


def test_default_mode_sends_without_hold(settings, clock, reader, account, django_capture_on_commit_callbacks):
    settings.ALERTS_FAST_MODE = False
    post(account)
    with patch('news.push.send_to_user', return_value=1) as send:
        process(django_capture_on_commit_callbacks)
        assert send.call_count == 1


def test_avalanche_collects_into_one_summary_alert(settings, clock, reader, account, django_capture_on_commit_callbacks):
    settings.ALERTS_FAST_MODE = True
    with patch('news.push.send_to_user', return_value=1) as send:
        for number in range(5):
            post(account, 200 + number)
        process(django_capture_on_commit_callbacks)
        clock.return_value += timedelta(minutes=5)
        post(account, 300)
        process(django_capture_on_commit_callbacks)
    row = Notification.objects.get()
    assert row.posts.count() == 6 and 'nowych wpisów' in row.title


def test_duplicate_text_from_second_account_is_skipped(clock, reader, account, django_capture_on_commit_callbacks):
    post(account, 100, text='Ten sam tekst')
    process(django_capture_on_commit_callbacks)
    post(account, 101, text='Ten sam tekst')
    process(django_capture_on_commit_callbacks)
    assert NotificationPost.objects.count() == 1


def settings_for(**extra):
    row = NotificationSettings(**extra)
    return row


def test_quiet_hours_are_user_settings(figure):
    default = settings_for()
    assert quiet_for(default, figure.pk, at(21)) and not quiet_for(default, figure.pk, at(11))
    assert quiet_for(default, figure.pk, at(4, 59)) and not quiet_for(default, figure.pk, at(5))
    off = settings_for(quiet_hours_enabled=False)
    assert not quiet_for(off, figure.pk, at(21))
    custom = settings_for(quiet_hours_start=time(1, 0), quiet_hours_end=time(5, 0))
    assert not quiet_for(custom, figure.pk, at(21)) and quiet_for(custom, figure.pk, at(0, 30))
    woke = settings_for(wake_person_ids=[figure.pk])
    assert not quiet_for(woke, figure.pk, at(21)) and quiet_for(woke, figure.pk + 1, at(21))


def test_wake_person_pushes_during_quiet_hours(clock, reader, account, figure, django_capture_on_commit_callbacks):
    NotificationSettings.objects.filter(user=reader).update(wake_person_ids=[figure.pk])
    clock.return_value = at(21)
    post(account)
    with patch('news.push.send_to_user', return_value=1) as send:
        process(django_capture_on_commit_callbacks)
    assert send.call_count == 1


def test_disabled_quiet_hours_push_at_night(clock, reader, account, django_capture_on_commit_callbacks):
    NotificationSettings.objects.filter(user=reader).update(quiet_hours_enabled=False)
    clock.return_value = at(21)
    post(account)
    with patch('news.push.send_to_user', return_value=1) as send:
        process(django_capture_on_commit_callbacks)
    assert send.call_count == 1


def test_default_night_push_waits(clock, reader, account, django_capture_on_commit_callbacks):
    clock.return_value = at(21)
    post(account)
    with patch('news.push.send_to_user', return_value=1) as send:
        process(django_capture_on_commit_callbacks)
        send.assert_not_called()
        assert Notification.objects.get().push_pending


class FakeWebPushException(Exception):
    response = None


@pytest.fixture(autouse=True)
def fake_pywebpush(monkeypatch):
    """Biblioteki pywebpush może brakować w środowisku testowym; sieci nigdy nie używamy."""
    module = types.ModuleType('pywebpush')
    module.webpush, module.WebPushException = Mock(), FakeWebPushException
    monkeypatch.setitem(sys.modules, 'pywebpush', module)
    return module


def subscription(user, endpoint):
    return PushSubscription.objects.create(user=user, device=uuid.uuid4(), consent_at=timezone.now(), endpoint=endpoint, keys={'p256dh': 'x', 'auth': 'y'},
        topics=['obserwowani'])


def test_retry_with_backoff_stops_after_three_and_never_duplicates(settings, clock, reader, account,
        django_capture_on_commit_callbacks):
    settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT = 'a', 'b', 'mailto:x@example.org'
    good, bad = subscription(reader, 'https://push.example/good'), subscription(reader, 'https://push.example/bad')
    calls = []

    def fake(subscription_info, **kwargs):
        calls.append(subscription_info['endpoint'])
        if subscription_info['endpoint'].endswith('bad'):
            raise Exception('synthetic outage')

    post(account)
    with patch('pywebpush.webpush', side_effect=fake):
        process(django_capture_on_commit_callbacks)
        for _ in range(6):
            clock.return_value += timedelta(minutes=2)
            process(django_capture_on_commit_callbacks)
    assert calls.count('https://push.example/good') == 1
    assert calls.count('https://push.example/bad') == 3
    assert PushDelivery.objects.get(subscription=bad).finished and PushDelivery.objects.get(subscription=good).sent_at
    assert PushSubscription.objects.filter(pk=bad.pk).exists()


def test_expired_subscription_is_deleted_without_retry(settings, clock, reader, account, django_capture_on_commit_callbacks):
    from pywebpush import WebPushException
    settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT = 'a', 'b', 'mailto:x@example.org'
    gone = subscription(reader, 'https://push.example/gone')
    error = WebPushException('gone')
    error.response = Mock(status_code=410)
    post(account)
    with patch('pywebpush.webpush', side_effect=error) as webpush:
        process(django_capture_on_commit_callbacks)
        clock.return_value += timedelta(minutes=5)
        process(django_capture_on_commit_callbacks)
    assert webpush.call_count == 1 and not PushSubscription.objects.filter(pk=gone.pk).exists()
    assert PushDelivery.objects.get().finished


def test_latency_metric_and_command(settings, clock, reader, account, django_capture_on_commit_callbacks):
    settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT = 'a', 'b', 'mailto:x@example.org'
    subscription(reader, 'https://push.example/ok')
    post(account)
    with patch('pywebpush.webpush'):
        process(django_capture_on_commit_callbacks)
    item = NotificationPost.objects.get()
    assert item.push_latency_seconds == pytest.approx(60, abs=1) and item.push_sent_at
    out = StringIO()
    call_command('alerty_opoznienie', '--json', stdout=out)
    result = json.loads(out.getvalue())
    assert result['razem']['liczba'] == 1 and result['zrodla']['x']['mediana_s'] == pytest.approx(60, abs=1)
    assert result['bez_potwierdzenia_push'] == 0
    text = StringIO()
    call_command('alerty_opoznienie', stdout=text)
    assert 'mediana' in text.getvalue()


CONFIG = {'daily_requests': 100, 'daily_posts': 100, 'monthly_usd': Decimal('5'), 'fast_poll_seconds': 60,
    'fast_mode': True}


def test_budget_pacing_never_goes_below_floor_and_slows_under_pressure(clock):
    calm = budget_snapshot(CONFIG, {}, at(12))
    assert calm['paced_interval_seconds'] >= 60 and calm['remaining_usd'] == '5'
    heavy = budget_snapshot(CONFIG, {'month': '2026-10', 'spent_upper_usd': '4.50', 'day': '2026-10-03',
        'daily_requests': 90}, at(12))
    assert heavy['paced_interval_seconds'] > calm['paced_interval_seconds']


def test_poll_interval_defaults_unchanged_and_fast_for_followed(account):
    account.poll_interval_minutes = 30
    slow = {'followed_minutes': 15}
    assert poll_minutes(account, slow, True) == 15 and poll_minutes(account, slow, False) == 30
    assert poll_minutes(account, {**slow, 'fast_mode': True, 'fast_poll_seconds': 60}, True) == 1
    assert poll_minutes(account, {**slow, 'fast_mode': True, 'fast_poll_seconds': 60}, False) == 30


def test_settings_api_validates_quiet_hours_and_wake_list(reader, figure):
    from news.notification_api import SettingsSerializer
    row = NotificationSettings.objects.get(user=reader)
    ok = SettingsSerializer(row, data={'quiet_hours_start': '22:00:00', 'quiet_hours_end': '06:00:00',
        'wake_person_ids': [figure.pk]}, partial=True)
    assert ok.is_valid(), ok.errors
    same = SettingsSerializer(row, data={'quiet_hours_start': '22:00:00', 'quiet_hours_end': '22:00:00'}, partial=True)
    assert not same.is_valid()
    stranger = SettingsSerializer(row, data={'wake_person_ids': [figure.pk + 999]}, partial=True)
    assert not stranger.is_valid()
