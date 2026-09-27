"""Automatyczne wpisy konta spin.clinic na X: silne spiny (domyślnie od 70/100) jako wpis + diagnoza w odpowiedziach.

Wątek to ten sam 2–3-wpisowy skrót co przycisk „Udostępnij” (news/x_share.py). Wyłączone domyślnie — działa dopiero
z kluczami konta z uprawnieniem zapisu (OAuth 1.0a: X_POST_API_KEY, X_POST_API_SECRET, X_POST_ACCESS_TOKEN,
X_POST_ACCESS_SECRET) i X_POST_ENABLED=true. Token odczytu (X_POLITICAL_BEARER_TOKEN) nie pozwala publikować.
Limit dzienny: X_POST_DAILY_LIMIT (domyślnie 3). Wpisów usuniętych przez autora nie publikujemy.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

TWEETS = 'https://api.x.com/2/tweets'
KEYS = ('X_POST_API_KEY', 'X_POST_API_SECRET', 'X_POST_ACCESS_TOKEN', 'X_POST_ACCESS_SECRET')


def enabled() -> bool:
    return os.environ.get('X_POST_ENABLED', '').strip().lower() == 'true' and all(os.environ.get(k, '').strip() for k in KEYS)


def _q(value: str) -> str:
    return quote(str(value), safe='~-._')


def _oauth_header(method: str, url: str) -> str:
    """Podpis OAuth 1.0a (HMAC-SHA1). Treść JSON nie wchodzi do podpisu — tylko parametry oauth_*."""
    env = {k: os.environ[k].strip() for k in KEYS}
    params = {'oauth_consumer_key': env['X_POST_API_KEY'], 'oauth_nonce': secrets.token_hex(16),
              'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())),
              'oauth_token': env['X_POST_ACCESS_TOKEN'], 'oauth_version': '1.0'}
    normalized = '&'.join(f'{_q(k)}={_q(v)}' for k, v in sorted(params.items()))
    base = '&'.join([method.upper(), _q(url), _q(normalized)])
    key = f"{_q(env['X_POST_API_SECRET'])}&{_q(env['X_POST_ACCESS_SECRET'])}"
    params['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return 'OAuth ' + ', '.join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(params.items()))


def post(text: str, reply_to: str | None = None) -> str:
    body = {'text': text}
    if reply_to:
        body['reply'] = {'in_reply_to_tweet_id': reply_to}
    response = requests.post(TWEETS, json=body, headers={'Authorization': _oauth_header('POST', TWEETS)}, timeout=(5, 30))
    if response.status_code not in (200, 201):
        raise RuntimeError(f'x_post_{response.status_code}: {response.text[:160]}')
    return str(response.json()['data']['id'])


def candidates(limit: int):
    from news.clinic import published_diagnoses
    minimum = int(os.environ.get('X_POST_MIN_INTENSITY', '70'))
    fresh = timezone.now() - timedelta(hours=int(os.environ.get('X_POST_FRESH_HOURS', '24')))
    return list(published_diagnoses().filter(verdict='spin', intensity__gte=minimum, x_posted_at__isnull=True,
                                             diagnosed_at__gte=fresh).order_by('-intensity', '-diagnosed_at')[:limit])


def run(dry_run: bool = False) -> dict:
    from news.clinic import detail_data
    from news.clinic_models import SpinDiagnosis
    if not dry_run and not enabled():
        return {'status': 'disabled'}
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    posted_today = SpinDiagnosis.objects.filter(x_posted_at__gte=start).count()
    room = max(0, int(os.environ.get('X_POST_DAILY_LIMIT', '3')) - posted_today)
    done = []
    for diagnosis in candidates(room if not dry_run else 3):
        thread = detail_data(diagnosis)['x_share']
        if dry_run:
            done.append({'id': diagnosis.pk, 'posts': thread})
            continue
        ids = []
        try:
            for text in thread:
                ids.append(post(text, ids[-1] if ids else None))
        except (requests.RequestException, RuntimeError, KeyError, ValueError) as error:
            logger.warning('x publish %s: %s', diagnosis.pk, error)
            if not ids:
                break  # nie udało się nawet pierwszego wpisu — klucze albo limit; spróbujemy przy następnym przebiegu
        diagnosis.x_posted_ids, diagnosis.x_posted_at = ids, timezone.now()
        diagnosis.save(update_fields=['x_posted_ids', 'x_posted_at'])
        done.append({'id': diagnosis.pk, 'posted': len(ids), 'of': len(thread)})
    return {'status': 'dry_run' if dry_run else 'ok', 'results': done}
