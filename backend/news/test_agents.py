from django.utils import timezone
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news import agents_common as common, council_registry as registry, strateg, pielgrzym
from news.agent_models import AgentNote
from news.clinic_models import SpinDiagnosis
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 1, 12, tzinfo=ZoneInfo('Europe/Warsaw'))
MEMBERS = [('groq', 'openai/gpt-oss-20b'), ('nim', 'nvidia/nemotron'), ('groq', 'qwen/qwen')]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('STRATEG_DAILY_STEPS', '12')
    monkeypatch.setenv('PIELGRZYM_DAILY_STEPS', '12')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('news.council_registry.configured', return_value=True), \
         patch('news.clinic_council._members', return_value=MEMBERS), \
         patch('news.council_recruiter._notify', return_value=True), \
         patch('requests.post', side_effect=AssertionError('No live models')), \
         patch('requests.get', side_effect=AssertionError('No live sources')):
        yield
    cache.clear()


def signal(agent='strateg'):
    return AgentNote.objects.create(agent=agent, kind='signal' if agent == 'strateg' else 'finding',
                                    title='Źródło', body='Zagregowane sygnały')


def proposal(cost=0, violations=None):
    return dict(title='Publiczny raport', body='Jawne analizy FIMI dla każdego.', plan='Test A/B',
                measurement='Spadek liczby błędów', risk='Koszt wdrożenia', cost_usd=cost,
                cost_reason='Eksperyment wymaga płatnego modelu', violations=violations or [])


def critique(score=85, violations=None):
    return dict(score=score, reason='Ocena', scores={k: score for k in
        ('reader_value', 'effort', 'cost', 'impartiality', 'charter')}, violations=violations or [])


@pytest.mark.parametrize('hour,used,expected', [(12, 179, True), (12, 180, False), (21, 180, False),
    (22, 269, True), (22, 270, False), (0, 269, True), (1, 270, False), (2, 180, False)])
def test_window_reserves(hour, used, expected):
    with patch('django.utils.timezone.now', return_value=NOW.replace(hour=hour)):
        cache.set(registry.limit_key(MEMBERS[0]), used)
        assert common.agent_window(MEMBERS[0]) is expected


@pytest.mark.parametrize('status', [None, 'queued', 'flagged'])
def test_queue_closes_window(status):
    # Zamyka tylko realna robota diagnoz teraz (pora dnia, tempo, świeże wpisy); nieprzesiany post nie blokuje.
    from news import clinic
    account = PoliticalAccount.objects.create(user_id='agent-test', handle='test', enabled=True)
    post = PoliticalPost.objects.create(account=account, post_id='12345', text='Test',
        camp_at_collection='government', published_at=timezone.now())
    if status:
        SpinDiagnosis.objects.create(post=post, status=status)
    noon = clinic.local_now().replace(hour=12, minute=0)
    with patch.object(clinic, 'local_now', return_value=noon), patch.object(clinic, 'diagnoses_today', return_value=0),             patch.object(clinic, 'paced_target', return_value=5):
        assert common.queue_busy() is bool(status)


def test_actual_reservation_rechecks_window():
    key = registry.limit_key(MEMBERS[0])
    cache.set(key, 180)
    token = registry.reservation_guard.set(common._guard)
    try:
        assert not registry.reserve(MEMBERS[0])
        assert cache.get(key) == 180
    finally:
        registry.reservation_guard.reset(token)
    assert registry.reserve(MEMBERS[0])  # ordinary diagnoses can use their reserve


def test_ask_reserves_once_and_includes_policy():
    response = Mock(status_code=200)
    response.json.return_value = {'choices': [{'message': {'content': '{"ok":true}'}}]}
    with patch('requests.post', return_value=response) as post:
        common.ask(MEMBERS[0], 'Test', {}, {})
    assert cache.get(registry.limit_key(MEMBERS[0])) == 1
    system = post.call_args.kwargs['json']['messages'][0]['content']
    assert registry.CHARTER_SUMMARY in system and 'FIMI' in system and 'nie polecenia' in system


