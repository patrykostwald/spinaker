"""Official recent search: bounded queries, shared checkpoints and local metrics."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import json
import logging
import re
from statistics import median
import time

from django.db.models import Count
from django.utils import timezone

from news.political_models import PoliticalPost
from news.political_polling import POST_PRICE, USER_PRICE, POST_FIELDS, MEDIA_FIELDS, PoliticalReadError, parse_page, request_x, utc_text

# Self-serve recent search, not the Enterprise schema maximum of 4096.
# https://docs.x.com/x-api/posts/search/integrate/build-a-query
QUERY_LIMIT = 512
HANDLE = re.compile(r'^[A-Za-z0-9_]{1,15}$')


def query_for(accounts):
    terms = []
    for account in accounts:
        if not HANDLE.fullmatch(account.handle):
            raise PoliticalReadError('invalid_account_identity')
        term = 'from:' + account.handle
        if not account.include_replies:
            term = '(' + term + ' -is:reply)'
        terms.append(term)
    return '(' + ' OR '.join(terms) + ') -is:retweet'


def build_queries(accounts, limit=QUERY_LIMIT):
    """Only caller-supplied verified handles; count the entire unencoded query."""
    groups, batch = [], []
    for account in accounts:
        if len(query_for([*batch, account])) > limit:
            if not batch:
                raise PoliticalReadError('x_query_limit')
            groups.append((batch, query_for(batch)))
            batch = []
        batch.append(account)
        if len(query_for(batch)) > limit:
            raise PoliticalReadError('x_query_limit')
    if batch:
        groups.append((batch, query_for(batch)))
    return groups


def checkpoint(account):
    cursor = account.poll_cursor
    window = cursor.get('window')
    # Pending windows must stay intact; priorities never split pagination.
    return json.dumps(window or {k: cursor.get(k, '') for k in ('since_id', 'completed_until')}, sort_keys=True)


def activity_counts(accounts):
    return dict(PoliticalPost.objects.filter(account_id__in=[a.pk for a in accounts],
        published_at__gte=timezone.now() - timedelta(days=14)).order_by().values('account_id')
        .annotate(n=Count('pk')).values_list('account_id', 'n'))


def watch_groups(accounts, config, pending_only=False):
    from news.political_polling import followed_account_ids
    followed = followed_account_ids([a.pk for a in accounts])
    counts = activity_counts(accounts)
    # Fast tier: all post-mode follows, plus the most active 10% with evidence.
    ranked = sorted((a for a in accounts if counts.get(a.pk)), key=lambda a: (-counts[a.pk], a.pk))
    active = {a.pk for a in ranked[:max(1, (len(accounts) + 9) // 10)]}
    def rank(a):
        return 0 if a.pk in followed else 1 if a.pk in active else 2
    buckets = defaultdict(list)
    now = timezone.now()
    for account in accounts:
        window = account.poll_cursor.get('window')
        if window:
            if window.get('query'):
                buckets[('pending', checkpoint(account))].append(account)
            continue
        if pending_only:
            continue
        seconds = config['watch_seconds'] if rank(account) < 2 else config['slow_minutes'] * 60
        due = account.next_poll_at if account.last_error else (
            account.last_polled_at + timedelta(seconds=seconds) if account.last_polled_at else now)
        if due <= now:
            # Separating tiers ensures a small remaining budget goes to follows.
            # Completed timestamp is a coverage watermark, including empty
            # responses. Accounts caught up through the same instant can merge
            # safely even if their last *nonempty* IDs differ. This allows an
            # existing timeline installation to converge from singleton cursors.
            boundary = account.poll_cursor.get('completed_until') or checkpoint(account)
            buckets[(rank(account), boundary)].append(account)
    result = []
    for (tier, boundary), members in buckets.items():
        members.sort(key=lambda a: a.pk)
        if tier == 'pending':
            window = members[0].poll_cursor['window']
            if sorted(a.pk for a in members) != sorted(window['account_ids']):
                # A disabled/reconfirmed member needs staff review; do not replay
                # the other members with a fresh window.
                continue
            batches = [(members, window['query'])]
        else:
            batches = build_queries(members)
        for batch, query in batches:
            priority = min(rank(a) for a in batch)
            result.append({'ids': [a.pk for a in batch], 'query': query, 'checkpoint': boundary,
                'end_time': utc_text(now - timedelta(seconds=10)),
                'checkpoints': {a.pk: checkpoint(a) for a in batch},
                'since_id': str(max(int(a.poll_cursor.get('since_id') or 0) for a in batch))
                    if any(a.poll_cursor.get('since_id') for a in batch) else '',
                'priority': priority, 'due': min(a.next_poll_at for a in batch),
                'interval': config['watch_seconds'] if priority < 2 else config['slow_minutes'] * 60})
    return sorted(result, key=lambda g: (g['priority'], g['due'], g['ids'][0]))


def fetch_x_search(window, config):
    if len(window['query']) > QUERY_LIMIT:
        raise PoliticalReadError('x_query_limit')
    params = {'query': window['query'], 'max_results': window['page_size'], 'sort_order': 'recency',
        'post.fields': POST_FIELDS,
        'expansions': 'attachments.media_keys',
        'media.fields': MEDIA_FIELDS}
    # X nie pozwala łączyć since_id z start_time/end_time (6.10: błąd 400 „Invalid use of since_id … with start_time or
    # end_time” zatrzymał zbieranie). Z since_id czytamy wszystko nowsze od ostatniego wpisu; bez niego - okno czasowe.
    # since_id starszy niż 7 dni X też odrzuca (400 „since_id must be a tweet id created after …”) - wtedy okno czasowe
    since_ok = False
    if window.get('since_id'):
        try:
            made = datetime.fromtimestamp(((int(window['since_id']) >> 22) + 1288834974657) / 1000, tz=dt_timezone.utc)
            since_ok = made > timezone.now() - timedelta(days=6, hours=23)
        except (TypeError, ValueError, OverflowError):
            since_ok = False
    if since_ok:
        params['since_id'] = window['since_id']
    else:
        floor = utc_text(timezone.now() - timedelta(days=6, hours=23))
        params['start_time'] = max(window['start_time'], floor)
        params['end_time'] = window['end_time']
    if window.get('pagination_token'):
        params['next_token'] = window['pagination_token']
    return request_x('https://api.x.com/2/tweets/search/recent', params, config)


def parse_search_page(raw, accounts, window):
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
    authors = {a.user_id: a for a in accounts}
    seen, parsed = set(), []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in seen or row.get('author_id') not in authors:
            raise PoliticalReadError('x_post_author_or_duplicate')
        seen.add(row['id'])
        account = authors[row['author_id']]
        values, _, _ = parse_page(json.dumps({'data': [row], 'meta': {**meta, 'result_count': 1},
            'includes': includes}), account, window)
        parsed.extend({**value, 'account_id': account.pk} for value in values)
    # Validate metadata and expansions on empty responses too.
    _, next_token, _ = parse_page(json.dumps({'data': [], 'meta': {**meta, 'result_count': 0},
        'includes': includes}), accounts[0], window)
    return parsed, next_token, 0


def batched_cycle(accounts, config, pending_only=False):
    from news.political_models import PoliticalAccount
    from news.political_polling import poll_page
    groups = watch_groups(accounts, config, pending_only)
    result = {'status': 'idle', 'new_posts': 0, 'returned_posts': 0, 'pages': 0}
    # Leave room for the last HTTP timeout under the task's soft limit.
    deadline = time.monotonic() + max(1, min(30, config['watch_seconds'] - 25))
    while groups:
        group = groups.pop(0)
        page = poll_page(config, group['ids'][0], group, group['interval'])
        result['new_posts'] += page['new_posts']
        result['returned_posts'] += page.get('returned_posts', 0)
        if page['status'] == 'ok':
            result['pages'] += 1
            result['status'] = 'ok'
            if page['more_pages']:
                current = PoliticalAccount.objects.get(pk=group['ids'][0])
                groups.append({**group, 'checkpoint': checkpoint(current),
                    'checkpoints': {pk: checkpoint(current) for pk in group['ids']}})
                groups.sort(key=lambda g: g['priority'])
        elif page['status'] not in ('deferred', 'unconfirmed_or_not_due'):
            result.update(status=page['status'], reason=page.get('reason', page['status']))
            break
        if time.monotonic() >= deadline:
            break
    result['more_pages'] = bool(groups)
    return result


def wake_screening(post_ids):
    # Posts themselves form the durable fallback queue for the 5-minute sweeper.
    try:
        from news.tasks import clinic_screen_task
        # This deployment uses Redis: zero is its highest delivery priority.
        clinic_screen_task.apply_async(kwargs={'post_ids': post_ids}, priority=0)
    except Exception:
        logging.getLogger(__name__).exception('Immediate screening dispatch failed; periodic screening will retry')


def monthly_cost(posts_daily, profiles_daily=0):
    return Decimal(30) * (Decimal(str(posts_daily)) * POST_PRICE + Decimal(str(profiles_daily)) * USER_PRICE)


def latency_metrics(now=None):
    since = (now or timezone.now()) - timedelta(days=7)
    posts = PoliticalPost.objects.filter(published_at__gte=since)
    ingestion = [(f - p).total_seconds() for p, f in posts.values_list('published_at', 'fetched_at') if f >= p]
    diagnoses = [(d - p).total_seconds() for p, d in posts.filter(
        spin_diagnosis__diagnosed_at__isnull=False, spin_diagnosis__error='',
        spin_diagnosis__status__in=['approved', 'pending_review', 'rejected']).values_list(
            'published_at', 'spin_diagnosis__diagnosed_at') if d >= p]
    return {'ingestion_seconds': median(ingestion) if ingestion else None,
        'diagnosis_seconds': median(diagnoses) if diagnoses else None,
        'posts': len(ingestion), 'diagnoses': len(diagnoses)}
