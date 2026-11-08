"""Stored post alerts, rolling groups and Warsaw quiet hours. No source API calls."""
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from news.notification_models import Follow, Notification, NotificationPost, NotificationSettings

logger = logging.getLogger(__name__)
WINDOW = timedelta(minutes=15)
FAST_WINDOW = timedelta(minutes=2)
FAST_HOLD = timedelta(seconds=60)
AVALANCHE = 5


def fast_mode():
    return bool(getattr(settings, 'ALERTS_FAST_MODE', False))


def group_window():
    """Szybki tryb: 1-2 minuty dla pojedynczego wpisu; 15 minut tylko przy lawinie."""
    return FAST_WINDOW if fast_mode() else WINDOW


def eligible_post(post, recent=False):
    if not post.available or not post.text.strip():
        return False
    if recent and post.published_at < timezone.now() - timedelta(hours=2):
        return False
    refs = post.source_data.get('referenced_tweets', post.source_data.get('referenced_posts', []))
    types = {ref.get('type') for ref in refs if isinstance(ref, dict)}
    if not post.account.include_reposts and ('retweeted' in types or post.text.startswith('RT @')):
        return False
    if not post.account.include_replies and ('replied_to' in types or post.source_data.get('in_reply_to_user_id')):
        return False
    return True


def post_data(post):
    diagnosis = getattr(post, 'spin_diagnosis', None)
    published = (post.available and diagnosis and diagnosis.status == 'approved'
        and not diagnosis.hidden_at and not diagnosis.withdrawn_at)
    return {'id': post.pk, 'title': ' '.join(post.text.split())[:90],
        'url': f'/klinika/{diagnosis.pk}' if published else post.url,
        'score': diagnosis.intensity if published else None,
        'quote': ' '.join(post.text.split())[:140]}


def notification_data(row):
    data = {key: getattr(row, key) for key in ('id', 'kind', 'title', 'url', 'created_at', 'read_at')}
    data['posts'] = [post_data(item.post) for item in row.posts.all() if item.post.available]
    if row.kind == 'followed_post':
        if len(data['posts']) == 1:
            data['url'] = data['posts'][0]['url']
        elif not data['posts']:
            data.update(title='Wpis jest niedostępny', url='/konto#powiadomienia')
    return data


def quiet_hours(now=None):
    hour = (now or timezone.now()).astimezone(ZoneInfo('Europe/Warsaw')).hour
    return hour >= 23 or hour < 7


def quiet_for(preferences, figure_id, now=None):
    """Cisza nocna jako ustawienie użytkownika (czas warszawski); osoby „budź mnie” ją przerywają."""
    if preferences is None:
        return quiet_hours(now)
    if not preferences.quiet_hours_enabled:
        return False
    if figure_id in (preferences.wake_person_ids or []):
        return False
    local = (now or timezone.now()).astimezone(ZoneInfo('Europe/Warsaw')).time().replace(second=0, microsecond=0)
    start, end = preferences.quiet_hours_start, preferences.quiet_hours_end
    if start == end:
        return False
    return start <= local < end if start < end else local >= start or local < end


def alert_payload(row):
    data = notification_data(row)
    payload = {key: data[key] for key in ('id', 'title', 'url', 'kind')}
    payload['tag'] = f'followed-figure-{row.figure_id}'
    if len(data['posts']) == 1:
        post = data['posts'][0]
        if post['score'] is not None:
            payload['body'] = f'Zbadane: {post["score"]}/100'
        elif post.get('quote'):
            payload['body'] = post['quote']
    return payload


def record_latency(row, sent_at):
    """Czas od publikacji wpisu do pierwszego przyjęcia push przez dostawcę."""
    for item in row.posts.select_related('post').filter(push_sent_at__isnull=True):
        item.push_sent_at = sent_at
        item.push_latency_seconds = max(0.0, (sent_at - item.post.published_at).total_seconds())
        item.save(update_fields=['push_sent_at', 'push_latency_seconds'])


def send_alert(user, row_id):
    """Wysyłka (i ponowienia) dla jednego alertu; błąd dostawcy nie przerywa pracy."""
    try:
        from news.push import send_to_user
        row = Notification.objects.get(pk=row_id)
        if send_to_user(user, alert_payload(row), notification=row):
            record_latency(row, timezone.now())
    except Exception:
        logger.warning('Followed post push delivery failed', exc_info=True)


