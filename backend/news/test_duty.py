from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from celery.schedules import crontab
from django.core.cache import cache
from rest_framework.test import APIClient

from news import duty, agents_common, agent_registry, task_heartbeat
from news.clinic_ai import ClinicAIError
from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.models import DutyAlarm, ImportState, RepairAction, RepairerState
from news.political_models import PoliticalAccount, PoliticalPost, AccountWardenRun

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 2, 14, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('CLINIC_DAILY_BUDGET_USD', '5')
    monkeypatch.setenv('DUTY_ENABLED', 'true')
    monkeypatch.setenv('REPAIRER_ENABLED', 'true')
    monkeypatch.setenv('REPAIRER_DRY_RUN', 'false')
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('No HTTP')), \
         patch('config.celery.app.send_task') as send:
        yield send
    cache.clear()


def diagnosis(at=NOW, cost=1, **fields):
    n = PoliticalPost.objects.count() + 1  # usunięte diagnozy zostawiają wpisy
    account, _ = PoliticalAccount.objects.get_or_create(user_id='1', defaults={'handle': 'test', 'camp': 'government', 'enabled': True})
    post = PoliticalPost.objects.create(account=account, post_id=str(n), text='Test', published_at=at, camp_at_collection='government')
    return SpinDiagnosis.objects.create(post=post, diagnosed_at=at, created_at=at,
        usage={'model': 'claude-sonnet', 'input_tokens': 0, 'output_tokens': 0, 'web_search_requests': int(cost * 100)}, **fields)


def interview(status='failed', error='timeout', ago=0):
    return ClinicInterview.objects.create(video_id=str(ClinicInterview.objects.count()), day=NOW.date(),
        status=status, error=error, created_at=NOW - timedelta(hours=ago), diagnosed_at=NOW - timedelta(hours=ago))


def context(now=NOW, entries=None):
    ctx = duty.Context(now)
    if entries is not None:
        ctx.entries = entries
    return ctx


@pytest.mark.parametrize('cost,severity', [(3, None), (4, 'warning'), (5, 'warning'), (6, 'critical')])
def test_budget_thresholds(cost, severity):
    diagnosis(cost=cost)
    found = duty.check_budget(context())
    assert ([a['severity'] for a in found] or [None]) == [severity]


def test_zero_budget_and_median(monkeypatch):
    monkeypatch.delenv('CLINIC_DAILY_BUDGET_USD')
    assert duty.check_budget(context()) == []
    diagnosis(at=NOW - timedelta(days=2), cost=1)
    diagnosis(at=NOW - timedelta(days=1), cost=1)
    row = diagnosis(cost=3)
    found = duty.check_budget(context())
    assert {a['key'] for a in found} == {'budget:daily', f'budget:diagnosis:{row.pk}'}
    assert found[0]['severity'] == 'critical'
    row.usage['web_search_requests'] = 200
    row.save()
    assert len(duty.check_budget(context())) == 1


@pytest.mark.parametrize('count,public,expected', [(3, False, False), (4, False, True), (0, True, True)])
def test_warden(count, public, expected):
    AccountWardenRun.objects.create(started_at=NOW, report={'events': [{'kind': 'disabled'}] * count})
    if public:
        PoliticalAccount.objects.create(user_id='100', handle='kprm', camp='public', enabled=False)
    assert bool(duty.check_warden(context())) is expected


def test_old_warden_events_do_not_count():
    AccountWardenRun.objects.create(started_at=NOW - timedelta(days=2), report={'events': [{'kind': 'disabled'}] * 10})
    assert duty.check_warden(context()) == []


@pytest.mark.parametrize('age,error,success,expected', [(25, 'timeout', False, True), (23, 'timeout', False, False),
    (25, '', False, False), (25, 'timeout', True, False)])
def test_never_worked(age, error, success, expected):
    ImportState.objects.create(name='gdelt:test', last_started=NOW - timedelta(hours=age), last_error=error,
                               last_success=NOW if success else None)
    assert bool(duty.check_importers(context(entries={}))) is expected