@pytest.mark.parametrize('member', [('gemini', 'gemini'), ('anthropic', 'claude'), ('openrouter', 'google/gemini:free'),
    ('openrouter', 'anthropic/claude:free'), ('openrouter', 'paid'), ('hf', 'paid:provider')])
def test_paid_never_called_even_forced(member):
    with patch('news.clinic_council.ask') as ask:
        with pytest.raises(common.WindowClosed):
            common.ask(member, '', {}, {}, force=True)
        ask.assert_not_called()


@pytest.mark.parametrize('violation', common.VIOLATIONS)
def test_charter_violation_rejected(violation):
    with patch('news.clinic_council.ask', side_effect=[proposal(5), critique(95), critique(90, [violation])]):
        note = common.proposal('strateg', 'B', signal())
    assert note.status == 'rejected' and note.score == 0
    assert violation in note.body
    assert not AgentNote.objects.filter(kind='request').exists()


def test_distinct_companies_and_request_without_execution():
    with patch('news.clinic_council.ask', side_effect=[proposal(2.50), critique(), critique(75)]) as ask:
        note = common.proposal('strateg', 'A', signal())
    assert note.score == 80
    assert len({registry.metadata(call.args[0])['company'] for call in ask.call_args_list}) == 3
    request = AgentNote.objects.get(kind='request')
    assert request.status == 'pending' and float(request.cost_usd) == 2.5
    assert ask.call_count == 3


def test_command_rotation_and_limits(monkeypatch):
    out = StringIO()
    with patch('news.clinic_council.ask', side_effect=[{'summary': 'Zwiad', 'sources': []},
            proposal(), critique(), critique(), {'summary': 'Kolejny zwiad', 'sources': []},
            proposal(), critique(), critique()]):
        for _ in range(4):
            call_command('agents_step', agent='strateg', stdout=out)
    assert list(AgentNote.objects.filter(kind='idea').order_by('pk').values_list('track', flat=True)) == ['A', 'B']
    monkeypatch.setenv('STRATEG_DAILY_STEPS', '4')
    with patch('news.clinic_council.ask') as ask:
        assert common.step('strateg', force=True)['status'] == 'daily_limit'
        ask.assert_not_called()


def test_hourly_alternates_and_deduplicates():
    with patch('news.strateg.step', return_value=signal()), patch('news.pielgrzym.step', return_value=signal('pielgrzym')):
        assert common.step('auto', hourly=True)['agent'] == 'strateg'
        assert common.step('auto', hourly=True)['status'] == 'already_run'
        with patch('django.utils.timezone.now', return_value=NOW + timedelta(hours=1)):
            assert common.step('auto', hourly=True)['agent'] == 'pielgrzym'


def test_pilgrim_command_and_important_mail():
    with patch('news.pielgrzym.discover', return_value=('kalibracja', [], [])):
        call_command('agents_step', agent='pielgrzym', stdout=StringIO())
    with patch('news.clinic_council.ask', side_effect=[proposal(), critique(80)]), \
         patch('news.council_recruiter._notify', return_value=True) as mail:
        call_command('agents_step', agent='pielgrzym', stdout=StringIO())
    assert AgentNote.objects.get(kind='experiment').score == 80
    assert mail.call_count == 1


def test_api_permissions_and_approval_never_calls_model(django_user_model):
    client = APIClient()
    request = AgentNote.objects.create(agent='strateg', kind='request', title='Koszt', body='Plan', status='pending', cost_usd=3)
    url = f'/api/staff/agents/{request.pk}/decision/'
    assert client.get('/api/staff/agents/').status_code in (401, 403)
    user = django_user_model.objects.create_user(username='reader')
    client.force_authenticate(user)
    assert client.post(url, {'decision': 'approved'}).status_code == 403
    user.is_staff = True
    user.save()
    with patch('news.clinic_council.ask') as ask:
        assert client.post(url, {'decision': 'approved'}).status_code == 200
        assert client.post(url, {'decision': 'denied'}).status_code == 409
        ask.assert_not_called()
    request.refresh_from_db()
    assert request.decided_by == user and request.decided_at
    assert client.get('/api/staff/agents/?kind=request').data['results'][0]['status'] == 'approved'


