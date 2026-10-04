import pytest

from news import opiekunowie
from news.agent_models import AgentNote

pytestmark = pytest.mark.django_db


def state(result='error'):
    return {'screen': {'enabled': True, 'result': result, 'schedule': 'co 5 min', 'summary': 'limit', 'last_run': '2026-10-05T06:00'}}


@pytest.fixture
def quiet(monkeypatch):
    from django.core.cache import cache
    cache.clear()
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)


def test_alarm_once_per_loop_then_repair(quiet, monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: state())
    raised = opiekunowie.alarms()
    assert [n.scores['loop'] for n in raised] == ['Diagnozy'] and opiekunowie.alarms() == []
    fix = {'change': 'Ponów po 429 z odstępem', 'why': 'limit', 'evidence': 'summary: limit', 'brief': 'retry', 'impact': 8, 'effort': 'S'}
    answers = iter([({'summary': 'S', 'fixes': [fix]}, ('groq', 'a')), ({'remove': [], 'reason': 'ok'}, ('nim', 'b'))])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    note = opiekunowie.repair(raised[0], force=True)
    assert note.scores['role'] == 'naprawiacz' and note.scores['alarm'] == raised[0].pk and note.score == 80
    assert opiekunowie.alarms_without_repair() == []


def test_improve_rotates_and_security_flags_unguarded_publication(quiet, monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: {})
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: ({'summary': 'S', 'fixes': [], 'risks': []}, ('groq', 'a')))
    first = opiekunowie.improve(force=True, count=2)
    second = opiekunowie.improve(force=True, count=2)
    assert {n.scores['loop'] for n in first}.isdisjoint({n.scores['loop'] for n in second})
    checks = opiekunowie.security_checks({'steps': [{'step': 'Zbieracz', 'guard': False}, {'step': 'Publikacja X', 'guard': False}]})
    assert any('Publikacja X' in c for c in checks) and any('bez' in c or 'nie ma żadnego' in c for c in checks)


def test_step_survives_failures(quiet, monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: {})
    monkeypatch.setattr(opiekunowie, 'improve', lambda force=False: (_ for _ in ()).throw(RuntimeError('x')))
    monkeypatch.setattr(opiekunowie, 'security', lambda force=False: [])
    out = opiekunowie.step()
    assert out['usprawnienia'].startswith('błąd') and out['alarmy'] == 0