def test_import_cadence_and_timer_survives_repeated_attempts():
    row = ImportState.objects.create(name='official:votings', last_started=NOW - timedelta(minutes=46))
    assert duty.check_importers(context())[0]['details']['cadence_seconds'] == 900
    row.last_started = NOW - timedelta(minutes=30)
    row.save()
    ctx = context()
    assert duty.check_importers(ctx) == []
    ctx.save()
    row.last_started = NOW + timedelta(minutes=16)
    row.save()
    ctx = context(NOW + timedelta(minutes=16))
    assert duty.check_importers(ctx)
    row.last_success = NOW
    row.save()
    assert duty.check_importers(context()) == []


def test_missing_access_card_is_a_decision_visible_in_panel():
    from news.models import Source
    Source.objects.create(name='Bez karty', url='https://www.gov.pl/web/test', source_type='institution')
    ImportState.objects.create(name='official:votings', last_started=NOW - timedelta(days=3),
                               last_error='no_approved_instruction')
    assert duty.check_importers(context()) == []
    metrics = {item['label']: item['value'] for item in duty.panel_section(NOW)['metrics']}
    assert metrics['Źródła bez karty dostępu'] == 1
    assert metrics['Importery bez zatwierdzonej karty'] == 1


@pytest.mark.parametrize('age,failures,expected', [(44, 2, False), (46, 0, True), (1, 3, True)])
def test_beat(age, failures, expected):
    name = 'sejm-votes-15m'
    cache.set('heartbeat:' + name, {'last_event': (NOW - timedelta(minutes=age)).isoformat(), 'consecutive_errors': failures})
    ctx = context()
    ctx.entries = {name: ctx.entries[name]}
    assert bool([a for a in duty.check_tasks(ctx) if a['key'].startswith('task:')]) is expected


def test_missing_pulse_grace_and_disabled(monkeypatch):
    ctx = context()
    ctx.entries = {'agents-window-hourly': ctx.entries['agents-window-hourly']}
    assert duty.check_tasks(ctx) == []
    ctx.save()
    later = context(NOW + timedelta(hours=4), ctx.entries)
    assert any(a['key'] == 'task:agents-window-hourly' for a in duty.check_tasks(later))
    monkeypatch.setenv('AGENTS_ENABLED', 'false')
    assert duty.check_tasks(later) == []


@pytest.mark.parametrize('errors,expected', [(['timeout', 'timeout'], False), (['timeout'] * 3, True),
    (['gemini: http_402 secret balance=999'], True), (['insufficient credit'], True), (['billing disabled'], True)])
def test_interview_errors(errors, expected):
    for i, error in enumerate(errors):
        interview(error=error, ago=i)
    found = duty.check_interviews(context())
    assert bool(found) is expected
    assert 'secret' not in str(found) and '999' not in str(found)


def test_interview_recovery_breaks_streak():
    interview(error='402', ago=3)
    interview(ago=2)
    interview(status='approved', error='', ago=1)
    assert duty.check_interviews(context()) == []


@pytest.mark.parametrize('hour,age,queued,expected', [(14, 4, True, True), (14, 2, True, False),
    (7, 4, True, False), (22, 4, True, False), (14, 4, False, False)])
def test_diagnosis_stall(hour, age, queued, expected):
    now = NOW.replace(hour=hour)
    if queued:
        diagnosis(at=now - timedelta(hours=age), cost=0, status='queued')
    assert bool(duty.check_diagnoses(context(now))) is expected


def test_recent_diagnosis_clears_stall():
    diagnosis(at=NOW - timedelta(hours=4), status='queued')
    diagnosis(at=NOW - timedelta(hours=1), verdict='spin')
    assert duty.check_diagnoses(context()) == []


@pytest.mark.parametrize('age,name,error,expected', [(7, 'official:votings', 'host_rate_limited:86400', True),
    (6, 'official:eli', 'host_rate_limited:86400', False), (7, 'official:prints', 'timeout', False),
    (7, 'other', 'host_rate_limited:86400', False)])
def test_official_rate_limit(age, name, error, expected):
    ImportState.objects.create(name=name, last_started=NOW - timedelta(hours=age), last_error=error)
    assert bool(duty.check_rate_limits(context())) is expected


