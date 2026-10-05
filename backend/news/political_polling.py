"""Opt-in official X polling with shared pre-request budget reservations."""
from datetime import datetime, timedelta, timezone as dt_timezone
import logging
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
POST_FIELDS = ('id,text,author_id,created_at,entities,attachments,note_post,public_metrics,'
    'possibly_sensitive,withheld,referenced_tweets,in_reply_to_user_id')
MEDIA_FIELDS = 'media_key,type,url,preview_image_url,alt_text,variants,duration_ms'
MAX_RESPONSE_BYTES = 1_000_000
NUMERIC_ID = re.compile(r'^[1-9][0-9]{0,18}$')

logger = logging.getLogger(__name__)


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
            'mode': os.environ.get('X_POLL_MODE', 'timeline'),
            'watch_seconds': max(30, int(os.environ.get('X_WATCH_SECONDS', '60'))),
            'slow_minutes': max(1, int(os.environ.get('X_WATCH_SLOW_MINUTES', '15'))),
            'followed_minutes': max(5, int(os.environ.get('X_FOLLOWED_POLL_MINUTES', '15'))),
            'daily_posts': int(os.environ.get('X_POLITICAL_DAILY_POST_LIMIT', '100')),
            'daily_requests': int(os.environ.get('X_POLITICAL_DAILY_REQUEST_LIMIT', '100')),
            'monthly_usd': Decimal(os.environ.get('X_POLITICAL_MONTHLY_USD_LIMIT', '5')),
            'lookback_hours': int(os.environ.get('X_POLITICAL_INITIAL_LOOKBACK_HOURS', '24'))}
        if not (config['mode'] in ('timeline', 'batched') and 5 <= config['page_size'] <= 100 and 1 <= config['daily_posts'] <= 10000
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
    params = {'max_results': window['page_size'],
        'post.fields': POST_FIELDS,
        'expansions': 'attachments.media_keys',
        'media.fields': MEDIA_FIELDS, 'end_time': window['end_time']}
    exclude = ([] if account.include_reposts else ['retweets']) + ([] if account.include_replies else ['replies'])
    if exclude:
        params['exclude'] = ','.join(exclude)
    if window.get('since_id'):
        params['since_id'] = window['since_id']
    else:
        params['start_time'] = window['start_time']
    if window.get('pagination_token'):
        params['pagination_token'] = window['pagination_token']
    return request_x(f'https://api.x.com/2/users/{account.user_id}/tweets', params, config)


def request_x(url, params, config):
    started = time.monotonic()
    with requests.get(url, params=params,
            headers={'Authorization': 'Bearer ' + config['token'], 'Accept': 'application/json'},
            timeout=(5, 15), allow_redirects=False, stream=True) as response:
        from news.repairer import provider_event
        provider_event('x', None if response.status_code == 200 else f'http_{response.status_code}')
        if response.status_code != 200:
            wait = 3600 if response.status_code in (401, 402, 403) else 300
            try:
                wait = max(wait, int(response.headers.get('retry-after', 0)),
                    int(response.headers.get('x-rate-limit-reset', 0)) - int(time.time()))
            except (ValueError, TypeError):
                pass
            error = PoliticalReadError(f'x_http_{response.status_code}', response.status_code, min(wait, 86400))
            # opis błędu od X (bez danych dostępowych) - bez niego 400 było nie do zdiagnozowania (6.10)
            try:
                body = response.raw.read(2000, decode_content=True).decode('utf-8', 'replace')
                error.detail = ' '.join(body.split())[:300]
            except Exception:  # noqa: BLE001
                error.detail = ''
            raise error
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES or time.monotonic() - started > 25:
                raise PoliticalReadError('x_response_limit', 200)
            chunks.append(chunk)
        return b''.join(chunks)


def media_url(value, host='pbs.twimg.com'):
    if not isinstance(value, str) or len(value) > 1024:
        return ''
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == 'https' and parsed.hostname == host and not parsed.username and parsed.port in (None, 443) else ''
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
    if not isinstance(users, list) or users:
        raise PoliticalReadError('unexpected_x_user_expansion')
    author = {'id': account.user_id, 'username': account.handle, 'name': account.display_name}
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
            if item.get('type') not in ('photo', 'video', 'animated_gif'):
                continue
            attachment = {'media_key': key, 'type': item['type']}
            if media_url(candidate):
                attachment['thumbnail_url'] = candidate
            if isinstance(item.get('alt_text'), str):
                attachment['alt_text'] = item['alt_text']
            if item['type'] in ('video', 'animated_gif'):
                variants = item.get('variants')
                attachment['variants'] = [dict(v) for v in variants
                    if isinstance(v, dict) and media_url(v.get('url'), 'video.twimg.com')] if isinstance(variants, list) else []
                duration = item.get('duration_ms')
                if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0:
                    attachment['duration_ms'] = duration
            if attachment.get('thumbnail_url') or item['type'] in ('video', 'animated_gif'):
                media.append(attachment)
        available = not bool(row.get('withheld'))
        parsed.append({'post_id': row['id'], 'url': f'https://x.com/{account.handle}/status/{row["id"]}',
            'text': text if available else '', 'published_at': published,
            'source_data': row if available else {}, 'author_data': author if available else {},
            'media': media if available else [], 'available': available, 'camp_at_collection': account.camp})
    return parsed, token, len(users)


def followed_account_ids(account_ids):
    from django.conf import settings
    from news.clinic import figures_by_account
    from news.notification_models import Follow
    if not getattr(settings, 'ACCOUNTS_ENABLED', False):
        return set()
    figures = figures_by_account(account_ids)
    followed = set(Follow.objects.filter(mode='posts', figure_id__in=[f.pk for f in figures.values()],
        user__is_active=True).values_list('figure_id', flat=True))
    return {pk for pk, figure in figures.items() if figure.pk in followed}


def poll_minutes(account, config, followed):
    return max(5, min(account.poll_interval_minutes, config.get('followed_minutes', 15))) if followed else account.poll_interval_minutes


def due_at(account, config, followed):
    # A new follow may shorten an existing schedule, but never a retry/backoff or pagination lease.
    if followed and account.last_polled_at and not account.last_error and not account.poll_cursor.get('window'):
        return min(account.next_poll_at, account.last_polled_at + timedelta(minutes=poll_minutes(account, config, True)))
    return account.next_poll_at


def reserve(account_id, config, group=None):
    """Serialize every paid page through one database lease, including both modes.

    Accounts mirror the group's completed checkpoint so mode/group changes cannot
    replay history. An unfinished window always keeps its original membership.
    """
    from news.x_watch import checkpoint, query_for
    now, token = timezone.now(), uuid4().hex
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='political-x-budget')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        budget = dict(state.cursor)
        if budget.get('lease_until', '') > now.isoformat() or budget.get('blocked_until', '') > now.isoformat():
            return None, 'deferred'
        ids = group['ids'] if group else [account_id]
        accounts = list(PoliticalAccount.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        followed = followed_account_ids(ids)
        if len(accounts) != len(ids) or any(not a.enabled or not a.is_confirmed() for a in accounts):
            return None, 'unconfirmed_or_not_due'
        account = accounts[0]
        if group:
            if any(checkpoint(a) != group['checkpoints'][a.pk] for a in accounts):
                return None, 'deferred'
            if any(a.next_poll_at > now and (a.last_error or a.poll_cursor.get('window')) for a in accounts):
                return None, 'deferred'
        elif due_at(account, config, account.pk in followed) > now:
            return None, 'unconfirmed_or_not_due'
        month, day = now.astimezone(dt_timezone.utc).strftime('%Y-%m'), now.astimezone(dt_timezone.utc).date().isoformat()
        if budget.get('month') != month:
            budget = {'month': month, 'spent_upper_usd': '0'}
        if budget.get('day') != day:
            budget.update(day=day, daily_requests=0, daily_posts=0)
        cursor = dict(account.poll_cursor)
        window = cursor.get('window')
        identities = {str(a.pk): a.confirmation_fingerprint for a in accounts}
        if window and window.get('identities', identities) != identities:
            return None, 'account_changed'
        if group and not window and query_for(accounts) != group['query']:
            return None, 'account_changed'
        if not window:
            window = {'since_id': cursor.get('since_id', ''),
                'start_time': cursor.get('completed_until') or utc_text(now - timedelta(hours=config['lookback_hours'])),
                'end_time': group['end_time'] if group else utc_text(now - timedelta(seconds=30)),
                'page_size': max(10, config['page_size']) if group else config['page_size'], 'newest_id': '',
                'identities': identities}
            if group:
                window.update(query=group['query'], account_ids=ids, since_id=group['since_id'])
        if group and window.get('account_ids') != ids:
            return None, 'deferred'
        # A response saved before a DB/worker failure is consumed locally, without
        # another reservation or network request. Keep the original accounting date.
        read = PoliticalRead.objects.filter(pk=window.get('read_id'), response_body__isnull=False).first()
        if read is None:
            minimum = 10 if group else 5
            remaining = min(config['daily_posts'] - budget.get('daily_posts', 0),
                int((config['monthly_usd'] - Decimal(budget.get('spent_upper_usd', '0'))) / POST_PRICE))
            slots = min(window['page_size'], remaining)
            if budget.get('daily_requests', 0) >= config['daily_requests'] or slots < minimum:
                return None, 'budget_limit'
            window = {**window, 'page_size': slots}
            cost = POST_PRICE * slots
            read = PoliticalRead.objects.create(account=account, started_at=now, reserved_posts=slots, reserved_usd=cost,
                account_ids=ids)
            window['read_id'] = read.pk
            budget.update(spent_upper_usd=str(Decimal(budget.get('spent_upper_usd', '0')) + cost),
                daily_requests=budget.get('daily_requests', 0) + 1, daily_posts=budget.get('daily_posts', 0) + slots)
        budget.update(lease=token, lease_until=(now + timedelta(minutes=2)).isoformat())
        state.cursor, state.last_started = budget, now
        state.save(update_fields=['cursor', 'last_started'])
        for current in accounts:
            current.poll_cursor = {**current.poll_cursor, 'window': window}
            current.next_poll_at = now + timedelta(minutes=2)
            current.save(update_fields=['poll_cursor', 'next_poll_at'])
        return (accounts, window, read, token, {a.pk: a.confirmation_fingerprint for a in accounts}), 'reserved'


def _bounded(call, seconds=40):
    """Twardy limit czasu na całe pobranie z X (6.10: odczyty zawisały i proces był ubijany, zanim zapisał błąd -
    np. przy zawieszonym DNS, którego nie obejmuje timeout w requests). Po przekroczeniu zgłaszamy zwykły błąd,
    więc rezerwacja wraca do limitu, a wątek w tle kończy się sam."""
    import concurrent.futures
    import sys
    if 'pytest' in sys.modules:  # testy podmieniają pobieranie na kod z bazą testową, która nie jest widoczna z innego wątku
        return call()
    from django.db import connection

    def run():
        try:
            return call()
        finally:
            connection.close()  # połączenie z bazą otwarte w wątku (np. przez zapis zdarzenia dostawcy)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(run)
    try:
        return future.result(timeout=seconds)
    except concurrent.futures.TimeoutError:
        logger.warning('x: fetch exceeded %ss', seconds)
        raise PoliticalReadError('x_timeout', 504, 300)
    finally:
        pool.shutdown(wait=False)


def poll_page(config, account_id, group=None, interval=None):
    from news.x_watch import fetch_x_search, parse_search_page, wake_screening
    reservation, status = reserve(account_id, config, group)
    if reservation is None:
        return {'status': status, 'new_posts': 0}
    accounts, window, read, token, fingerprints = reservation
    account = accounts[0]
    try:
        raw = bytes(read.response_body) if read.response_body is not None else None
        logger.info('x read %s: reserved %s posts, fetching (%s)', read.pk, read.reserved_posts, 'search' if group else 'timeline')
        if raw is None:
            raw = _bounded(lambda: fetch_x_search(window, config) if group else fetch_x_timeline(account, window, config))
            logger.info('x read %s: got %s bytes', read.pk, len(raw))
            # Durable inbox: never fetch an already received page just because the
            # later post transaction fails. Cleared after successful consumption.
            PoliticalRead.objects.filter(pk=read.pk).update(response_body=raw)
        if group:
            rows, next_token, user_count = parse_search_page(raw, accounts, window)
        else:
            rows, next_token, user_count = parse_page(raw, account, window)
            rows = [{**row, 'account_id': account.pk} for row in rows]
        logger.info('x read %s: parsed %s posts', read.pk, len(rows))
        digest = sha256(raw).hexdigest()
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name='political-x-budget')
            current_accounts = list(PoliticalAccount.objects.select_for_update().filter(pk__in=fingerprints).order_by('pk'))
            if state.cursor.get('lease') != token:
                raise PoliticalReadError('x_lease_superseded')
            if any(not a.enabled or not a.is_confirmed() or a.confirmation_fingerprint != fingerprints[a.pk]
                   for a in current_accounts):
                raise PoliticalReadError('x_account_changed_during_read')
            added_ids = []
            for values in rows:
                existing = PoliticalPost.objects.filter(post_id=values['post_id']).first()
                if existing is not None:
                    if existing.account_id != values['account_id']:
                        raise PoliticalReadError('x_post_source_conflict')
                    # Preserve first fetched_at and staff withdrawals; no new events.
                    continue
                post, created = PoliticalPost.objects.update_or_create(post_id=values['post_id'], defaults={
                    **values, 'response_sha256': digest, 'fetched_at': timezone.now(), 'watch_priority': True})
                if created:
                    added_ids.append(post.pk)
            newest = max([int(window.get('newest_id') or window.get('since_id') or 0)] + [int(row['post_id']) for row in rows])
            for current in current_accounts:
                cursor = dict(current.poll_cursor)
                if next_token:
                    cursor['window'] = {k: v for k, v in {**window, 'pagination_token': next_token,
                        'newest_id': str(newest) if newest else ''}.items() if k != 'read_id'}
                else:
                    cursor.pop('window', None)
                    cursor['since_id'] = str(newest) if newest else cursor.get('since_id', '')
                    cursor['completed_until'] = window['end_time']
                current.poll_cursor, current.last_error = cursor, ''
                current.last_polled_at = timezone.now()
                seconds = interval or poll_minutes(current, config, current.pk in followed_account_ids([current.pk])) * 60
                current.next_poll_at = timezone.now() + timedelta(seconds=0 if group and next_token else 60 if next_token else seconds)
                current.save(update_fields=['poll_cursor', 'last_error', 'last_polled_at', 'next_poll_at'])
            used_cost = POST_PRICE * len(rows) + USER_PRICE * user_count
            budget = dict(state.cursor)
            if budget.get('day') == read.started_at.astimezone(dt_timezone.utc).date().isoformat():
                budget['daily_posts'] -= read.reserved_posts - len(rows)
            if budget.get('month') == read.started_at.astimezone(dt_timezone.utc).strftime('%Y-%m'):
                budget['spent_upper_usd'] = str(Decimal(budget['spent_upper_usd']) - read.reserved_usd + used_cost)
            budget.update(lease=None, lease_until='')
            state.cursor, state.last_success, state.last_error = budget, timezone.now(), ''
            state.save(update_fields=['cursor', 'last_success', 'last_error'])
            read.status, read.http_status, read.returned_posts, read.finished_at = 'ok', 200, len(rows), timezone.now()
            read.response_body = None
            read.save(update_fields=['status', 'http_status', 'returned_posts', 'finished_at', 'response_body'])
            if added_ids:
                transaction.on_commit(lambda: wake_screening(added_ids))
        return {'status': 'ok', 'new_posts': len(added_ids), 'returned_posts': len(rows), 'account_id': account.pk,
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
                # odczyt z błędem HTTP nic nie kosztuje u X: zwracamy rezerwację do dziennego limitu i budżetu
                # (6.10: pętla błędów 400 co minutę zjadała dzienny limit wpisów, choć nic nie pobrano)
                if http_status and http_status != 200 and not read.response_body:
                    if budget.get('day') == read.started_at.astimezone(dt_timezone.utc).date().isoformat():
                        budget['daily_posts'] = max(0, budget.get('daily_posts', 0) - read.reserved_posts)
                    if budget.get('month') == read.started_at.astimezone(dt_timezone.utc).strftime('%Y-%m'):
                        budget['spent_upper_usd'] = str(max(Decimal('0'), Decimal(budget['spent_upper_usd']) - read.reserved_usd))
                if http_status in (401, 402, 403, 429):
                    budget['blocked_until'] = (timezone.now() + timedelta(seconds=wait)).isoformat()
                detail = getattr(exc, 'detail', '')
                state.cursor, state.last_error = budget, (f'{code}: {detail}' if detail else code)[:500]
                state.save(update_fields=['cursor', 'last_error'])
                PoliticalAccount.objects.filter(pk__in=fingerprints).update(last_error=code,
                    next_poll_at=timezone.now() + timedelta(seconds=wait))
                if http_status == 400:
                    # zła prośba nie naprawi się sama: porzucamy zapamiętane okno (stronę i parametry), następny odczyt
                    # zaczyna od ostatniego pewnego wpisu (since_id)
                    for current in PoliticalAccount.objects.filter(pk__in=fingerprints):
                        cursor = dict(current.poll_cursor); cursor.pop('window', None)
                        PoliticalAccount.objects.filter(pk=current.pk).update(poll_cursor=cursor)
            PoliticalRead.objects.filter(pk=read.pk).update(status='error', http_status=http_status, finished_at=timezone.now())
        return {'status': 'error', 'reason': code, 'new_posts': 0, 'account_id': account.pk}


def release_stale(now=None, minutes=10):
    """Odczyty, które zarezerwowały limit, ale nigdy się nie zakończyły (proces ubity w trakcie, 5-6.10: 376 takich
    odczytów zjadło dzienny limit przy zerze pobranych wpisów). Oznaczamy je jako porzucone i oddajemy limit wpisów
    i budżet z tego samego dnia/miesiąca; przeterminowaną blokadę (lease) zdejmujemy."""
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=minutes)
    with transaction.atomic():
        state = ImportState.objects.select_for_update().filter(name='political-x-budget').first()
        stale = list(PoliticalRead.objects.select_for_update().filter(status='reserved', response_body__isnull=True, started_at__lt=cutoff))
        if not stale and not state:
            return 0
        budget = dict(state.cursor) if state else {}
        for read in stale:
            if budget.get('day') == read.started_at.astimezone(dt_timezone.utc).date().isoformat():
                budget['daily_posts'] = max(0, budget.get('daily_posts', 0) - read.reserved_posts)
            if budget.get('month') == read.started_at.astimezone(dt_timezone.utc).strftime('%Y-%m'):
                budget['spent_upper_usd'] = str(max(Decimal('0'), Decimal(budget.get('spent_upper_usd', '0')) - read.reserved_usd))
        if stale:
            PoliticalRead.objects.filter(pk__in=[r.pk for r in stale]).update(status='abandoned', finished_at=now)
        if budget.get('lease_until') and budget['lease_until'] < now.isoformat():
            budget.update(lease=None, lease_until='')
        if state and (stale or budget != state.cursor):
            state.cursor = budget
            state.save(update_fields=['cursor'])
    if stale:
        logger.warning('x: released %s stale reservations', len(stale))
    return len(stale)


