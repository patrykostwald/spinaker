from django.conf import settings
from django.db import models


class Follow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='follows')
    figure = models.ForeignKey('news.PublicFigure', null=True, blank=True, on_delete=models.CASCADE)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='followers')
    thread = models.ForeignKey('news.PersonalContextThread', null=True, blank=True, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        constraints = [
            models.CheckConstraint(condition=(models.Q(figure__isnull=False, target_user__isnull=True, thread__isnull=True) | models.Q(figure__isnull=True, target_user__isnull=False, thread__isnull=True) | models.Q(figure__isnull=True, target_user__isnull=True, thread__isnull=False)), name='follow_exactly_one_target'),
            *[models.UniqueConstraint(fields=['user', field], name=f'unique_follow_{field}') for field in ('figure', 'target_user', 'thread')],
        ]

    @property
    def kind(self):
        return 'figure' if self.figure_id else 'user' if self.target_user_id else 'thread'

    @property
    def target_id(self):
        return self.figure_id or self.target_user_id or self.thread_id


class NotificationSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    email_digest = models.CharField(max_length=8, choices=[('off', 'Wyłączony'), ('daily', 'Codziennie'), ('weekly', 'Co tydzień')], default='off')
    push_spin_of_day = models.BooleanField(default=False)
    push_followed = models.BooleanField(default=False)
    push_thread_replies = models.BooleanField(default=False)
    last_digest_at = models.DateTimeField(null=True, blank=True)


class Notification(models.Model):
    group_key = models.CharField(max_length=100, null=True, blank=True, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=240)
    url = models.CharField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'read_at'], name='notification_user_read')]


class NotificationEvent(models.Model):
    """Durable local outbox: publication never waits for the broker or delivery."""
    kind = models.CharField(max_length=24)
    target_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind', 'target_id'], name='unique_notification_event')]