def test_rate_limit_timer_recovery_and_repeated_attempts():
    row = ImportState.objects.create(name='official:eli', last_started=NOW, last_error='host_rate_limited:86400')
    ctx = context(); assert duty.check_rate_limits(ctx) == []; ctx.save()
    row.last_started = NOW + timedelta(hours=7)
    row.save()
    assert duty.check_rate_limits(context(NOW + timedelta(hours=7)))
    row.last_success = NOW + timedelta(hours=6)
    row.save()
    assert duty.check_rate_limits(context(NOW + timedelta(hours=7))) == []


def test_alarm_dedup_close_reopen_and_no_models(isolated):
    diagnosis(cost=6)
    with patch('news.clinic_ai._client', side_effect=AssertionError('No model')), \
         patch('news.clinic_ai._call_gemini', side_effect=AssertionError('No model')), \
         patch('news.clinic_council.ask', side_effect=AssertionError('No model')):
        assert duty.run(NOW)['errors'] == 0
        duty.run(NOW + timedelta(minutes=15))
        row = DutyAlarm.objects.get(key='budget:daily')
        assert row.occurrences == 2 and row.first_seen == NOW
        assert DutyAlarm.objects.filter(key='budget:daily').count() == 1
        SpinDiagnosis.objects.all().delete()
        duty.run(NOW + timedelta(minutes=30))
        row.refresh_from_db()
        assert row.status == 'closed' and row.closed_at
        diagnosis(cost=6)
        duty.run(NOW + timedelta(minutes=45))
        row.refresh_from_db()
        assert row.status == 'open' and row.closed_at is None and row.occurrences == 3
    # Zadania bez pulsu dostają Naprawiacza, ale wyłącznie z listy przejrzanych, bezpiecznych zadań.
    assert all(call.args[0] in duty.SAFE_TASKS for call in isolated.call_args_list)


def test_failed_check_does_not_close_alarm():
    diagnosis(cost=6)
    duty.run(NOW)
    with patch('news.duty.diagnosis_costs', side_effect=ValueError('secret')):
        assert duty.run(NOW)['errors'] == 1
    assert DutyAlarm.objects.get(key='budget:daily').status == 'open'
    assert DutyAlarm.objects.get(key='check:check_budget').status == 'open'
    duty.run(NOW)
    assert DutyAlarm.objects.get(key='check:check_budget').status == 'closed'


def test_safe_dispatch_two_hours_and_broker_failure(isolated):
    ctx = context()
    data = duty.alarm('task:test', 'warning', 'Test', {}, NOW, 'Sprawdź.', 'sejm-votes-15m')
    duty.reconcile('test', [data], ctx, duty.Run(NOW))
    assert isolated.call_count == 1
    assert 'Wysłano Naprawiacza' in DutyAlarm.objects.get().dispatch_note
    duty.reconcile('test', [data], context(NOW + timedelta(hours=1)), duty.Run(NOW + timedelta(hours=1)))
    assert isolated.call_count == 1
    isolated.side_effect = RuntimeError('broker secret')
    duty.reconcile('test', [data], context(NOW + timedelta(hours=2)), duty.Run(NOW + timedelta(hours=2)))
    assert isolated.call_count == 2
    duty.reconcile('test', [data], context(NOW + timedelta(hours=2, minutes=15)), duty.Run(NOW + timedelta(hours=2, minutes=15)))
    assert isolated.call_count == 2
    assert 'secret' not in DutyAlarm.objects.get().dispatch_note


@pytest.mark.parametrize('beat', ['agents-window-hourly', 'account-warden-nightly', 'krs-agent-night', 'seba'])
def test_unreviewed_task_never_dispatched(beat, isolated):
    duty.reconcile('test', [duty.alarm('test', 'warning', 'Test', {}, NOW, 'Sprawdź.', beat)], context(), duty.Run(NOW))
    isolated.assert_not_called()


def test_diagnosis_retry_requires_explicit_positive_budget(monkeypatch, isolated):
    monkeypatch.delenv('CLINIC_DAILY_BUDGET_USD')
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    duty.reconcile('test', [duty.alarm('test', 'warning', 'Test', {}, NOW, 'Sprawdź.', 'clinic-diagnoses-day')], context(), duty.Run(NOW))
    isolated.assert_not_called()


