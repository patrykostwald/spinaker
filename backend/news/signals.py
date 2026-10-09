from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from news.models import Article, Source, EvidenceLink, ArticleContent
from news.clinic_models import SpinDiagnosis


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


@receiver(post_save, sender=SpinDiagnosis)
@receiver(post_delete, sender=SpinDiagnosis)
def diagnosis_changed(**kwargs):
    from news.clinic_stats import CACHE_KEY
    keys = [CACHE_KEY, 'clinic-stats:v3']
    cache.delete_many(keys)
    transaction.on_commit(lambda: cache.delete_many(keys))


@receiver(post_save, sender=SpinDiagnosis)
def diagnosis_thread_changed(sender, instance, raw=False, **kwargs):
    from news.features import threads_enabled
    if not threads_enabled():
        return None
    if not raw:
        from news.diagnosis_threads import sync_diagnosis_thread
        sync_diagnosis_thread(instance.pk)


from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.models import Thread, ThreadItem


@receiver(post_save, sender=PersonalContextThread)
@receiver(post_save, sender=PersonalContextThreadItem)
@receiver(post_delete, sender=PersonalContextThreadItem)
@receiver(post_save, sender=Thread)
@receiver(post_save, sender=ThreadItem)
@receiver(post_delete, sender=ThreadItem)
def thread_text_changed(sender, instance, raw=False, **kwargs):
    from news.features import threads_enabled
    if not threads_enabled():
        return None
    from news.thread_review import authoring, enqueue, snapshot
    from news.thread_review_models import ThreadReview
    if raw or authoring.get():
        return
    item = isinstance(instance, (PersonalContextThreadItem, ThreadItem))
    thread = instance.thread if item else instance
    personal = isinstance(thread, PersonalContextThread)
    if (personal and thread.owner_id is not None) or (not personal and not thread.slug.startswith('dr-spin-')):
        return
    review = ThreadReview.objects.filter(**{'thread' if personal else 'editorial_thread': thread}).first()
    if review is None:
        # Builders enqueue once all boxes exist. Direct edits cannot make an unchecked thread public.
        type(thread).objects.filter(pk=thread.pk).update(**{'is_public' if personal else 'published': False})
        return
    evidence = review.payload.get('evidence', {})
    current = snapshot(thread, evidence)
    if current['texts'] != review.working_texts or item:
        enqueue(thread, evidence)
    elif review.status != 'approved':
        type(thread).objects.filter(pk=thread.pk).update(**{'is_public' if personal else 'published': False})