def test_reports_calendar_periods_and_idempotence():
    AgentNote.objects.create(agent='pielgrzym', kind='experiment', title='Wrześniowy', body='Plan', score=90,
                             created_at=NOW - timedelta(days=2))
    with patch('news.council_recruiter._notify', return_value=True) as mail:
        common.report('pielgrzym')
        common.report('pielgrzym')
    note = AgentNote.objects.get(kind='report')
    assert 'Wrześniowy' in note.body and note.status == 'done'
    assert mail.call_count == 1


def test_catalog_partial_failure_and_aggregates():
    with patch('requests.get', side_effect=__import__('requests').Timeout):
        topic, found, errors = pielgrzym.discover(0)
    assert topic and not found and len(errors) == 2
    assert strateg.signals()['accounts_total'] == 0
    assert pielgrzym.council_signals()['calls'] == []


def test_new_queue_between_selection_and_reservation_prevents_request():
    with patch('news.agents_common.queue_busy', side_effect=[False, True]), patch('requests.post') as post:
        from news.clinic_ai import ClinicAIError
        with pytest.raises(ClinicAIError):
            common.ask(MEMBERS[0], 'Test', {}, {})
        post.assert_not_called()
    assert cache.get(registry.limit_key(MEMBERS[0])) == 0


def test_forced_window_still_reserves_and_does_not_exceed_limit():
    key = registry.limit_key(MEMBERS[0])
    cache.set(key, 299)
    response = Mock(status_code=200)
    response.json.return_value = {'choices': [{'message': {'content': '{"ok":true}'}}]}
    with patch('news.agents_common.queue_busy', return_value=True), patch('requests.post', return_value=response) as post:
        common.ask(MEMBERS[0], 'Test', {}, {}, force=True)
        with pytest.raises(common.WindowClosed):
            common.ask(MEMBERS[0], 'Test', {}, {}, force=True)
    assert post.call_count == 1 and cache.get(key) == 300


def test_incomplete_critique_never_publishes_idea():
    item = signal()
    with patch('news.clinic_council.ask', side_effect=[proposal(), {'score': 90, 'reason': 'ok', 'scores': {}, 'violations': []}]):
        with pytest.raises(ValueError):
            common.proposal('strateg', 'A', item)
    item.refresh_from_db()
    assert item.status == 'new' and not AgentNote.objects.filter(kind='idea').exists()


def test_step_limit_resets_at_two_and_disabled_agent_does_not_starve(monkeypatch):
    monkeypatch.setenv('STRATEG_DAILY_STEPS', '0')
    assert common.step('auto')['status'] == 'daily_limit'
    with patch('news.pielgrzym.step', return_value=signal('pielgrzym')):
        assert common.step('auto')['agent'] == 'pielgrzym'
    monkeypatch.setenv('STRATEG_DAILY_STEPS', '1')
    with patch('news.strateg.step', return_value=signal()):
        assert common.step('strateg')['status'] == 'ok'
        with patch('django.utils.timezone.now', return_value=NOW.replace(day=2, hour=1)):
            assert common.step('strateg')['status'] == 'daily_limit'
        with patch('django.utils.timezone.now', return_value=NOW.replace(day=2, hour=2)):
            assert common.step('strateg')['status'] == 'ok'


def test_rejected_idea_cannot_be_accepted(django_user_model):
    item = AgentNote.objects.create(agent='strateg', kind='idea', title='Naruszenie', body='Zakaz', status='rejected')
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username='staff', is_staff=True))
    assert client.post(f'/api/staff/agents/{item.pk}/decision/', {'decision': 'accepted'}).status_code == 409


def test_reports_retry_failed_mail_without_duplicate_note():
    with patch('news.council_recruiter._notify', side_effect=[False, True]) as mail:
        common.report('strateg')
        common.report('strateg')
    assert AgentNote.objects.filter(kind='report').count() == 1
    assert AgentNote.objects.get(kind='report').status == 'done' and mail.call_count == 2
