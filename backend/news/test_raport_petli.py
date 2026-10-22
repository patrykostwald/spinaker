"""Raport pętli (audyt 5.10, punkt 5.1): kontrakty, stan pętli, tekst, mail raz dziennie, endpoint panelu."""
import json
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news import raport_petli
from news.agent_models import AgentNote
from news.models import RepairerState

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 7, 5, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    for name in ('LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL', 'X_POST_ALERT_EMAIL'):
        monkeypatch.delenv(name, raising=False)
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.post', side_effect=AssertionError('Bez sieci')), \
         patch('requests.get', side_effect=AssertionError('Bez sieci')):
        yield
    cache.clear()


def note(agent='strateg', kind='idea', days=0, **fields):
    row = AgentNote.objects.create(agent=agent, kind=kind, title=fields.pop('title', f'{agent} {kind}'), body='b', **fields)
    AgentNote.objects.filter(pk=row.pk).update(created_at=NOW - timedelta(days=days))
    return row


def loop(report, key):
    return next(l for c in report['categories'] for l in c['loops'] if l['key'] == key)


def test_contracts_cover_every_note_producer_and_are_complete():
    from config.celery import app
    from news import agent_registry
    agents = {v for v, _ in AgentNote._meta.get_field('agent').choices}
    covered = {a for c in raport_petli.CONTRACTS for a in c['agents']}
    assert agents <= covered, f'Agenci bez kontraktu pętli: {agents - covered}'
    categories = {k for k, _ in raport_petli.CATEGORIES}
    for c in raport_petli.CONTRACTS:
        assert c['consumer'] in raport_petli.CONSUMERS, c['key']
        assert c['category'] in categories and c['cadence_h'] > 0 and c['sla_days'] > 0
        assert c['registry'] in agent_registry.REGISTRY or (not c['registry'] and not c['beats']), c['key']  # krok człowieka bez zadania
        assert all(b in app.conf.beat_schedule for b in c['beats']), c['key']
    assert len(raport_petli.BY_KEY) == len(raport_petli.CONTRACTS)


def test_beat_plan_has_daily_report():
    from news.daily_schedule import BEAT_PLAN
    assert BEAT_PLAN['raport-petli-daily'] == ('raport_petli_task', {'hour': 7, 'minute': 5})


def test_states_ok_warn_bad_idle(monkeypatch):
    note('strateg', days=0, score=80, title='Najlepszy pomysł')
    note('strateg', days=10)  # czeka ponad SLA 7 dni
    note('automatyk', 'audit', days=0)
    RepairerState.objects.create(key='pulse:recenzent-2h', data={'result': 'error', 'consecutive_errors': 4,
                                                                 'started_at': NOW.isoformat(), 'repair_hint': 'TransactionManagementError'})
    monkeypatch.setenv('X_POLITICAL_POLLING_ENABLED', 'false')
    report = raport_petli.build(NOW)
    strateg = loop(report, 'strateg')
    assert strateg['state'] == 'warn' and strateg['pending'] == 1 and 'czeka dłużej niż 7 dni' in strateg['reason']
    assert strateg['outputs_24h'] == 1 and strateg['outputs_7d'] == 1
    assert strateg['top'][0]['title'] == 'Najlepszy pomysł' and report['top'][0]['score'] == 80
    assert loop(report, 'automatyk')['state'] == 'ok' and loop(report, 'automatyk')['reason'] == ''
    rec = loop(report, 'recenzent')
    assert rec['state'] == 'bad' and 'błąd (4 z rzędu)' in rec['reason']
    assert loop(report, 'zbieracz-x')['state'] == 'idle'
    assert loop(report, 'kartograf')['state'] == 'bad' and 'brak wyniku' in loop(report, 'kartograf')['reason']
    assert sum(report['summary'].values()) == len(raport_petli.CONTRACTS)


def test_automatyk_fresh_output_is_ok():
    note('automatyk', 'audit', days=0)
    assert loop(raport_petli.build(NOW), 'automatyk')['state'] == 'ok'


def test_waiting_only_pulse_is_warning():
    note('projektant', 'report', days=2)
    RepairerState.objects.create(key='pulse:projektant-daily', data={'result': 'skipped', 'started_at': NOW.isoformat()})
    proj = loop(raport_petli.build(NOW), 'projektant')
    assert proj['state'] == 'warn' and 'czeka na okno' in proj['reason']


