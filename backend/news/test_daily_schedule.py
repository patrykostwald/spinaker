from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news import daily_schedule as schedule, rescuer, clinic, clinic_ai, schedule_health
from news.clinic_models import ClinicDailyMessage, ClinicInterview, SpinDiagnosis, WeeklyReport
from news.models import DutyAlarm, RepairAction, RepairerState, Thread
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 4, 22, 30, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for name in ('X_POLITICAL_POLLING_ENABLED', 'CLINIC_INTERVIEW_ENABLED', 'DR_SPIN_THREADS_ENABLED',
                 'DUTY_ENABLED', 'REPAIRER_ENABLED'):
        monkeypatch.setenv(name, 'true')
    monkeypatch.setenv('CLINIC_DAILY_BUDGET_USD', '5')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('Bez prawdziwego HTTP')), \
         patch('news.social_publish._mail', return_value=True) as mail, \
         patch('news.push_events._enqueue_staff') as push, \
         patch('config.celery.app.send_task') as send:
        yield SimpleNamespace(mail=mail, push=push, send=send)
    cache.clear()


def post(camp='government', account=None, **fields):
    n = PoliticalPost.objects.count() + 1
    account = account or PoliticalAccount.objects.create(user_id=str(n), handle='konto' + str(n), camp=camp, enabled=True)
    return PoliticalPost.objects.create(account=account, post_id=str(n), text='Na program edukacyjny przeznaczono 20 mln zł.',
        camp_at_collection=camp, published_at=NOW - timedelta(hours=2),
        fetched_at=fields.pop('fetched_at', NOW - timedelta(hours=1)), **fields)


def diagnosis(**fields):
    return SpinDiagnosis.objects.create(post=post(), **fields)


def milestone(key):
    return next(m for m in schedule.MILESTONES if m.key == key)


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_poll(state, monkeypatch):
    monkeypatch.setenv('X_POLITICAL_POLLING_ENABLED', str(state != 'na').lower())
    if state == 'done':
        RepairerState.objects.create(key='pulse:political-x-minute', data={'last_success': (NOW - timedelta(minutes=9)).isoformat()})
    assert schedule.check_poll(NOW)[0] == state


def test_poll_uses_success_not_last_event_and_night_window():
    night = NOW.replace(hour=2)
    row = RepairerState.objects.create(key='pulse:political-x-minute', data={
        'last_event': night.isoformat(), 'last_success': (night - timedelta(minutes=119)).isoformat()})
    assert schedule.check_poll(night)[0] == 'done'
    assert schedule.check_poll(night + timedelta(minutes=2))[0] == 'late'
    row.data = {'last_event': NOW.isoformat(), 'last_success': (NOW - timedelta(minutes=11)).isoformat()}
    row.save()
    assert schedule.check_poll(NOW)[0] == 'late'


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_screen(state):
    if state != 'na':
        p = post()
        if state == 'done':
            SpinDiagnosis.objects.create(post=p, status='not_applicable')
    assert schedule.check_screen(NOW)[0] == state


def test_screen_uses_fetch_time():
    post(fetched_at=NOW - timedelta(minutes=29))
    assert schedule.check_screen(NOW)[0] == 'done'
    assert schedule.check_screen(NOW + timedelta(minutes=2))[0] == 'late'


@pytest.mark.parametrize('state', ['done', 'late', 'na', 'budget'])
def test_diagnoses(state):
    if state == 'done':
        diagnosis(status='approved', diagnosed_at=NOW, verdict='spin')
    elif state != 'na':
        diagnosis(status='queued', screen_score=80)
    with patch('news.clinic.budget_left', return_value=0 if state == 'budget' else 5):
        assert schedule.check_diagnoses(NOW)[0] == state


def test_diagnosis_before_deadline_and_previous_day():
    diagnosis(status='queued', screen_score=80)
    diagnosis(status='approved', diagnosed_at=NOW - timedelta(days=1), verdict='spin')
    early = NOW.replace(hour=9)
    with patch('news.clinic.budget_left', return_value=5):
        # Kandydat musi być dostępny w chwili kontroli.
        PoliticalPost.objects.update(published_at=early - timedelta(hours=1))
        assert schedule.check_diagnoses(early)[0] == 'running'
        assert schedule.check_diagnoses(early.replace(hour=10))[0] == 'late'


