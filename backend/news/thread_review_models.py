"""Durable, versioned publication gate shared by all Dr. Spin threads."""
from django.db import models


class ThreadReview(models.Model):
    thread = models.OneToOneField('news.PersonalContextThread', null=True, blank=True,
        on_delete=models.CASCADE, related_name='publication_review')
    editorial_thread = models.OneToOneField('news.Thread', null=True, blank=True,
        on_delete=models.CASCADE, related_name='publication_review')
    status = models.CharField(max_length=12, default='pending', db_index=True, choices=[
        ('pending', 'Do kontroli'), ('waiting', 'Czeka na darmowy model'),
        ('rejected', 'Odrzucona'), ('approved', 'Zatwierdzona')])
    revision = models.PositiveIntegerField(default=1)
    fingerprint = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    working_texts = models.JSONField(default=dict)
    step = models.PositiveSmallIntegerField(default=0)
    reason = models.TextField(blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(thread__isnull=False, editorial_thread__isnull=True) |
            models.Q(thread__isnull=True, editorial_thread__isnull=False)), name='thread_review_target_091')]


class ThreadReviewRound(models.Model):
    review = models.ForeignKey(ThreadReview, on_delete=models.CASCADE, related_name='rounds')
    revision = models.PositiveIntegerField()
    role = models.CharField(max_length=40)
    model = models.CharField(max_length=200, blank=True)
    result = models.CharField(max_length=12, choices=[('pass', 'Zaliczono'), ('reject', 'Odrzucono'), ('wait', 'Oczekiwanie')])
    reason = models.TextField()
    texts = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pk']