def deliver_post(event):
    from news.clinic import figures_by_account
    from news.political_models import PoliticalPost
    post = PoliticalPost.objects.select_related('account').filter(pk=event.target_id).first()
    # Age was checked when the event was queued, not after a worker outage.
    if not post or not eligible_post(post):
        return
    figure = figures_by_account([post.account_id]).get(post.account_id)
    if not figure:
        return
    recipients = Follow.objects.filter(figure=figure, mode='posts', created_at__lte=event.created_at,
        user__is_active=True).select_related('user')
    for follow in recipients:
        # Serialize different post events for this recipient/figure, including empty groups.
        with transaction.atomic():
            locked = Follow.objects.select_for_update().filter(pk=follow.pk, mode='posts').first()
            if not locked:
                continue
            preferences = NotificationSettings.objects.filter(user=follow.user).first()
            if preferences and not preferences.service_enabled:
                continue
            if NotificationPost.objects.filter(notification__user=follow.user, post=post).exists():
                continue
            now = timezone.now()
            # Ten sam tekst tej osoby z innego konta (dubel) nie wysyła drugiego alertu.
            if NotificationPost.objects.filter(notification__user=follow.user, notification__figure=figure,
                    post__text=post.text, notification__created_at__gt=now - timedelta(minutes=10)).exists():
                continue
            window = group_window()
            join = Q(created_at__gt=now - window) | Q(push_sent_at__gt=now - window) | Q(push_pending=True)
            if fast_mode():
                # Lawina wpisów: dłuższe okno, jeden zbiorczy alert.
                join |= Q(created_at__gt=now - WINDOW, post_count__gte=AVALANCHE)
            row = Notification.objects.filter(user=follow.user, figure=figure, kind='followed_post').annotate(
                post_count=Count('posts')).filter(join).order_by('-created_at', '-pk').first()
            if not row:
                row = Notification.objects.create(user=follow.user, figure=figure, kind='followed_post',
                    push_pending=bool(settings.PUSH_ENABLED and preferences and preferences.push_followed))
            NotificationPost.objects.create(notification=row, post=post)
            count = row.posts.count()
            row.title = (f'{figure.canonical_name}: {post_data(post)["title"]}' if count == 1
                else f'{figure.canonical_name.split()[-1]}: {count} nowe wpisy' if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14)
                else f'{figure.canonical_name.split()[-1]}: {count} nowych wpisów')[:240]
            row.url, row.read_at = post_data(post)['url'], None
            row.save(update_fields=['title', 'url', 'read_at'])


def update_diagnosis(diagnosis):
    # Update the original group even if the user has since changed follow mode.
    rows = Notification.objects.filter(posts__post_id=diagnosis.post_id)
    for row in rows:
        row.read_at = None
        if row.posts.count() == 1:
            row.url = f'/klinika/{diagnosis.pk}'
        row.save(update_fields=['read_at', 'url'])


def flush_post_pushes():
    """Called by the existing outbox worker, including cycles with no new events.

    Claim before delivery gives at-most-once first attempts; unsuccessful devices
    are retried by ``push._send_alert`` (do 3 prób w 10 minut). Quiet hours are
    per user (Warsaw time); groups wait until the quiet period ends.
    """
    if not settings.PUSH_ENABLED:
        return
    now = timezone.now()
    ids = list(Notification.objects.filter(push_pending=True).values_list('pk', flat=True)[:100])
    retry = list(Notification.objects.filter(push_pending=False, push_deliveries__finished=False,
        push_deliveries__next_attempt_at__lte=now).values_list('pk', flat=True).distinct()[:100])
    for pk in retry:
        row = Notification.objects.select_related('user').filter(pk=pk).first()
        if row and row.user.is_active:
            send_alert(row.user, pk)
    window = group_window()
    for pk in ids:
        with transaction.atomic():
            row = Notification.objects.select_related('user').filter(pk=pk).first()
            if row is None:
                continue
            if fast_mode() and row.created_at > now - FAST_HOLD:
                continue
            # Same lock order as intake, also serializing pushes from separate groups.
            follow = Follow.objects.select_for_update().filter(user=row.user, figure_id=row.figure_id).first()
            row = Notification.objects.select_for_update(of=('self',)).select_related('user').get(pk=pk)
            if not row.push_pending:
                continue
            preferences = NotificationSettings.objects.filter(user=row.user).first()
            if quiet_for(preferences, row.figure_id, now):
                continue
            content_allowed = bool(follow and follow.mode == 'posts' and row.posts.filter(post__available=True).exists())
            if row.kind == 'followed_diagnosis':
                from news.clinic import published_diagnoses
                diagnosis = published_diagnoses().filter(pk=row.url.rsplit('/', 1)[-1]).first()
                content_allowed = bool(follow and diagnosis and (follow.mode == 'diagnoses'
                    or (follow.mode == 'strong_spin' and diagnosis.intensity >= 70)))
            allowed = (row.user.is_active and content_allowed and preferences is not None
                and preferences.service_enabled and preferences.push_followed)
            if allowed and Notification.objects.filter(user=row.user, figure_id=row.figure_id,
                    push_sent_at__gt=now - window).exclude(pk=row.pk).exists():
                continue
            row.push_pending = False
            row.push_sent_at = now if allowed else None
            row.save(update_fields=['push_pending', 'push_sent_at'])
            if allowed:
                transaction.on_commit(lambda user=row.user, row_id=row.pk: send_alert(user, row_id))
