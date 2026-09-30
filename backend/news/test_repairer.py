from datetime import datetime, timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from celery.schedules import crontab
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import repairer as r
from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.models import ArchiveJob, FetchAttempt, FetchRequest, ImportState, RepairAction, RepairerState, Source
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
EMPTY = {'sections': [], 'actions': []}
NOW = datetime(2026, 9, 30, 8, 0, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('REPAIRER_ENABLED', 'true')
    monkeypatch.setenv('REPAIRER_DRY_RUN', 'false')
    with patch('news.admin_finance.openrouter_balance', return_value={'balance': 'unknown', 'checked_at': 'unknown'}), \
         patch('config.celery.app.send_task') as send, patch('news.social_publish._mail', return_value=True) as mail:
        yield send, mail
    cache.clear()


def diagnosis(error='connection', **kwargs):
    account, _ = PoliticalAccount.objects.get_or_create(user_id='repair-test', defaults={'handle': 'repair'})
    post = PoliticalPost.objects.create(account=account, post_id=uuid4().hex, published_at=NOW)
    return SpinDiagnosis.objects.create(post=post, status='failed', error=error, diagnosed_at=NOW, **kwargs)


def beat():
    return {'task': 'scraper.tasks.import_official_task', 'args': ['votings'],
            'kwargs': {}, 'schedule': crontab(minute='*/15')}


def pulse(phase='error', ago=3600, summary='ConnectionError'):
    return {'phase': phase, 'result': phase, 'summary': summary,
            'last_event': (NOW - timedelta(seconds=ago)).isoformat(),
            'started_at': (NOW - timedelta(seconds=ago)).isoformat()}


@pytest.mark.parametrize('error', ['timeout', 'connection', 'HTTP 429', 'provider_503',
    'council_too_few_members', 'gemini_daily_limit', 'HTTP 504'])
def test_transient(error):
    assert r.transient(error)


@pytest.mark.parametrize('error', ['402 connection', '404 timeout', 'missing_key timeout',
    'invalid_json', 'rejected', '401', '403', 'unknown', 'insufficient credits timeout'])
def test_permanent_not_retried(error):
    assert not r.transient(error)
    row = diagnosis(error)
    r.repair_diagnoses(r.Run(NOW), EMPTY)
    row.refresh_from_db()
    assert row.status == 'failed' and row.repair_attempts == 0


def test_diagnosis_counter_content_dry_run_and_age():
    row = diagnosis(usage={'saved': 'keep'}, headline='Keep diagnosis content')
    ctx = r.Run(NOW, True)
    r.repair_diagnoses(ctx, EMPTY)
    row.refresh_from_db()
    assert row.status == 'failed' and row.repair_attempts == 0 and not RepairAction.objects.exists()
    assert ctx.actions[0]['result'] == 'retried'
    for expected in (1, 2):
        r.repair_diagnoses(r.Run(NOW), EMPTY)
        row.refresh_from_db()
        assert row.status == 'queued' and row.repair_attempts == expected
        assert row.usage == {'saved': 'keep'} and row.headline == 'Keep diagnosis content'
        row.status = 'failed'
        row.save(update_fields=['status'])
    # Retention of journal cannot reset the permanent counter.
    RepairAction.objects.all().delete()
    r.repair_diagnoses(r.Run(NOW), EMPTY)
    row.refresh_from_db()
    assert row.status == 'failed' and row.repair_attempts == 2
    old = diagnosis()
    SpinDiagnosis.objects.filter(pk=old.pk).update(diagnosed_at=NOW - timedelta(hours=49))
    hidden = diagnosis(hidden_at=NOW)
    daily = diagnosis('groq_daily_limit')
    r.repair_diagnoses(r.Run(NOW), EMPTY)
    for item in (old, hidden, daily):
        item.refresh_from_db()
        assert item.status == 'failed'
    r.repair_diagnoses(r.Run(NOW + timedelta(days=1)), EMPTY)
    daily.refresh_from_db()
    assert daily.status == 'queued'


def test_task_dispatch_exact_args_limits_and_dry_run(isolated):
    send, _ = isolated
    cache.set('heartbeat:sejm-votes-15m', pulse())
    r.retry_task(r.Run(NOW, True), 'sejm-votes-15m', beat())
    send.assert_not_called()
    assert not RepairAction.objects.exists()
    for hours in (0, 0.5, 1, 2, 3):
        r.retry_task(r.Run(NOW + timedelta(hours=hours)), 'sejm-votes-15m', beat())
    assert send.call_count == 3
    send.assert_called_with('scraper.tasks.import_official_task', args=['votings'], kwargs={}, retry=False)
    assert RepairAction.objects.filter(result='retried').count() == 3


@pytest.mark.parametrize('summary', ['Wyłączone', 'Nieskonfigurowane', '402'])
def test_task_disabled_or_permanent(summary, isolated):
    cache.set('heartbeat:task', pulse(summary=summary))
    r.retry_task(r.Run(NOW), 'task', beat())
    isolated[0].assert_not_called()


def test_task_unsafe_running_and_broker_failure(isolated):
    send, _ = isolated
    r.retry_task(r.Run(NOW), 'costly', {'task': 'news.tasks.krs_agent_task'})
    assert RepairAction.objects.get().result == 'needs_owner'
    cache.set('heartbeat:task', pulse(phase='running', ago=100))
    r.retry_task(r.Run(NOW), 'task', beat())
    send.assert_not_called()
    cache.set('heartbeat:task', pulse())
    send.side_effect = RuntimeError('connection secret-token-123')
    r.retry_task(r.Run(NOW), 'task', beat())
    r.retry_task(r.Run(NOW), 'task', beat())
    assert send.call_count == 1
    assert 'secret-token' not in str(list(RepairAction.objects.values()))


def test_beat_aliases_share_dispatch_and_daily_budget(isolated):
    from config.celery import app
    entries = {'one': beat(), 'two': beat()}
    fake = SimpleNamespace(conf=SimpleNamespace(beat_schedule=entries), send_task=app.send_task)
    with patch('config.celery.app', fake):
        ctx = r.Run(NOW)
        r.retry_task(ctx, 'one', beat())
        r.retry_task(ctx, 'two', beat())
        r.retry_task(r.Run(NOW + timedelta(minutes=15)), 'two', beat())
    assert isolated[0].call_count == 1


def test_stale_running_task_needs_both_cadence_and_hard_timeout(isolated):
    from config.celery import app
    fake = SimpleNamespace(conf=SimpleNamespace(beat_schedule={'task': beat()}), send_task=app.send_task,
                           tasks={beat()['task']: SimpleNamespace(time_limit=3500)})
    with patch('config.celery.app', fake):
        cache.set('heartbeat:task', pulse('running', ago=3300))
        r.retry_task(r.Run(NOW), 'task', beat())
        isolated[0].assert_not_called()
        cache.set('heartbeat:task', pulse('running', ago=4000))
        r.retry_task(r.Run(NOW), 'task', beat())
        assert isolated[0].call_count == 1


def test_heartbeat_retains_permanent_classification_without_secret(isolated):
    from news.task_heartbeat import failed
    sender = SimpleNamespace(name='scraper.tasks.import_official_task', request=SimpleNamespace(id='secret-test', args=['votings'], kwargs={}))
    error = RuntimeError('password secret-test-key')
    error.response = SimpleNamespace(status_code=402)
    failed(sender=sender, task_id='secret-test', args=['votings'], kwargs={}, exception=error)
    data = cache.get('heartbeat:sejm-votes-15m')
    assert data['repair_error'] == 'permanent'
    assert 'secret-test-key' not in str(data)
    r.retry_task(r.Run(NOW), 'sejm-votes-15m', beat())
    isolated[0].assert_not_called()


def test_tasks_use_panel_staleness_and_skip_self(isolated):
    from news.admin_status import tasks
    entries = {'stale': beat(), 'fresh': beat(), 'repairer-15m': {'task': 'news.tasks.repairer_task', 'schedule': crontab(minute='*/15')}}
    cache.set('heartbeat:stale', pulse(phase='ok', ago=1801))
    cache.set('heartbeat:fresh', pulse(phase='ok', ago=100))
    cache.set('heartbeat:repairer-15m', pulse())
    from config.celery import app
    fake = SimpleNamespace(conf=SimpleNamespace(beat_schedule=entries), send_task=app.send_task)
    with patch('config.celery.app', fake):
        r.repair_tasks(r.Run(NOW), {'sections': [tasks(NOW)]})
    assert isolated[0].call_count == 1


@pytest.mark.parametrize('phase,ago,deleted', [('error', 1700, True), ('ok', 1700, True),
    ('running', 9000, False), ('error', 100, False)])
def test_lock_timeout_and_active_pulse(phase, ago, deleted):
    entries = {'diagnose': {'task': 'news.tasks.clinic_diagnose_task'}}
    cache.set('clinic-diagnose-lock', '1')
    cache.set('unrelated-lock', '1')
    cache.set('heartbeat:diagnose', pulse(phase=phase, ago=ago))
    with patch('config.celery.app', SimpleNamespace(conf=SimpleNamespace(beat_schedule=entries))):
        r.repair_locks(r.Run(NOW, True), EMPTY)
        assert cache.get('clinic-diagnose-lock') == '1'
        r.repair_locks(r.Run(NOW), EMPTY)
    assert (cache.get('clinic-diagnose-lock') is None) == deleted
    assert cache.get('unrelated-lock') == '1'


def test_atomic_delete_rechecks_pulse_and_lease():
    cache.set('test-lock', 'old')
    cache.set('heartbeat:test', pulse())
    guards = {'heartbeat:test': cache.get('heartbeat:test')}
    cache.set('heartbeat:test', pulse('running'))
    assert not r.compare_delete('test-lock', 'old', guards)
    cache.set('test-lock', 'new')
    assert not r.compare_delete('test-lock', 'old')
    assert cache.get('test-lock') == 'new'


def test_redis_delete_is_atomic_and_compares_all_guard_bytes():
    from django.core.cache.backends.redis import RedisCache, RedisSerializer
    from unittest.mock import MagicMock
    backend = RedisCache('redis://unused', {})
    serializer = RedisSerializer()
    client = MagicMock()
    backend._cache = SimpleNamespace(get_client=lambda *a, **k: client, _serializer=serializer)
    old_pulse = pulse()
    raw = [serializer.dumps('old'), serializer.dumps(old_pulse)]
    client.mget.return_value = raw
    client.eval.return_value = 0  # Pulse changed between MGET and Lua.
    with patch.object(r, 'caches', {'default': backend}):
        assert not r.compare_delete('lock', 'old', {'heartbeat:test': old_pulse})
        assert client.eval.call_args.args[1:] == (2, ':1:lock', ':1:heartbeat:test', *raw)
        assert "redis.call('get', KEYS[i]) ~= ARGV[i]" in client.eval.call_args.args[0]
        client.eval.return_value = 1
        assert r.compare_delete('lock', 'old', {'heartbeat:test': old_pulse})
        client.mget.return_value = [None, raw[1]]
        assert not r.compare_delete('lock', 'old', {'heartbeat:test': old_pulse})


def test_fetch_reuses_audited_reaper():
    from scraper.test_fetch_reaper import approved_instruction
    from scraper.utils import _reserve_fetch_request
    source = Source.objects.create(name='Repair fetch', url='https://example.org')
    instruction = approved_instruction(source)
    request_id = uuid4()
    _reserve_fetch_request(source=source, instruction=instruction,
        requested_kind=FetchAttempt.RequestedKind.FEED, url=instruction.endpoint,
        hostname_transport=True, request_id=request_id)
    FetchRequest.objects.filter(request_id=request_id).update(reserved_at=NOW - timedelta(hours=2))
    r.repair_fetches(r.Run(NOW, True), EMPTY)
    assert FetchRequest.objects.get().state == 'reserved'
    r.repair_fetches(r.Run(NOW), EMPTY)
    assert FetchRequest.objects.get().state == 'abandoned'
    assert FetchAttempt.objects.filter(request_id=request_id, outcome='abandoned').count() == 1
    r.repair_fetches(r.Run(NOW), EMPTY)
    assert RepairAction.objects.filter(rule='fetch').count() == 1


def test_archives_backoff_attempts_quarantine_limit_and_dry_run():
    source = Source.objects.create(name='Repair archive', url='https://example.org', is_active=True, scrape_enabled=True)
    # Permanent errors at the front must not starve all later transient jobs.
    for i in range(51):
        ArchiveJob.objects.create(source=source, url=f'https://example.org/permanent{i}', kind='page',
            status='failed', attempts=2, available_at=NOW - timedelta(days=2), last_error='402')
    for i in range(55):
        ArchiveJob.objects.create(source=source, url=f'https://example.org/{i}', kind='page',
            status='failed', attempts=2, available_at=NOW - timedelta(hours=1), last_error='ConnectionError')
    for i, fields in enumerate([{'last_error': '402'}, {'status': 'quarantined'},
                               {'attempts': 5}, {'available_at': NOW + timedelta(hours=1)}]):
        data = dict(status='failed', attempts=2, available_at=NOW, last_error='Timeout')
        data.update(fields)
        ArchiveJob.objects.create(source=source, url=f'https://example.org/skip{i}', kind='page', **data)
    r.repair_archives(r.Run(NOW, True), EMPTY)
    assert not ArchiveJob.objects.filter(status='pending').exists()
    ctx = r.Run(NOW)
    r.repair_archives(ctx, EMPTY)
    assert len(ctx.actions) == 20
    assert ArchiveJob.objects.filter(status='pending').count() == 20
    assert not ArchiveJob.objects.filter(url__contains='skip', status='pending').exists()
    assert set(ArchiveJob.objects.filter(status='pending').values_list('attempts', flat=True)) == {2}
    assert set(ArchiveJob.objects.filter(status='pending').values_list('available_at', flat=True)) == {NOW - timedelta(hours=1)}


def test_importer_mapping_cadence_shared_task_budget_and_dry_run(isolated):
    row = ImportState.objects.create(name='official:votings', last_error='ConnectionError', last_success=NOW - timedelta(hours=2))
    r.repair_importers(r.Run(NOW, True), EMPTY)
    isolated[0].assert_not_called()
    r.repair_importers(r.Run(NOW), EMPTY)
    r.retry_task(r.Run(NOW), 'sejm-votes-15m', beat())
    assert isolated[0].call_count == 1
    row.last_error = '402'
    row.save()
    r.repair_importers(r.Run(NOW + timedelta(hours=3)), EMPTY)
    assert isolated[0].call_count == 1
    row.last_error, row.last_success = 'Timeout', NOW
    row.save()
    r.repair_importers(r.Run(NOW), EMPTY)
    assert isolated[0].call_count == 1


def test_interview_enabled_single_retry_content_and_dry_run():
    row = ClinicInterview.objects.create(day=NOW.date(), video_id='abcdefghijk', url='https://www.youtube.com/watch?v=abcdefghijk',
        status='failed', error='connection', transcript='keep')
    with patch('news.clinic_interview.enabled', return_value=False):
        r.repair_interviews(r.Run(NOW), EMPTY)
    row.refresh_from_db()
    assert row.status == 'failed'
    with patch('news.clinic_interview.enabled', return_value=True):
        r.repair_interviews(r.Run(NOW, True), EMPTY)
        row.refresh_from_db()
        assert row.status == 'failed'
        row.error = '402'
        row.save(update_fields=['error'])
        r.repair_interviews(r.Run(NOW), EMPTY)
        row.refresh_from_db()
        assert row.status == 'failed'
        row.error = 'connection'
        row.save(update_fields=['error'])
        r.repair_interviews(r.Run(NOW), EMPTY)
        row.refresh_from_db()
        assert (row.status, row.repair_attempts, row.transcript) == ('queued', 1, 'keep')
        row.status, row.error = 'failed', 'connection'
        row.save(update_fields=['status', 'error'])
        r.repair_interviews(r.Run(NOW), EMPTY)
        row.refresh_from_db()
        assert row.status == 'failed' and row.repair_attempts == 1


def owner_data(detail='402 secret-api-key', section='Portfele'):
    return {'sections': [], 'actions': [{'title': 'Sprawdź portfel', 'status': 'error', 'detail': detail, 'section': section}]}


def test_mail_at_eight_daily_dedup_empty_no_secrets(isolated):
    _, mail = isolated
    r.owner_digest(r.Run(NOW - timedelta(minutes=1)), owner_data())
    mail.assert_not_called()
    r.owner_digest(r.Run(NOW, True), owner_data())
    mail.assert_not_called()
    assert not RepairerState.objects.exists()
    r.owner_digest(r.Run(NOW), owner_data())
    r.owner_digest(r.Run(NOW + timedelta(hours=1)), owner_data())
    r.owner_digest(r.Run(NOW + timedelta(days=1)), owner_data())
    assert mail.call_count == 1
    assert 'secret-api-key' not in str(mail.call_args)
    different = owner_data(section='Konsylium')
    r.owner_digest(r.Run(NOW + timedelta(days=2)), different)
    assert mail.call_count == 2
    r.owner_digest(r.Run(NOW + timedelta(days=3)), EMPTY)
    assert mail.call_count == 2
    r.owner_digest(r.Run(NOW + timedelta(days=4)), different)
    assert mail.call_count == 3


def test_council_429_no_action_and_failed_mail_once_a_day(isolated):
    assert r.owner_items(owner_data('429', 'Konsylium')) == []
    _, mail = isolated
    mail.return_value = False
    r.owner_digest(r.Run(NOW), owner_data())
    r.owner_digest(r.Run(NOW), owner_data())
    assert mail.call_count == 1
    r.owner_digest(r.Run(NOW + timedelta(days=1)), owner_data())
    assert mail.call_count == 2


def test_run_flags_lock_rule_isolation_retention_and_command(monkeypatch):
    old = RepairAction.objects.create(created_at=NOW - timedelta(days=31), rule='test', target='old', result='fixed', description='test')
    def broken(ctx, data):
        raise RuntimeError('token secret_password')
    def good(ctx, data):
        ctx.record('test', 'next', 'fixed', 'OK')
    with patch('news.admin_status.snapshot', return_value=EMPTY), patch.object(r, 'RULES', (broken, good)):
        result = r.run(dry_run=True, now=NOW)
        assert [a['result'] for a in result['actions']] == ['failed', 'fixed']
        assert RepairAction.objects.count() == 1
        assert not RepairerState.objects.exists()
        result = r.run(now=NOW)
        assert not RepairAction.objects.filter(pk=old.pk).exists()
        assert 'secret_password' not in str(result)
        cache.set(r.RUN_LOCK, 'someone', 60)
        assert r.run(now=NOW)['status'] == 'locked'
        assert cache.get(r.RUN_LOCK) == 'someone'
        cache.delete(r.RUN_LOCK)
        monkeypatch.setenv('REPAIRER_ENABLED', 'false')
        assert r.run(now=NOW)['status'] == 'disabled'
        monkeypatch.setenv('REPAIRER_ENABLED', 'true')
        monkeypatch.setenv('REPAIRER_DRY_RUN', 'true')
        before = RepairAction.objects.count()
        output = StringIO()
        call_command('repairer', stdout=output)
        assert '"dry_run": true' in output.getvalue()
        assert RepairAction.objects.count() == before


def test_panel_shared_snapshot_annotation_and_heartbeat():
    from news.admin_status import snapshot
    from news.task_heartbeat import started, succeeded
    from config.celery import app
    assert r.cadence(app.conf.beat_schedule['repairer-15m']['schedule']) == 900
    sender = SimpleNamespace(name='news.tasks.repairer_task', request=SimpleNamespace(id='repair-test', args=[], kwargs={}))
    started(sender=sender, task_id='repair-test', args=[], kwargs={})
    succeeded(sender=sender, result={'status': 'ok', 'failed': 0})
    assert cache.get('heartbeat:repairer-15m')['phase'] == 'ok'
    cache.set('heartbeat:sejm-votes-15m', pulse())
    RepairAction.objects.create(created_at=NOW, rule='task', target='sejm-votes-15m', result='retried', description='test')
    data = snapshot(NOW)
    section = next(s for s in data['sections'] if s['title'] == 'Naprawiacz')
    assert any(i['title'] == 'Wymaga Ciebie' for i in section['items'])
    assert any(m == {'label': 'retried', 'value': 1} for m in section['metrics'])
    assert any('— naprawiacz ponawia' in a['title'] for a in data['actions'])


def test_public_health_and_database_failure():
    client = APIClient()
    assert client.get('/api/health/').status_code == 200
    with patch('news.views.connection.cursor', side_effect=RuntimeError('password secret')):
        response = client.get('/api/health/')
    assert response.status_code == 503
    assert response.data == {'status': 'unavailable'}


def test_global_limit_across_rules_and_second_run_lock():
    def many(ctx, data):
        for index in range(30):
            ctx.record('test', str(index), 'fixed', 'OK')
    with patch('news.admin_status.snapshot', return_value=EMPTY), patch.object(r, 'RULES', (many, many)):
        result = r.run(now=NOW)
    assert len(result['actions']) == RepairAction.objects.count() == 20
    assert cache.get(r.RUN_LOCK) is None


def test_repeated_owner_problem_does_not_consume_repair_capacity():
    first = r.Run(NOW)
    first.record('importer', 123, 'needs_owner', 'Sprawdź konfigurację.')
    second = r.Run(NOW + timedelta(minutes=15))
    second.record('importer', 123, 'needs_owner', 'Sprawdź konfigurację.')
    assert second.actions == []
    assert RepairAction.objects.count() == 1


def test_interview_url_mismatch_never_creates_another_row():
    ClinicInterview.objects.create(day=NOW.date(), video_id='abcdefghijk',
        url='https://www.youtube.com/watch?v=zyxwvutsrqp', status='failed', error='connection')
    with patch('news.clinic_interview.enabled', return_value=True):
        r.repair_interviews(r.Run(NOW), EMPTY)
    assert ClinicInterview.objects.count() == 1
    assert ClinicInterview.objects.get().status == 'failed'


def test_watchdog_recovery_cooldown_disk_and_state(tmp_path):
    """Execute bash with mocked commands; never connect to Docker or the web."""
    import os
    import shutil
    import subprocess
    from pathlib import Path

    bash = str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/usr/bin/bash.exe') if os.name == 'nt' else shutil.which('bash')
    if not bash or not Path(bash).exists():
        pytest.skip('Bash is unavailable on this test host')
    work = tmp_path.as_posix()
    script = (Path(__file__).resolve().parents[2] / 'deploy/watchdog.sh').read_text(encoding='utf-8')
    script = script.replace('/srv/spin-clinic', work).replace('/var/lib/spin-watchdog', 'state')
    watchdog = tmp_path / 'watchdog.sh'
    watchdog.write_text(script, encoding='utf-8', newline='\n')
    wrapper = tmp_path / 'test.sh'
    wrapper.write_text('''#!/usr/bin/env bash
docker() {
    case "$*" in
        *" ps -q --all "*) printf '%s\\n' "${@: -1}" ;;
        "inspect "*) [[ "${@: -1}" != "$DOWN" ]] && echo true || echo false ;;
        *) printf '%s\\n' "$*" >> "$LOG" ;;
    esac
}
curl() { [[ "$HTTP_FAIL" == 0 ]]; }
logger() { :; }
date() { echo "$NOW"; }
df() { printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n/dev/test 100 91 9 %s%% /\\n' "$DISK"; }
source "$SCRIPT"
''', encoding='utf-8', newline='\n')
    log = tmp_path / 'commands'
    def tick(now, *, fail=True, down='', disk=20):
        env = {**os.environ, 'LOG': log.as_posix(), 'SCRIPT': watchdog.as_posix(),
               'NOW': str(now), 'HTTP_FAIL': str(int(fail)), 'DOWN': down, 'DISK': str(disk)}
        result = subprocess.run([bash, wrapper.as_posix()], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        assert result.returncode == 0, result.stderr
    tick(10000, down='worker')
    tick(10300)
    assert 'up -d worker' in log.read_text()
    assert 'restart frontend backend' not in log.read_text()
    tick(10600)
    assert log.read_text().count('restart frontend backend') == 1
    for now in (10900, 11200, 11500):
        tick(now)
    assert log.read_text().count('restart frontend backend') == 1
    tick(12400)
    assert log.read_text().count('restart frontend backend') == 2
    tick(12700, fail=False, disk=91)
    assert (tmp_path / 'state/home-failures').read_text().strip() == '0'
    commands = log.read_text()
    assert 'image prune -f' in commands
    assert 'builder prune -f --filter until=168h' in commands
    assert 'volume' not in commands and 'system prune' not in commands
