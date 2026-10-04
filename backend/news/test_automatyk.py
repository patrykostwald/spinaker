import pytest

from news import automatyk
from news.agent_models import AgentNote

pytestmark = pytest.mark.django_db


def test_loops_reference_real_agents():
    from news.agent_registry import REGISTRY
    assert not {i for _, _, _, steps in automatyk.LOOPS for _, i, _ in steps if i and i not in REGISTRY}
    assert all(any(g for _, _, g in steps) for _, _, _, steps in automatyk.LOOPS)


def test_step_checks_without_ai_and_keeps_checked_fixes(monkeypatch):
    rows = {'screen': {'enabled': False, 'result': 'warn', 'schedule': 'co 5 min', 'summary': '', 'last_run': None},
            'dr-spin': {'enabled': True, 'result': 'error', 'schedule': 'co 10 min', 'summary': 'limit', 'last_run': None}}
    monkeypatch.setattr(automatyk, 'health', lambda: rows)
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)
    fix = {'loop': 'Diagnozy', 'change': 'Strażnik wpisów przed Dr. Spinem włączony', 'why': 'stoi', 'evidence': 'wyłączony',
           'kind': 'strażnik', 'effort': 'S', 'impact': 9, 'brief': 'włącz flagę'}
    answers = iter([({'summary': 'S', 'issues': [{'loop': 'Diagnozy', 'problem': 'stoi', 'severity': 'wysoki'}],
                      'fixes': [fix, {**fix, 'change': 'Ogólnik', 'impact': 2}]}, ('groq', 'a')),
                    ({'remove': [1], 'reason': 'ogólnik'}, ('nim', 'b'))])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    note = automatyk.step(force=True)
    assert any('Strażnik wpisów' in c and 'wyłączony' in c for c in note.scores['checks'])
    assert any('Dr. Spin' in c and 'błędem' in c for c in note.scores['checks'])
    assert [f['change'] for f in note.scores['fixes']] == [fix['change']]
    assert AgentNote.objects.filter(agent='automatyk', kind='idea', score=90).count() == 1
    assert automatyk.step() == note  # raz dziennie