def test_failed_diagnosis_remains_due_and_requeue_preserves_snapshot():
    row = diagnosis(status='failed', error='timeout', screen_score=85, diagnosed_at=NOW,
                    usage={'snapshot': {'headline': 'Zapisany wynik'}})
    assert schedule.check_diagnoses(NOW)[0] == 'late'
    with patch('news.tasks.clinic_diagnose_task.apply') as run:
        rescuer.apply_remedy(milestone('diagnoses'), 'diagnoses')
    run.assert_called_once()
    row.refresh_from_db()
    assert row.status == 'queued' and row.usage['snapshot']['headline'] == 'Zapisany wynik'


def test_diagnosis_permanent_failure_is_not_requeued():
    row = diagnosis(status='failed', error='http_401', diagnosed_at=NOW)
    rescuer.requeue_diagnosis()
    row.refresh_from_db()
    assert row.status == 'failed'


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_interview(state, monkeypatch):
    monkeypatch.setenv('CLINIC_INTERVIEW_ENABLED', str(state != 'na').lower())
    if state == 'done':
        ClinicInterview.objects.create(day=NOW.date() - timedelta(days=1), video_id='wywiad', status='pending_review', diagnosed_at=NOW)
    assert schedule.check_interview(NOW)[0] == state


def test_interview_two_deadlines_and_pending_review():
    assert schedule.check_interview(NOW.replace(hour=7))[0] == 'waiting'
    assert schedule.check_interview(NOW.replace(hour=8))[0] == 'late'
    row = ClinicInterview.objects.create(day=NOW.date() - timedelta(days=1), video_id='test', status='flagged')
    assert schedule.check_interview(NOW.replace(hour=8))[0] == 'running'
    assert schedule.check_interview(NOW.replace(hour=18))[0] == 'late'
    row.status = 'pending_review'
    row.save()
    assert schedule.check_interview(NOW)[0] == 'done'
    row.hidden_at = NOW
    row.save()
    assert schedule.check_interview(NOW)[0] == 'late'


@pytest.mark.parametrize('camp', clinic.CAMPS)
@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_messages(camp, state):
    for _ in range(2 if state == 'na' else 3):
        post(camp)
    if state == 'done':
        ClinicDailyMessage.objects.create(day=NOW.date(), camp=camp, message='Przekaz', status='pending_review')
    assert schedule.check_message(camp, NOW)[0] == state


def test_message_accounts_not_post_count_and_final_check():
    p = post()
    post(account=p.account)
    post(account=p.account)
    assert schedule.check_message('government', NOW)[0] == 'na'
    post(); post()
    assert schedule.check_message('government', NOW.replace(hour=12, minute=29))[0] == 'waiting'
    assert schedule.check_message('government', NOW.replace(hour=12, minute=30))[0] == 'late'
    assert '22:15' in schedule.check_message('government', NOW)[1]['detail']


def test_message_one_busy_account_does_not_hide_two_other_accounts():
    first = post()
    for _ in range(65):
        post(account=first.account)
    post(); post()
    assert len({p.account_id for p in clinic.message_posts(NOW.date(), 'government')}) == 3
    assert schedule.check_message('government', NOW)[0] == 'late'


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_publication(state):
    if state != 'na':
        diagnosis(status='approved', diagnosed_at=NOW, verdict='spin', intensity=90,
                  x_posted_at=NOW if state == 'done' else None)
    assert schedule.check_publication(NOW)[0] == state


def test_publication_excludes_hidden_and_unapproved():
    row = diagnosis(status='pending_review', diagnosed_at=NOW, verdict='spin', intensity=90)
    assert schedule.check_publication(NOW)[0] == 'na'
    row.status, row.hidden_at = 'approved', NOW
    row.save()
    assert schedule.check_publication(NOW)[0] == 'na'


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_thread(state):
    if state == 'done':
        from news.thread_review import authoring
        token = authoring.set(True)  # a thread that already passed the publication review
        try:
            Thread.objects.create(slug=f'dr-spin-kontekst-{NOW.date()}', title='Kontekst', published=True)
        finally:
            authoring.reset(token)
    with patch('news.clinic.spin_of_day_by_camp', return_value={'order': ['government'], 'spins': {'government': {'id': 1}}}), \
         patch('news.dr_spin_threads._candidates', return_value=[] if state == 'na' else [1, 2, 3]):
        assert schedule.check_thread(NOW)[0] == state


@pytest.mark.parametrize('state', ['done', 'late', 'na'])
def test_weekly(state):
    if state == 'done':
        WeeklyReport.objects.create(week_start=NOW.date() - timedelta(days=6), week_end=NOW.date(), summary='Raport.')
    assert schedule.check_weekly(NOW - timedelta(days=1) if state == 'na' else NOW)[0] == state


