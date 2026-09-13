"""Opt-in, read-only official X polling. One budgeted page per scheduler cycle."""
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4

import requests
from django.db import transaction
from django.utils import timezone

from news.models import ImportState
from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead


POST_PRICE = Decimal('0.005')
USER_PRICE = Decimal('0.010')
MAX_RESPONSE_BYTES = 1_000_000
NUMERIC_ID = re.compile(r'^[1-9][0-9]{0,18}$')


class PoliticalReadError(Exception):
    def __init__(self, code, http_status=None, retry_seconds=300):
        self.code, self.http_status, self.retry_seconds = code, http_status, retry_seconds
        super().__init__(code)


def configuration():
    token = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
    if os.environ.get('X_POLITICAL_POLLING_ENABLED', '').lower() != 'true' or not token:
        return None
    try:
        config = {'token': token, 'page_size': int(os.environ.get('X_POLITICAL_PAGE_SIZE', '10')),
            'daily_posts': int(os.environ.get('X_POLITICAL_DAILY_POST_LIMIT', '100')),
            'daily_requests': int(os.environ.get('X_POLITICAL_DAILY_REQUEST_LIMIT', '100')),
            'monthly_usd': Decimal(os.environ.get('X_POLITICAL_MONTHLY_USD_LIMIT', '5')),
            'lookback_hours': int(os.environ.get('X_POLITICAL_INITIAL_LOOKBACK_HOURS', '24'))}
        if not (5 <= config['page_size'] <= 100 and 1 <= config['daily_posts'] <= 10000
                and 1 <= config['daily_requests'] <= 10000 and config['monthly_usd'].is_finite()
                and Decimal('0') < config['monthly_usd'] <= Decimal('10000')
                and 1 <= config['lookback_hours'] <= 168):
            raise ValueError()
        return config
    except (ValueError, InvalidOperation):
        raise PoliticalReadError('invalid_political_configuration')


