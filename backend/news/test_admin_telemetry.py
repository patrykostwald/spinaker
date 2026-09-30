from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from celery.schedules import crontab
from django.core.cache import cache

from news import admin_telemetry as telemetry
from news.models import Article, ArticleContent, ArchiveJob, ImportState, Source
from news.political_models import PoliticalAccount, PoliticalPost


def boundaries():
    today = datetime(2026, 9, 30, tzinfo=ZoneInfo('Europe/Warsaw'))
    return today + timedelta(minutes=30), today, today - timedelta(days=1), today + timedelta(days=1)


def metrics(section):
    return {row['label']: row['value'] for row in section['metrics']}


@pytest.mark.django_db
def test_ingestion_includes_new_methods_and_reads_only_nonempty_content():
    now, today, yesterday, tomorrow = boundaries()
    source = Source.objects.create(name='Source 049', url='https://example.org')
    current = Article.objects.create(source=source, title='Now', url='https://example.org/now',
                                     ingestion_method='new-method', scraped_at=now)
    older = Article.objects.create(source=source, title='Yesterday', url='https://example.org/old',
                                   ingestion_method='rss', scraped_at=now - timedelta(hours=2))
    ArticleContent.objects.create(article=current, text='Text', fetched_at=now)
    ArticleContent.objects.create(article=older, text='', fetched_at=now)
    ArchiveJob.objects.create(source=source, url='https://example.org/archive', kind='page', status='failed')
    section = telemetry.intake(now, today, yesterday, tomorrow)
    assert metrics(section) == {'Dziś': 1, 'Wczoraj': 1, '7 dni': 2}
    rows = {row['title']: row for row in section['items']}
    assert metrics(rows['new-method'])['Dziś'] == 1
    assert metrics(rows['Czytanie treści'])['Dziś'] == 1
    assert metrics(rows['RSS'])['Źródła z materiałem w 24 h'] == 1
    assert rows['Archiwa']['status'] == section['status'] == 'error'
    series = telemetry.telemetry_series(today, tomorrow)
    assert [p['value'] for p in series[0]['points']] == [0, 0, 0, 0, 0, 1, 1]
    assert series[0]['points'][-1]['date'] == '2026-09-30'


@pytest.mark.django_db
def test_x_budget_uses_utc_period_and_never_exposes_raw_errors():
    now, today, yesterday, tomorrow = boundaries()
    account = PoliticalAccount.objects.create(user_id='490', handle='test049', last_error='http_402 token=private-secret')
    PoliticalPost.objects.create(account=account, post_id='490', fetched_at=now, published_at=now)
    state = ImportState.objects.create(name='political-x-budget', last_error='HTTP 402 key=private-secret', cursor={
        'day': '2026-09-29', 'month': '2026-09', 'daily_requests': 3, 'daily_posts': 5,
        'spent_upper_usd': '0.05', 'blocked_until': (now + timedelta(hours=1)).isoformat(), 'lease': 'private-secret'})
    section = telemetry.x_read(now, today, yesterday, tomorrow)
    assert section['status'] == 'error'
    data = metrics(section)
    assert data['Dziś'] == 1
    assert data['Zapytania w dobie budżetu UTC'] == 3
    assert data['Wydane w miesiącu (USD, górny szacunek)'] == .05
    assert 'private-secret' not in str(section)
    assert 'brak środków' in str(section)
    state.cursor['day'] = '2026-09-28'
    state.cursor['month'] = '2026-08'
    state.save()
    data = metrics(telemetry.x_read(now, today, yesterday, tomorrow))
    assert data['Zapytania w dobie budżetu UTC'] == 'unknown'
    assert data['Wydane w miesiącu (USD, górny szacunek)'] == 'unknown'


def test_schedule_uses_warsaw_and_respects_weekends_and_dst():
    now = datetime(2026, 9, 30, 23, 40, tzinfo=telemetry.WARSAW)
    assert telemetry.next_run(crontab(hour=23, minute=30), now).isoformat() == '2026-10-01T23:30:00+02:00'
    assert telemetry.next_run(crontab(hour=20, minute=0, day_of_week='sun'), now).isoformat() == '2026-10-04T20:00:00+02:00'
    spring = datetime(2026, 3, 29, 1, 0, tzinfo=telemetry.WARSAW)
    assert telemetry.next_run(crontab(hour=2, minute=30), spring).date().isoformat() == '2026-03-30'


@pytest.mark.django_db
def test_no_krs_cache_is_unknown_and_storage_counts_are_cached():
    cache.clear()
    now, today, yesterday, tomorrow = boundaries()
    section = telemetry.agents(now, today, tomorrow)
    krs = next(row for row in section['items'] if row['title'] == 'Agent KRS')
    assert metrics(krs)['Wydatki dziś (USD, cache)'] == 'unknown'
    assert metrics(krs)['Osoby podjęte dziś (cache)'] == 'unknown'
    with patch('news.admin_telemetry.os.scandir', side_effect=FileNotFoundError):
        result = telemetry.storage(now)
    backup = next(row for row in result['items'] if row['title'] == 'Kopia zapasowa')
    assert metrics(backup)['Wiek pliku kopii (h)'] == 'unknown'
    assert cache.get('admin-status:table-counts:v1') is not None
    cache.clear()


def test_error_messages_are_classified_without_echoing_secrets():
    assert telemetry.safe_error('402 bearer=token-secret').startswith('402 — brak środków')
    assert 'token-secret' not in telemetry.safe_error('failed: token-secret')
    assert telemetry.safe_error('') == ''


@pytest.mark.django_db
def test_all_telemetry_sections_can_be_collected_without_network():
    now, today, yesterday, tomorrow = boundaries()
    with patch('requests.sessions.Session.request', side_effect=AssertionError('network forbidden')):
        sections = telemetry.extended_sections(now, today, yesterday, tomorrow)
    assert len(sections) == 6
    assert all(not row['description'].startswith('Nie udało') for row in sections)
    assert all(set(row) == {'title', 'status', 'description', 'last_event', 'metrics', 'items'} for row in sections)
