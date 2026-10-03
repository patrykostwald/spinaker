from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.test import APIClient

from news.features import accounts_enabled, threads_enabled, push_enabled, preview_active
from news.preview import MAX_AGE, SALT, PreviewMiddleware, key_digest, valid_preview


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.PREVIEW_KEY = 'test-only-preview-secret'
    settings.ACCOUNTS_ENABLED = False
    settings.THREADS_ENABLED = False
    settings.PUSH_ENABLED = False
    settings.VAPID_PUBLIC_KEY = 'public'
    settings.VAPID_PRIVATE_KEY = 'private'
    settings.VAPID_SUBJECT = 'mailto:test@example.org'
    cache.clear()


def enter(client, settings):
    return client.get('/api/preview/', {'klucz': settings.PREVIEW_KEY}, secure=True)


def signed_cookie():
    return signing.dumps(key_digest(), salt=SALT)


def test_entry_secure_cookies_and_no_secret(settings):
    client = APIClient()
    response = enter(client, settings)
    assert response.status_code == 302 and response['Location'] == '/podglad'
    assert response['Cache-Control'] == 'private, no-store'
    assert response['Referrer-Policy'] == 'no-referrer'
    assert response['X-Robots-Tag'] == 'noindex, nofollow'
    for name in ('sc_preview', 'sc_preview_sig'):
        cookie = response.cookies[name]
        assert cookie['max-age'] == MAX_AGE and cookie['secure']
        assert cookie['samesite'] == 'Lax' and cookie['path'] == '/'
    assert response.cookies['sc_preview_sig']['httponly']
    assert not response.cookies['sc_preview']['httponly']
    assert response.cookies['sc_preview'].value == '1'
    assert settings.PREVIEW_KEY not in str(response.headers) + str(response.cookies) + response.content.decode()
    assert client.get('/api/preview/status/').json() == {'active': True}
    assert not preview_active.get()


@pytest.mark.parametrize('key', ['', 'wrong', 'zażółć'])
def test_bad_key_is_empty_404(key):
    response = APIClient().get('/api/preview/', {'klucz': key})
    assert response.status_code == 404 and not response.content and not response.cookies


def test_unconfigured_feature_and_old_cookie(settings):
    cookie = signed_cookie()
    settings.PREVIEW_KEY = ''
    assert not valid_preview(cookie)
    response = APIClient().get('/api/preview/', {'klucz': 'test-only-preview-secret'})
    assert response.status_code == 404 and not response.cookies


def test_missing_slash_never_echoes_key(settings):
    response = APIClient().get('/api/preview', {'klucz': settings.PREVIEW_KEY})
    assert response.status_code == 302 and response['Location'] == '/podglad'
    assert response['Cache-Control'] == 'private, no-store'


def test_exit_clears_preview_but_not_account(settings):
    client = APIClient()
    enter(client, settings)
    client.cookies['sessionid'] = 'existing-account-session'
    response = client.get('/api/preview/off/')
    assert response.status_code == 302 and response['Location'] == '/'
    for name in ('sc_preview', 'sc_preview_sig'):
        assert response.cookies[name]['max-age'] == 0
        assert response.cookies[name]['path'] == '/'
    assert 'sessionid' not in response.cookies
    assert not client.get('/api/preview/status/').json()['active']


def test_key_rotation_and_tampering(settings):
    cookie = signed_cookie()
    assert valid_preview(cookie)
    assert not valid_preview(cookie + 'bad')
    settings.PREVIEW_KEY = 'rotated-secret'
    assert not valid_preview(cookie)
    client = APIClient()
    client.cookies['sc_preview_sig'] = cookie
    client.cookies['sc_preview'] = '1'
    response = client.get('/api/preview/status/')
    assert not response.json()['active']
    assert response.cookies['sc_preview']['max-age'] == 0


def test_expired_cookie():
    with patch('django.core.signing.time.time', return_value=100):
        cookie = signed_cookie()
    with patch('django.core.signing.time.time', return_value=101 + MAX_AGE):
        assert not valid_preview(cookie)


def test_ip_throttle_even_with_valid_key_and_untrusted_forwarding(settings):
    client = APIClient()
    for attempt in range(10):
        assert client.get('/api/preview/', {'klucz': 'bad'}, HTTP_X_FORWARDED_FOR=f'198.51.100.{attempt}').status_code == 404
    assert enter(client, settings).status_code == 404
    assert client.get('/api/preview/', {'klucz': settings.PREVIEW_KEY}, REMOTE_ADDR='192.0.2.2').status_code == 302


@pytest.mark.parametrize('cookies,expected', [({}, False), ({'sc_preview': '1'}, False), ({'sc_preview_sig': 'bad'}, False), ({'signed': True}, True)])
def test_flags_are_request_local(cookies, expected):
    request = RequestFactory().get('/')
    request.COOKIES = {'sc_preview_sig': signed_cookie()} if cookies.get('signed') else cookies
    def view(request):
        assert (accounts_enabled(), threads_enabled(), push_enabled()) == (expected,) * 3
        return HttpResponse()
    response = PreviewMiddleware(view)(request)
    assert 'Cookie' in response['Vary']
    assert not accounts_enabled() and not threads_enabled() and not push_enabled()


def test_public_flags_still_work(settings):
    settings.ACCOUNTS_ENABLED = settings.THREADS_ENABLED = settings.PUSH_ENABLED = True
    assert accounts_enabled() and threads_enabled() and push_enabled()


