from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Article, Source
from scraper.quality_enrichment import enrich_quality_cycle


@pytest.mark.django_db
def test_status_reports_derived_quality_counts_without_changing_articles():
    source = Source.objects.create(name='Source', url='https://source.example')
    article = Article.objects.create(source=source, title='Title', url='https://source.example/a')
    enrich_quality_cycle(limit=10)
    output = StringIO()
    call_command('data_quality_status', stdout=output)
    assert Article.objects.filter(pk=article.pk).count() == 1
    assert 'DATA_QUALITY: articles=1 profiles=1 relations=0' in output.getvalue()
    assert 'DATA_QUALITY_ENRICHMENT: last_pk=' in output.getvalue()
