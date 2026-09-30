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