def test_context_resets_after_exception_and_isolation():
    request = RequestFactory().get('/')
    request.COOKIES['sc_preview_sig'] = signed_cookie()
    def view(request):
        assert preview_active.get()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(accounts_enabled).result() is False
        raise RuntimeError('test')
    with pytest.raises(RuntimeError):
        PreviewMiddleware(view)(request)
    assert not preview_active.get()


def test_query_redacted_before_downstream_handling(settings):
    request = RequestFactory().get('/api/preview/', {'klucz': settings.PREVIEW_KEY})
    request.META['RAW_URI'] = request.get_full_path()
    request.META['REQUEST_URI'] = request.get_full_path()
    def view(request):
        assert request.GET == {} and request.get_full_path() == '/api/preview/'
        assert settings.PREVIEW_KEY not in str(request.META)
        return HttpResponse()
    PreviewMiddleware(view)(request)
    assert not hasattr(request, '_preview_key_valid')


def test_preview_never_enables_bulk_workers():
    from news import notify, push
    from news.notification_tasks import process_notification_events, send_notification_digests
    from news.account_lifecycle import send_account_verification, send_password_reset
    token = preview_active.set(True)
    try:
        assert accounts_enabled() and push_enabled()
        assert not notify.enabled() and not push.enabled()
        assert push.send_to_topic('spin-dnia', {}) == 0
        # Without DB access: disabled workers must return before any query/send.
        process_notification_events()
        send_notification_digests()
        send_account_verification('reader@example.org')
        send_password_reset('reader@example.org')
    finally:
        preview_active.reset(token)


@pytest.mark.django_db
def test_preview_registers_ordinary_account_and_delivers_transactional_mail(settings):
    from news.account_lifecycle import send_account_verification, send_password_reset
    client = APIClient(enforce_csrf_checks=True)
    enter(client, settings)
    csrf = client.get('/api/account/me/').data['csrfToken']
    data = {'username': 'previewreader', 'email': 'reader@example.org', 'password': 'Str0ng~unique~zxcv!',
            'accepted_terms': True, 'accepted_privacy': True, 'adult': True, 'is_staff': True, 'is_superuser': True}
    assert client.post('/api/account/register/', data, format='json').status_code == 403
    with patch('news.account_lifecycle.send_account_verification.apply_async') as queued:
        response = client.post('/api/account/register/', data, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 201
    user = get_user_model().objects.get(username='previewreader')
    assert not user.is_staff and not user.is_superuser
    assert not user.account_identity.email_verified
    assert user.account_identity.accepted_at and user.account_identity.accepted_terms_version
    assert not preview_active.get()
    grant = queued.call_args.kwargs['kwargs']['preview_grant']
    with patch('news.account_lifecycle.send_account_mail') as mail:
        send_account_verification(user.email, preview_grant=grant)
        assert mail.call_count == 1
    with patch('news.account_lifecycle.send_password_reset.apply_async') as queued_reset:
        response = client.post('/api/account/password-reset/', {'email': user.email}, format='json', HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    with patch('news.account_lifecycle.send_account_mail') as mail:
        send_password_reset(user.email, **queued_reset.call_args.kwargs['kwargs'])
        assert mail.call_count == 1
    settings.PREVIEW_KEY = 'changed'
    with patch('news.account_lifecycle.send_account_mail') as mail:
        send_password_reset(user.email, preview_grant=grant)
        mail.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['email', 'accepted_terms', 'accepted_privacy'])
def test_preview_requires_email_and_consents(settings, field):
    client = APIClient()
    enter(client, settings)
    data = {'username': 'previewreader', 'email': 'reader@example.org', 'password': 'Str0ng~unique~zxcv!',
            'accepted_terms': True, 'accepted_privacy': True}
    del data[field]
    assert client.post('/api/account/register/', data, format='json').status_code == 400


@pytest.mark.django_db
def test_account_and_push_api_require_signature(settings):
    client = APIClient()
    client.cookies['sc_preview'] = '1'
    assert client.get('/api/account/me/').data['accounts_enabled'] is False
    assert client.get('/api/push/subscriptions/').data['enabled'] is False
    assert client.get('/api/community/threads/').status_code == 404
    enter(client, settings)
    assert client.get('/api/account/me/').data['accounts_enabled'] is True
    assert client.get('/api/push/subscriptions/').data['enabled'] is True
    assert client.get('/api/community/threads/').status_code == 200
    assert client.post('/api/editor/threads/', {}, format='json').status_code in (401, 403)
    assert not APIClient().get('/api/account/me/').data['accounts_enabled']


@pytest.mark.django_db
def test_tester_login_grants_preview_only_to_testers(settings):
    from io import StringIO
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from rest_framework.test import APIClient
    settings.PREVIEW_KEY = 'k' * 32
    call_command('create_tester', 'politycznyux', password='Proste-Haslo-47', stdout=StringIO())
    get_user_model().objects.create_user(username='zwykly', password='Proste-Haslo-47')
    client = APIClient()
    bad = client.post('/api/preview/login/', {'username': 'zwykly', 'password': 'Proste-Haslo-47'}, format='json')
    assert bad.status_code == 403 and 'sc_preview_sig' not in bad.cookies
    ok = client.post('/api/preview/login/', {'username': 'PolitycznyUX', 'password': 'Proste-Haslo-47'}, format='json')
    assert ok.status_code == 200 and ok.json()['next'] == '/podglad'
    assert ok.cookies['sc_preview'].value == '1' and ok.cookies['sc_preview_sig'].value
    user = get_user_model().objects.get(username='politycznyux')
    assert not user.is_staff and user.account_identity.email_verified