def political_poll_cycle():
    from news.x_watch import batched_cycle
    try:
        config = configuration()
    except PoliticalReadError as exc:
        return {'status': 'disabled', 'reason': exc.code, 'new_posts': 0}
    if config is None:
        return {'status': 'disabled', 'reason': 'x_not_configured', 'new_posts': 0}
    release_stale()
    candidates = list(PoliticalAccount.objects.filter(enabled=True, confirmed_at__isnull=False,
        confirmed_by__is_active=True, confirmed_by__is_staff=True).select_related('confirmed_by'))
    candidates = [a for a in candidates if a.is_confirmed()]
    # Complete pages using the endpoint that issued their token, even after a
    # mode switch. Never reinterpret a search token as a timeline token.
    if config.get('mode', 'timeline') == 'batched':
        pending = [a for a in candidates if a.poll_cursor.get('window') and not a.poll_cursor['window'].get('query')]
        if not pending:
            return batched_cycle(candidates, config)
        candidates = pending
    elif any(a.poll_cursor.get('window', {}).get('query') for a in candidates):
        return batched_cycle(candidates, config, pending_only=True)
    followed = followed_account_ids([a.pk for a in candidates])
    candidates = [a for a in candidates if due_at(a, config, a.pk in followed) <= timezone.now()]
    candidates.sort(key=lambda a: (a.pk not in followed, due_at(a, config, a.pk in followed), a.pk))
    if not candidates:
        return {'status': 'idle', 'reason': 'no_confirmed_due_accounts', 'new_posts': 0}
    return poll_page(config, candidates[0].pk)
