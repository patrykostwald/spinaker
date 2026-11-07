"""Local budget pacing for opt-in fast alerts. No network or credentials."""
from calendar import monthrange
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal
from math import ceil

from django.utils import timezone

from news.models import ImportState


def budget_snapshot(config, cursor=None, now=None):
    now = (now or timezone.now()).astimezone(dt_timezone.utc)
    if cursor is None:
        state = ImportState.objects.filter(name='political-x-budget').first()
        cursor = state.cursor if state else {}
    same_month = cursor.get('month') == now.strftime('%Y-%m')
    same_day = cursor.get('day') == now.date().isoformat()
    spent = Decimal(cursor.get('spent_upper_usd', '0')) if same_month else Decimal('0')
    requests = int(cursor.get('daily_requests', 0)) if same_day else 0
    posts = int(cursor.get('daily_posts', 0)) if same_day else 0
    remaining = max(0, config['daily_requests'] - requests)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_left = ((midnight + timedelta(days=1)) - now).total_seconds()
    # Slow down if money has been spent faster than the month's elapsed share.
    elapsed = (now - midnight.replace(day=1)).total_seconds()
    month_seconds = monthrange(now.year, now.month)[1] * 86400
    expected = config['monthly_usd'] * Decimal(str(max(elapsed, 86400) / month_seconds))
    pressure = max(Decimal('1'), spent / expected)
    interval = max(config.get('fast_poll_seconds', 60),
        ceil(seconds_left / max(1, remaining) * float(pressure)))
    return {'fast_mode': bool(config.get('fast_mode')), 'daily_requests': requests,
        'daily_request_limit': config['daily_requests'], 'daily_posts': posts,
        'daily_post_limit': config['daily_posts'], 'spent_upper_usd': str(spent),
        'monthly_usd_limit': str(config['monthly_usd']),
        'remaining_usd': str(max(Decimal('0'), config['monthly_usd'] - spent)),
        'paced_interval_seconds': interval, 'next_fast_poll_at': cursor.get('next_fast_poll_at', '')}
