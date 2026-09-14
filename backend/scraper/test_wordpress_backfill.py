"""Synthetic WordPress envelopes. No public HTTP requests or live database writes."""
from datetime import datetime, timedelta, timezone as dt_timezone
import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.utils import timezone

from news.models import Article, ArticleContent, ArchiveJob, ImportState, Source, SourceAccessInstruction
from scraper.archive import SourceDelay
from scraper.wordpress_backfill import (VERIFIED_ENDPOINTS, collection_url, decode_collection,
    featured_image, fetch_collection, gmt_date, run_wordpress_source, wordpress_cycle)


ENDPOINT = VERIFIED_ENDPOINTS['liberte.pl']


def post(number, **extra):
    return {'id': number, 'date_gmt': '2010-01-02T10:11:12',
        'link': f'https://liberte.pl/test-{number}/', 'title': {'rendered': f'Test &amp; <em>{number}</em>'},
        'featured_media': 1000 + number, '_embedded': {'wp:featuredmedia': [
            {'id': 1000 + number, 'media_type': 'image', 'source_url': f'https://liberte.pl/image-{number}.jpg'}]},
        **extra}


def envelope(rows, total=None):
    return json.dumps({'status': 200, 'headers': {'X-WP-Total': str(len(rows) if total is None else total)},
        'body': rows}).encode('utf-8')


@pytest.fixture
def source(db):
    source = Source.objects.create(name='WordPress fixture', url='https://liberte.pl/feed/')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api',
        allowed_scope='metadata', endpoint=ENDPOINT,
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3)
    return source


def due(source):
    state = ImportState.objects.get(name=f'wordpress-archive:{source.pk}')
    state.cursor['available_at'] = timezone.now().isoformat()
    state.save(update_fields=['cursor'])
    return state


def seed_snapshot(source, monkeypatch, cutoff=105):
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([{'id': cutoff}], cutoff))
    result = run_wordpress_source(source.pk)
    assert result['phase'] == 'snapshot' and result['new_records'] == 0
    return due(source)


def test_snapshot_and_overlap_exclude_newer_ids_without_skipping_history(source, monkeypatch):
    seed_snapshot(source, monkeypatch)
    requests = []

    def fetch(source_id, endpoint, address):
        params = parse_qs(urlsplit(address).query)
        requests.append(params)
        offset = int(params['offset'][0])
        if offset == 0:
            return envelope([post(n) for n in range(1, 101)], 105)
        # New publications, even backdated, have larger IDs; they do not change
        # the first page, nor extend this snapshot's fixed ID cutoff.
        return envelope([post(n, date_gmt='2000-01-01T00:00:00') for n in range(100, 110)], 109)

    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', fetch)
    assert run_wordpress_source(source.pk)['new_records'] == 100
    due(source)
    result = run_wordpress_source(source.pk)
    assert result['complete'] and result['new_records'] == 5
    assert Article.objects.count() == 105
    assert not Article.objects.filter(url='https://liberte.pl/test-106/').exists()
    assert [item['offset'] for item in requests] == [['0'], ['99']]
    assert all(item['orderby'] == ['id'] and item['order'] == ['asc'] for item in requests)


def test_only_metadata_and_gmt_are_saved(source, monkeypatch):
    seed_snapshot(source, monkeypatch, cutoff=1)
    item = post(1, content={'rendered': 'ARTICLE BODY MUST NOT BE SAVED'}, excerpt={'rendered': 'NO SUMMARY'},
        date='2030-04-05T12:00:00', modified_gmt='2026-09-09T12:00:00')
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([item]))
    assert run_wordpress_source(source.pk)['new_records'] == 1
    article = Article.objects.get()
    assert article.title == 'Test & 1' and article.description == ''
    assert article.published_date == datetime(2010, 1, 2, 10, 11, 12, tzinfo=dt_timezone.utc)
    assert article.image_url == 'https://liberte.pl/image-1.jpg'
    assert article.category == 'article' and article.ingestion_method == 'archive'
    assert article.content.text == '' and article.content.status == 'metadata_only'
    assert article.content.method == 'wordpress_rest_metadata_v1'
    assert 'date_gmt=2010-01-02T10:11:12' in article.evidence_note
    assert 'ARTICLE BODY' not in article.evidence_note