def test_empty_weekly_summary_is_not_done():
    WeeklyReport.objects.create(week_start=NOW.date() - timedelta(days=6), week_end=NOW.date(), summary='')
    assert schedule.check_weekly(NOW)[0] == 'late'


def test_warsaw_midnight_and_dst():
    utc = datetime(2026, 10, 25, 23, 15, tzinfo=ZoneInfo('UTC'))
    assert schedule.bounds(utc)[0].date().isoformat() == '2026-10-26'
    assert schedule.at(utc, 10).hour == 10
    assert schedule.bounds(datetime(2026, 3, 29, 12, tzinfo=schedule.WARSAW))[0].utcoffset() == timedelta(hours=1)


def test_rescuer_order_spacing_limit_and_mail_once(isolated):
    item = replace(milestone('interview'), check=lambda now: schedule.result('late', 'Brak wywiadu.'))
    for number in range(3):
        now = NOW + timedelta(minutes=15 * number)
        rescuer.guard(now, items=(item,))
        args = isolated.send.call_args.kwargs['args']
        assert rescuer.state_data(item.key, now)['attempts'][-1]['remedy'] == item.remedies[number]
        rescuer.finish(args[1], args[2], 'failed', 'Błąd kontrolowany.')
        rescuer.guard(now + timedelta(minutes=14), items=(item,))
        assert isolated.send.call_count == number + 1
    for minute in (45, 60, 75):
        rescuer.guard(NOW + timedelta(minutes=minute), items=(item,))
    assert isolated.send.call_count == 3
    isolated.mail.assert_called_once()
    assert isolated.mail.call_args.kwargs['important'] is True
    isolated.push.assert_called_once()
    assert DutyAlarm.objects.get(key='schedule:interview').severity == 'critical'
    assert RepairAction.objects.filter(rule='schedule:proposal').count() == 1
    assert 'Błąd kontrolowany' in rescuer.state_data(item.key, NOW)['repairer_request']
    # Kolejna data w Warszawie ma własny limit.
    rescuer.guard(NOW + timedelta(days=1), items=(item,))
    assert isolated.send.call_count == 4


def test_rescuer_worker_loss_lease_and_broker_failure(isolated):
    item = replace(milestone('screen'), check=lambda now: schedule.result('late', 'Brak oceny.'))
    rescuer.guard(NOW, items=(item,))
    rescuer.guard(NOW + timedelta(minutes=15), items=(item,))
    assert isolated.send.call_count == 1
    isolated.send.side_effect = RuntimeError('sekretny token')
    rescuer.guard(NOW + timedelta(minutes=40), items=(item,))
    attempts = rescuer.state_data('screen', NOW)['attempts']
    assert len(attempts) == 2 and all(a['status'] == 'failed' for a in attempts)
    assert 'sekretny' not in str(attempts)


def test_recovery_closes_alarm_and_budget_never_repaired(isolated):
    check = Mock(return_value=schedule.result('late', 'Brak diagnozy.'))
    item = replace(milestone('diagnoses'), check=check)
    rescuer.guard(NOW, items=(item,))
    check.return_value = schedule.result('budget', 'Budżet wyczerpany.')
    rescuer.guard(NOW + timedelta(minutes=60), items=(item,))
    assert DutyAlarm.objects.get(key='schedule:diagnoses').status == 'closed'
    assert isolated.send.call_count == 1
    check.return_value = schedule.result('done', 'Gotowe.')
    rescuer.guard(NOW + timedelta(minutes=75), items=(item,))
    isolated.mail.assert_not_called()


def test_failed_check_preserves_alarm_and_never_dispatches(isolated):
    check = Mock(return_value=schedule.result('late', 'Brak.'))
    item = replace(milestone('screen'), check=check)
    rescuer.guard(NOW, items=(item,))
    check.side_effect = ValueError('sekret')
    rescuer.guard(NOW + timedelta(hours=1), items=(item,))
    assert DutyAlarm.objects.get(key='schedule:screen').status == 'open'
    assert DutyAlarm.objects.get(key='schedule-check:screen').status == 'open'
    assert isolated.send.call_count == 1


