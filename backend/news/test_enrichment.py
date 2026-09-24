from unittest.mock import patch
import pytest
from django.utils import timezone
from news.models import Article, Source, ArchiveJob
from news.enrichment import fill_missing_thumbnail
from scraper.archive import process, _HOST_STATES


@pytest.fixture
def record(db):
    source = Source.objects.create(name='Publisher', url='https://example.org')
    return Article.objects.create(source=source, title='Source title', url='https://example.org/story',
        description='Source description', published_date=timezone.now(), category='article',
        ingestion_method='rss', evidence_note='Existing source evidence')


def metadata(image='https://example.org/thumbnail.jpg'):
    return {'image_url': image, 'image_source': 'meta:og:image'}


@pytest.mark.django_db
def test_fills_only_empty_thumbnail_and_preserves_source_fields(record):
    original = (record.title, record.description, record.published_date, record.category)
    assert fill_missing_thumbnail(record.pk, metadata(), record.url, 'a' * 64)
    record.refresh_from_db()
    assert record.image_url == metadata()['image_url']
    assert (record.title, record.description, record.published_date, record.category) == original
    assert record.evidence_note.startswith('Existing source evidence\n')
    assert record.url in record.evidence_note and 'meta:og:image' in record.evidence_note
    assert 'a' * 64 in record.evidence_note
    evidence = record.evidence_note
    assert not fill_missing_thumbnail(record.pk, metadata('https://example.org/new.jpg'), record.url, 'b' * 64)
    record.refresh_from_db()
    assert record.evidence_note == evidence and record.image_url == metadata()['image_url']


@pytest.mark.django_db
@pytest.mark.parametrize('changes', [
    {'ingestion_method': 'manual'}, {'category_reviewed': True}, {'image_url': 'https://example.org/editor.jpg'}])
def test_editorial_or_existing_values_are_not_changed(record, changes):
    Article.objects.filter(pk=record.pk).update(**changes)
    assert not fill_missing_thumbnail(record.pk, metadata(), record.url, 'a' * 64)
    record.refresh_from_db()
    assert record.evidence_note == 'Existing source evidence'


@pytest.mark.django_db
def test_missing_unattributed_or_foreign_metadata_is_not_used(record):
    assert not fill_missing_thumbnail(record.pk, {'image_url': metadata()['image_url']}, record.url, 'a' * 64)
    assert not fill_missing_thumbnail(record.pk, metadata(''), record.url, 'a' * 64)
    assert not fill_missing_thumbnail(record.pk, metadata(), 'https://example.org/another', 'a' * 64)
    record.refresh_from_db()
    assert record.image_url == ''


@pytest.mark.django_db
def test_archive_enriches_rss_record_without_an_extra_network_request(record):
    job = ArchiveJob.objects.create(source=record.source, url=record.url, kind='page')
    html = b'<title>Later headline</title><meta property="og:type" content="article"><meta property="og:image" content="/image.jpg">'
    _HOST_STATES.clear()
    with patch('scraper.archive.fetch_feed', side_effect=lambda url, **_: b'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else html):
        assert process(job) == 0
    record.refresh_from_db()
    assert record.image_url == 'https://example.org/image.jpg'
    assert record.title == 'Source title'
    assert 'meta:og:image' in record.evidence_note
    _HOST_STATES.clear()

