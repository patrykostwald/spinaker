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


class ProfilePreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_preference')
    public_activity = models.BooleanField(default=False)


class ThreadFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_favorites')
    thread = models.ForeignKey('news.Thread', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'thread'], name='unique_user_thread_favorite')]
