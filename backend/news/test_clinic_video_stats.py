"""Alerty i równa miara filmów, bez prawdziwej poczty i wywołań API."""
import json
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import clinic, clinic_ai, clinic_video_stats as stats
from news.clinic_models import SpinDiagnosis
from news.models import RepairerState
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 3)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, settings):
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    settings.CLINIC_VIDEO_MONTHLY_ALERT_PLN = 50
    settings.CLINIC_VIDEO_USD_PLN = 4
    cache.clear()
    original = timezone.localdate
    monkeypatch.setattr(timezone, 'localdate', lambda value=None, timezone=None:
                        TODAY if value is None else original(value, timezone))
    monkeypatch.setattr('requests.sessions.Session.request',
                        lambda *a, **kw: pytest.fail('Niedozwolone prawdziwe HTTP'))
    mail = Mock(return_value=True)
    monkeypatch.setattr('news.social_publish._mail', mail)
    monkeypatch.setattr('news.council_recruiter._owner_email', lambda: 'owner@example.test')
    yield mail
    cache.clear()


def spend(day, usd, camp='government'):
    token = stats.video_camp.set(camp)
    try:
        stats.record_cost(usd, day)
    finally:
        stats.video_camp.reset(token)


def post(day, camp, statuses=None, *, no_diagnosis=False, snapshot=False):
    account, _ = PoliticalAccount.objects.get_or_create(
        user_id='1' if camp == 'government' else '2',
        defaults={'handle': camp, 'camp': camp, 'enabled': True})
    row = PoliticalPost.objects.create(
        account=account, post_id=str(100 + PoliticalPost.objects.count()),
        text='Wpis', url='https://x.com/a/status/123', camp_at_collection=camp,
        published_at=timezone.make_aware(datetime.combine(day, time(12))),
        media=[{'type': 'video', 'media_key': f'v{n}'} for n in range(len(statuses or ['unseen']))])
    if not no_diagnosis:
        videos = [{'index': n + 1, 'media_key': f'v{n}', 'status': status,
                   'limitation': 'budżet Gemini' if status in ('unseen', 'thumbnail') else ''}
                  for n, status in enumerate(statuses or ['unseen'])]
        usage = {'videos': videos}
        if snapshot:
            usage = {'snapshot': {'usage': usage}}
        SpinDiagnosis.objects.create(post=row, status='failed' if snapshot else 'approved', usage=usage)
    return row


def test_monthly_threshold_strict_and_once_per_month(isolated):
    spend(TODAY, 12.5)
    assert not stats.notify()
    spend(TODAY, 0.01)
    assert stats.notify()
    cache.clear()
    spend(TODAY, 100)
    assert not stats.notify()
    assert isolated.call_count == 1
    november = date(2026, 11, 1)
    spend(november, 13)
    assert stats.notify(today=november)
    assert isolated.call_count == 2
    assert stats.monthly_cost(november)['usd'] == 13


def test_threshold_and_exchange_rate_are_configurable(settings, isolated):
    settings.CLINIC_VIDEO_MONTHLY_ALERT_PLN = 80
    settings.CLINIC_VIDEO_USD_PLN = 5
    spend(TODAY, 16)
    assert not stats.notify()
    spend(TODAY, 1)
    assert stats.notify()
    assert stats.monthly_cost()['pln'] == 85


@pytest.mark.parametrize('failure', [False, RuntimeError('SMTP')])
def test_failed_mail_does_not_consume_alert(isolated, failure):
    spend(TODAY, 13)
    isolated.side_effect = [failure, True]
    assert not stats.notify()
    assert stats.notify()
    assert not stats.notify()
    assert isolated.call_count == 2


def test_legacy_cache_import_and_only_video_cost(isolated):
    yesterday = TODAY - timedelta(days=1)
    cache.set(clinic_ai.GEMINI_SPEND_KEY.format(day=yesterday.isoformat(), task='video'), {'usd': 2})
    cache.set(clinic_ai.GEMINI_SPEND_KEY.format(day=TODAY.isoformat(), task='video'),
              {'usd': 3, 'calls': 1, 'searches': 0, 'thinking': 0})
    payload = {'usageMetadata': {'promptTokenCount': 1_000_000, 'thoughtsTokenCount': 1_000_000}}
    clinic_ai.record_gemini_spend('image', payload)
    token = stats.video_camp.set('opposition')
    try:
        clinic_ai.record_gemini_spend('video', payload)
    finally:
        stats.video_camp.reset(token)
    assert stats.monthly_cost()['usd'] == 8.5
    values = stats.costs(TODAY, TODAY)
    assert values['opposition'] == 3.5 and values['unassigned'] == 3
    assert clinic_ai.gemini_spent_today() == 10
    assert not isolated.called


def test_alert_does_not_stop_next_gemini_call(monkeypatch, isolated, settings):
    settings.CLINIC_VIDEO_MONTHLY_ALERT_PLN = 1
    monkeypatch.setenv('GEMINI_DAILY_BUDGET_USD', '10')
    response = Mock(status_code=200)
    response.json.return_value = {'usageMetadata': {'promptTokenCount': 1_000_000}}
    api = Mock(return_value=response)
    monkeypatch.setattr(clinic_ai.requests, 'post', api)
    for _ in range(2):
        assert clinic_ai.gemini_post('gemini', {}, key='fake', timeout=1, task='video') is response
    assert api.call_count == 2 and isolated.call_count == 1
    monkeypatch.setenv('GEMINI_DAILY_BUDGET_USD', '1')
    with pytest.raises(clinic_ai.ClinicAIError, match='gemini_daily_budget'):
        clinic_ai.gemini_post('gemini', {}, key='fake', timeout=1, task='video')
    assert api.call_count == 2