def test_text_has_fixed_sections_and_no_secrets():
    note('wynalazca', 'finding', days=0, score=70, title='Klucz sk-abcdefghijklmnopqrstuvwxyz w tytule')
    body = raport_petli.text(raport_petli.build(NOW))
    for heading in ('== Wymaga uwagi ==', '== Treść dnia ==', '== przeszłość.today ==', '== Najlepsze nowe pomysły i ustalenia (7 dni) =='):
        assert heading in body
    assert 'sk-abcdefghij' not in body and '[ukryte]' in body and '—' not in body


def test_send_once_per_day_with_fallback_recipient(monkeypatch):
    monkeypatch.setenv('COUNCIL_RECRUITER_EMAIL', 'wlasciciel@example.com')
    with patch('news.social_publish._mail', return_value=True) as mail:
        assert raport_petli.send(NOW)['status'] == 'ok'
        assert raport_petli.send(NOW)['status'] == 'already_run'
    to, subject, body = mail.call_args.args[:3]
    assert to == 'wlasciciel@example.com' and subject == 'spin.clinic · Raport pętli 06.10' and mail.call_args.kwargs['important'] is True
    assert mail.call_count == 1
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'petle@example.com')
    assert raport_petli.recipient() == 'petle@example.com'


def test_send_without_address_is_not_configured():
    with patch('news.social_publish._mail') as mail:
        assert raport_petli.send(NOW)['status'] == 'not_configured'
    mail.assert_not_called()


def test_task_and_command(monkeypatch):
    from news.tasks import raport_petli_task
    monkeypatch.setenv('LOOP_REPORT_ENABLED', 'false')
    assert raport_petli_task() == {'status': 'disabled'}
    out = StringIO()
    call_command('raport_petli', stdout=out)
    assert 'Raport pętli spin.clinic' in out.getvalue()
    out = StringIO()
    call_command('raport_petli', '--json', stdout=out)
    assert json.loads(out.getvalue())['summary']
    out = StringIO()
    with patch('news.social_publish._mail', return_value=False):
        call_command('raport_petli', '--wyslij', stdout=out)
    assert 'LOOP_REPORT_EMAIL' in out.getvalue()


def test_staff_endpoint_contract(django_user_model):
    client = APIClient()
    assert client.get('/api/staff/petle/').status_code in (401, 403)
    client.force_authenticate(django_user_model.objects.create_user(username='staff', is_staff=True))
    data = client.get('/api/staff/petle/').data
    assert set(data['summary']) == {'ok', 'warn', 'bad', 'idle'}
    assert [c['key'] for c in data['categories']] == ['tresc', 'agenci', 'przeszlosc', 'niezawodnosc', 'konsylium', 'dane']
    assert [c['label'] for c in data['categories']][2] == 'przeszłość.today'
    row = data['categories'][1]['loops'][0]
    assert {'key', 'label', 'state', 'reason', 'last_run', 'outputs_24h', 'outputs_7d', 'pending', 'consumer', 'cadence_h'} <= set(row)
    assert row['state'] in ('ok', 'warn', 'bad', 'idle')


def test_panel_section_lists_problems():
    card = raport_petli.panel_section(NOW)
    assert card['title'] == 'Pętle agentów' and card['status'] in ('ok', 'warn', 'error')


def test_labels_fit_under_gear_and_keys_unique(django_user_model):
    for c in raport_petli.CONTRACTS:
        assert len(c['label']) <= 14, c['label']
    for key, _ in raport_petli.CATEGORIES:
        keys = [c['key'] for c in raport_petli.CONTRACTS if c['category'] == key]
        assert len(keys) == len(set(keys))
    assert raport_petli.short('a' * 80) == 'a' * 59 + '…' and raport_petli.short('x; y') == 'x'
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username='staff2', is_staff=True))
    for c in client.get('/api/staff/petle/').data['categories']:
        for row in c['loops']:
            assert len(row['reason']) <= 60 and row['title']


