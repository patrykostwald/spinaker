"""Single delivery entry point and local publication outbox."""
import logging
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from news.account_models import PersonalContextThread
from news.clinic_models import SpinDiagnosis
from news.community_models import CommunityThreadOpinion
from news.notification_models import Notification, NotificationEvent, NotificationSettings

logger = logging.getLogger(__name__)


def enabled():
    return getattr(settings, 'ACCOUNTS_ENABLED', False)


def notify(user, kind, title, url):
    """Called by the worker; in-app delivery survives unavailable push providers."""
    if not enabled() or not user.is_active:
        return None
    row = Notification.objects.create(user=user, kind=kind, title=title[:240], url=url[:1024])
    preferences = NotificationSettings.objects.filter(user=user).first()
    push_field = 'push_thread_replies' if kind == 'thread_reply' else 'push_spin_of_day' if kind == 'spin_of_day' else 'push_followed'
    if getattr(settings, 'PUSH_ENABLED', False) and preferences and getattr(preferences, push_field):
        def deliver():
            try:
                from news.push import send_to_user
                send_to_user(user, {'title': row.title, 'url': row.url, 'kind': row.kind, 'id': row.pk})
            except ImportError:
                pass
            except Exception:
                logger.warning('Notification push delivery failed', exc_info=True)
        transaction.on_commit(deliver)
    return row


def queue_event(kind, target_id):
    if enabled():
        try:
            # A savepoint isolates an outbox error from the publishing transaction.
            with transaction.atomic():
                NotificationEvent.objects.get_or_create(kind=kind, target_id=target_id)
        except Exception:
            logger.exception('Could not queue notification event')


@receiver(pre_save, sender=SpinDiagnosis)
@receiver(pre_save, sender=PersonalContextThread)
def remember_publication(sender, instance, raw=False, **kwargs):
    if raw or not enabled():
        return
    field = 'status' if sender is SpinDiagnosis else 'published_at'
    previous = sender.objects.filter(pk=instance.pk).values_list(field, flat=True).first() if instance.pk else None
    instance._notification_first_publication = previous != 'approved' if sender is SpinDiagnosis else not previous


@receiver(post_save, sender=SpinDiagnosis)
def diagnosis_published(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, '_notification_first_publication', False) and instance.status == 'approved' and not instance.hidden_at:
        queue_event('diagnosis', instance.pk)


@receiver(post_save, sender=PersonalContextThread)
def thread_published(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, '_notification_first_publication', False) and instance.is_public and instance.published_at and not instance.hidden_at:
        queue_event('thread', instance.pk)


@receiver(post_save, sender=CommunityThreadOpinion)
def opinion_published(sender, instance, created, raw=False, **kwargs):
    if not raw and created:
        queue_event('reply', instance.pk)
