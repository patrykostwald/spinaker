from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.core.management import call_command

from news import clinic, council_auditor as audit, council_health as health, inquisitor as iq, repairer
from news.clinic_models import CouncilCall, InquisitorReview, SpinDiagnosis
from news.models import RepairAction, RepairerState
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 9, 30, 21, 45, tzinfo=ZoneInfo('Europe/Warsaw'))
MEMBERS = [('groq', 'openai/gpt-oss-20b'), ('nim', 'nvidia/nemotron'), ('groq', 'qwen/qwen')]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('INQUISITOR_DAILY', '3')
    monkeypatch.setenv('INQUISITOR_AUTO_HIDE', 'false')
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('news.clinic.local_now', return_value=NOW), \
         patch('news.social_publish._mail', return_value=True) as mail, \
         patch('config.celery.app.send_task') as dispatch, \
         patch('news.council_registry.available', return_value=True), \
         patch('news.council_registry.configured', return_value=True), \
         patch('news.clinic_council._members', return_value=MEMBERS), \
         patch('news.clinic_ai.enabled', return_value=True), \
         patch('requests.post', side_effect=AssertionError('Network forbidden')):
        yield mail, dispatch
    cache.clear()


def diagnosis(camp='government', **kwargs):
    account, _ = PoliticalAccount.objects.get_or_create(user_id='audit', defaults={'handle': 'audit'})
    post = PoliticalPost.objects.create(account=account, post_id=uuid4().hex[:19],
        published_at=NOW, fetched_at=NOW, camp_at_collection=camp, text='Tekst wpisu do kontroli.')
    values = dict(status='approved', verdict='partial', intensity=40, headline='Nie zmieniać',
        diagnosed_at=NOW, provider='anthropic', created_at=NOW,
        usage={'council': {'chair': 'gemini-3.8-flash', 'agreement': '3/4', 'members': [], 'diversity': {'degraded': True}}})
    return SpinDiagnosis.objects.create(post=post, **{**values, **kwargs})


def answer(verdict='error'):
    return {**{k: k != 'quotes' or verdict == 'ok' for k in iq.CHECKS}, 'verdict': verdict, 'reason': 'Technika bez cytatu.'}


def test_failures_only_permanent():
    for error in ['council_too_few_members: 2', '429', 'ReadTimeout', 'timed out', 'gemini_daily_limit',
                  'rate_limited', 'connection', 'http_503', 'unknown', 'invalid_json', 'gemini_402', 'api_401']:
        diagnosis(status='failed', error=error)
    assert clinic.failures_today() == 3
    with patch('news.clinic_ai.enabled', return_value=True), patch('news.clinic.diagnose'):
        assert clinic.run_diagnoses(limit=0)['status'] == 'ok'


def test_bench_and_midnight_return():
    m = MEMBERS[0]
    assert health.bench(m, NOW)
    assert not health.bench(m, NOW)
    assert health.adjust_roles('CLINIC_COUNCIL', MEMBERS) == MEMBERS[1:]
    with patch('django.utils.timezone.now', return_value=NOW + timedelta(days=1)):
        assert health.adjust_roles('CLINIC_COUNCIL', MEMBERS) == MEMBERS


def test_streak_resets_on_success_and_ranking():
    for kind in ['402', 'timeout', 'ok', '429', '429']:
        CouncilCall.objects.create(provider=MEMBERS[0][0], model=MEMBERS[0][1], outcome=kind, seconds=2, created_at=NOW)
    for _ in range(3):
        CouncilCall.objects.create(provider=MEMBERS[1][0], model=MEMBERS[1][1], outcome='timeout', seconds=7, created_at=NOW)
    data = audit.run(now=NOW)
    assert not cache.get(health.bench_key(MEMBERS[0], NOW))
    assert cache.get(health.bench_key(MEMBERS[1], NOW))
    assert len([a for a in data['actions'] if a['rule'] == 'auditor:bench']) == 1
    cache.set(f'council:ranking:{NOW.date()}', {':'.join(MEMBERS[2]): 1})
    assert health.adjust_roles('CLINIC_COUNCIL_CHAIR', MEMBERS)[0] == MEMBERS[2]