def test_stoi_shows_last_error_reason():
    """„[STOI] Dyżurny: duty-15m: błąd (279 z rzędu)” bez powodu - raport ma mówić DLACZEGO (6.10)."""
    cache.set('heartbeat:duty-15m', {'result': 'error', 'consecutive_errors': 279, 'started_at': NOW.isoformat(),
                                     'last_error': "AttributeError: 'datetime.timedelta' object has no attribute 'day_of_month'"})
    state = raport_petli.loop_state(raport_petli.BY_KEY['dyzurny'], NOW)
    assert state['state'] == 'bad'
    assert state['reason'].startswith("duty-15m: błąd (279 z rzędu): AttributeError: 'datetime.timedelta'")
    text = raport_petli.text(raport_petli.build(NOW))
    assert '[STOI] Dyżurny: duty-15m: błąd (279 z rzędu): AttributeError' in text


def test_partial_pulse_is_warning_with_reason():
    cache.set('heartbeat:duty-15m', {'result': 'ok', 'started_at': NOW.isoformat(), 'last_output_at': NOW.isoformat(),
                                     'partial': 'check_warden: RuntimeError: boom'})
    state = raport_petli.loop_state(raport_petli.BY_KEY['dyzurny'], NOW)
    assert state['state'] == 'warn' and 'częściowo - check_warden: RuntimeError: boom' in state['reason']


def test_new_loop_grace_period_then_stoi():
    """Pętla dopisana po pierwszym zapisie first_seen: rytm + 1 h bez „STOI”, potem zwykła cisza."""
    from news import petle_bezpieczniki as fuses
    raport_petli.first_seen(NOW)  # istniejące pętle: stara data, bez okresu ochronnego
    extra = raport_petli.contract('nowa-petla', 'Nowa', 'tresc', 24, 'public', 1, counter='position_checks')
    with patch.object(raport_petli, 'CONTRACTS', raport_petli.CONTRACTS + (extra,)):
        seen = raport_petli.first_seen(NOW)
        state = raport_petli.loop_state(extra, NOW + timedelta(hours=10), seen)
        assert state['state'] == 'ok' and state['new'] and state['reason'].startswith('nowa pętla')
        later = raport_petli.loop_state(extra, NOW + timedelta(hours=26), seen)
        assert later['state'] == 'bad' and 'brak wyniku' in later['reason']
        assert 'petle:silent:nowa-petla' not in {f['key'] for f in fuses.silent_loops(NOW + timedelta(hours=10))}
    # stare pętle bez wyniku nadal stoją od razu (bez okresu ochronnego)
    assert raport_petli.loop_state(raport_petli.BY_KEY['badacz'], NOW, raport_petli.first_seen(NOW))['state'] == 'bad'


def test_loops_deployed_6_10_have_grace():
    seen = raport_petli.first_seen(NOW)
    for key in ('zmiana-zdania', 'raport-petli'):
        state = raport_petli.loop_state(raport_petli.BY_KEY[key], NOW + timedelta(hours=20), seen)
        assert state['state'] != 'bad', state


def test_auto_send_once_manual_override_and_pulse(monkeypatch):
    """Mail 3 razy w 30 min (6.10): ścieżka automatyczna najwyżej raz na dzień, --wyslij jawnie wymusza,
    --wyslij --raz (skrypt wdrożenia) pomija; każda wysyłka zapisuje puls pętli."""
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'petle@example.com')
    from news.tasks import raport_petli_task
    with patch('news.social_publish._mail', return_value=True) as mail:
        call_command('raport_petli', '--wyslij', '--raz', stdout=StringIO())
        assert mail.call_count == 1
        call_command('raport_petli', '--wyslij', '--raz', stdout=StringIO())
        assert raport_petli_task()['status'] == 'already_run'
        assert raport_petli.send(NOW + timedelta(minutes=30))['status'] == 'already_run'
        assert mail.call_count == 1
        call_command('raport_petli', '--wyslij', stdout=StringIO())
        assert mail.call_count == 2
    pulse = raport_petli.pulse('raport-petli-daily')
    assert pulse['result'] == 'ok' and pulse['last_success'] == NOW.isoformat()
    state = raport_petli.loop_state(raport_petli.BY_KEY['raport-petli'], NOW + timedelta(hours=1))
    assert state['ran_24h'] and state['state'] == 'ok'
    assert len(RepairerState.objects.get(key='raport-petli:2026-10-06').data['sends']) == 2


def test_seba_not_marked_off_when_flag_unset(monkeypatch):
    monkeypatch.delenv('SEBA_ENABLED', raising=False)
    assert raport_petli.loop_state(raport_petli.BY_KEY['seba'], NOW)['state'] != 'idle'