def test_capacity_backoff_and_success_reset():
    current = NOW
    with patch('news.agents_common.step', side_effect=ClinicAIError('groq: http_429')) as step:
        for hours in (2, 4, 8, 12, 12):
            with patch('django.utils.timezone.now', return_value=current):
                assert agents_common.window_step()['backoff_hours'] == hours
                calls = step.call_count
                assert agents_common.window_step()['status'] == 'no_free_models'
                assert step.call_count == calls
            current += timedelta(hours=hours)
    with patch('django.utils.timezone.now', return_value=current), patch('news.agents_common.step', return_value={'status': 'ok'}):
        assert agents_common.window_step()['status'] == 'ok'
    data = RepairerState.objects.get(key='agents-window').data
    assert data['capacity_failures'] == 0 and data['next_attempt'] is None and data['last_success']


def test_window_closed_and_unrelated_error():
    with patch('news.agents_common.step', return_value={'status': 'closed'}):
        assert agents_common.window_step()['status'] == 'no_free_models'
    RepairerState.objects.filter(key='agents-window').delete()
    with patch('news.agents_common.step', side_effect=ClinicAIError('invalid_json')):
        with pytest.raises(ClinicAIError):
            agents_common.window_step()


def test_agents_day_without_success():
    RepairerState.objects.create(key='agents-window', data={'first_attempt': (NOW - timedelta(hours=24)).isoformat()})
    assert duty.check_tasks(context(entries={}))[0]['key'] == 'agents:no-success'
    RepairerState.objects.filter(key='agents-window').update(data={'last_success': NOW.isoformat()})
    assert duty.check_tasks(context(entries={})) == []


def test_heartbeat_counts_errors_and_skips():
    sender = SimpleNamespace(name='news.tasks.agents_window_task', request=SimpleNamespace(args=(), kwargs={}, id='run'))
    for i in range(3):
        task_heartbeat.record(sender, 'running')
        task_heartbeat.succeeded(sender, {'status': 'error'})
    assert cache.get('heartbeat:agents-window-hourly')['consecutive_errors'] == 3
    task_heartbeat.succeeded(sender, {'status': 'no_free_models'})
    pulse = cache.get('heartbeat:agents-window-hourly')
    assert pulse['consecutive_errors'] == 0 and pulse['result'] == 'skipped' and not pulse.get('last_success')
    assert pulse['summary'] == 'Pominięto: brak wolnych modeli'
    task_heartbeat.succeeded(sender, {'status': 'ok'})
    assert cache.get('heartbeat:agents-window-hourly')['last_success']


def test_registry_covers_every_beat_task():
    from config.celery import app
    assert {e['task'] for e in app.conf.beat_schedule.values()} <= {s['task'] for s in agent_registry.REGISTRY.values()}
    assert agent_registry.REGISTRY['seba']['flag'] == 'SEBA_ENABLED'
    assert agent_registry.REGISTRY['second-key']['flag'] == 'WARDEN_SECOND_KEY_ENABLED'
    assert agent_registry.schedule_label(crontab(minute='*/15')) == 'co 15 min'
    assert agent_registry.schedule_label(crontab(hour=3, minute=10)) == 'codziennie 3:10'
    assert agent_registry.next_run(crontab(hour=3, minute=10), NOW) == NOW.replace(day=3, hour=3, minute=10)


def test_map_staff_only_and_reports(django_user_model):
    from news.agent_models import AgentNote
    client = APIClient()
    assert client.get('/api/staff/agents/map/').status_code in (401, 403)
    user = django_user_model.objects.create_user('duty-reader')
    client.force_authenticate(user)
    assert client.get('/api/staff/agents/map/').status_code == 403
    user.is_staff = True; user.save()
    for i in range(6):
        AgentNote.objects.create(agent='strateg', kind='report', title=f'Raport {i}', body='Treść')
    response = client.get('/api/staff/agents/map/')
    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control']
    assert len(response.data['reports']) == 5
    assert response.data['reports'][0]['title'] == 'Raport 5'
    rows = response.data['results']
    assert next(r for r in rows if r['name'] == 'Seba')['schedule'] == 'co godzinę, minuta: 30'
    assert any(row['collector'] for row in rows)


def test_panel_counts():
    diagnosis(cost=6)
    duty.run(NOW)
    section = duty.panel_section(NOW)
    metrics = {m['label']: m['value'] for m in section['metrics']}
    assert section['status'] == 'error' and metrics['Krytyczne'] == 1
    assert metrics['Najstarszy alarm'] != 'unknown'
