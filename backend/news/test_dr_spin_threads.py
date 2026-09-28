"""Nitki z lokalnej Bazy; model i sieć zastąpione w testach."""
import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic_ai, dr_spin_threads as threads
from news.clinic_models import SpinDiagnosis
from news.models import Article, ArticleContent, EvidenceLink, Source, Thread, ThreadItem
from news.test_clinic import account, post


@pytest.fixture
def context(db, monkeypatch):
    monkeypatch.setenv('DR_SPIN_THREADS_ENABLED', 'true')
    # Żaden test nie może przypadkiem skorzystać z prawdziwego modelu.
    def unavailable(*args, **kwargs):
        raise clinic_ai.ClinicAIError('Brak darmowego modelu')
    monkeypatch.setattr(clinic_ai, '_free_chat', unavailable)
    diagnosis = SpinDiagnosis.objects.create(
        post=post(account()), status='approved', verdict='spin', intensity=85,
        headline='Podatki i budżet', summary='Spór o podatki.',
        claims=[{'claim': 'Podatki wzrosły.', 'assessment': 'unverified', 'explanation': 'Brak danych.'}],
        techniques=[{'name': 'Uproszczenie', 'quote': 'Budżet państwa', 'explanation': 'Brak kontekstu.'}],
        diagnosed_at=timezone.now())
    source = Source.objects.create(name='Ministerstwo', url='https://www.gov.pl', source_type='institution')
    rows = [Article.objects.create(source=source, title=f'Podatki i budżet {index}',
                                   url=f'https://www.gov.pl/material/{index}', published_date=timezone.now())
            for index in range(7)]
    return diagnosis, rows


def fake_selection(monkeypatch, rows, extra=None):
    def chat(system, user, schema, max_tokens):
        payload = json.loads(user)
        assert len(payload['candidates']) <= 20
        assert all(set(row) == {'id', 'title', 'source', 'date'} for row in payload['candidates'])
        return {'title': 'Podatki w kontekście', 'items': (extra or []) + [
            {'id': row.pk, 'why': 'Materiał opisuje kontekst budżetu.'} for row in rows]}, {}
    monkeypatch.setattr(clinic_ai, '_free_chat', chat)


def test_happy_path_and_external_card(context, monkeypatch):
    diagnosis, rows = context
    fake_selection(monkeypatch, rows[:3])
    result = threads.build_daily_thread()
    thread = Thread.objects.get(pk=result['id'])
    assert thread.published and thread.created_by is None and thread.thread_type == 'context'
    assert thread.description == threads.DISCLOSURE
    items = list(thread.thread_items.all())
    assert [item.position for item in items] == [0, 1, 2, 3]
    assert items[0].article_id is None and items[0].external_url == diagnosis.post.url
    assert items[0].editorial_note == f'Wpis: Poseł Test. Diagnoza Dr. Spina: https://spin.clinic/klinika/{diagnosis.pk}'
    assert [item.article_id for item in items[1:]] == [row.pk for row in rows[:3]]
    response = APIClient().get(f'/api/threads/{thread.slug}/')
    assert response.status_code == 200
    assert response.data['author_name'] == 'Dr. Spin'
    assert response.data['items'][0]['article']['reference_only'] is True
    assert response.data['items'][0]['article']['url'] == diagnosis.post.url


def test_fallback_without_ai(context):
    result = threads.build_daily_thread()
    assert result['fallback'] and len(result['items']) == 5
    assert all(item['why'] == threads.FALLBACK_NOTE for item in result['items'])


def test_invalid_and_duplicate_ids_are_rejected(context, monkeypatch):
    _, rows = context
    fake_selection(monkeypatch, rows[:3], [
        {'id': 999999, 'why': 'Spoza listy.'}, {'id': str(rows[3].pk), 'why': 'Zły typ.'},
        {'id': True, 'why': 'Zły typ.'}, {'id': rows[0].pk, 'why': 'Poprawny.'}])
    result = threads.build_daily_thread()
    assert not result['fallback']
    assert [item['id'] for item in result['items']] == [row.pk for row in rows[:3]]


@pytest.mark.parametrize('data', [None, [], {'items': None}, {'items': [{'id': 999999, 'why': 'Obcy.'}]}])
def test_malformed_or_too_short_selection_uses_fallback(context, monkeypatch, data):
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: (data, {}))
    result = threads.build_daily_thread()
    assert result['fallback'] and len(result['items']) == 5


def test_once_per_day_and_history(context, monkeypatch):
    first = threads.build_daily_thread()
    monkeypatch.setattr(clinic_ai, '_free_chat', lambda *args, **kwargs: pytest.fail('Powtórne wywołanie AI'))
    assert threads.build_daily_thread()['status'] == 'exists'
    assert Thread.objects.count() == 1 and ThreadItem.objects.count() == 6
    tomorrow = timezone.localdate() + timedelta(days=1)
    monkeypatch.setattr(threads.timezone, 'localdate', lambda: tomorrow)
    fake_selection(monkeypatch, context[1][:3])
    second = threads.build_daily_thread()
    assert first['id'] != second['id'] and Thread.objects.count() == 2


