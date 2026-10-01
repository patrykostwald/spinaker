"""Proposal journal; agents never execute proposals or paid experiments."""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class AgentNote(models.Model):
    agent = models.CharField(max_length=12, choices=[(v, v) for v in ('strateg', 'pielgrzym')])
    kind = models.CharField(max_length=12, choices=[(v, v) for v in ('signal', 'idea', 'finding', 'experiment', 'request', 'report')])
    track = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('', '—')], blank=True)
    title = models.CharField(max_length=240)
    body = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    scores = models.JSONField(default=dict, blank=True)
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    critiques = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, default='new', choices=[(v, v) for v in
        ('new', 'accepted', 'rejected', 'done', 'pending', 'approved', 'denied')])
    cost_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['agent', 'kind', 'created_at'], name='agent_kind_created')]
        constraints = [models.CheckConstraint(condition=models.Q(score__lte=100), name='agent_score_range')]