def utc_text(value):
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fetch_x_timeline(account, window, config):
    """Only this fixed official endpoint receives the bearer token; redirects fail."""
    if not NUMERIC_ID.fullmatch(account.user_id):
        raise PoliticalReadError('invalid_account_identity')
    params = {'max_results': window['page_size'], 'exclude': 'retweets',
        'post.fields': 'id,text,created_at,entities,attachments,note_post,public_metrics,possibly_sensitive,withheld',
        'expansions': 'author_id,attachments.media_keys',
        'user.fields': 'id,name,username,profile_image_url,protected',
        'media.fields': 'media_key,type,url,preview_image_url,alt_text', 'end_time': window['end_time']}
    if window.get('since_id'):
        params['since_id'] = window['since_id']
    else:
        params['start_time'] = window['start_time']
    if window.get('pagination_token'):
        params['pagination_token'] = window['pagination_token']
    started = time.monotonic()
    with requests.get(f'https://api.x.com/2/users/{account.user_id}/tweets', params=params,
            headers={'Authorization': 'Bearer ' + config['token'], 'Accept': 'application/json'},
            timeout=(5, 15), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            wait = 3600 if response.status_code in (401, 402, 403) else 300
            try:
                wait = max(wait, int(response.headers.get('retry-after', 0)),
                    int(response.headers.get('x-rate-limit-reset', 0)) - int(time.time()))
            except (ValueError, TypeError):
                pass
            raise PoliticalReadError(f'x_http_{response.status_code}', response.status_code, min(wait, 86400))
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES or time.monotonic() - started > 25:
                raise PoliticalReadError('x_response_limit', 200)
            chunks.append(chunk)
        return b''.join(chunks)


def media_url(value):
    if not isinstance(value, str) or len(value) > 1024:
        return ''
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == 'https' and parsed.hostname == 'pbs.twimg.com' and not parsed.username and parsed.port in (None, 443) else ''
    except ValueError:
        return ''


def parse_page(raw, account, window):
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise PoliticalReadError('invalid_x_json')
    if not isinstance(payload, dict) or payload.get('errors'):
        raise PoliticalReadError('x_partial_or_invalid_response')
    rows, meta, includes = payload.get('data', []), payload.get('meta'), payload.get('includes', {})
    if (not isinstance(rows, list) or len(rows) > window['page_size'] or not isinstance(meta, dict)
            or meta.get('result_count') != len(rows) or not isinstance(includes, dict)):
        raise PoliticalReadError('invalid_x_page')
    token = meta.get('next_token', '')
    if (not isinstance(token, str) or len(token) > 2048 or (token and token == window.get('pagination_token'))):
        raise PoliticalReadError('x_pagination_did_not_advance')
    users = includes.get('users', [])
    if not isinstance(users, list) or len(users) > 1:
        raise PoliticalReadError('unexpected_x_user_expansion')
    author = users[0] if users else {}
    if rows and (not isinstance(author, dict) or author.get('id') != account.user_id
            or str(author.get('username', '')).lower() != account.handle.lower()
            or author.get('protected') is not False or not isinstance(author.get('name'), str)):
        raise PoliticalReadError('x_account_identity_not_confirmed')
    author = {key: author[key] for key in ('id', 'username', 'name', 'protected') if key in author}
    if users and media_url(users[0].get('profile_image_url')):
        author['profile_image_url'] = users[0]['profile_image_url']
    media_items = includes.get('media', [])
    if not isinstance(media_items, list) or len(media_items) > 400:
        raise PoliticalReadError('invalid_x_media')
    parsed, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not NUMERIC_ID.fullmatch(row['id']):
            raise PoliticalReadError('invalid_x_post_identity')
        if row['id'] in seen or row.get('author_id') != account.user_id:
            raise PoliticalReadError('x_post_author_or_duplicate')
        seen.add(row['id'])
        if window.get('since_id') and int(row['id']) <= int(window['since_id']):
            raise PoliticalReadError('x_post_before_cursor')
        note = row.get('note_post')
        text = note.get('text') if isinstance(note, dict) else row.get('text')
        if not isinstance(text, str) or not text or len(text) > 100000:
            raise PoliticalReadError('missing_x_post_text')
        try:
            published = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            if published.tzinfo is None or published > timezone.now() + timedelta(minutes=5):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise PoliticalReadError('missing_x_post_date')
        if published > datetime.fromisoformat(window['end_time'].replace('Z', '+00:00')):
            raise PoliticalReadError('x_post_outside_window')
        if not window.get('since_id') and published < datetime.fromisoformat(window['start_time'].replace('Z', '+00:00')):
            raise PoliticalReadError('x_post_outside_window')
        attached = row.get('attachments', {})
        keys = attached.get('media_keys', []) if isinstance(attached, dict) else []
        if not isinstance(keys, list):
            raise PoliticalReadError('invalid_x_attachments')
        media = []
        for key in keys:
            matches = [item for item in media_items if isinstance(item, dict) and item.get('media_key') == key]
            if len(matches) != 1:
                continue
            item = matches[0]
            candidate = item.get('url') if item.get('type') == 'photo' else item.get('preview_image_url')
            if item.get('type') in ('photo', 'video', 'animated_gif') and media_url(candidate):
                media.append({'media_key': key, 'type': item['type'], 'thumbnail_url': candidate})
        available = not bool(row.get('withheld'))
        parsed.append({'post_id': row['id'], 'url': f'https://x.com/{account.handle}/status/{row["id"]}',
            'text': text if available else '', 'published_at': published,
            'source_data': row if available else {}, 'author_data': author if available else {},
            'media': media if available else [], 'available': available, 'camp_at_collection': account.camp})
    return parsed, token, len(users)


def reserve(account_id, config):
    """A global DB lease serializes reservation across worker processes as well."""
    now, token = timezone.now(), uuid4().hex
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='political-x-budget')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        budget = dict(state.cursor)
        if budget.get('lease_until', '') > now.isoformat() or budget.get('blocked_until', '') > now.isoformat():
            return None, 'deferred'
        account = PoliticalAccount.objects.select_for_update().get(pk=account_id)
        if not account.enabled or not account.is_confirmed() or account.next_poll_at > now:
            return None, 'unconfirmed_or_not_due'
        month, day = now.astimezone(dt_timezone.utc).strftime('%Y-%m'), now.astimezone(dt_timezone.utc).date().isoformat()
        if budget.get('month') != month:
            budget = {'month': month, 'spent_upper_usd': '0'}
        if budget.get('day') != day:
            budget.update(day=day, daily_requests=0, daily_posts=0)
        cursor = dict(account.poll_cursor)
        window = cursor.get('window') or {'since_id': cursor.get('since_id', ''),
            'start_time': cursor.get('completed_until') or utc_text(now - timedelta(hours=config['lookback_hours'])),
            'end_time': utc_text(now - timedelta(seconds=30)), 'page_size': config['page_size'], 'newest_id': ''}
        slots = window['page_size']
        cost = POST_PRICE * slots + USER_PRICE
        if (budget.get('daily_requests', 0) >= config['daily_requests']
                or budget.get('daily_posts', 0) + slots > config['daily_posts']
                or Decimal(budget.get('spent_upper_usd', '0')) + cost > config['monthly_usd']):
            return None, 'budget_limit'
        read = PoliticalRead.objects.create(account=account, reserved_posts=slots, reserved_usd=cost)
        budget.update(spent_upper_usd=str(Decimal(budget.get('spent_upper_usd', '0')) + cost),
            daily_requests=budget.get('daily_requests', 0) + 1, daily_posts=budget.get('daily_posts', 0) + slots,
            lease=token, lease_until=(now + timedelta(minutes=2)).isoformat())
        state.cursor, state.last_started = budget, now
        state.save(update_fields=['cursor', 'last_started'])
        account.poll_cursor = {**cursor, 'window': window}
        account.next_poll_at = now + timedelta(minutes=2)
        account.save(update_fields=['poll_cursor', 'next_poll_at'])
        return (account, window, read, token, account.confirmation_fingerprint), 'reserved'