def test_report_camps_windows_missing_results_and_costs():
    yesterday = TODAY - timedelta(days=1)
    gov = post(yesterday, 'government', ['full', 'partial', 'thumbnail', 'unseen'])
    gov.account.camp = 'opposition'
    gov.account.save()
    post(yesterday, 'opposition', no_diagnosis=True)
    post(TODAY - timedelta(days=7), 'opposition', ['full'], snapshot=True)
    post(TODAY - timedelta(days=8), 'government', ['unseen'])
    post(TODAY, 'government', ['full'])
    spend(yesterday, 1.25, 'government')
    spend(TODAY - timedelta(days=7), 0.5, 'opposition')
    report = stats.build_report()
    day, week = report['periods']
    row = day['camps']['government']
    assert row['posts'] == 1 and row['videos'] == 4
    assert [row[k] for k in stats.STATUSES] == [1, 1, 1, 1]
    assert row['unwatched_share'] == 0.5 and row['cost_pln'] == 5
    assert row['reasons'] == {'budżet Gemini': 2}
    assert day['camps']['opposition']['reasons'] == {'brak diagnozy': 1}
    assert week['camps']['opposition']['posts'] == 2
    assert week['camps']['opposition']['full'] == 1
    assert week['camps']['opposition']['cost_usd'] == 0.5
    assert not report['warning']


@pytest.mark.parametrize('days,changing,empty,warning', [
    (2, False, False, False), (3, False, False, True),
    (3, True, False, False), (3, False, True, False)])
def test_warning_requires_same_side_for_three_days(days, changing, empty, warning):
    for offset in range(1, days + 1):
        day = TODAY - timedelta(days=offset)
        reverse = changing and offset == 2
        post(day, 'government', ['full' if reverse else 'unseen'])
        if not (empty and offset == 2):
            post(day, 'opposition', ['unseen' if reverse else 'full'])
    assert bool(stats.build_report()['warning']) is warning


def test_exactly_ten_percentage_points_do_not_warn():
    for offset in range(1, 4):
        day = TODAY - timedelta(days=offset)
        post(day, 'government', ['unseen'] + ['full'] * 9)
        post(day, 'opposition', ['full'] * 10)
    assert not stats.build_report()['warning']


def test_combined_daily_mail_warning_and_monthly_alert(isolated):
    from news.tasks import clinic_video_stats_task
    for offset in range(1, 4):
        day = TODAY - timedelta(days=offset)
        post(day, 'government', ['thumbnail'])
        post(day, 'opposition', ['full'])
    spend(TODAY, 13)
    assert clinic_video_stats_task() == {'sent': True}
    assert clinic_video_stats_task() == {'sent': False}
    assert not stats.notify()
    recipient, subject, body = isolated.call_args.args
    assert recipient == 'owner@example.test' and 'alert kosztu' in subject
    assert '3 kolejne dni' in body and 'Ostatnie 7 dni' in body
    assert 'Oglądanie trwa nadal' in body and isolated.call_count == 1


def test_command_is_read_only_and_json_matches_report(isolated):
    out = StringIO()
    call_command('clinic_video_stats', '--json', stdout=out)
    assert json.loads(out.getvalue()) == stats.build_report()
    assert not isolated.called
    assert not RepairerState.objects.exists()


def test_stats_are_staff_only(django_user_model):
    client = APIClient()
    url = '/api/staff/clinic/queue/'
    assert client.get(url).status_code in (401, 403)
    user = django_user_model.objects.create_user(username='staff', is_staff=True)
    client.force_authenticate(user=user)
    response = client.get(url)
    assert response.status_code == 200
    assert response.data['video_stats']['as_of'] == TODAY.isoformat()


def test_failed_diagnosis_preserves_video_results(monkeypatch):
    row = post(TODAY - timedelta(days=1), 'government', ['full'])
    diagnosis = row.spin_diagnosis
    diagnosis.usage = {'snapshot': {'usage': diagnosis.usage},
                       'snapshot_at': (timezone.now() - timedelta(days=8)).isoformat()}
    diagnosis.save()
    videos = [{'index': 1, 'status': 'partial', 'limitation': 'fragment'}]
    def attachments(*args, video_results, **kwargs):
        assert stats.video_camp.get() == 'government'
        video_results.extend(videos)
        return 'Opis filmu'
    monkeypatch.setattr('news.post_attachments.describe', attachments)
    monkeypatch.setattr(clinic_ai, 'provider', lambda: 'anthropic')
    monkeypatch.setattr(clinic_ai, '_call', Mock(side_effect=clinic_ai.ClinicAIError('gemini_daily_budget')))
    diagnosis = clinic.diagnose(diagnosis)
    diagnosis.refresh_from_db()
    assert diagnosis.status == 'failed' and diagnosis.usage['videos'] == videos
    assert 'snapshot' not in diagnosis.usage
    assert stats.build_report()['periods'][0]['camps']['government']['partial'] == 1
    assert stats.video_camp.get() == 'unassigned'


def test_periods_use_warsaw_midnight():
    row = post(TODAY, 'government', ['full'])
    row.published_at = timezone.make_aware(datetime(2026, 10, 2, 0, 5)).astimezone(datetime_timezone.utc)
    row.save()
    assert row.published_at.date() == date(2026, 10, 1)
    yesterday = stats.build_report()['periods'][0]['camps']['government']
    assert yesterday['posts'] == 1
