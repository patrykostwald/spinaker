"""OAuth 2 authorization code + PKCE. Provider tokens live only in this request."""
import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from news.account_models import AccountIdentity, UserXConnection
from news.account_security import AccountEnabled

SESSION = 'account_x_oauth'


def x_enabled():
    return bool(settings.X_OAUTH_CLIENT_ID and settings.X_OAUTH_CLIENT_SECRET)


def public_identity(user):
    connection = getattr(user, 'x_connection', None) if user else None
    selected = connection and connection.use_x_name
    return {'display_name': '@' + connection.username if selected else user.username if user else 'Usunięte konto',
            'x_profile': 'https://x.com/' + connection.username if selected else None}


class XConnectionView(APIView):
    permission_classes = [AccountEnabled, IsAuthenticated]

    def get(self, request):
        connection = getattr(request.user, 'x_connection', None)
        return Response({'connected': bool(connection), 'username': connection.username if connection else '',
            'use_x_name': bool(connection and connection.use_x_name), 'oauth_enabled': x_enabled(),
            'connect_url': '/api/account/x/start/?mode=connect' if x_enabled() else None})

    def patch(self, request):
        choice = serializers.BooleanField().run_validation(request.data.get('use_x_name'))
        if not UserXConnection.objects.filter(user=request.user).update(use_x_name=choice):
            return Response({'detail': 'Najpierw połącz konto X.'}, status=400)
        return Response({'use_x_name': choice})

    def delete(self, request):
        identity = getattr(request.user, 'account_identity', None)
        if not request.user.has_usable_password() and not (identity and identity.google_sub):
            return Response({'detail': 'Przed rozłączeniem ustaw hasło przez potwierdzony e-mail.'}, status=400)
        UserXConnection.objects.filter(user=request.user).delete()
        request.session.pop(SESSION, None)
        return Response(status=204)


class XConnectionStartView(APIView):
    permission_classes = [AccountEnabled]

    def get(self, request):
        if not x_enabled():
            return Response(status=404)
        connecting = request.query_params.get('mode') == 'connect' or 'x-connection' in request.path
        if connecting and not request.user.is_authenticated:
            return Response(status=403)
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        redirect = settings.ACCOUNT_PUBLIC_URL.rstrip('/') + '/api/account/x/callback/'
        request.session[SESSION] = {'state': state, 'verifier': verifier, 'created': time.time(),
            'user_id': request.user.pk if connecting else None, 'redirect': redirect,
            'consent': request.query_params.get('accepted_terms') == 'true' and request.query_params.get('adult') == 'true',
            'terms': settings.ACCOUNT_TERMS_VERSION, 'privacy': settings.ACCOUNT_PRIVACY_VERSION}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return HttpResponseRedirect('https://x.com/i/oauth2/authorize?' + urlencode({
            'response_type': 'code', 'client_id': settings.X_OAUTH_CLIENT_ID, 'redirect_uri': redirect,
            'scope': 'users.read tweet.read', 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256'}))


class XConnectionCallbackView(APIView):
    permission_classes = [AccountEnabled]

    def get(self, request):
        destination = settings.ACCOUNT_PUBLIC_URL.rstrip('/') + '/konto'
        failed = HttpResponseRedirect(destination + '?x=failed')
        flow = request.session.pop(SESSION, None)
        if (not x_enabled() or not flow or request.query_params.get('error')
                or not hmac.compare_digest(str(request.query_params.get('state', '')).encode(), flow['state'].encode())
                or not 0 <= time.time() - flow['created'] <= 600 or not request.query_params.get('code')):
            return failed
        if flow['user_id'] and (not request.user.is_authenticated or request.user.pk != flow['user_id']):
            return failed
        if not cache.add('x-oauth-used:' + hashlib.sha256(flow['state'].encode()).hexdigest(), True, 600):
            return failed
        try:
            response = requests.post('https://api.x.com/2/oauth2/token',
                auth=(settings.X_OAUTH_CLIENT_ID, settings.X_OAUTH_CLIENT_SECRET), data={
                    'code': request.query_params['code'], 'grant_type': 'authorization_code',
                    'client_id': settings.X_OAUTH_CLIENT_ID, 'redirect_uri': flow['redirect'],
                    'code_verifier': flow['verifier']}, timeout=(5, 20))
            response.raise_for_status()
            token = response.json()['access_token']
            response = requests.get('https://api.x.com/2/users/me', headers={'Authorization': f'Bearer {token}'}, timeout=(5, 20))
            response.raise_for_status()
            profile = response.json()['data']
            if not re.fullmatch(r'\d{1,32}', str(profile['id'])) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', profile['username']):
                return failed
            with transaction.atomic():
                connection = UserXConnection.objects.select_related('user').filter(x_user_id=profile['id']).first()
                if flow['user_id']:
                    if connection and connection.user_id != flow['user_id']:
                        return failed
                    UserXConnection.objects.update_or_create(user=request.user, defaults={
                        'x_user_id': profile['id'], 'username': profile['username']})
                    return HttpResponseRedirect(destination + '?x=connected')
                if connection:
                    user = connection.user
                    if not user.is_active:
                        return failed
                    connection.username = profile['username']
                    connection.save(update_fields=['username'])
                else:
                    if not flow['consent']:
                        return failed
                    user = get_user_model().objects.create_user(username='czytelnik_' + secrets.token_hex(8), password=None)
                    AccountIdentity.objects.create(user=user, email=None, email_verified=False, adult_declared_at=timezone.now(),
                        accepted_terms_version=flow['terms'], accepted_privacy_version=flow['privacy'], accepted_at=timezone.now())
                    UserXConnection.objects.create(user=user, x_user_id=profile['id'], username=profile['username'], use_x_name=True)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        except (requests.RequestException, KeyError, TypeError, ValueError, IntegrityError):
            return failed
        return HttpResponseRedirect(destination)