def political_poll_cycle():
    try:
        config = configuration()
    except PoliticalReadError as exc:
        return {'status': 'disabled', 'reason': exc.code, 'new_posts': 0}
    if config is None:
        return {'status': 'disabled', 'reason': 'x_not_configured', 'new_posts': 0}
    candidates = PoliticalAccount.objects.filter(enabled=True, confirmed_at__isnull=False,
        confirmed_by__is_active=True, confirmed_by__is_staff=True, next_poll_at__lte=timezone.now()).order_by('next_poll_at', 'pk')
    account = next((item for item in candidates if item.is_confirmed()), None)
    if account is None:
        return {'status': 'idle', 'reason': 'no_confirmed_due_accounts', 'new_posts': 0}
    reservation, status = reserve(account.pk, config)
    if reservation is None:
        return {'status': status, 'new_posts': 0}
    account, window, read, token, fingerprint = reservation
    try:
        raw = fetch_x_timeline(account, window, config)
        rows, next_token, user_count = parse_page(raw, account, window)
        digest = sha256(raw).hexdigest()
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name='political-x-budget')
            current = PoliticalAccount.objects.select_for_update().get(pk=account.pk)
            if state.cursor.get('lease') != token:
                raise PoliticalReadError('x_lease_superseded')
            if not current.enabled or not current.is_confirmed() or current.confirmation_fingerprint != fingerprint:
                raise PoliticalReadError('x_account_changed_during_read')
            added = 0
            for values in rows:
                existing = PoliticalPost.objects.filter(post_id=values['post_id']).first()
                if existing is not None and existing.account_id != account.pk:
                    raise PoliticalReadError('x_post_source_conflict')
                if existing is not None and not existing.available:
                    # A staff withdrawal must not be undone by a later poll/replay.
                    continue
                _, created = PoliticalPost.objects.update_or_create(post_id=values['post_id'], defaults={
                    **values, 'account': current, 'response_sha256': digest, 'fetched_at': timezone.now()})
                added += int(created)
            newest = max([int(window.get('newest_id') or 0)] + [int(row['post_id']) for row in rows])
            cursor = dict(current.poll_cursor)
            if next_token:
                cursor['window'] = {**window, 'pagination_token': next_token, 'newest_id': str(newest) if newest else ''}
            else:
                cursor.pop('window', None)
                cursor['since_id'] = str(newest) if newest else cursor.get('since_id', '')
                cursor['completed_until'] = window['end_time']
            current.poll_cursor, current.last_error = cursor, ''
            current.last_polled_at = timezone.now()
            current.next_poll_at = timezone.now() + timedelta(seconds=60 if next_token else current.poll_interval_minutes * 60)
            current.save(update_fields=['poll_cursor', 'last_error', 'last_polled_at', 'next_poll_at'])
            # Settle only a fully validated response. Unknown/error outcomes keep
            # the full reservation; repeated resources get no assumed discount.
            used_cost = POST_PRICE * len(rows) + USER_PRICE * user_count
            budget = dict(state.cursor)
            if budget.get('day') == read.started_at.astimezone(dt_timezone.utc).date().isoformat():
                budget['daily_posts'] -= read.reserved_posts - len(rows)
            budget['spent_upper_usd'] = str(Decimal(budget['spent_upper_usd']) - read.reserved_usd + used_cost)
            budget.update(lease=None, lease_until='')
            state.cursor, state.last_success, state.last_error = budget, timezone.now(), ''
            state.save(update_fields=['cursor', 'last_success', 'last_error'])
            read.status, read.http_status, read.returned_posts, read.finished_at = 'ok', 200, len(rows), timezone.now()
            read.save(update_fields=['status', 'http_status', 'returned_posts', 'finished_at'])
        return {'status': 'ok', 'new_posts': added, 'returned_posts': len(rows), 'account_id': account.pk,
            'more_pages': bool(next_token), 'published_threads': 0}
    except Exception as exc:
        code = exc.code if isinstance(exc, PoliticalReadError) else 'x_read_failed'
        wait = exc.retry_seconds if isinstance(exc, PoliticalReadError) else 300
        http_status = getattr(exc, 'http_status', None)
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name='political-x-budget')
            if state.cursor.get('lease') == token:
                budget = dict(state.cursor)
                budget.update(lease=None, lease_until='')
                if http_status in (401, 402, 403, 429):
                    budget['blocked_until'] = (timezone.now() + timedelta(seconds=wait)).isoformat()
                state.cursor, state.last_error = budget, code
                state.save(update_fields=['cursor', 'last_error'])
                PoliticalAccount.objects.filter(pk=account.pk).update(last_error=code,
                    next_poll_at=timezone.now() + timedelta(seconds=wait))
            PoliticalRead.objects.filter(pk=read.pk).update(status='error', http_status=http_status, finished_at=timezone.now())
        return {'status': 'error', 'reason': code, 'new_posts': 0, 'account_id': account.pk}
