from datetime import timedelta

import pytest
from django.utils import timezone

from news.models import Article, Source, SourceUsageDecision
from news.usage_gate import effective_uses


pytestmark = pytest.mark.django_db


def article():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    item = Article.objects.create(source=source, title='Article', url='https://example.org/a')
    return source, item


def decision(source, *, version=1, status='approved', uses=None, host='example.org', valid_until=None):
    return SourceUsageDecision.objects.create(
        source=source, version=version, status=status,
        allowed_uses=uses or ['ai_draft_metadata'],
        applies_until_acquired_at=timezone.now() + timedelta(days=1),
        frozen_host=host, terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', valid_until=valid_until)


def test_missing_decision_denies_every_use():
    _, item = article()
    assert effective_uses(item) == frozenset()


def test_newer_suspension_blocks_older_approval():
    source, item = article()
    decision(source, version=1)
    decision(source, version=2, status='suspended')
    assert effective_uses(item) == frozenset()


def test_expired_decision_denies_every_use():
    source, item = article()
    decision(source, valid_until=timezone.now() - timedelta(seconds=1))
    assert effective_uses(item) == frozenset()


def test_host_mismatch_denies_every_use():
    source, item = article()
    decision(source, host='old.example.org')
    assert effective_uses(item) == frozenset()


def test_only_decision_uses_are_returned():
    source, item = article()
    decision(source, uses=['public_card', 'ai_draft_metadata'])
    assert effective_uses(item) == frozenset({'public_card', 'ai_draft_metadata'})