def test_duplicate_worker_does_not_repeat_remedy(isolated):
    check = Mock(return_value=schedule.result('late', 'Brak.'))
    item = replace(milestone('screen'), check=check)
    rescuer.guard(NOW, items=(item,))
    args = isolated.send.call_args.kwargs['args']
    with patch.object(schedule, 'MILESTONES', (item,)), patch.object(rescuer, 'apply_remedy', return_value={'status': 'error'}) as apply:
        rescuer.execute(*args)
        rescuer.execute(*args)
    apply.assert_called_once()


def test_rescuer_does_not_execute_yesterdays_message(isolated):
    item = replace(milestone('message-government'), check=lambda now: schedule.result('late', 'Brak.'))
    rescuer.guard(NOW - timedelta(days=1), items=(item,))
    with patch.object(rescuer, 'apply_remedy') as apply:
        assert rescuer.execute(*isolated.send.call_args.kwargs['args'])['status'] == 'expired'
    apply.assert_not_called()


@pytest.mark.parametrize('remedy,next_candidate', [('interview_run', None), ('interview_pick', False), ('interview_next', True)])
def test_interview_remedies(remedy, next_candidate):
    with patch('news.clinic_interview.release_stuck') as release, patch('news.clinic_interview.pick_yesterday') as pick, \
         patch('news.tasks.clinic_interview_task.apply') as run:
        rescuer.apply_remedy(milestone('interview'), remedy)
        release.assert_called_once()
        run.assert_called_once()
        if next_candidate is None:
            pick.assert_not_called()
        else:
            pick.assert_called_once_with(next_candidate=next_candidate)


def test_publication_dispatches_both_channels():
    with patch('news.tasks.x_publish_task.apply') as x, patch('news.tasks.social_publish_task.apply') as social:
        rescuer.apply_remedy(milestone('publication'), 'publication')
        x.assert_called_once(); social.assert_called_once()


@pytest.mark.parametrize('remedy,index', [('message_free', 0), ('message_backup', 1), ('message_paid', 2)])
def test_message_remedies_are_explicit_and_only_missing(remedy, index):
    with patch('news.clinic.run_daily_messages') as run:
        rescuer.apply_remedy(milestone('message-opposition'), remedy)
    assert run.call_args.kwargs == {'day': NOW.date(), 'camps': ('opposition',),
                                   'models': (clinic_ai.DAILY_MESSAGE_MODELS[index],), 'only_missing': True}


def test_paid_reservation_survives_errors_and_cache_clear(settings):
    from news.daily_message_fallback import reserve
    settings.DAILY_MESSAGE_PAID_FALLBACK_USD = '.03'
    assert str(reserve(1000)) == '0.013500'
    cache.clear()
    reserve(1000)
    with pytest.raises(clinic_ai.ClinicAIError, match='daily_message_paid_budget'):
        reserve(1000)
    assert RepairerState.objects.get(key='message-paid:2026-10-04').data['calls'] == 2


@pytest.mark.parametrize('limit', ['0', '-1', 'NaN', 'Infinity', 'niewłaściwy'])
def test_paid_invalid_or_zero_limit_blocks(limit, settings):
    from news.daily_message_fallback import reserve
    settings.DAILY_MESSAGE_PAID_FALLBACK_USD = limit
    with pytest.raises(clinic_ai.ClinicAIError):
        reserve(1000)


def test_paid_call_has_no_retry_and_retains_reservation(monkeypatch):
    from news.daily_message_fallback import generate
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    count = SimpleNamespace(status_code=200, json=lambda: {'totalTokens': 1000})
    with patch('requests.post', side_effect=[count, SimpleNamespace(status_code=503)]) as call:
        with pytest.raises(clinic_ai.ClinicAIError, match='gemini_503'):
            generate('Instrukcja', 'Dane', {})
    assert call.call_count == 2
    assert call.call_args.kwargs['json']['generationConfig']['thinkingConfig'] == {'thinkingBudget': 0}
    assert RepairerState.objects.get(key='message-paid:2026-10-04').data['calls'] == 1


def test_paid_success_and_limit_before_generate(monkeypatch, settings):
    from news.daily_message_fallback import generate
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    count = SimpleNamespace(status_code=200, json=lambda: {'totalTokens': 1000})
    answer = SimpleNamespace(status_code=200, json=lambda: {'candidates': [{'finishReason': 'STOP', 'content': {
        'parts': [{'text': '{"message": "Przekaz po polsku", "themes": []}'}]}}]})
    with patch('requests.post', side_effect=[count, answer]) as call:
        data, usage = generate('Instrukcja', 'Dane', {})
    assert data['message'] == 'Przekaz po polsku' and usage['paid_fallback'] is True
    assert call.call_count == 2
    settings.DAILY_MESSAGE_PAID_FALLBACK_USD = '0'
    with patch('requests.post', return_value=count) as call:
        with pytest.raises(clinic_ai.ClinicAIError, match='daily_message_paid_budget'):
            generate('Instrukcja', 'Dane', {})
    assert call.call_count == 1 and call.call_args.args[0].endswith(':countTokens')