@pytest.mark.parametrize('value', [None, '', '0000-00-00T00:00:00', 'invalid', '2020-01-01T10:00:00+02:00'])
def test_unknown_or_conflicting_gmt_date_is_not_invented(value):
    assert gmt_date(value) is None


def test_thumbnail_requires_matching_featured_media_identity():
    item = post(1)
    item['_embedded']['wp:featuredmedia'][0]['id'] = 9000
    assert featured_image(item) == ''
    item = post(1)
    item['_embedded']['wp:featuredmedia'][0]['media_type'] = 'file'
    assert featured_image(item) == ''
    item = post(1)
    item['_embedded']['wp:featuredmedia'][0]['source_url'] = 'http://127.0.0.1/private'
    assert featured_image(item) == ''


def test_legacy_api_gets_supported_top_level_metadata_fields():
    query = parse_qs(urlsplit(collection_url(ENDPOINT)).query)
    fields = query['_fields'][0].split(',')
    assert 'title' in fields and '_embedded' in fields and 'title.rendered' not in fields
    assert 'content' not in fields and 'excerpt' not in fields
    assert query['_embed'] == ['wp:featuredmedia']


def test_existing_metadata_is_preserved_while_missing_thumbnail_is_filled(source, monkeypatch):
    old_date = datetime(2009, 2, 3, tzinfo=dt_timezone.utc)
    article = Article.objects.create(source=source, url=post(1)['link'], title='Original title',
        published_date=old_date, description='Original evidence', category='reportage', ingestion_method='rss')
    seed_snapshot(source, monkeypatch, 1)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([post(1)]))
    result = run_wordpress_source(source.pk)
    article.refresh_from_db()
    assert result['new_records'] == 0 and result['metadata_filled'] == 1
    assert article.title == 'Original title' and article.published_date == old_date
    assert article.category == 'reportage' and article.description == 'Original evidence'
    assert article.image_url == 'https://liberte.pl/image-1.jpg'


def test_failed_page_rolls_back_metadata_and_cursor_before_replay(source, monkeypatch):
    state = seed_snapshot(source, monkeypatch, 2)
    before = {key: state.cursor[key] for key in ('offset', 'cutoff_id', 'processed')}
    stamp = state.last_success
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([post(1), post(2)]))
    from scraper.wordpress_backfill import save_metadata
    calls = 0

    def saving(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('Synthetic write failure')
        return save_metadata(*args)

    with patch('scraper.wordpress_backfill.save_metadata', side_effect=saving):
        assert run_wordpress_source(source.pk)['status'] == 'error'
    state.refresh_from_db()
    assert {key: state.cursor[key] for key in before} == before and state.last_success == stamp
    assert not Article.objects.exists() and not ArticleContent.objects.exists()
    due(source)
    assert run_wordpress_source(source.pk)['new_records'] == 2
    assert Article.objects.count() == 2


def test_deletion_shifting_offsets_rewinds_instead_of_skipping(source, monkeypatch):
    seed_snapshot(source, monkeypatch, 6)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([post(n) for n in (1, 2, 3)], 6))
    assert run_wordpress_source(source.pk)['new_records'] == 3
    due(source)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([post(n) for n in (4, 5, 6)], 5))
    result = run_wordpress_source(source.pk)
    assert result['phase'] == 'rewound' and result['status'] == 'partial' and result['new_records'] == 0
    state = due(source)
    assert state.cursor['offset'] == 0 and state.cursor['cutoff_id'] == 6
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([post(n) for n in (1, 3, 4, 5, 6)], 5))
    result = run_wordpress_source(source.pk)
    assert result['complete'] and result['new_records'] == 3
    assert Article.objects.count() == 6  # A publisher deletion does not erase our existing record.


@pytest.mark.parametrize('field,value', [('is_active', False), ('scrape_enabled', False),
    ('catalog_stage', 'excluded'), ('catalog_stage', 'candidate')])
