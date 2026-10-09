import base64
import sys
import types
from unittest.mock import Mock, patch
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import path
from rest_framework.test import APIClient
from news.push_api import SubscriptionsView
from news.push import send_to_topic, send_to_user
from news.push_models import PushSubscription, PushEvent
from news.push_events import evening_spin, dr_spin_published

urlpatterns = [path('api/push/subscriptions/', SubscriptionsView.as_view())]
pytestmark = pytest.mark.django_db
URL = '/api/push/subscriptions/'


@pytest.fixture(autouse=True)
def setup():
    cache.clear()
    with override_settings(ROOT_URLCONF=__name__, PUSH_ENABLED=True, VAPID_PUBLIC_KEY='public',
                           VAPID_PRIVATE_KEY='private', VAPID_SUBJECT='mailto:push@example.org'):
        yield


def payload():
    encode = lambda data: base64.urlsafe_b64encode(data).rstrip(b'=').decode()
    return {'endpoint': 'https://fcm.googleapis.com/fcm/send/device',
            'keys': {'p256dh': encode(b'\x04' + b'x' * 64), 'auth': encode(b'x' * 16)},
            'topics': ['spin-dnia'], 'consent_version': '2026-09-30'}


def subscribe(client, data=None):
    csrf = client.get(URL).data['csrfToken']
    return client.post(URL, data or payload(), format='json', HTTP_X_CSRFTOKEN=csrf)


@pytest.mark.parametrize('authenticated', [False, True])
def test_subscription_consent_and_withdrawal(authenticated):
    client = APIClient(enforce_csrf_checks=True)
    user = get_user_model().objects.create_user(username='reader') if authenticated else None
    if user:
        client.force_authenticate(user)
    assert client.post(URL, payload(), format='json').status_code == 403
    assert subscribe(client).status_code == 201
    row = PushSubscription.objects.get()
    assert row.user == user and row.consent_at and row.consent_version == '2026-09-30'
    assert client.get(URL).data['results'][0]['topics'] == ['spin-dnia']
    assert APIClient().get(URL).data['results'] == []
    assert subscribe(APIClient(enforce_csrf_checks=True)).status_code == 409
    assert subscribe(client, {**payload(), 'topics': ['obserwowani']}).status_code == 201
    assert PushSubscription.objects.count() == 1
    csrf = client.get(URL).data['csrfToken']
    assert client.delete(URL, HTTP_X_CSRFTOKEN=csrf).status_code == 204
    assert not PushSubscription.objects.exists()


@pytest.mark.parametrize('changes', [
    {'endpoint': 'https://127.0.0.1/internal'}, {'endpoint': 'https://fcm.googleapis.com.evil.org/test'},
    {'endpoint': 'http://fcm.googleapis.com/test'}, {'topics': ['invalid']},
    {'keys': {'auth': 'bad'}}, {'consent_version': 'old'}, {'topics': []},
])
def test_invalid_subscription(changes):
    assert subscribe(APIClient(enforce_csrf_checks=True), {**payload(), **changes}).status_code == 400
    assert not PushSubscription.objects.exists()


@pytest.mark.parametrize('settings', [{'PUSH_ENABLED': False}, {'VAPID_PRIVATE_KEY': ''},
                                     {'VAPID_PUBLIC_KEY': ''}, {'VAPID_SUBJECT': ''}])
def test_disabled_without_keys(settings):
    with override_settings(**settings):
        client = APIClient(enforce_csrf_checks=True)
        assert client.get(URL).data['enabled'] is False
        assert client.get(URL).data['public_key'] == ''
        assert subscribe(client).status_code == 503
        assert send_to_topic('spin-dnia', {}) == 0


@pytest.fixture
def provider(monkeypatch):
    module = types.ModuleType('pywebpush')
    class Error(Exception):
        def __init__(self, status):
            self.response = Mock(status_code=status)
    module.WebPushException = Error
    module.webpush = Mock()
    monkeypatch.setitem(sys.modules, 'pywebpush', module)
    return module