def test_health_legacy_and_quality_per_camp():
    row = diagnosis(claims=[{'assessment': 'unverified'}])
    row.usage['council']['members'] = [{'provider': 'gemini', 'model': 'gemini-x', 'status': 'brak odpowiedzi', 'note': '402 SECRET'}]
    row.save(update_fields=['usage'])
    diagnosis('opposition', verdict='unclear', intensity=0)
    data = audit.observe(NOW)
    assert data['quality']['government']['unverified'] == 1
    assert data['quality']['opposition']['unclear'] == 1
    assert data['quality']['government']['degraded'] == 1
    assert 'SECRET' not in str(data)
    assert data['throughput']['government']['published'] == 1


def test_extra_diagnosis_max_once_hour_and_budget(isolated):
    diagnosis(status='queued', verdict='', diagnosed_at=None)
    with patch('news.clinic.budget_left', return_value=1):
        audit.run(now=NOW)
        audit.run(now=NOW + timedelta(minutes=1))
    assert isolated[1].call_count == 1
    cache.delete('auditor:extra-diagnosis')
    with patch('news.clinic.budget_left', return_value=0):
        audit.run(now=NOW + timedelta(hours=1))
    assert isolated[1].call_count == 1


def test_dry_run_no_writes_no_cache_no_ai(isolated):
    diagnosis()
    before = (RepairAction.objects.count(), RepairerState.objects.count())
    with patch('news.clinic_council.ask', side_effect=AssertionError('AI forbidden')):
        for name in ['council_audit', 'inquisitor']:
            out = StringIO()
            call_command(name, '--dry-run', stdout=out)
            assert 'dry_run' in out.getvalue()
    assert (RepairAction.objects.count(), RepairerState.objects.count()) == before
    assert not InquisitorReview.objects.exists()
    assert not cache.get('clinic-diagnose-lock') and not cache.get('council-audit-lock')
    assert not isolated[0].called and not isolated[1].called


def test_stratified_no_repeat_and_daily_limit():
    for camp in clinic.CAMPS:
        for _ in range(5):
            diagnosis(camp)
    rows = iq.sample(NOW, 3)
    assert {r.camp for r in rows} == set(clinic.CAMPS)
    with patch('news.clinic_council.ask', return_value=answer('ok')) as ask:
        first = iq.run(now=NOW, limit=999)
        assert len(first['reviews']) == 3 and ask.call_count == 6
        assert iq.run(now=NOW)['status'] == 'daily_limit'
    assert not {r.diagnosis_id for r in InquisitorReview.objects.all()} & {r.pk for r in iq.sample(NOW, 3)}
    camps = list(InquisitorReview.objects.values_list('camp', flat=True))
    assert sorted(camps.count(c) for c in clinic.CAMPS) == [1, 2]


def test_multiple_partial_runs_balance_camps():
    for camp in clinic.CAMPS:
        for _ in range(3):
            diagnosis(camp)
    with patch('news.clinic_council.ask', return_value=answer('ok')):
        iq.run(now=NOW, limit=1)
        iq.run(now=NOW, limit=1)
    assert set(InquisitorReview.objects.values_list('camp', flat=True)) == set(clinic.CAMPS)


@pytest.mark.parametrize('verdicts, expected', [(['ok', 'ok'], 'ok'), (['error', 'error'], 'error'),
    (['error', 'ok'], 'doubt'), (['doubt', 'error'], 'doubt'), ([], 'doubt')])
def test_combined(verdicts, expected):
    assert iq.combine([{'verdict': v} for v in verdicts]) == expected


def test_no_edits_even_unanimous_error_and_decision(isolated, django_user_model):
    row = diagnosis()
    before = SpinDiagnosis.objects.values().get(pk=row.pk)
    with patch('news.clinic_council.ask', return_value=answer()):
        iq.run(now=NOW)
    assert SpinDiagnosis.objects.values().get(pk=row.pk) == before
    review = InquisitorReview.objects.get()
    assert review.verdict == 'error'
    user = django_user_model.objects.create(username='owner', is_staff=True)
    assert iq.decide(review.pk, user, 'reject')
    row.refresh_from_db()
    assert row.status == 'rejected' and row.headline == before['headline'] and row.usage == before['usage']
    assert not iq.decide(review.pk, user, 'approve')
    assert isolated[0].called