def test_disabled_source_does_not_fetch_or_create_cursor(source, monkeypatch, field, value):
    Source.objects.filter(pk=source.pk).update(**{field: value})
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: pytest.fail('network'))
    assert run_wordpress_source(source.pk)['status'] == 'disabled'
    assert not ImportState.objects.exists()


def test_source_disabled_during_fetch_prevents_all_writes(source, monkeypatch):
    seed_snapshot(source, monkeypatch, 1)

    def fetch(*args):
        Source.objects.filter(pk=source.pk).update(scrape_enabled=False)
        return envelope([post(1)])

    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', fetch)
    assert run_wordpress_source(source.pk)['status'] == 'disabled'
    assert not Article.objects.exists()
    state = ImportState.objects.get()
    assert state.cursor['offset'] == 0 and state.cursor['cutoff_id'] == 1


@pytest.mark.parametrize('rows,total,error', [([post(2), post(1)], 2, 'ordering'),
    ([post(1), post(1)], 2, 'identity'), ([], 5, 'empty_page'),
    ([post(1, link='https://foreign.example/item')], 1, 'metadata')])
def test_bad_collection_does_not_advance(source, monkeypatch, rows, total, error):
    seed_snapshot(source, monkeypatch, 6)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope(rows, total))
    result = run_wordpress_source(source.pk)
    assert result['status'] == 'error' and error in result['error']
    assert ImportState.objects.get().cursor['offset'] == 0
    assert not Article.objects.exists()


def test_host_gate_defers_without_network(source, monkeypatch):
    gate = SimpleNamespace(acquire=lambda **kwargs: False)
    monkeypatch.setattr('scraper.wordpress_backfill.host_state', lambda hostname: {'lock': gate})
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_feed', lambda url: pytest.fail('network'))
    with pytest.raises(SourceDelay):
        fetch_collection(source.pk, ENDPOINT, collection_url(ENDPOINT))


def test_robots_denial_prevents_api_fetch(source, monkeypatch):
    from threading import Lock
    gate = {'lock': Lock(), 'next_allowed': 0}
    monkeypatch.setattr('scraper.wordpress_backfill.host_state', lambda hostname: gate)
    monkeypatch.setattr('scraper.wordpress_backfill.robots', lambda url: SimpleNamespace(can_fetch=lambda *args: False))
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_feed', lambda url: pytest.fail('network'))
    with pytest.raises(ValueError, match='robots_disallowed'):
        fetch_collection(source.pk, ENDPOINT, collection_url(ENDPOINT))
    assert not gate['lock'].locked() and gate['next_allowed'] > 0


def test_retry_after_envelope_is_preserved():
    from scraper.html_archive import retry_delay
    with pytest.raises(Exception) as error:
        decode_collection(json.dumps({'status': 429, 'headers': {'Retry-After': '1800'}, 'body': {}}).encode())
    assert retry_delay(error.value, 1) == 1800


@pytest.mark.django_db
def test_unconfirmed_gzc_is_not_enabled_by_importer(monkeypatch):
    source = Source.objects.create(name='GZC fixture', url='https://gzc.cieszyn.pl/', catalog_stage='candidate',
        is_active=False, scrape_enabled=False)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: pytest.fail('network'))
    assert wordpress_cycle()['new_records'] == 0
    assert run_wordpress_source(source.pk)['status'] == 'disabled'
    source.refresh_from_db()
    assert source.catalog_stage == 'candidate' and not source.is_active


def incomplete_liberte_post():
    # Metadata-only public record inspected on 2026-09-09. No guessed title/date.
    return {'id': 30200, 'date_gmt': '2011-12-15T05:32:00', 'link': 'https://liberte.pl/107/',
        'title': {'rendered': ''}, 'featured_media': 0}


