"""Celery workers for the local publication outbox and opt-in email digests."""
from datetime import timedelta
import logging
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from news.notification_models import Follow, Notification, NotificationEvent, NotificationSettings
from news.notify import enabled, notify

logger = logging.getLogger(__name__)


@shared_task(name='news.notification_tasks.retry_thread_moderation_mail', soft_time_limit=50, time_limit=60)
def retry_thread_moderation_mail():
    from news.thread_moderation import deliver_mail
    deliver_mail(max_messages=2)


def _deliver_event(event):
    if event.kind == 'post':
        from news.followed_posts import deliver_post
        deliver_post(event)
        return
    if event.kind == 'account_newsletter':
        import secrets
        from news.account_models import AccountIdentity
        from news.newsletter_models import NewsletterSubscriber
        from news.newsletter import send_confirmation
        identity = AccountIdentity.objects.filter(pk=event.target_id, email_verified=True,
            newsletter_consent_at__isnull=False, user__is_active=True).first()
        if not identity:
            return
        subscriber, _ = NewsletterSubscriber.objects.get_or_create(email=identity.email, defaults={
            'token': secrets.token_urlsafe(32), 'consent_version': '2026-10-03', 'source': 'account'})
        if subscriber.status == 'unsubscribed':
            if subscriber.unsubscribed_at and subscriber.unsubscribed_at >= identity.newsletter_consent_at:
                return
            subscriber.status, subscriber.token, subscriber.source = 'pending', secrets.token_urlsafe(32), 'account'
            subscriber.consent_version, subscriber.unsubscribed_at = '2026-10-03', None
            subscriber.save()
        if send_confirmation(subscriber.pk) in ('failed', 'no_smtp'):
            raise RuntimeError('Newsletter confirmation awaits delivery')
        return
    if event.kind == 'moderation':
        from news.thread_social_models import ThreadModerationDecision
        decision = ThreadModerationDecision.objects.select_related('report').filter(pk=event.target_id).first()
        if decision:
            ids = {decision.report.reporter_id, decision.report.target_author_id} - {None}
            for user in get_user_model().objects.filter(pk__in=ids):
                notify(user, 'report_status', 'Rozpatrzono zgłoszenie', '/konto#zgloszenia')
        return
    if event.kind == 'vote_result':
        from news.clinic_models import ClinicInterview
        from news.interview_vote_models import InterviewVote
        interview = ClinicInterview.objects.filter(pk=event.target_id).first()
        if interview:
            for vote in InterviewVote.objects.filter(ballot__day=interview.day).select_related('user', 'candidate'):
                won = vote.candidate.video_id == interview.video_id
                notify(vote.user, 'vote_result', f"{'Wybrano' if won else 'Nie wybrano'}: {vote.candidate.title}", '/konto#aktywnosc')
        return
    if event.kind == 'diagnosis':
        from news.clinic import figures_by_account, published_diagnoses
        diagnosis = published_diagnoses().filter(pk=event.target_id).first()
        if not diagnosis:
            return
        from news.followed_posts import update_diagnosis
        update_diagnosis(diagnosis)
        figure = figures_by_account({diagnosis.post.account_id}).get(diagnosis.post.account_id)
        if not figure:
            return
        modes = ['diagnoses', 'strong_spin'] if diagnosis.intensity >= 70 else ['diagnoses']
        recipients = Follow.objects.filter(figure=figure, mode__in=modes, created_at__lte=event.created_at).exclude(
            user__notifications__posts__post=diagnosis.post)
        kind, title, url = 'followed_diagnosis', f'Nowa diagnoza: {figure.canonical_name}', f'/klinika/{diagnosis.pk}'
    elif event.kind == 'thread':
        from news.community import public_threads
        if not settings.THREADS_ENABLED:
            return
        thread = public_threads().filter(pk=event.target_id).select_related('owner').first()
        if not thread or not thread.owner_id:
            return
        recipients = Follow.objects.filter(target_user=thread.owner, created_at__lte=event.created_at).exclude(user=thread.owner).exclude(user__muted_users__target_id=thread.owner_id)
        kind, title, url = 'followed_thread', f'{thread.owner.username}: {thread.title}', f'/tropy/{thread.pk}'
    elif event.kind == 'thread_comment':
        from news.community import public_threads
        from news.thread_social_models import ThreadComment
        if not settings.THREADS_ENABLED:
            return
        comment = ThreadComment.objects.select_related('thread').filter(pk=event.target_id,
            thread__in=public_threads(), hidden_at__isnull=True, deleted_at__isnull=True).first()
        if not comment:
            return
        ids = set(Follow.objects.filter(thread=comment.thread, created_at__lte=event.created_at).values_list('user_id', flat=True))
        # The owner already has a durable grouped notification written with the comment.
        ids.discard(comment.thread.owner_id)
        ids.discard(comment.author_id)
        from news.account_models import MutedUser
        ids -= set(MutedUser.objects.filter(user_id__in=ids, target_id=comment.author_id).values_list('user_id', flat=True))
        for user in get_user_model().objects.filter(pk__in=ids, is_active=True):
            notify(user, 'thread_reply', f'Nowy komentarz: {comment.thread.title}', f'/tropy/{comment.thread_id}')
        return
    elif event.kind == 'reply':
        from news.community import public_threads
        from news.community_models import CommunityThreadOpinion
        if not settings.THREADS_ENABLED:
            return
        opinion = CommunityThreadOpinion.objects.select_related('thread', 'user').filter(pk=event.target_id, thread__in=public_threads()).first()
        if not opinion:
            return
        ids = set(Follow.objects.filter(thread=opinion.thread, created_at__lte=event.created_at).values_list('user_id', flat=True))
        ids.add(opinion.thread.owner_id)
        ids.discard(opinion.user_id)
        for user in get_user_model().objects.filter(pk__in=ids, is_active=True):
            notify(user, 'thread_reply', f'Nowa opinia: {opinion.thread.title}', f'/tropy/{opinion.thread_id}')
        return
    else:
        return
    for user in get_user_model().objects.filter(pk__in=recipients.values('user_id'), is_active=True):
        notify(user, kind, title, url, figure=figure if event.kind == 'diagnosis' else None)


