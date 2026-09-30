from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from time import perf_counter

import pytest
from celery.schedules import crontab
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import admin_status as status
from news import task_heartbeat as heartbeat
from news.clinic_models import ClinicInterview, CouncilRecruitment, CouncilSeat, SpinDiagnosis
from news.models import ImportState
from news.political_models import PoliticalAccount, PoliticalPost


@pytest.fixture(autouse=True)
def no_credit_network():
    with patch('news.admin_finance.openrouter_balance', return_value={'balance': 'unknown', 'checked_at': 'unknown'}):
        yield


@pytest.mark.django_db
def test_anonymous_and_regular_user_cannot_read_status():
    client = APIClient()
    with patch.object(status, 'server', side_effect=AssertionError('Must not collect data')):
        response = client.get('/api/admin/status/')
        assert response.status_code == 403
        assert 'sections' not in response.data
        client.force_authenticate(get_user_model().objects.create_user('reader048'))
        assert client.get('/api/admin/status/').status_code == 403


@pytest.mark.django_db
def test_staff_snapshot_shape_and_recorded_failures():
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user('owner048', is_staff=True))
    ImportState.objects.create(name='test-import', last_error='ConnectionError')
    CouncilSeat.objects.create(provider='gemini', model='test-model', status='suspended', last_error='http_402')
    CouncilRecruitment.objects.create(provider='gemini', model='candidate048', decision='would_admit', mode='trial')
    ClinicInterview.objects.create(day=timezone.localdate(), video_id='abcdefghijk', status='pending_review', title='Wywiad testowy', channel='Kanał')
    started = perf_counter()
    response = client.get('/api/admin/status/')
    print(f'\nStaff snapshot: {(perf_counter() - started) * 1000:.1f} ms (local test database)')
    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control']
    sections = {s['title']: s for s in response.data['sections']}
    assert len(sections) == 19
    assert {"Pobieranie i czytanie", "Kolejki", "AI i koszty", "Agenci", "YouTube"} <= set(sections)
    assert len(response.data['wallets']) == 3
    assert len(response.data['series']) == 3
    assert len(response.data['kpis']) == 4
    assert sections['Źródła / harvestery']['status'] == 'error'
    assert sections['Konsylium']['status'] == 'error'
    assert any('402 — brak środków' in r['description'] for r in sections['Konsylium']['items'])
    assert sections['Rekruter']['items'][0]['title'] == 'gemini · candidate048'
    assert sections['Zadania w tle']['items']
    assert 'transkrypcja albo diagnoza' in str(sections['Wywiad dnia']['metrics'])
    for section in sections.values():
        assert set(section) == {'title', 'status', 'description', 'last_event', 'metrics', 'items'}
        assert section['status'] in {'ok', 'warn', 'error', 'unknown'}
        assert section['description'] != 'Nie udało się odczytać stanu.'


def test_pulses_match_arguments_and_preserve_failure():
    cache.clear()
    entries = {'votes': {'task': 'test.import', 'args': ['votes'], 'schedule': crontab(minute='*/5')},
               'prints': {'task': 'test.import', 'args': ['prints'], 'schedule': crontab(minute=10)}}
    sender = SimpleNamespace(name='test.import', request=SimpleNamespace(id='048', args=['votes'], kwargs={}))
    with patch('config.celery.app', SimpleNamespace(conf=SimpleNamespace(beat_schedule=entries))):
        heartbeat.started(sender=sender, task_id='048', args=['votes'], kwargs={})
        heartbeat.failed(sender=sender, task_id='048', args=['votes'], kwargs={}, exception=ValueError('secret'))
        pulse = cache.get('heartbeat:votes')
        assert pulse['result'] == 'error' and pulse['summary'] == 'ValueError'
        assert cache.get('heartbeat:prints') is None
        assert status.tasks(timezone.now())['status'] == 'error'
        heartbeat.started(sender=sender, task_id='048', args=['votes'], kwargs={})
        heartbeat.succeeded(sender=sender, result={'imported': 2, 'token': 'secret'})
        assert cache.get('heartbeat:votes')['summary'] == 'imported: 2'
        old = timezone.now() - timedelta(minutes=11)
        cache.set('heartbeat:votes', {**cache.get('heartbeat:votes'), 'started_at': old.isoformat()})
        assert status.tasks(timezone.now())['status'] == 'warn'
    cache.clear()


def test_cadence_includes_nights_and_weekends():
    assert heartbeat.cadence(crontab(minute='*/5')) == 300
    assert heartbeat.cadence(crontab(hour=5, minute=20, day_of_week='mon')) == 7 * 86400
    assert heartbeat.cadence(crontab(hour='7,10', minute=5)) == 21 * 3600


@pytest.mark.django_db
def test_warsaw_day_boundaries_and_diagnosis_errors_last_24h():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 9, 30, 0, 30, tzinfo=ZoneInfo('Europe/Warsaw'))
    account = PoliticalAccount.objects.create(user_id='480', handle='test048')
    for i, hours in enumerate((0, 2, 25)):
        stamp = now - timedelta(hours=hours)
        post = PoliticalPost.objects.create(account=account, post_id=str(480 + i), fetched_at=stamp, published_at=stamp)
        SpinDiagnosis.objects.create(post=post, created_at=stamp, diagnosed_at=stamp, status='failed', error='recent' if hours < 24 else 'old')
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user('dates048', is_staff=True))
    with patch.object(status.timezone, 'now', return_value=now):
        response = client.get('/api/admin/status/')
    sections = {s['title']: s for s in response.data['sections']}
    assert sections['X — pobieranie wpisów']['metrics'][:2] == [status.metric('Dziś', 1), status.metric('Wczoraj', 1)]
    errors = [i for i in sections['Diagnozy']['items'] if i['title'] == 'Błąd diagnozy (24 h)']
    assert len(errors) == 1
    assert errors[0]['description'] == status.safe_error('recent')
    assert errors[0]['metrics'] == [status.metric('Liczba', 2)]


@pytest.mark.django_db
def test_unavailable_section_does_not_hide_others():
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user('staff048', is_staff=True))
    with patch.object(status, 'tasks', side_effect=RuntimeError('sensitive')):
        response = client.get('/api/admin/status/')
    assert response.status_code == 200
    assert response.data['sections'][1]['status'] == 'unknown'
    assert b'sensitive' not in response.content
