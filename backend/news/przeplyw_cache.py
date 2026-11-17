"""Invalidate 24-hour graphs when source evidence changes.

Bulk writers using QuerySet.update/bulk_create must call invalidate() after their
transaction; these Django operations intentionally do not emit model signals.
"""
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save

KEY = 'przeszlosc:przeplyw:revision'


def revision():
    value = cache.get(KEY)
    if value is None:
        cache.add(KEY, uuid4().hex, timeout=None)
        value = cache.get(KEY)
    return value


def invalidate(**kwargs):
    cache.set(KEY, uuid4().hex, timeout=None)


def changed(sender, using, **kwargs):
    # Immediate invalidation also protects reads made inside the writing transaction.
    invalidate()
    transaction.on_commit(invalidate, using=using)


def connect():
    from django.apps import apps
    names = ('PublicFigure', 'RegisteredOrganisation', 'PublicFigureOrganisationRelation',
             'PublicRecord', 'PublicRecordPerson', 'PoliticalPost', 'PoliticalAccount',
             'PoliticalAccountCandidate', 'SocialHandleEvidence', 'SpinDiagnosis',
             'PublicFigureArticleReference', 'Article', 'Source', 'PublicFigureRole',
             'ParliamentaryRosterEntry', 'ParliamentaryVoting', 'Ballot')
    for name in names:
        model = apps.get_model('news', name)
        for signal in (post_save, post_delete):
            signal.connect(changed, sender=model, dispatch_uid=f'przeplyw:{name}:{id(signal)}')
