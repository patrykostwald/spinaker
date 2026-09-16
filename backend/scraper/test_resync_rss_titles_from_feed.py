from io import StringIO
from unittest.mock import patch

import pytest
from django.utils import timezone

from news.models import Article, Source, SourceAccessInstruction
from django.core.management import call_command


FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<title>Test feed</title>
<item><title>Poprawny tyło tytuł z pieniądze</title>
<link>https://nik.example/a</link></item>
</channel></rss>
""".encode('utf-8')


@pytest.fixture
def source(db):
    source = Source.objects.create(name='NIK fixture', url='https://nik.example',
        rss_url='https://nik.example/rss')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='rss',
        allowed_scope='metadata', endpoint=source.rss_url,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test',
        minimum_interval_seconds=3, daily_request_cap=24)
    return source


@pytest.mark.django_db
def test_corrupted_title_is_healed_from_a_fresh_fetch(source):
    article = Article.objects.create(source=source, url='https://nik.example/a',
        title='Poprawny ty??o tytu?? z pieni??dze')

    with patch('scraper.management.commands.resync_rss_titles_from_feed.fetch_feed', return_value=FEED):
        out = StringIO()
        call_command('resync_rss_titles_from_feed', source.pk, apply=True, stdout=out)

    article.refresh_from_db()
    assert article.title == 'Poprawny tyło tytuł z pieniądze'
    assert 'healed=1' in out.getvalue()


@pytest.mark.django_db
def test_clean_title_is_left_untouched(source):
    article = Article.objects.create(source=source, url='https://nik.example/a',
        title='Już poprawny tytuł')

    with patch('scraper.management.commands.resync_rss_titles_from_feed.fetch_feed', return_value=FEED):
        out = StringIO()
        call_command('resync_rss_titles_from_feed', source.pk, apply=True, stdout=out)

    article.refresh_from_db()
    assert article.title == 'Już poprawny tytuł'
    assert 'healed=0' in out.getvalue()


@pytest.mark.django_db
def test_dry_run_does_not_write(source):
    article = Article.objects.create(source=source, url='https://nik.example/a',
        title='Poprawny ty??o tytu?? z pieni??dze')

    with patch('scraper.management.commands.resync_rss_titles_from_feed.fetch_feed', return_value=FEED):
        out = StringIO()
        call_command('resync_rss_titles_from_feed', source.pk, stdout=out)

    article.refresh_from_db()
    assert article.title == 'Poprawny ty??o tytu?? z pieni??dze'
    assert 'dry_run: healed=1' in out.getvalue()
