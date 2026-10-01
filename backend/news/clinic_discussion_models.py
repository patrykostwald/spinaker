"""Oceny wywiadów i niezależna dyskusja; treść komentarza pozostaje niezmienna."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone
from news.account_models import CommentReport
from news.clinic_models import POLARITIES


class InterviewOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_opinions')
    interview = models.ForeignKey('news.ClinicInterview', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=POLARITIES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'interview'], name='one_opinion_per_user_interview'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='interview_opinion_valid_polarity'),
        ]


class ClinicComment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clinic_comments')
    diagnosis = models.ForeignKey('news.SpinDiagnosis', null=True, blank=True, on_delete=models.CASCADE, related_name='comments')
    interview = models.ForeignKey('news.ClinicInterview', null=True, blank=True, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    legacy_opinion = models.OneToOneField('news.SpinOpinion', null=True, blank=True, on_delete=models.SET_NULL, related_name='discussion_comment')
    body = models.CharField(max_length=1000, validators=[MaxLengthValidator(1000)])
    body_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=240, blank=True)
    hidden_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    screening = models.CharField(max_length=16, default='pending', db_index=True, choices=[
        ('pending', 'Sprawdzanie'), ('clean', 'Bez naruszeń'), ('flagged', 'Ukryte przez filtr'),
        ('unavailable', 'Brak odpowiedzi filtra'), ('legacy', 'Komentarz sprzed migracji')])
    needs_review = models.BooleanField(default=True, db_index=True)
    reply_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.CheckConstraint(condition=(
            models.Q(diagnosis__isnull=False, interview__isnull=True) |
            models.Q(diagnosis__isnull=True, interview__isnull=False)), name='clinic_comment_exactly_one_target')]
        indexes = [models.Index(fields=['author', 'created_at'], name='clinic_comment_author_date')]

    def clean(self):
        super().clean()
        if self.parent_id:
            parent = self.parent
            if parent.parent_id or parent.pk == self.pk or (parent.diagnosis_id, parent.interview_id) != (self.diagnosis_id, self.interview_id):
                raise ValidationError({'parent': 'Odpowiedź może dotyczyć tylko głównego komentarza w tej dyskusji.'})


class ClinicCommentReport(models.Model):
    comment = models.ForeignKey(ClinicComment, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clinic_comment_reports')
    reason = models.CharField(max_length=16, choices=CommentReport.REASONS)
    details = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['reporter', 'comment'], name='one_report_per_user_clinic_comment')]