def test_auto_hide_only_unanimous(monkeypatch):
    monkeypatch.setenv('INQUISITOR_AUTO_HIDE', 'true')
    first, second = diagnosis(), diagnosis('opposition')
    with patch('news.inquisitor.sample', return_value=[first, second]), \
         patch('news.clinic_council.ask', side_effect=[answer(), answer('ok'), answer(), answer()]):
        iq.run(now=NOW)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == 'approved' and second.status == 'pending_review'


def test_independence_and_no_paid_fallback():
    row = diagnosis()
    with patch('news.clinic_council._members', return_value=[('gemini', 'gemini-3.8-flash'),
            MEMBERS[0], ('openrouter', MEMBERS[0][1] + ':free'), MEMBERS[1]]):
        picked = iq.reviewers(row)
    assert picked == [MEMBERS[0], MEMBERS[1]]
    row.usage['council']['chair'] = MEMBERS[0][1]
    assert iq.reviewers(row) == MEMBERS[1:]


def test_daytime_priority_lock_and_invalid_answers():
    row = diagnosis()
    diagnosis(status='queued', verdict='', diagnosed_at=None)
    assert iq.run(now=NOW.replace(hour=12))['status'] == 'diagnoses_first'
    cache.set('clinic-diagnose-lock', 'diagnosis')
    assert iq.run(now=NOW)['status'] == 'locked'
    assert cache.get('clinic-diagnose-lock') == 'diagnosis'
    cache.delete('clinic-diagnose-lock')
    with patch('news.clinic_council.ask', return_value={'verdict': 'error', 'reason': 'SECRET'}):
        iq.run(now=NOW)
    assert InquisitorReview.objects.get(diagnosis=row).verdict == 'doubt'


def test_urgent_six_hours_recovery_only_reported(isolated):
    mail = isolated[0]
    def notify(now, active):
        repairer.notify_problem(repairer.Run(now), 'test', active, 'Problem', 'Automatyka', 'Działanie')
    notify(NOW, False)
    assert not mail.called
    notify(NOW, True)
    notify(NOW + timedelta(hours=5), True)
    assert mail.call_count == 1
    notify(NOW + timedelta(hours=6), True)
    assert mail.call_count == 2
    notify(NOW + timedelta(hours=6, minutes=1), False)
    notify(NOW + timedelta(hours=6, minutes=2), False)
    assert mail.call_count == 3 and 'rozwiązane' in mail.call_args.args[1]
    notify(NOW + timedelta(hours=7), True)
    assert mail.call_count == 3


def test_wallet_secret_and_recovery(isolated):
    repairer.provider_event('gemini', 'http_402 Bearer SECRET-DO-NOT-LOG')
    repairer.provider_event('gemini', '429')
    assert isolated[0].call_count == 1
    repairer.provider_event('gemini')
    assert isolated[0].call_count == 2
    assert 'rozwiązane' in isolated[0].call_args.args[1]
    assert 'SECRET' not in str(isolated[0].call_args_list)
    assert 'SECRET' not in str(list(RepairAction.objects.values()))
    assert 'SECRET' not in str(list(RepairerState.objects.values()))


def test_quorum_two_hours_and_no_night_false_recovery(isolated):
    diagnosis()
    now = NOW.replace(hour=23, minute=0)
    with patch('news.council_registry.available', return_value=False):
        repairer.operational_notifications(repairer.Run(now))
        assert not isolated[0].called
        repairer.operational_notifications(repairer.Run(now + timedelta(hours=2)))
        assert isolated[0].call_count == 1
    repairer.operational_notifications(repairer.Run(now + timedelta(hours=2, minutes=5)))
    assert 'rozwiązane' in isolated[0].call_args.args[1]


def test_model_call_timing_sanitized():
    with patch('news.clinic_council._ask', side_effect=iq.council.ClinicAIError('http_429 SECRET')), \
         patch('news.council_recruiter.record'):
        with pytest.raises(iq.council.ClinicAIError):
            iq.council.ask(MEMBERS[0], '', '', {})
    row = CouncilCall.objects.get()
    assert row.outcome == '429' and row.seconds >= 0


def test_panel_and_week_findings():
    row = diagnosis()
    InquisitorReview.objects.create(diagnosis=row, created_at=NOW, camp=row.camp, answers=[answer()], verdict='error')
    panel = audit.panel_section(NOW + timedelta(seconds=1))
    inbox = next(c for c in panel['items'] if c['title'] == 'Do decyzji właściciela')
    assert '/inquisitorreview/' in inbox['items'][0]['href']
    findings = iq.findings(NOW - timedelta(days=7), NOW + timedelta(seconds=1))
    assert findings[0]['issues'] == {'quotes': 1}