def test_normal_messages_never_use_paid_model():
    with patch.object(clinic_ai, '_free_chat', side_effect=clinic_ai.ClinicAIError('free_models_unavailable')) as free, \
         patch('news.daily_message_fallback.generate') as paid:
        with pytest.raises(clinic_ai.ClinicAIError):
            clinic_ai.daily_message('Opozycja', str(NOW.date()), [
                {'author': 'Autor testowy', 'text': 'Na program edukacyjny przeznaczono 20 mln zł.'}])
    assert free.call_count == 2
    paid.assert_not_called()


def test_health_cooldown_failures_and_recovery():
    now = NOW.replace(hour=18, minute=5)
    for name in ('duty-15m', 'clinic-screen-5m'):
        RepairerState.objects.create(key='pulse:' + name, data={'last_event': now.isoformat()})
    with patch.object(schedule_health, 'probe', return_value=('warning', 'Brak odpowiedzi.')) as probe, \
         patch('shutil.disk_usage', return_value=SimpleNamespace(free=9, total=100)):
        schedule_health.run(now)
        schedule_health.run(now + timedelta(hours=5))
    assert probe.call_count == 5
    assert DutyAlarm.objects.filter(key__startswith='health:', status='open').count() == 6
    with patch.object(schedule_health, 'probe', return_value=('ok', 'Klucz odpowiada.')), \
         patch('shutil.disk_usage', return_value=SimpleNamespace(free=11, total=100)):
        schedule_health.run(now + timedelta(hours=6))
    assert DutyAlarm.objects.filter(key='health:disk').get().status == 'closed'
    assert DutyAlarm.objects.get(key='health:beat').status == 'open'


