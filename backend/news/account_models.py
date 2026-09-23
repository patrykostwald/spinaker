from django.conf import settings
from django.db import models


class SavedTopic(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_topics')
    label = models.CharField(max_length=80)
    query = models.CharField(max_length=200, blank=True, default='')
    categories = models.JSONField(default=list)
    topics = models.JSONField(default=list)
    sources = models.ManyToManyField('news.Source', blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    slot = models.PositiveSmallIntegerField(editable=False)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'slot'], name='unique_topic_owner_slot'),
            models.CheckConstraint(condition=models.Q(slot__gte=0, slot__lt=10), name='topic_slot_max_ten'),
        ]


class ArticleOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_opinions')
    article = models.ForeignKey('news.Article', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Pozytywny'), ('negative', 'Negatywny')])
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'article'], name='one_opinion_per_user_article'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='opinion_valid_polarity'),
        ]


class ThreadOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_opinions')
    thread = models.ForeignKey('news.Thread', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Pozytywny'), ('negative', 'Negatywny')])
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'thread'], name='one_opinion_per_user_thread'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='thread_opinion_valid_polarity'),
        ]


class ProfilePreference(models.Model):
    THEME_CHOICES = [
        ('auto', 'Automatyczny'),
        ('dark', 'Ciemny'),
        ('light', 'Jasny'),
        ('pastel', 'Pastelowy'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_preference')
    public_activity = models.BooleanField(default=False)
    theme_preference = models.CharField(max_length=8, choices=THEME_CHOICES, default='auto')


class UserXConnection(models.Model):
    """A minimal, OAuth-proven X identity used only to enable share controls.

    No access or refresh token is persisted: publication remains in the X
    compose window, under the user's final control.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='x_connection')
    x_user_id = models.CharField(max_length=32, unique=True)
    username = models.CharField(max_length=15)
    connected_at = models.DateTimeField(auto_now_add=True)


class ThreadFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_favorites')
    thread = models.ForeignKey('news.Thread', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'thread'], name='unique_user_thread_favorite')]


class ArticleFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_favorites')
    article = models.ForeignKey('news.Article', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'article'], name='unique_user_article_favorite')]


class PersonalContextThread(models.Model):
    """Private, owner-scoped context thread. It is never a public editorial Thread."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='personal_context_threads')
    title = models.CharField(max_length=140)
    description = models.CharField(max_length=500, blank=True, default='')
    query = models.CharField(max_length=200, blank=True, default='')
    categories = models.JSONField(default=list)
    topics = models.JSONField(default=list)
    sources = models.ManyToManyField('news.Source', blank=True, related_name='personal_context_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']


class PersonalContextThreadItem(models.Model):
    thread = models.ForeignKey(PersonalContextThread, on_delete=models.CASCADE, related_name='items')
    article = models.ForeignKey('news.Article', on_delete=models.CASCADE, related_name='personal_context_thread_items')
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['thread', 'article'], name='unique_personal_context_thread_article'),
            models.UniqueConstraint(fields=['thread', 'position'], name='unique_personal_context_thread_position'),
        ]


class CommentReport(models.Model):
    REASONS = [
        ('spam', 'Spam'), ('abuse', 'Naruszenie zasad'), ('privacy', 'Dane prywatne'),
        ('off_topic', 'Poza tematem'), ('other', 'Inne'),
    ]
    STATUSES = [('new', 'Nowe'), ('reviewed', 'Rozpatrzone'), ('hidden', 'Ukryte')]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_reports')
    article_opinion = models.ForeignKey(ArticleOpinion, null=True, blank=True, on_delete=models.CASCADE,
        related_name='reports')
    thread_opinion = models.ForeignKey(ThreadOpinion, null=True, blank=True, on_delete=models.CASCADE,
        related_name='reports')
    reason = models.CharField(max_length=16, choices=REASONS)
    details = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=16, choices=STATUSES, default='new', db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_comment_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', '-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(article_opinion__isnull=False, thread_opinion__isnull=True) |
                           models.Q(article_opinion__isnull=True, thread_opinion__isnull=False)),
                name='comment_report_has_exactly_one_target',
            ),
            models.UniqueConstraint(fields=['reporter', 'article_opinion'], name='unique_reporter_article_comment_report'),
            models.UniqueConstraint(fields=['reporter', 'thread_opinion'], name='unique_reporter_thread_comment_report'),
        ]
