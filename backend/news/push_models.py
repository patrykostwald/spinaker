from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name='push_subscriptions')
    device = models.UUIDField(db_index=True)
    endpoint = models.URLField(max_length=2048, unique=True)
    keys = models.JSONField()
    topics = models.JSONField(default=list)
    consent_version = models.CharField(max_length=32)
    consent_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)


class PushEvent(models.Model):
    key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PushDelivery(models.Model):
    """One durable delivery per alert and device; successes are never retried."""
    notification = models.ForeignKey('news.Notification', on_delete=models.CASCADE, related_name='push_deliveries')
    subscription = models.ForeignKey(PushSubscription, null=True, on_delete=models.SET_NULL)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    finished = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['notification', 'subscription'], name='unique_alert_push_device_113')]
