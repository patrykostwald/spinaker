"""Stored post alerts, rolling groups and Warsaw quiet hours. No source API calls."""
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from news.notification_models import Follow, Notification, NotificationPost, NotificationSettings

logger = logging.getLogger(__name__)
WINDOW = timedelta(minutes=15)


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
        'score': diagnosis.intensity if published else None}


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
            row = Notification.objects.filter(user=follow.user, figure=figure, kind='followed_post').filter(
                Q(created_at__gt=now - WINDOW) | Q(push_sent_at__gt=now - WINDOW) | Q(push_pending=True)
            ).order_by('-created_at', '-pk').first()
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

    Claim before delivery gives at-most-once push attempts; the durable centre
    remains available if the provider fails. Quiet-hour groups wait until 07:00.
    """
    if not settings.PUSH_ENABLED or quiet_hours():
        return
    ids = Notification.objects.filter(push_pending=True).values_list('pk', flat=True)[:100]
    for pk in list(ids):
        with transaction.atomic():
            row = Notification.objects.select_related('user').filter(pk=pk).first()
            if row is None:
                continue
            # Same lock order as intake, also serializing pushes from separate groups.
            follow = Follow.objects.select_for_update().filter(user=row.user, figure_id=row.figure_id).first()
            row = Notification.objects.select_for_update(of=('self',)).select_related('user').get(pk=pk)
            if not row.push_pending:
                continue
            content_allowed = bool(follow and follow.mode == 'posts' and row.posts.filter(post__available=True).exists())
            if row.kind == 'followed_diagnosis':
                from news.clinic import published_diagnoses
                diagnosis = published_diagnoses().filter(pk=row.url.rsplit('/', 1)[-1]).first()
                content_allowed = bool(follow and diagnosis and (follow.mode == 'diagnoses'
                    or (follow.mode == 'strong_spin' and diagnosis.intensity >= 70)))
            allowed = (row.user.is_active and content_allowed and NotificationSettings.objects.filter(user=row.user,
                service_enabled=True, push_followed=True).exists())
            if allowed and Notification.objects.filter(user=row.user, figure_id=row.figure_id,
                    push_sent_at__gt=timezone.now() - WINDOW).exclude(pk=row.pk).exists():
                continue
            row.push_pending = False
            row.push_sent_at = timezone.now() if allowed else None
            row.save(update_fields=['push_pending', 'push_sent_at'])
            if allowed:
                data = notification_data(row)
                payload = {key: data[key] for key in ('id', 'title', 'url', 'kind')}
                payload['tag'] = f'followed-figure-{row.figure_id}'
                if len(data['posts']) == 1 and data['posts'][0]['score'] is not None:
                    payload['body'] = f'Zbadane: {data["posts"][0]["score"]}/100'
                def send(user=row.user, payload=payload):
                    try:
                        from news.push import send_to_user
                        send_to_user(user, payload)
                    except Exception:
                        logger.warning('Followed post push delivery failed', exc_info=True)
                transaction.on_commit(send)
