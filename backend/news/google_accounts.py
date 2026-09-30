"""Minimal Google authorization-code OIDC login; no provider tokens are stored."""
import base64
import hashlib
import hmac
import json
import math
import secrets
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_models import AccountIdentity
from news.account_security import AccountEnabled

SESSION_KEY = 'account_google_oauth'
CALLBACK_PATH = '/api/account/google/callback/'
JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs'


def google_enabled():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def _verify_signature(token):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError:
        # Explicit fallback for installations without cryptography.
        response = requests.get('https://oauth2.googleapis.com/tokeninfo',
                                params={'id_token': token}, timeout=10)
        response.raise_for_status()
        return response.json()
    header_part, payload_part, signature_part = token.split('.')
    header = json.loads(_decode(header_part))
    if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
        raise ValueError('Invalid signing algorithm')
    keys = cache.get('account_google_jwks')
    key = next((key for key in (keys or []) if key.get('kid') == header['kid']), None)
    if key is None:
        response = requests.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        keys = response.json()['keys']
        cache.set('account_google_jwks', keys, 3600)
        key = next((key for key in keys if key.get('kid') == header['kid']), None)
    if not key or key.get('kty') != 'RSA' or key.get('use', 'sig') != 'sig':
        raise ValueError('Unknown signing key')
    public_key = rsa.RSAPublicNumbers(int.from_bytes(_decode(key['e']), 'big'),
                                      int.from_bytes(_decode(key['n']), 'big')).public_key()
    public_key.verify(_decode(signature_part), f'{header_part}.{payload_part}'.encode('ascii'),
                      padding.PKCS1v15(), hashes.SHA256())
    return json.loads(_decode(payload_part))


def verify_id_token(token, nonce):
    if not isinstance(token, str) or len(token) > 16384:
        raise ValueError('Invalid token')
    claims = _verify_signature(token)
    audience = claims.get('aud')
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not (audience == client_id or isinstance(audience, list) and client_id in audience):
        raise ValueError('Invalid audience')
    if isinstance(audience, list) and len(audience) > 1 and claims.get('azp') != client_id:
        raise ValueError('Missing authorized party')
    if claims.get('azp', client_id) != client_id:
        raise ValueError('Invalid authorized party')
    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ValueError('Invalid issuer')
    expires = float(claims.get('exp', 0))
    issued = float(claims.get('iat', 0))
    if not math.isfinite(expires) or expires <= time.time():
        raise ValueError('Expired token')
    if not math.isfinite(issued) or issued > time.time() + 60:
        raise ValueError('Future token')
    if not hmac.compare_digest(str(claims.get('nonce', '')), nonce):
        raise ValueError('Invalid nonce')
    subject = claims.get('sub')
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise ValueError('Invalid subject')
    if claims.get('email_verified') not in (True, 'true'):
        raise ValueError('Unverified email')
    email = str(claims.get('email', '')).strip().lower()
    validate_email(email)
    if len(email) > 254:
        raise ValueError('Invalid email')
    claims['email'] = email
    return claims


class GoogleStartView(APIView):
    permission_classes = [AccountEnabled]

    def get(self, request):
        if not google_enabled():
            return Response({'detail': 'Logowanie Google jest niedostępne.'}, status=404)
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        redirect_uri = settings.ACCOUNT_PUBLIC_URL.rstrip('/') + CALLBACK_PATH
        request.session[SESSION_KEY] = {
            'state': state, 'nonce': nonce, 'verifier': verifier, 'created': time.time(),
            'redirect_uri': redirect_uri,
            'consent': request.query_params.get('accepted_terms') == 'true'
                       and request.query_params.get('accepted_privacy') == 'true',
            'terms_version': settings.ACCOUNT_TERMS_VERSION,
            'privacy_version': settings.ACCOUNT_PRIVACY_VERSION,
        }
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return HttpResponseRedirect('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID, 'redirect_uri': redirect_uri,
            'response_type': 'code', 'scope': 'openid email', 'state': state, 'nonce': nonce,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'prompt': 'select_account',
        }))


class GoogleCallbackView(APIView):
    permission_classes = [AccountEnabled]

    def get(self, request):
        destination = settings.ACCOUNT_PUBLIC_URL.rstrip('/') + '/konto'
        failed = HttpResponseRedirect(destination + '/potwierdz?google_error=1')
        flow = request.session.pop(SESSION_KEY, None)
        if not google_enabled() or not flow or request.query_params.get('error'):
            return failed
        if not hmac.compare_digest(str(request.query_params.get('state', '')).encode(), flow['state'].encode()):
            return failed
        if time.time() - flow['created'] > 600 or not request.query_params.get('code'):
            return failed
        try:
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'code': request.query_params['code'], 'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
                'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
                'redirect_uri': flow['redirect_uri'], 'grant_type': 'authorization_code',
                'code_verifier': flow['verifier'],
            }, timeout=10)
            response.raise_for_status()
            claims = verify_id_token(response.json()['id_token'], flow['nonce'])
            with transaction.atomic():
                identity = AccountIdentity.objects.select_related('user').filter(google_sub=claims['sub']).first()
                if identity is None:
                    if not flow['consent']:
                        return failed
                    # An email match is never authorization to attach a new identity.
                    if (AccountIdentity.objects.filter(email__iexact=claims['email']).exists()
                            or get_user_model().objects.filter(email__iexact=claims['email']).exists()):
                        return failed
                    user = get_user_model().objects.create_user(
                        username='czytelnik_' + secrets.token_hex(8), email=claims['email'], password=None)
                    identity = AccountIdentity.objects.create(
                        user=user, email=claims['email'], email_verified=True, google_sub=claims['sub'],
                        accepted_terms_version=flow['terms_version'],
                        accepted_privacy_version=flow['privacy_version'], accepted_at=timezone.now())
                if not identity.user.is_active:
                    return failed
            login(request, identity.user, backend='django.contrib.auth.backends.ModelBackend')
        except Exception:
            # Provider errors and invalid signatures receive the same public result.
            # Never log tokens, authorization codes, email addresses, or secrets.
            return failed
        return HttpResponseRedirect(destination)
