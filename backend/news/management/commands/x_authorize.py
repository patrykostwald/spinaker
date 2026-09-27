"""Podpina konto X (np. @spinclinic) do aplikacji deweloperskiej — logowanie PIN (OAuth 1.0a), bez zakładania nowej aplikacji.

Wymaga w .env.production: X_POST_API_KEY i X_POST_API_SECRET (klucze aplikacji z uprawnieniem Read and write).
1. Uruchom komendę — wypisze link.
2. Otwórz link w przeglądarce, w której jesteś zalogowany jako konto, które ma publikować, i kliknij „Authorize app”.
3. Wpisz PIN z ekranu X — komenda wypisze X_POST_ACCESS_TOKEN i X_POST_ACCESS_SECRET do wklejenia w .env.production.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import parse_qs, quote

import requests
from django.core.management.base import BaseCommand, CommandError

API = 'https://api.x.com/oauth'


def _q(value) -> str:
    return quote(str(value), safe='~-._')


def _signed(url: str, extra: dict, token_secret: str = '') -> str:
    params = {'oauth_consumer_key': os.environ['X_POST_API_KEY'].strip(), 'oauth_nonce': secrets.token_hex(16),
              'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())), 'oauth_version': '1.0', **extra}
    normalized = '&'.join(f'{_q(k)}={_q(v)}' for k, v in sorted(params.items()))
    base = '&'.join(['POST', _q(url), _q(normalized)])
    key = f"{_q(os.environ['X_POST_API_SECRET'].strip())}&{_q(token_secret)}"
    params['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return 'OAuth ' + ', '.join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(params.items()))


class Command(BaseCommand):
    help = 'Podpina konto X do publikowania (PIN) i wypisuje X_POST_ACCESS_TOKEN / X_POST_ACCESS_SECRET.'

    def handle(self, *args, **options):
        if not (os.environ.get('X_POST_API_KEY', '').strip() and os.environ.get('X_POST_API_SECRET', '').strip()):
            raise CommandError('Najpierw dopisz X_POST_API_KEY i X_POST_API_SECRET w .env.production i przebuduj kontenery.')
        response = requests.post(f'{API}/request_token', headers={'Authorization': _signed(f'{API}/request_token', {'oauth_callback': 'oob'})}, timeout=30)
        if response.status_code != 200:
            raise CommandError(f'X odrzucił zapytanie ({response.status_code}): {response.text[:200]}')
        token = parse_qs(response.text)
        request_token, request_secret = token['oauth_token'][0], token['oauth_token_secret'][0]
        self.stdout.write('\n1. Otwórz ten link w przeglądarce zalogowanej jako konto, które ma publikować (np. @spinclinic):')
        self.stdout.write(f'   https://api.x.com/oauth/authorize?oauth_token={request_token}\n')
        pin = input('2. Kliknij „Authorize app” i wpisz tutaj PIN z ekranu X: ').strip()
        response = requests.post(f'{API}/access_token', headers={'Authorization': _signed(f'{API}/access_token', {'oauth_token': request_token, 'oauth_verifier': pin}, request_secret)}, timeout=30)
        if response.status_code != 200:
            raise CommandError(f'Nie udało się ({response.status_code}): {response.text[:200]}')
        access = parse_qs(response.text)
        self.stdout.write(f"\nPodpięte konto: @{access.get('screen_name', ['?'])[0]}")
        self.stdout.write('3. Wklej te dwie linie do .env.production (nie wysyłaj ich nikomu):\n')
        self.stdout.write(f"X_POST_ACCESS_TOKEN={access['oauth_token'][0]}")
        self.stdout.write(f"X_POST_ACCESS_SECRET={access['oauth_token_secret'][0]}\n")
