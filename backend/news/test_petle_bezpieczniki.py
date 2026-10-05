"""Bezpieczniki pętli (audyt 5.10, punkt 5.2): zator wyników, cisza, powtórki, kolejka Seby, odbiorca w SLA."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache

from news import duty, duty_extra, petle_bezpieczniki as fuses, raport_petli
from news.agent_models import AgentNote, SebaReview
from news.models import DutyAlarm, RepairerState

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
    row = AgentNote.objects.create(agent=agent, kind=kind, title=fields.pop('title', f'{agent} {kind} {AgentNote.objects.count()}'),
                                   body='b', **fields)
    AgentNote.objects.filter(pk=row.pk).update(created_at=NOW - timedelta(days=days))
    return AgentNote.objects.get(pk=row.pk)


def keys(found):
    return {f['key'] for f in found}


def test_every_note_producer_has_contract_with_consumer():
    agents = {v for v, _ in AgentNote._meta.get_field('agent').choices}
    for agent in agents:
        contracts = [c for c in raport_petli.CONTRACTS if agent in c['agents']]
        assert contracts, f'{agent} produkuje AgentNote, a nie ma kontraktu pętli'
        assert all(c['consumer'] for c in contracts)


def test_registered_in_duty_checks():
    for check in fuses.CHECKS:
        assert check in duty_extra.CHECKS and check in duty.CHECKS


def test_unused_outputs_threshold(monkeypatch):
    for _ in range(11):
        note('wynalazca', 'finding', days=9)
    found = fuses.unused_outputs(NOW)
    hit = next(f for f in found if f['key'] == 'petle:unused:wynalazca')
    assert hit['loop'] == 'wynalazca' and hit['level'] == 'warn' and hit['details']['waiting'] == 11
    monkeypatch.setenv('LOOP_UNUSED_MAX', '3')
    assert next(f for f in fuses.unused_outputs(NOW) if f['key'] == 'petle:unused:wynalazca')['level'] == 'bad'


def test_green_pulse_without_output():
    RepairerState.objects.create(key='pulse:automatyk-daily', data={'result': 'ok', 'last_success': NOW.isoformat(),
                                                                     'started_at': NOW.isoformat()})
    assert 'petle:green-empty:automatyk' in keys(fuses.unused_outputs(NOW))
    note('automatyk', 'audit', days=0)
    assert 'petle:green-empty:automatyk' not in keys(fuses.unused_outputs(NOW))


def test_silence_over_two_cadences():
    note('kontroler', 'audit', days=3)  # rytm 24 h
    note('wynalazca', 'finding', days=1)  # rytm 72 h
    found = keys(fuses.silent_loops(NOW))
    assert 'petle:silent:kontroler' in found and 'petle:silent:wynalazca' not in found


def test_disabled_loop_is_not_checked(monkeypatch):
    monkeypatch.setenv('AGENTS_ENABLED', 'false')
    assert 'petle:silent:kontroler' not in keys(fuses.silent_loops(NOW))


def test_duplicate_titles_and_old_seba_queue(monkeypatch):
    for n in range(3):
        note('strateg', title=f'Newsletter tygodniowy z najlepszymi diagnozami {n}')
    monkeypatch.setenv('SEBA_ENABLED', 'true')
    idea = note('architekt', title='Inny pomysł')
    SebaReview.objects.filter(note=idea).update(created_at=NOW - timedelta(hours=50), last_error='Limit dostawcy 429.')
    found = {f['key']: f for f in fuses.quality(NOW)}
    assert found['petle:duplicates:strateg']['details']['pairs'] == 3
    assert found['petle:seba-queue']['loop'] == 'seba' and found['petle:seba-queue']['details']['reasons'] == ['Limit dostawcy 429.']


def test_consumers_owner_and_agent_readers(django_user_model):
    note('strateg', days=10)
    note('kartograf', 'finding', days=9)
    found = keys(fuses.consumers(NOW))
    assert 'petle:consumer:strateg' in found and 'petle:consumer:kartograf' in found
    decided = note('strateg', days=2)
    AgentNote.objects.filter(pk=decided.pk).update(status='rejected', decided_at=NOW - timedelta(days=1))
    note('prawnik', 'review', days=1)  # Prawnik przeczytał ustalenia po najstarszym
    found = keys(fuses.consumers(NOW))
    assert 'petle:consumer:strateg' not in found and 'petle:consumer:kartograf' not in found


def test_duty_run_opens_warnings_and_report_marks_loop(monkeypatch):
    monkeypatch.setenv('DUTY_ENABLED', 'true')
    for _ in range(11):
        note('technolog', 'finding', days=9)
    duty.run(NOW)
    alarm = DutyAlarm.objects.get(key='petle:unused:technolog')
    assert alarm.status == 'open' and alarm.severity == 'warning' and alarm.rule == 'check_unused_outputs'
    report = raport_petli.build(NOW)
    technolog = next(l for c in report['categories'] for l in c['loops'] if l['key'] == 'technolog')
    assert 'Technolog: 11 wpisów czeka ponad 7 dni' in technolog['reason'] and technolog['state'] in ('warn', 'bad')
