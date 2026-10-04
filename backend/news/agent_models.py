"""Proposal journal; agents never execute proposals or paid experiments."""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.utils import timezone


class AgentNote(models.Model):
    agent = models.CharField(max_length=12, choices=[(v, v) for v in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca', 'technolog', 'automatyk')])
    kind = models.CharField(max_length=12, choices=[(v, v) for v in ('signal', 'idea', 'finding', 'experiment', 'request', 'report', 'review', 'audit')])
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

    def save(self, *args, **kwargs):
        creating = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if creating and self.kind in ('idea', 'experiment', 'finding'):
                from news.seba import enabled
                if enabled():
                    SebaReview.objects.get_or_create(note=self)


class SebaReview(models.Model):
    note = models.OneToOneField(AgentNote, null=True, blank=True, on_delete=models.CASCADE, related_name='seba_review')
    warden = models.OneToOneField('news.WardenReview', null=True, blank=True,
        on_delete=models.CASCADE, related_name='seba_review')
    status = models.CharField(max_length=16, default='queued', db_index=True)
    phase = models.CharField(max_length=12, default='critique')
    rounds = models.PositiveSmallIntegerField(default=0)
    revision = models.JSONField(default=dict, blank=True)
    critiques = models.JSONField(default=list, blank=True)
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=32, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(note__isnull=False, warden__isnull=True) |
                models.Q(note__isnull=True, warden__isnull=False)), name='seba_one_subject'),
            models.CheckConstraint(condition=models.Q(rounds__lte=2), name='seba_two_rounds'),
        ]