@pytest.mark.parametrize('flag', [None, 'false', '1'])
def test_disabled_without_database_or_ai(monkeypatch, flag):
    monkeypatch.delenv('DR_SPIN_THREADS_ENABLED', raising=False)
    if flag is not None:
        monkeypatch.setenv('DR_SPIN_THREADS_ENABLED', flag)
    monkeypatch.setattr(threads.clinic, 'spin_of_day_by_camp', lambda: pytest.fail('Flaga nie zatrzymała pracy'))
    assert threads.build_daily_thread() == {'status': 'disabled'}
    assert threads.build_daily_thread(dry_run=True) == {'status': 'disabled'}


def test_dry_run_command_does_not_write(context):
    output = StringIO()
    call_command('dr_spin_thread', '--dry-run', stdout=output)
    result = json.loads(output.getvalue())
    assert result['status'] == 'dry_run' and result['title'] and result['main'] and len(result['items']) == 5
    assert not Thread.objects.exists() and not ThreadItem.objects.exists()


def test_insufficient_context_and_missing_spin(context, monkeypatch):
    Article.objects.exclude(pk__in=[row.pk for row in context[1][:2]]).delete()
    assert threads.build_daily_thread()['status'] == 'insufficient_context'
    monkeypatch.setattr(threads.clinic, 'spin_of_day_by_camp', lambda: {'order': ['government'], 'spins': {'government': None}})
    assert threads.build_daily_thread()['status'] == 'no_spin'
    assert not Thread.objects.exists()


def test_search_uses_local_content_and_links_and_filters_dates(context):
    diagnosis, rows = context
    Article.objects.all().delete()
    source = Source.objects.get()
    def make(index, **kwargs):
        return Article.objects.create(source=source, title='Dokument', url=f'https://example.org/{index}',
                                      published_date=timezone.now() - timedelta(days=kwargs.pop('days', 1)), **kwargs)
    content = make(1)
    ArticleContent.objects.create(article=content, text='Podatki')
    linked = make(2)
    EvidenceLink.objects.create(article=linked, phrase='budżet', source_url='https://www.gov.pl/dowod')
    make(3, days=61, description='Podatki')
    make(4, days=-1, description='Podatki')
    make(5, category='tweet', description='Podatki')
    spin = threads.clinic.spin_of_day_by_camp()['spins']['opposition']
    assert {row.pk for row in threads._candidates(spin)} == {content.pk, linked.pk}


def test_limit_and_official_preference(context):
    spin = threads.clinic.spin_of_day_by_camp()['spins']['opposition']
    source = Source.objects.create(name='Media', url='https://example.org')
    for index in range(25):
        Article.objects.create(source=source, title='Podatki i budżet', url=f'https://example.org/{index}',
                               published_date=timezone.now())
    candidates = threads._candidates(spin)
    assert len(candidates) == 20
    assert all(threads._preferred(row) for row in candidates[:7])


def test_task_lock_and_release(monkeypatch):
    from news.tasks import dr_spin_thread_task
    cache.delete('dr-spin-thread-lock')
    cache.add('dr-spin-thread-lock', '1', timeout=400)
    try:
        assert dr_spin_thread_task() == {'status': 'locked'}
    finally:
        cache.delete('dr-spin-thread-lock')
    def broken():
        raise RuntimeError('Błąd testowy')
    monkeypatch.setattr(threads, 'build_daily_thread', broken)
    with pytest.raises(RuntimeError):
        dr_spin_thread_task()
    assert cache.get('dr-spin-thread-lock') is None


def test_confirmed_video_preferred_and_candidate_urls_unique(context):
    from django.contrib.contenttypes.models import ContentType
    from news.political_models import OfficialVideoChannel
    spin = threads.clinic.spin_of_day_by_camp()['spins']['opposition']
    source = Source.objects.create(name='Oficjalny kanał', url='https://www.youtube.com/channel/UCtest')
    video = Article.objects.create(source=source, title='Podatki i budżet', url='https://www.youtube.com/watch?v=test',
                                   published_date=timezone.now(), ingestion_method='youtube', category='video')
    # Podobny URL to ten sam materiał, nawet jeśli Baza ma drugi rekord z fragmentem.
    Article.objects.create(source=source, title=video.title, url=video.url + '#t=10',
                           published_date=timezone.now(), ingestion_method='youtube', category='video')
    assert not threads._preferred(video)
    OfficialVideoChannel.objects.create(subject_content_type=ContentType.objects.get_for_model(Source),
        subject_object_id=source.pk, channel_url=source.url, channel_id='UCtest', status='confirmed',
        evidence_url='https://www.gov.pl/kanal')
    candidates = threads._candidates(spin)
    assert candidates[0].source_id == source.pk
    assert len([row for row in candidates if row.source_id == source.pk]) == 1


def test_selection_limits(context, monkeypatch):
    fake_selection(monkeypatch, context[1])
    result = threads.build_daily_thread()
    assert len(result['items']) == 6
    assert ThreadItem.objects.count() == 7
