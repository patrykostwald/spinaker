"""Regression coverage for the Polish-diacritics corruption investigated in
this session: confirmed as literal '?' bytes stored in Source.name /
catalog_notes for a batch of inactive justice-catalog candidate rows,
while a fresh write through this exact pipeline (Django ORM -> psycopg2 ->
PostgreSQL, UTF8 client/server encoding) round-trips correctly. These
tests pin that current correctness so a future change to encoding, driver
options, or connection settings cannot silently reintroduce it.
"""
import pytest

from news.models import Source
from scraper.utils import upsert_article


ALL_POLISH_DIACRITICS = 'ąćęłńóśżź ĄĆĘŁŃÓŚŻŹ'


@pytest.fixture
def source(db):
    return Source.objects.create(name='Roundtrip test publisher', url='https://roundtrip.example')


@pytest.mark.django_db
def test_source_name_with_polish_diacritics_round_trips(source):
    name = f'Prokuratura Okręgowa w Łodzi {ALL_POLISH_DIACRITICS}'
    obj = Source.objects.create(name=name, url='https://roundtrip.example/source')
    obj.refresh_from_db()
    assert obj.name == name
    assert '?' not in obj.name


@pytest.mark.django_db
def test_article_title_with_polish_diacritics_round_trips(source):
    title = f'Rządowe centrum ds. bezpieczeństwa ogłasza zmiany {ALL_POLISH_DIACRITICS}'
    article, created = upsert_article(source=source, title=title,
        url='https://roundtrip.example/article', published_date=None)
    assert created
    article.refresh_from_db()
    assert article.title == title
    assert '?' not in article.title
