from datetime import timedelta

import pytest
from django.utils import timezone

from news.models import (Article, ArticleContent, ArticleQualityProfile,
                         ArticleRelation, QualityIssue, Source, SourceQualityState)
from scraper.quality_enrichment import canonicalize_url, enrich_quality


def article(source, title, url, date=None):
    return Article.objects.create(source=source, title=title, url=url,
                                  published_date=date or timezone.now())


def test_canonicalize_url_only_removes_transport_noise():
    assert canonicalize_url('HTTPS://WWW.Example.org/a/?utm_source=x&b=2&a=1#part') == 'https://example.org/a?a=1&b=2'


@pytest.mark.django_db
def test_same_source_canonical_duplicate_is_flagged_but_preserved():
    source = Source.objects.create(name='A', url='https://a.example')
    first = article(source, 'One', 'https://a.example/story?utm_source=x')
    second = article(source, 'Two', 'https://a.example/story')
    enrich_quality(limit=10)
    assert Article.objects.filter(pk__in=[first.pk, second.pk]).count() == 2
    assert QualityIssue.objects.filter(article=second, code='canonical_duplicate', active=True).exists()


@pytest.mark.django_db
def test_equal_content_across_sources_creates_relation_without_merging():
    a = Source.objects.create(name='A', url='https://a.example')
    b = Source.objects.create(name='B', url='https://b.example')
    first = article(a, 'Original', 'https://a.example/story')
    second = article(b, 'Syndicated', 'https://b.example/story')
    for item in (first, second):
        ArticleContent.objects.create(article=item, text='body', response_sha256='f' * 64,
                                      source_url=item.url)
    enrich_quality(limit=10)
    relation = ArticleRelation.objects.get()
    assert {relation.left_id, relation.right_id} == {first.pk, second.pk}
    assert relation.evidence['basis'] == 'exact_content_sha256'
    assert Article.objects.count() == 2


@pytest.mark.django_db
def test_enrichment_is_idempotent_and_records_provenance_metrics():
    source = Source.objects.create(name='A', url='https://a.example')
    item = article(source, 'Story', 'https://a.example/story')
    enrich_quality(limit=10); enrich_quality(limit=10)
    assert ArticleQualityProfile.objects.filter(article=item).count() == 1
    state = SourceQualityState.objects.get(source=source)
    assert state.sample_size == 1
    assert state.metrics['date_rate'] == 1.0
    assert state.rules_version == 'quality-v1'


@pytest.mark.django_db
def test_parser_drift_is_reported_after_material_drop():
    source = Source.objects.create(name='A', url='https://a.example')
    now = timezone.now()
    for index in range(20):
        article(source, f'Old {index}', f'https://a.example/old/{index}', now)
    enrich_quality(limit=100)
    for index in range(20):
        Article.objects.create(source=source, title=f'New {index}', url=f'https://a.example/new/{index}')
    enrich_quality(limit=100)
    state = SourceQualityState.objects.get(source=source)
    assert state.drift['date_rate'] == {'baseline': 1.0, 'current': 0.5}
