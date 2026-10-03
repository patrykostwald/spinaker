"""Social 085: independent comments, durable rate events and moderation audit."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ThreadComment(models.Model):
    thread = models.ForeignKey('news.PersonalContextThread', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    hidden_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['created_at', 'id']


class ThreadCommentReaction(models.Model):
    """Ocena komentarza przez innych czytelników: ✓ trafny, ? wątpliwy, ✕ nietrafny (jedna na osobę, zmienialna)."""
    comment = models.ForeignKey(ThreadComment, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    polarity = models.CharField(max_length=8, default='positive', choices=[('positive', 'Trafny'), ('doubt', 'Wątpliwy'), ('negative', 'Nietrafny')])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['comment', 'user'], name='comment_reaction_user_087')]


class ThreadRateEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=8)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['user', 'kind', 'created_at'], name='thread_rate_window_085')]


class ThreadModerationReport(models.Model):
    thread = models.ForeignKey('news.PersonalContextThread', null=True, on_delete=models.SET_NULL, related_name='moderation_reports')
    target_author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    target_kind = models.CharField(max_length=8, default='thread')
    comment = models.ForeignKey(ThreadComment, null=True, blank=True, on_delete=models.SET_NULL)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    reason = models.CharField(max_length=16)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, default='new', db_index=True)
    ai_assessment = models.JSONField(default=dict)
    snapshot = models.TextField()
    appeal = models.TextField(blank=True)
    appealed_at = models.DateTimeField(null=True)
    appealed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['created_at', 'id']


class ThreadModerationDecision(models.Model):
    report = models.ForeignKey(ThreadModerationReport, on_delete=models.PROTECT, related_name='decisions')
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=8, choices=[('hide', 'Ukryj'), ('restore', 'Przywróć')])
    rule = models.CharField(max_length=40)
    explanation = models.TextField()
    is_appeal = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)


class ThreadModerationMail(models.Model):
    decision = models.ForeignKey(ThreadModerationDecision, on_delete=models.CASCADE, related_name='mail')
    recipient = models.EmailField()
    sent_at = models.DateTimeField(null=True)
    last_attempt_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['decision', 'recipient'], name='thread_decision_recipient_085')]


class ThreadStepReaction(models.Model):
    """Reakcja czytelnika na jeden krok tropu: boks albo powiązanie prowadzące do niego (news/thread_steps.py)."""
    thread = models.ForeignKey('news.PersonalContextThread', on_delete=models.CASCADE, related_name='step_reactions')
    item = models.ForeignKey('news.PersonalContextThreadItem', on_delete=models.CASCADE, related_name='step_reactions')
    part = models.CharField(max_length=8, choices=[('box', 'Boks'), ('context', 'Powiązanie')])
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_step_reactions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Trafny'), ('doubt', 'Wątpliwy'), ('negative', 'Nietrafny')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['item', 'part', 'user'], name='thread_step_reaction_user')]
        indexes = [models.Index(fields=['thread', 'user'])]
