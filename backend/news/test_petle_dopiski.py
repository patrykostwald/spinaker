"""Dopiski z audytu pętli: tematy maili agentów, raporty czekające na zgodę, krok „Właściciel”, sprint w Raporcie pętli,
„Ostatnie raporty agentów” bez szumu."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from news import petle_bezpieczniki as fuses, raport_petli
from news.agent_models import AgentNote, BuildTicket
from news.report_models import InstitutionalReport

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 12, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.post', side_effect=AssertionError('Bez sieci')), \
         patch('requests.get', side_effect=AssertionError('Bez sieci')):
        yield
    cache.clear()


def note(agent, kind='idea', days=0, **fields):
    row = AgentNote.objects.create(agent=agent, kind=kind, title=fields.pop('title', f'{agent} {kind}'), body='b', **fields)
    AgentNote.objects.filter(pk=row.pk).update(created_at=NOW - timedelta(days=days))
    return AgentNote.objects.get(pk=row.pk)


def loop(report, key):
    return next(l for c in report['categories'] for l in c['loops'] if l['key'] == key)


def report(hours, n=1):
    return InstitutionalReport.objects.create(kind='weekly', audience='media', sample_key=f'k{n}', status='awaiting_approval',
                                              awaiting_since=NOW - timedelta(hours=hours))


# 1. tematy maili --------------------------------------------------------------------------------------------------

def test_agent_mail_has_own_subject(monkeypatch):
    from news import agents_common as common
    monkeypatch.setenv('COUNCIL_RECRUITER_EMAIL', 'wlasciciel@example.com')
    with patch('news.social_publish._mail', return_value=True) as mail:
        assert common.notify(note('architekt', 'report', title='Plan rozwoju'))
        assert common.notify(note('opiekun', 'audit', title='Diagnozy · alarmowy: 1 krok'))
    subjects = [c.args[1] for c in mail.call_args_list]
    assert subjects == ['spin.clinic · Architekt: Plan rozwoju', 'spin.clinic · Opiekun pętli: Diagnozy · alarmowy: 1 krok']
    from news.council_recruiter import _notify
    with patch('news.social_publish._mail', return_value=True) as mail:
        _notify('egzamin', 'treść')
    assert mail.call_args.args[1] == 'spin.clinic · Rekruter Konsylium: egzamin'


# 2. raporty czekające na zgodę -----------------------------------------------------------------------------------

@override_settings(REPORTS_ENABLED=True)
def test_awaiting_report_is_not_done_and_late_after_day():
    from news.daily_schedule import check_institutional_reports
    report(2)
    status, data = check_institutional_reports(NOW)
    assert status == 'waiting' and 'czeka na Twoją zgodę' in data['detail']
    report(30, 2)
    assert check_institutional_reports(NOW)[0] == 'late'
    InstitutionalReport.objects.update(status='approved')
    assert check_institutional_reports(NOW)[0] == 'done'


def test_awaiting_report_fuse_and_loop_state(monkeypatch):
    monkeypatch.setenv('REPORTS_ENABLED', 'true')
    report(30)
    found = {f['key']: f for f in fuses.deadlines(NOW)}
    assert found['petle:reports-awaiting']['loop'] == 'raporty' and found['petle:reports-awaiting']['level'] == 'warn'
    rap = loop(raport_petli.build(NOW), 'raporty')
    assert rap['pending'] == 1 and 'Raporty: 1 czeka na Twoją zgodę ponad 24 h' in rap['reason'] and rap['state'] != 'ok'


def test_raportysta_sets_awaiting_since():
    import inspect
    from news import raportysta
    assert "report.awaiting_since = timezone.now()" in inspect.getsource(raportysta)


# 3. krok „Właściciel” ------------------------------------------------------------------------------------------

def test_owner_step_has_pulse_and_warns_on_waiting_proposals(monkeypatch):
    from news import automatyk, opiekunowie
    monkeypatch.setattr('news.agent_registry.snapshot', lambda now=None: [])
    rows = automatyk.health()
    assert rows['owner-decisions']['result'] == 'ok'
    note('strateg', days=9)
    decided = note('architekt', days=3)
    AgentNote.objects.filter(pk=decided.pk).update(status='accepted', decided_at=NOW - timedelta(days=2))
    row = automatyk.health()['owner-decisions']
    assert row['result'] == 'warn' and '1 propozycji czeka' in row['summary'] and row['last_run'] == NOW - timedelta(days=2)
    state, checks = automatyk.loops_state()
    step = next(s for l in state if l['loop'] == 'Rozwój serwisu' for s in l['steps'] if s['step'] == 'Właściciel')
    assert step['human'] and step['result'] == 'warn'
    assert any('Właściciel' in c for c in checks)
    alarm = AgentNote.objects.create(agent='opiekun', kind='audit', title='a', body='b',
                                     scores={'role': 'alarmowy', 'loop': 'Rozwój serwisu', 'alerts': [step]})
    assert opiekunowie.repair(alarm, force=True) is None  # bez wywołania modelu dla decyzji człowieka
    decyzje = loop(raport_petli.build(NOW), 'decyzje')
    assert decyzje['state'] == 'warn' and decyzje['pending'] == 1
    assert 'petle:owner-decisions' in {f['key'] for f in fuses.deadlines(NOW)}


# 4. sprint w raporcie -----------------------------------------------------------------------------------------

def test_overdue_ticket_fuse_and_report_section():
    BuildTicket.objects.create(title='Oś czasu', status='approved', due_date=NOW.date() - timedelta(days=2), executor='codex')
    BuildTicket.objects.create(title='Eksport CSV', status='approved', due_date=NOW.date() + timedelta(days=3))
    BuildTicket.objects.create(title='Nowy pomysł', status='proposed')
    found = {f['key']: f for f in fuses.deadlines(NOW)}
    assert found['petle:tickets-overdue']['level'] == 'bad' and found['petle:tickets-overdue']['loop'] == 'sprint'
    data = raport_petli.build(NOW)
    assert data['sprint']['open'] == 3 and data['sprint']['overdue'] == 1 and data['sprint']['proposed'] == 1
    assert loop(data, 'sprint')['state'] == 'bad'
    body = raport_petli.text(data)
    assert '== Sprint tygodnia ==' in body and 'PO TERMINIE' in body and 'Oś czasu' in body and 'Eksport CSV' in body


# 5. ostatnie raporty bez szumu ---------------------------------------------------------------------------------

def test_recent_reports_skip_noise_and_show_unread_first(django_user_model):
    for n in range(20):
        note('strateg', 'report', title=f'Czytelnik testowy: diagnoza {n}', scores={'reader': 'plain'})
    note('dyrygent', 'report', title='Plan dnia')
    read = note('automatyk', 'report', title='Automatyk się uczy', status='done')
    for n in range(9):
        note('architekt', 'report', days=1, title=f'Plan rozwoju {n}')
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username='staff', is_staff=True))
    with patch('news.agent_registry.snapshot', return_value=[]):
        reports = client.get('/api/staff/agents/map/').data['reports']
    titles = [r['title'] for r in reports]
    assert len(reports) == 8 and all(r['status'] == 'new' for r in reports) and read.title not in titles
    assert not any(t.startswith(('Czytelnik testowy', 'Plan dnia')) for t in titles)


def test_strateg_loop_excludes_plain_reader_notes():
    for n in range(3):
        note('strateg', 'report', days=10, title=f'Czytelnik {n}', scores={'reader': 'plain'})
    data = raport_petli.build(NOW)
    assert loop(data, 'strateg')['pending'] == 0 and loop(data, 'czytelnik')['outputs_7d'] == 0
    assert loop(data, 'czytelnik')['pending'] == 0  # SLA 14 dni