def test_missing_title_is_queued_with_evidence_and_next_page_resumes(source, monkeypatch):
    seed_snapshot(source, monkeypatch, 30202)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection',
        lambda *args: envelope([post(30199), incomplete_liberte_post()], 4))
    result = run_wordpress_source(source.pk)
    assert result['status'] == 'partial' and result['new_records'] == 1 and result['incomplete_records'] == 1
    assert not Article.objects.filter(url='https://liberte.pl/107/').exists()
    job = ArchiveJob.objects.get(url='https://liberte.pl/107/')
    assert job.kind == 'page' and job.status == 'pending' and job.last_error == 'wordpress_missing_title'
    evidence = ImportState.objects.get(name=f'wordpress-gap:{source.pk}:30200')
    assert evidence.cursor['missing_fields'] == ['title']
    assert evidence.cursor['date_gmt_raw'] == '2011-12-15T05:32:00'
    assert evidence.cursor['archive_job_id'] == job.pk and len(evidence.cursor['response_sha256']) == 64
    state = due(source)
    assert state.cursor['offset'] == 2 and state.cursor['last_id'] == 30200
    assert state.cursor['processed'] == 2 and state.imported == 1  # examined != saved Articles
    assert state.cursor['incomplete_records_seen'] == 1 and state.cursor['recent_incomplete'][0]['post_id'] == 30200
    assert state.last_error == 'wordpress_missing_titles_queued'
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection',
        lambda *args: envelope([incomplete_liberte_post(), post(30201), post(30202)], 4))
    result = run_wordpress_source(source.pk)
    assert result['complete'] and result['new_records'] == 2 and result['incomplete_records'] == 0
    assert Article.objects.count() == 3 and ArchiveJob.objects.count() == 1
    state.refresh_from_db()
    assert state.cursor['incomplete_records_seen'] == 1  # observed gap remains visible after good pages


def test_incomplete_record_does_not_reset_existing_queue_backoff(source, monkeypatch):
    old_job = ArchiveJob.objects.create(source=source, url='https://liberte.pl/107/', kind='page',
        status='error', last_error='missing_source_title', attempts=4,
        available_at=timezone.now() + timedelta(hours=8))
    before = (old_job.status, old_job.last_error, old_job.attempts, old_job.available_at)
    seed_snapshot(source, monkeypatch, 30200)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([incomplete_liberte_post()]))
    assert run_wordpress_source(source.pk)['complete']
    old_job.refresh_from_db()
    assert (old_job.status, old_job.last_error, old_job.attempts, old_job.available_at) == before
    assert ArchiveJob.objects.count() == 1 and not Article.objects.exists()


def test_gap_queue_evidence_and_good_articles_roll_back_with_cursor(source, monkeypatch):
    state = seed_snapshot(source, monkeypatch, 30200)
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection',
        lambda *args: envelope([post(30199), incomplete_liberte_post()]))
    from scraper.wordpress_backfill import save_incomplete_metadata
    def fail_after_gap(*args):
        save_incomplete_metadata(*args)
        raise ValueError('Synthetic transaction failure')
    with patch('scraper.wordpress_backfill.save_incomplete_metadata', side_effect=fail_after_gap):
        assert run_wordpress_source(source.pk)['status'] == 'error'
    state.refresh_from_db()
    assert state.cursor['offset'] == 0 and state.imported == 0
    assert not ArchiveJob.objects.exists() and not Article.objects.exists() and not ArticleContent.objects.exists()
    assert not ImportState.objects.filter(name__startswith='wordpress-gap:').exists()
    due(source)
    assert run_wordpress_source(source.pk)['new_records'] == 1
    assert ArchiveJob.objects.count() == 1 and ImportState.objects.filter(name__startswith='wordpress-gap:').count() == 1


def test_missing_title_does_not_authorize_foreign_permalink(source, monkeypatch):
    seed_snapshot(source, monkeypatch, 30200)
    item = {**incomplete_liberte_post(), 'link': 'https://foreign.example/107/'}
    monkeypatch.setattr('scraper.wordpress_backfill.fetch_collection', lambda *args: envelope([item]))
    assert run_wordpress_source(source.pk)['status'] == 'error'
    assert ImportState.objects.get(name=f'wordpress-archive:{source.pk}').cursor['offset'] == 0
    assert not ArchiveJob.objects.exists() and not Article.objects.exists()
