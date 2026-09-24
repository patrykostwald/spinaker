from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from news.models import Article, Source, EvidenceLink, ArticleContent


def invalidate_search():
    cache.add('search-generation', 1, timeout=None)
    cache.incr('search-generation')


@receiver(post_save, sender=ArticleContent)
@receiver(post_delete, sender=ArticleContent)
@receiver(post_save, sender=Article)
@receiver(post_delete, sender=Article)
@receiver(post_save, sender=Source)
@receiver(post_delete, sender=Source)
@receiver(post_save, sender=EvidenceLink)
@receiver(post_delete, sender=EvidenceLink)
def article_changed(**kwargs):
    transaction.on_commit(invalidate_search)
