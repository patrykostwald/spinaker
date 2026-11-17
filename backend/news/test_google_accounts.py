import base64
import json
import sys
import time
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import path
from rest_framework.test import APIClient

from news.account_models import AccountIdentity
from news.google_accounts import GoogleStartView, GoogleCallbackView, verify_id_token, SESSION_KEY

urlpatterns = [
    path('api/account/google/start/', GoogleStartView.as_view()),
    path('api/account/google/callback/', GoogleCallbackView.as_view()),
]
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def settings():
    cache.clear()
    with override_settings(ROOT_URLCONF=__name__, ACCOUNTS_ENABLED=True,
                           GOOGLE_OAUTH_CLIENT_ID='google-client', GOOGLE_OAUTH_CLIENT_SECRET='secret',
                           ACCOUNT_PUBLIC_URL='https://spin.example', ACCOUNT_TERMS_VERSION='v1',
                           ACCOUNT_PRIVACY_VERSION='v1'):
        yield


def claims(nonce='nonce'):
    return {'iss': 'https://accounts.google.com', 'aud': 'google-client', 'sub': 'google-subject',
            'exp': time.time() + 600, 'iat': time.time(), 'nonce': nonce,
            'email': 'Reader@example.org', 'email_verified': True}


def start(client, consent=True):
    response = client.get('/api/account/google/start/',
                          {'accepted_terms': 'true', 'adult': 'true'} if consent else {})
    assert response.status_code == 302
    query = parse_qs(urlparse(response.url).query)
    assert query['code_challenge_method'] == ['S256']
    assert query['scope'] == ['openid email']
    return client.session[SESSION_KEY]


def callback(client, flow):
    return client.get('/api/account/google/callback/', {'state': flow['state'], 'code': 'code'})


def test_mocked_google_signup_and_replay():
    client = APIClient()
    flow = start(client)
    with patch('news.google_accounts.requests.post', return_value=Mock(json=lambda: {'id_token': 'token'})) as post, \
            patch('news.google_accounts._verify_signature', return_value=claims(flow['nonce'])):
        assert callback(client, flow).url == 'https://spin.example/konto'
        identity = AccountIdentity.objects.get(google_sub='google-subject')
        assert identity.email == 'reader@example.org' and identity.email_verified
        assert identity.accepted_terms_version == 'v1' and identity.accepted_at
        assert not identity.user.has_usable_password()
        assert post.call_args.kwargs['data']['code_verifier'] == flow['verifier']
        assert str(identity.user_id) == client.session['_auth_user_id']
        assert callback(client, flow).url.endswith('/konto/potwierdz?google_error=1')
        assert post.call_count == 1


def test_google_new_account_requires_adult_declaration():
    client = APIClient()
    client.get('/api/account/google/start/', {'accepted_terms': 'true', 'adult': 'false'})
    flow = client.session[SESSION_KEY]
    with patch('news.google_accounts.requests.post', return_value=Mock(json=lambda: {'id_token': 'token'})), \
            patch('news.google_accounts._verify_signature', return_value=claims(flow['nonce'])):
        assert callback(client, flow).url.endswith('/konto/potwierdz?google_error=1')
    assert not AccountIdentity.objects.exists()


@pytest.mark.parametrize('consent,existing', [(False, False), (True, True)])
def test_google_requires_consent_and_never_links_existing_email(consent, existing):
    if existing:
        get_user_model().objects.create_user(username='existing', email='reader@example.org')
    client = APIClient()
    flow = start(client, consent)
    with patch('news.google_accounts.requests.post', return_value=Mock(json=lambda: {'id_token': 'token'})), \
            patch('news.google_accounts._verify_signature', return_value=claims(flow['nonce'])):
        assert callback(client, flow).url.endswith('/konto/potwierdz?google_error=1')
    assert not AccountIdentity.objects.exists()
    assert '_auth_user_id' not in client.session


def test_google_existing_subject_and_disabled_user():
    user = get_user_model().objects.create_user(username='existing')
    AccountIdentity.objects.create(user=user, email='old@example.org', google_sub='google-subject', email_verified=True)
    for active in (True, False):
        user.is_active = active
        user.save()
        client = APIClient()
        flow = start(client, False)
        with patch('news.google_accounts.requests.post', return_value=Mock(json=lambda: {'id_token': 'token'})), \
                patch('news.google_accounts._verify_signature', return_value=claims(flow['nonce'])):
            response = callback(client, flow)
        assert response.url.endswith('/konto/potwierdz?google_error=1') is (not active)
    assert get_user_model().objects.count() == 1


def test_google_rejects_state_expired_flow_and_disabled_config():
    client = APIClient()
    flow = start(client)
    with patch('news.google_accounts.requests.post') as post:
        assert callback(client, {**flow, 'state': 'wrong'}).url.endswith('/konto/potwierdz?google_error=1')
        flow = start(client)
        assert callback(client, {**flow, 'state': 'błędny'}).url.endswith('/konto/potwierdz?google_error=1')
        flow = start(client)
        session = client.session
        session[SESSION_KEY] = {**flow, 'created': time.time() - 601}
        session.save()
        assert callback(client, flow).url.endswith('/konto/potwierdz?google_error=1')
        post.assert_not_called()
    with override_settings(GOOGLE_OAUTH_CLIENT_SECRET=''):
        assert client.get('/api/account/google/start/').status_code == 404


@pytest.mark.parametrize('field,value', [
    ('aud', 'another-client'), ('iss', 'https://attacker.example'), ('exp', 1),
    ('nonce', 'wrong'), ('email_verified', False), ('sub', ''), ('azp', 'another-client'),
    ('email', 'invalid'), ('iat', 99999999999),
    ('aud', ['google-client', 'other-client']), ('exp', float('nan')),
])
def test_id_token_rejects_invalid_claims(field, value):
    with patch('news.google_accounts._verify_signature', return_value={**claims(), field: value}):
        with pytest.raises(Exception):
            verify_id_token('token', 'nonce')


def test_jwks_signature_verified_and_tampering_rejected():
    pytest.importorskip('cryptography')
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()

    def encode(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

    cache.set('account_google_jwks', [{'kid': 'test-key', 'kty': 'RSA',
        'n': encode(numbers.n.to_bytes(256, 'big')), 'e': encode(numbers.e.to_bytes(3, 'big'))}])
    header = encode(json.dumps({'alg': 'RS256', 'kid': 'test-key'}).encode())
    payload = encode(json.dumps(claims()).encode())
    message = f'{header}.{payload}'
    signature = encode(key.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256()))
    assert verify_id_token(f'{message}.{signature}', 'nonce')['sub'] == 'google-subject'
    changed = encode(json.dumps({**claims(), 'sub': 'attacker'}).encode())
    with pytest.raises(Exception):
        verify_id_token(f'{header}.{changed}.{signature}', 'nonce')


def test_tokeninfo_fallback_still_validates_claims():
    with patch.dict(sys.modules, {'cryptography': None, 'cryptography.hazmat.primitives': None,
                                 'cryptography.hazmat.primitives.asymmetric': None}), \
            patch('news.google_accounts.requests.get', return_value=Mock(json=lambda: claims())) as get:
        assert verify_id_token('provider-token', 'nonce')['email'] == 'reader@example.org'
        assert get.call_args.kwargs == {'params': {'id_token': 'provider-token'}, 'timeout': 10}
        with pytest.raises(ValueError):
            verify_id_token('provider-token', 'wrong')
