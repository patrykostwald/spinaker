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


def test_agent_map_handles_seconds_schedule(monkeypatch):
    """Tryb ciągły zbieracza X: harmonogram jako timedelta nie może wywracać mapy agentów (audyt 5.10)."""
    from datetime import timedelta
    from config.celery import app
    from news.agent_registry import snapshot
    monkeypatch.setitem(app.conf.beat_schedule, 'political-x-minute', {'task': 'news.tasks.political_poll_task', 'schedule': timedelta(seconds=60)})
    rows = [r for r in snapshot() if r['beat'] == 'political-x-minute']
    assert rows and rows[0]['schedule'] == 'co 1 min'


def test_automatyk_learns_lessons_and_uses_them(monkeypatch):
    import types
    monkeypatch.setattr('requests.get', lambda *a, **k: types.SimpleNamespace(content=b''))
    monkeypatch.setattr('feedparser.parse', lambda c: types.SimpleNamespace(entries=[{'link': 'https://temporal.io/x', 'title': 'Retries', 'summary': ''}]))
    lesson = {'title': 'Ponowienia z odstępem', 'lesson': 'retry', 'apply': 'Diagnozy: ponów po 429', 'source_url': 'https://temporal.io/x'}
    answers = iter([({'summary': 'S', 'lessons': [lesson, {**lesson, 'source_url': 'https://zmyslone.pl'}]}, ('groq', 'a')),
                    ({'remove': [], 'reason': 'ok'}, ('nim', 'b'))])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    assert automatyk.learn_due()
    note = automatyk.learn(force=True)
    assert [l['title'] for l in note.scores['lessons']] == ['Ponowienia z odstępem'] and not automatyk.learn_due()
    assert automatyk.knowledge() == ['Ponowienia z odstępem: Diagnozy: ponów po 429']
