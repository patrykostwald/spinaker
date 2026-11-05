"""Persistent daily ballot; account IDs stay private."""
from django.conf import settings
from django.db import models


class InterviewBallot(models.Model):
    day = models.DateField(unique=True)
    refreshed_at = models.DateTimeField(null=True, blank=True)


class InterviewCandidate(models.Model):
    ballot = models.ForeignKey(InterviewBallot, on_delete=models.CASCADE, related_name='candidates')
    video_id = models.CharField(max_length=11)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    channel = models.CharField(max_length=200, blank=True)
    guest_name = models.CharField(max_length=300, blank=True)
    guest_keys = models.JSONField(default=list)
    duration = models.PositiveIntegerField(default=0)
    views = models.PositiveBigIntegerField(default=0)
    score = models.PositiveBigIntegerField(default=0)
    loudness = models.PositiveBigIntegerField(default=0)
    top = models.BooleanField(default=False)
    from_ranking = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ballot', 'video_id'], name='interview_candidate_video_day')]


class InterviewSubmission(models.Model):
    candidate = models.ForeignKey(InterviewCandidate, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'candidate'], name='interview_submission_once')]


class InterviewVote(models.Model):
    ballot = models.ForeignKey(InterviewBallot, on_delete=models.CASCADE, related_name='votes')
    candidate = models.ForeignKey(InterviewCandidate, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'ballot'], name='interview_vote_user_day')]


class InterviewMessage(models.Model):
    """Wiadomość czytelnika do Dr. Spina przy głosowaniu (propozycja tematu, uwaga). Widzi ją tylko zespół."""
    ballot = models.ForeignKey(InterviewBallot, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
