"""Miniatury kont X (13.10): zbieranie wpisów nie prosi o profile_image_url, więc avatar_url w API był pusty.

Osobny moduł, bez zmian w zapytaniach zbierających wpisy (x_watch, political_polling, nastroje, odbior_spinu):
- jedno wywołanie GET /2/users/by na najwyżej 100 kont (usernames, user.fields=profile_image_url), przez istniejące
  `political_polling.request_x` (stały host api.x.com, bez przekierowań, limit rozmiaru i czasu);
- budżet: ta sama rezerwacja co odczyty wpisów (ImportState 'political-x-budget': dzierżawa, limit dzienny zapytań,
  limit miesięczny USD; koszt USER_PRICE za konto); brak budżetu = przerwanie z komunikatem, nic poza limitem;
- tożsamość: zapis tylko, gdy id konta z X zgadza się z PoliticalAccount.user_id (nie po samej nazwie);
- adres: tylko https://pbs.twimg.com/profile_images/..., wariant _bigger; odświeżanie najwyżej co 30 dni na konto.
Harmonogram (beat) NIE jest dodany - docs/SPINA_V3_API.md opisuje, jak go włączyć po zgodzie właściciela.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

BATCH = 100
REFRESH_DAYS = 30
ENDPOINT = 'https://api.x.com/2/users/by'
AVATAR_HOST = 'pbs.twimg.com'


class AvatarError(Exception):
    pass


def clean_avatar(value) -> str:
    """Adres miniatury tylko z pbs.twimg.com/profile_images po https, wariant _bigger; inaczej pusty napis."""
    if not isinstance(value, str) or len(value) > 500:
        return ''
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme != 'https' or parts.hostname != AVATAR_HOST or not parts.path.startswith('/profile_images/'):
        return ''
    if parts.query or parts.fragment or parts.username or parts.password or parts.port:
        return ''
    return value.replace('_normal.', '_bigger.')


def due_accounts(older_than_days=REFRESH_DAYS, limit=200, now=None):
    from django.db.models import Q
    from news.political_models import PoliticalAccount
    now = now or timezone.now()
    rows = (PoliticalAccount.objects.filter(enabled=True)
            .filter(Q(avatar_checked_at__isnull=True) | Q(avatar_checked_at__lt=now - timedelta(days=older_than_days)))
            .order_by('avatar_checked_at', 'pk'))
    return [a for a in rows[:limit * 2] if a.is_confirmed()][:limit]


def estimate(n_accounts) -> dict:
    from news.political_polling import USER_PRICE
    calls = -(-n_accounts // BATCH)
    return {'accounts': n_accounts, 'calls': calls, 'usd_upper': str(USER_PRICE * n_accounts)}


def reserve(n_accounts, config, now=None):
    """Rezerwacja w tym samym budżecie co odczyty wpisów. (token, koszt) albo AvatarError z powodem."""
    from news.models import ImportState
    from news.political_polling import USER_PRICE
    now, token = now or timezone.now(), uuid4().hex
    cost = USER_PRICE * n_accounts
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='political-x-budget')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        budget = dict(state.cursor or {})
        if budget.get('lease_until', '') > now.isoformat() or budget.get('blocked_until', '') > now.isoformat():
            raise AvatarError('budżet zajęty albo wstrzymany (dzierżawa innego odczytu albo blokada po błędzie X) - spróbuj później')
        month, day = now.strftime('%Y-%m'), now.date().isoformat()
        if budget.get('month') != month:
            budget = {'month': month, 'spent_upper_usd': '0'}
        if budget.get('day') != day:
            budget.update(day=day, daily_requests=0, daily_posts=0)
        if budget.get('daily_requests', 0) >= config['daily_requests']:
            raise AvatarError('brak budżetu: dzienny limit zapytań X wyczerpany')
        if Decimal(budget.get('spent_upper_usd', '0')) + cost > config['monthly_usd']:
            raise AvatarError(f'brak budżetu: miesięczny limit USD nie pomieści {cost} USD')
        budget.update(spent_upper_usd=str(Decimal(budget.get('spent_upper_usd', '0')) + cost),
                      daily_requests=budget.get('daily_requests', 0) + 1, lease=token,
                      lease_until=(now + timedelta(minutes=2)).isoformat(),
                      avatar_reads=budget.get('avatar_reads', 0) + 1)
        state.cursor, state.last_started = budget, now
        state.save(update_fields=['cursor', 'last_started'])
    return token, cost


def settle(token, reserved, used):
    """Zwolnienie dzierżawy i rozliczenie: koszt zarezerwowany minus faktyczny (konta zwrócone przez X)."""
    from news.models import ImportState
    with transaction.atomic():
        state = ImportState.objects.select_for_update().filter(name='political-x-budget').first()
        if state is None:
            return
        budget = dict(state.cursor or {})
        budget['spent_upper_usd'] = str(max(Decimal('0'), Decimal(budget.get('spent_upper_usd', '0')) - reserved + used))
        if budget.get('lease') == token:
            budget.update(lease=None, lease_until='')
        state.cursor = budget
        state.save(update_fields=['cursor'])


def parse(raw, accounts) -> tuple[dict, int]:
    """({pk konta: avatar} tylko dla kont, których id z X zgadza się z user_id, liczba obiektów zwróconych przez X -
    każdy jest płatny, także odrzucony przez kontrolę tożsamości)."""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise AvatarError('nieprawidłowa odpowiedź X (JSON)') from None
    by_handle = {a.handle.lower(): a for a in accounts}
    found = {}
    rows = (payload.get('data') or []) if isinstance(payload, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        account = by_handle.get(str(row.get('username', '')).lower())
        if account is None or str(row.get('id')) != account.user_id:
            continue
        found[account.pk] = clean_avatar(row.get('profile_image_url'))
    return found, len(rows) if isinstance(rows, list) else 0


def refresh(*, limit=200, older_than_days=REFRESH_DAYS, dry_run=False, config=None, now=None) -> dict:
    from news.political_models import PoliticalAccount
    from news.political_polling import USER_PRICE, PoliticalReadError, configuration, request_x
    now = now or timezone.now()
    accounts = due_accounts(older_than_days, limit, now)
    result = {**estimate(len(accounts)), 'updated': 0, 'empty': 0, 'dry_run': dry_run}
    if dry_run or not accounts:
        return result
    config = config or configuration()
    if config is None:
        raise AvatarError('API X wyłączone (X_POLITICAL_POLLING_ENABLED albo brak tokenu)')
    for start in range(0, len(accounts), BATCH):
        batch = accounts[start:start + BATCH]
        token, reserved = reserve(len(batch), config, now)
        used = Decimal('0')
        try:
            raw = request_x(ENDPOINT, {'usernames': ','.join(a.handle for a in batch), 'user.fields': 'profile_image_url'}, config)
            found, returned = parse(raw, batch)
            used = USER_PRICE * returned
        except PoliticalReadError as error:
            raise AvatarError(f'X: {error.code}') from None
        finally:
            settle(token, reserved, used)
        for account in batch:
            avatar = found.get(account.pk, '')
            PoliticalAccount.objects.filter(pk=account.pk).update(
                avatar_url=avatar or account.avatar_url, avatar_checked_at=now)
            result['updated' if avatar else 'empty'] += 1
    return result
