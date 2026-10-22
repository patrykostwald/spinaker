"""Wspólne logowanie: kod jednorazowy, token sesji, wylogowanie wszędzie, nagłówek Bearer."""
from __future__ import annotations

import pytest
from django.core import signing

from spina3 import sso

from .conftest import make_user

pytestmark = pytest.mark.django_db


def test_code_exchange_and_token(spina3_settings):
    user = make_user('sso1')
    code = sso.issue_code(user)
    assert sso.redeem_code(code) == user
    assert sso.redeem_code(code, audience='inny') is None
    token = sso.issue_token(user)
    assert sso.verify_token(token) == user
    sso.logout_everywhere(user)
    assert sso.verify_token(token) is None


def test_expired_code(monkeypatch, spina3_settings):
    user = make_user('sso2')
    code = sso.issue_code(user)
    spina3_settings.SPINA3_SSO_CODE_MAX_AGE = 0
    import time
    time.sleep(1.1)
    assert sso.redeem_code(code) is None


def test_tampered_token():
    user = make_user('sso3')
    token = sso.issue_token(user) + 'x'
    assert sso.verify_token(token) is None
    with pytest.raises(signing.BadSignature):
        signing.TimestampSigner(salt=sso.TOKEN_SALT).unsign_object(token)


def test_bearer_authentication_only_in_token_mode(api, spina3_settings):
    user = make_user('sso4')
    token = sso.issue_token(user)
    response = api.get('/api/spina3/me/boxes/', HTTP_AUTHORIZATION=f'Bearer {token}')
    assert response.status_code in (401, 403)   # auth_mode=session: nagłówek ignorowany
    spina3_settings.SPINA3['flags']['auth_mode'] = 'token'
    response = api.get('/api/spina3/me/boxes/', HTTP_AUTHORIZATION=f'Bearer {token}')
    assert response.status_code == 200
    response = api.post('/api/spina3/auth/exchange/', {'code': sso.issue_code(user)}, format='json')
    assert response.status_code == 200 and response.json()['token']
    response = api.post('/api/spina3/auth/exchange/', {'code': 'zly'}, format='json')
    assert response.status_code == 401