def test_watchdog_cannot_clear_inquisitor_lease():
    cache.set('clinic-diagnose-lock', 'inquisitor:active')
    cache.set('heartbeat:clinic-diagnoses-day', {'phase': 'ok', 'last_event': (NOW - timedelta(hours=2)).isoformat()})
    repairer.repair_locks(repairer.Run(NOW), {})
    assert cache.get('clinic-diagnose-lock') == 'inquisitor:active'


def test_stalled_diagnoses_and_x_recovery_not_at_night(isolated):
    row = diagnosis(status='queued', verdict='', diagnosed_at=None, created_at=NOW - timedelta(hours=4))
    PoliticalPost.objects.filter(pk=row.post_id).update(fetched_at=NOW - timedelta(hours=3))
    repairer.operational_notifications(repairer.Run(NOW))
    assert isolated[0].call_count == 2
    repairer.operational_notifications(repairer.Run(NOW + timedelta(hours=3)))
    assert isolated[0].call_count == 2
    next_morning = (NOW + timedelta(days=1)).replace(hour=7, minute=0)
    repairer.operational_notifications(repairer.Run(next_morning))
    assert isolated[0].call_count == 2
    row.status, row.verdict, row.diagnosed_at = 'approved', 'no_spin', next_morning
    row.save(update_fields=['status', 'verdict', 'diagnosed_at'])
    PoliticalPost.objects.filter(pk=row.post_id).update(fetched_at=next_morning)
    repairer.operational_notifications(repairer.Run(next_morning))
    assert isolated[0].call_count == 4
    assert all('rozwiązane' in call.args[1] for call in isolated[0].call_args_list[2:])


def test_admin_owner_decision_buttons(client, django_user_model):
    owner = django_user_model.objects.create_superuser(username='owner', password='test')
    client.force_login(owner)
    row = diagnosis()
    review = InquisitorReview.objects.create(diagnosis=row, camp=row.camp, verdict='error')
    url = f'/admin/news/inquisitorreview/{review.pk}/change/'
    response = client.get(url)
    assert response.status_code == 200 and b'_inquisitor_reject' in response.content
    response = client.post(url, {'_inquisitor_reject': '1'})
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.status == 'rejected' and row.headline == 'Nie zmieniać'


def test_limit_after_failed_calls_no_repeat():
    diagnosis()
    with patch('news.clinic_council.ask', side_effect=iq.council.ClinicAIError('429')) as ask:
        iq.run(now=NOW)
        iq.run(now=NOW)
    assert ask.call_count == 2 and InquisitorReview.objects.count() == 1


def test_schema_cannot_convert_missing_evidence_to_unanimous_error():
    contradictory = {**{k: True for k in iq.CHECKS}, 'verdict': 'error', 'reason': 'brak uzasadnienia'}
    assert iq.validate(contradictory)['verdict'] == 'doubt'


def test_durable_quota_without_cache_lease():
    for _ in range(3):
        row = diagnosis()
        assert iq.reserve_review(row, MEMBERS[:2], NOW, 3)
    cache.clear()
    assert iq.reserve_review(diagnosis(), MEMBERS[:2], NOW, 3) is None
    assert InquisitorReview.objects.count() == 3


def test_run_history_allowlist_and_bound():
    for _ in range(15):
        health.record_run({'status': 'budget', 'spent_today_usd': 2, 'error': 'Bearer SECRET', 'raw': 'SECRET'})
    runs = RepairerState.objects.get(key='diagnosis-runs').data['runs']
    assert len(runs) == 12 and all(r['status'] == 'budget' for r in runs)
    assert 'SECRET' not in str(runs)


def test_legacy_wallet_failure_is_adopted_and_only_success_resolves(isolated):
    from news.clinic_models import CouncilSeat
    diagnosis()
    CouncilSeat.objects.create(provider='gemini', model='gemini-x', last_error='http_402 SECRET')
    repairer.operational_notifications(repairer.Run(NOW))
    assert isolated[0].call_count == 1
    repairer.provider_event('gemini')
    assert isolated[0].call_count == 2
    repairer.operational_notifications(repairer.Run(NOW))
    assert isolated[0].call_count == 2
