"""Nitki czytelników (faza II): linki spoza Bazy, reakcje i zgłoszenia nitek.

Link dodany przez czytelnika nie trafia do Bazy materiałów (tam są tylko źródła za zgodą).
Zapisujemy wyłącznie adres, domenę i tytuł — bez treści i bez zdjęć. Ten sam adres (po
normalizacji) to zawsze jeden rekord, więc wiele nitek wskazuje na ten sam box.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

TITLE_ORIGINS = [('publisher', 'Tytuł z metadanych strony'), ('reader', 'Tytuł podany przez czytelnika')]


class CommunityLink(models.Model):
    canonical_url = models.URLField(max_length=1024, unique=True)
    domain = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=300)
    title_origin = models.CharField(max_length=10, choices=TITLE_ORIGINS, default='reader')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    hidden_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'link czytelnika'
        verbose_name_plural = 'linki czytelników'

    def __str__(self):
        return f'{self.domain}: {self.title[:60]}'


class CommunityThreadOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_thread_opinions')
    thread = models.ForeignKey('news.PersonalContextThread', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Przydatna'), ('negative', 'Nieprzydatna')])
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'thread'], name='one_opinion_per_user_community_thread'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='community_opinion_valid_polarity'),
        ]


class CommunityThreadReport(models.Model):
    REASONS = [('spam', 'Spam'), ('abuse', 'Naruszenie zasad'), ('privacy', 'Dane prywatne'),
               ('copyright', 'Naruszenie praw autorskich'), ('other', 'Inne')]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_reports')
    thread = models.ForeignKey('news.PersonalContextThread', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=16, choices=REASONS)
    details = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=10, default='new', db_index=True,
                              choices=[('new', 'Nowe'), ('resolved', 'Rozpatrzone')])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['reporter', 'thread'], name='one_report_per_user_thread')]
        verbose_name = 'zgłoszenie nitki'
        verbose_name_plural = 'zgłoszenia nitek'