def test_send_topic_and_user(provider):
    user = get_user_model().objects.create_user(username='push-user')
    client = APIClient()
    client.force_authenticate(user)
    subscribe(client)
    assert send_to_topic('nitki-dr-spina', {}) == 0
    assert send_to_topic('spin-dnia', {'title': 'Spin dnia'}) == 1
    assert send_to_user(user, {}) == 0
    subscribe(client, {**payload(), 'topics': ['obserwowani']})
    assert send_to_user(user, {'title': 'Nowość'}) == 1
    assert provider.webpush.call_args.kwargs['timeout'] == 10
    assert provider.webpush.call_args.kwargs['vapid_claims'] == {'sub': 'mailto:push@example.org'}


@pytest.mark.parametrize('status,remaining', [(404, 0), (410, 0), (503, 1)])
def test_cleanup_expired(provider, status, remaining):
    subscribe(APIClient())
    provider.webpush.side_effect = provider.WebPushException(status)
    assert send_to_topic('spin-dnia', {}) == 0
    assert PushSubscription.objects.count() == remaining


def test_evening_deduplication(provider):
    subscribe(APIClient())
    with patch('news.clinic.spin_of_day_by_camp', return_value={'spins': {'government': {'id': 1}}}):
        assert evening_spin() == 1
        assert evening_spin() == 0
    assert provider.webpush.call_count == 1
    assert PushEvent.objects.count() == 1


def test_thread_hook_after_commit(django_capture_on_commit_callbacks):
    instance = Mock(pk=123, published=True, created_by_id=None, slug='dr-spin-kontekst-2026-09-30', title='Kontekst')
    with patch('news.push_events.deliver_event.delay') as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            dr_spin_published(None, instance)
            enqueue.assert_not_called()
        assert enqueue.call_args.args[1] == 'nitki-dr-spina'
        assert enqueue.call_args.args[2]['url'] == '/thread/dr-spin-kontekst-2026-09-30'


def _diagnosis(status, verdict='spin'):
    from news.political_models import PoliticalAccount, PoliticalPost
    from news.clinic_models import SpinDiagnosis
    from django.utils import timezone
    account = PoliticalAccount.objects.create(handle='posel', display_name='Jan Poseł', camp='ruling')
    post = PoliticalPost.objects.create(account=account, post_id='1', text='Tekst', published_at=timezone.now(), camp_at_collection='ruling')
    return SpinDiagnosis.objects.create(post=post, status=status, verdict=verdict, headline='Nagłówek diagnozy')


def test_live_spin_alert_on_approval_once(django_capture_on_commit_callbacks):
    from django.utils import timezone
    with patch('news.push_events._enqueue') as enqueue, patch('news.push_events._morning_eta', return_value=None):
        with django_capture_on_commit_callbacks(execute=True):
            row = _diagnosis('pending_review', verdict='no_spin')
        enqueue.assert_not_called()
        with django_capture_on_commit_callbacks(execute=True):
            row.status, row.verdict, row.reviewed_at = 'approved', 'spin', timezone.now()
            row.save()
        key, topic, data, eta = enqueue.call_args.args
        assert key == f'spin:{row.pk}' and topic == 'spiny-na-zywo'
        assert data['url'] == f'/klinika/{row.pk}' and 'Jan Poseł' in data['title']


def test_review_alert_goes_to_staff(django_capture_on_commit_callbacks):
    with patch('news.push_events._enqueue_staff') as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            row = _diagnosis('pending_review')
        assert enqueue.call_args.args[0] == f'review:{row.pk}'


def test_quiet_hours_delay_to_morning():
    import datetime
    from django.utils import timezone
    from news.push_events import _morning_eta
    late = timezone.make_aware(datetime.datetime(2026, 10, 1, 23, 30))
    assert timezone.localtime(_morning_eta(late)).hour == 7
    assert _morning_eta(timezone.make_aware(datetime.datetime(2026, 10, 1, 12, 0))) is None


@pytest.fixture(autouse=True)
def threads_feature(monkeypatch):
    monkeypatch.setattr('django.conf.settings.THREADS_ENABLED', True)