@shared_task(name='news.notification_tasks.process_notification_events', soft_time_limit=50, time_limit=60)
def process_notification_events():
    if not enabled():
        return 0
    count = 0
    ids = list(NotificationEvent.objects.filter(processed_at__isnull=True).order_by('id').values_list('pk', flat=True)[:100])
    for pk in ids:
        try:
            with transaction.atomic():
                event = NotificationEvent.objects.select_for_update().get(pk=pk)
                if event.processed_at:
                    continue
                _deliver_event(event)
                event.processed_at = timezone.now()
                event.save(update_fields=['processed_at'])
            count += 1
        except Exception:
            logger.exception('Notification event delivery failed')
    from news.followed_posts import flush_post_pushes
    flush_post_pushes()
    return count


@shared_task(name='news.notification_tasks.send_notification_digests', soft_time_limit=240, time_limit=270)
def send_notification_digests():
    if not enabled():
        return 0
    from news.account_mail import send_account_mail
    now, sent = timezone.now(), 0
    ids = NotificationSettings.objects.exclude(email_digest='off').values_list('pk', flat=True)
    for pk in ids.iterator():
        try:
            with transaction.atomic():
                preference = NotificationSettings.objects.select_for_update().select_related('user').get(pk=pk)
                if preference.email_digest == 'off':
                    continue
                days = 1 if preference.email_digest == 'daily' else 7
                if preference.last_digest_at and preference.last_digest_at > now - timedelta(days=days):
                    continue
                user = preference.user
                from news.account_models import AccountIdentity
                if not user.is_active or not user.email or not AccountIdentity.objects.filter(user=user, email_verified=True).exists():
                    continue
                rows = Notification.objects.exclude(kind='clinic_reply').filter(user=user, emailed_at__isnull=True, created_at__lte=now, created_at__gt=preference.last_digest_at or now - timedelta(days=days)).order_by('created_at')
                batch = list(rows[:100])
                if not batch:
                    preference.last_digest_at = now
                    preference.save(update_fields=['last_digest_at'])
                    continue
                origin = settings.ACCOUNT_PUBLIC_URL
                body = 'Co nowego w spin.clinic:\n\n' + '\n\n'.join(f'{row.title}\n{row.url if row.url.startswith("https://x.com/") else origin + row.url}' for row in batch)
                remaining = rows.count() - len(batch)
                if remaining:
                    body += f'\n\nPozostałe powiadomienia: {remaining}. Zobacz wszystkie: {origin}/konto'
                body += f'\n\nUstawienia powiadomień: {origin}/konto\nOperator: iapply sp. z o.o.'
                if send_account_mail(user.email, 'Twoje powiadomienia ze spin.clinic', body):
                    rows.update(emailed_at=now)
                    preference.last_digest_at = now
                    preference.save(update_fields=['last_digest_at'])
                    sent += 1
        except Exception:
            logger.exception('Notification digest delivery failed')
    return sent