@pytest.mark.parametrize('provider', ['x', 'x-read', 'gemini', 'anthropic', 'groq'])
def test_health_uses_metadata_only(provider, monkeypatch):
    from news.x_publish import KEYS
    for key in (*KEYS, 'X_POLITICAL_BEARER_TOKEN', 'GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'GROQ_API_KEY'):
        monkeypatch.setenv(key, 'test-key')
    with patch('requests.get', return_value=SimpleNamespace(status_code=200)) as get:
        assert schedule_health.probe(provider)[0] == 'ok'
    assert get.call_args.args[0].endswith({'x': '/users/me', 'x-read': '/usage/tweets'}.get(provider, '/models'))


def test_panel_staff_only_and_no_network(django_user_model):
    client = APIClient()
    assert client.get('/api/staff/daily-schedule/').status_code in (401, 403)
    user = django_user_model.objects.create_user(username='osoba', password='test')
    client.force_authenticate(user)
    assert client.get('/api/staff/daily-schedule/').status_code == 403
    user.is_staff = True
    user.save()
    response = client.get('/api/staff/daily-schedule/')
    assert response.status_code == 200
    assert len(response.data['results']) == len(schedule.MILESTONES)
    assert 'no-store' in response['Cache-Control']


def test_beat_and_milestones_share_schedule():
    from config.celery import app
    for name, entry in schedule.beat_entries().items():
        assert app.conf.beat_schedule[name] == entry


def test_repairer_run_proposes_without_production_changes(isolated):
    from news import repairer
    def rule(ctx, snapshot):
        ctx.apply('test', 'cel', lambda: pytest.fail('Zmiana produkcji'), 'fixed', 'Naprawa.')
    with patch('news.admin_status.snapshot', return_value={}), patch.object(repairer, 'RULES', (rule,)):
        result = repairer.run(now=NOW)
    assert result['analysis_only'] is True
    assert RepairAction.objects.get().result == 'needs_owner'
    isolated.send.assert_not_called()


def test_screen_retries_unscored_flagged_and_old_posts():
    p = post()
    PoliticalPost.objects.filter(pk=p.pk).update(published_at=NOW - timedelta(days=5))
    row = SpinDiagnosis.objects.create(post=p, status='flagged', triage={'reason': 'Brak modelu.'})
    assert schedule.check_screen(NOW)[0] == 'late'
    with patch.object(clinic_ai, 'screen', return_value={'score': 50, 'provider': 'groq', 'model': 'test'}), \
         patch.object(clinic, 'send_review_alert', return_value='nothing'):
        clinic.run_screening(include_old=True)
    row.refresh_from_db()
    assert row.screen_score == 50 and row.status == 'flagged'
    assert schedule.check_screen(NOW)[0] == 'done'


def test_poll_durable_pulse_survives_cache_restart_and_failed_budget():
    from news import task_heartbeat
    sender = SimpleNamespace(name='news.tasks.political_poll_task', request=SimpleNamespace(id='1', args=(), kwargs={}))
    task_heartbeat.succeeded(sender=sender, result={'status': 'idle'})
    assert schedule.check_poll(NOW)[0] == 'done'
    cache.clear()
    later = NOW + timedelta(minutes=11)
    with patch('django.utils.timezone.now', return_value=later):
        task_heartbeat.succeeded(sender=sender, result={'status': 'budget_limit'})
    assert schedule.pulse('political-x-minute')['last_success'] == NOW.isoformat()
    assert schedule.check_poll(later)[0] == 'late'


def test_interview_next_skips_transient_failed_candidate(monkeypatch):
    from news import clinic_interview
    row = ClinicInterview.objects.create(day=NOW.date() - timedelta(days=1), video_id='pierwszy', status='failed', error='timeout')
    with patch.object(clinic_interview, 'enabled', return_value=True), \
         patch.object(clinic_interview, 'find_loudest_interview', return_value=None) as find:
        assert clinic_interview.pick_yesterday(next_candidate=True)['status'] == 'none_found'
    assert row.video_id in find.call_args.kwargs['exclude']
    row.refresh_from_db()
    assert row.status == 'failed'


def test_interview_rescue_processes_yesterday_before_old_queue():
    from news import clinic_interview
    ClinicInterview.objects.create(day=NOW.date() - timedelta(days=2), video_id='stary', status='queued')
    row = ClinicInterview.objects.create(day=NOW.date() - timedelta(days=1), video_id='wczoraj', status='queued')
    with patch.object(clinic_interview, 'enabled', return_value=True), \
         patch.object(clinic_interview, 'process') as process:
        clinic_interview.run_interviews(day=NOW.date() - timedelta(days=1))
    assert process.call_args.args[0].pk == row.pk


def test_message_remedy_preserves_completed_and_manual_review():
    for _ in range(3):
        post()
    row = ClinicDailyMessage.objects.create(day=NOW.date(), camp='government', message='Gotowy przekaz.', status='approved')
    with patch.object(clinic_ai, 'daily_message') as model:
        clinic.run_daily_messages(NOW.date(), camps=('government',), only_missing=True,
                                  models=(clinic_ai.DAILY_MESSAGE_MODELS[-1],))
    model.assert_not_called()
    row.refresh_from_db()
    assert row.message == 'Gotowy przekaz.'


def test_message_locks_are_separate_for_each_camp():
    cache.set(f'clinic-message:{NOW.date()}:government', 'inny-worker', 900)
    for camp in clinic.CAMPS:
        for _ in range(3):
            post(camp)
    with patch.object(clinic_ai, 'daily_message', return_value={'message': 'Przekaz.', 'themes': [], 'usage': {}}):
        result = clinic.run_daily_messages(NOW.date())
    assert set(result['created']) == {'opposition'}
    assert cache.get(f'clinic-message:{NOW.date()}:government') == 'inny-worker'


def test_third_failure_escalates_immediately_and_smtp_failure_not_repeated(isolated):
    isolated.mail.return_value = False
    item = replace(milestone('screen'), check=lambda now: schedule.result('late', 'Brak oceny.'))
    for minute in (-30, -15):
        rescuer.guard(NOW + timedelta(minutes=minute), items=(item,))
        _, stored, token = isolated.send.call_args.kwargs['args']
        rescuer.finish(stored, token, 'failed', 'Błąd próby.')
    rescuer.guard(NOW, items=(item,))
    with patch.object(schedule, 'MILESTONES', (item,)), patch.object(rescuer, 'apply_remedy', return_value={'status': 'error'}):
        rescuer.execute(*isolated.send.call_args.kwargs['args'])
    assert DutyAlarm.objects.get(key='schedule:screen').severity == 'critical'
    rescuer.guard(NOW + timedelta(minutes=20), items=(item,))
    isolated.mail.assert_called_once()
    assert 'Nie wysłano' in rescuer.state_data('screen', NOW)['mail']
