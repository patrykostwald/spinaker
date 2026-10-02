"""Ręczna publikacja i prywatna skrzynka osoby od social mediów."""
from django.conf import settings
from django.db import models


class SocialMaterial(models.Model):
    diagnosis = models.OneToOneField('SpinDiagnosis', on_delete=models.CASCADE, related_name='social_material')
    caption = models.TextField(blank=True)
    link = models.URLField(max_length=500, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SocialTask(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_tasks')
    content = models.TextField(max_length=4000)
    kind = models.CharField(max_length=12, choices=[('question', 'Pytanie'), ('task', 'Zadanie')])
    status = models.CharField(max_length=12, default='new', choices=[('new', 'Nowe'), ('progress', 'W toku'), ('done', 'Zrobione')])
    answer = models.TextField(blank=True, max_length=8000)
    answered_by = models.CharField(max_length=12, blank=True, choices=[('assistant', 'Asystent'), ('owner', 'Właściciel'), ('claude', 'Claude')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class SocialAssistantUsage(models.Model):
    # Atomic database counter shared by all workers, including fallback attempts.
    day = models.DateField(unique=True)
    calls = models.PositiveIntegerField(default=0)
