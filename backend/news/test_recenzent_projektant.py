import pytest

from news import projektant, recenzent
from news.agent_models import AgentNote

pytestmark = pytest.mark.django_db


@pytest.fixture
def models(monkeypatch):
    monkeypatch.setattr('news.agents_common.members', lambda n, force=False: [('groq', 'a'), ('nim', 'b')][:n])
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)


def test_recenzent_keeps_checked_findings_only(models, monkeypatch):
    items = [{'id': 'diagnoza:1', 'kind': 'diagnoza', 'url': 'https://spin.clinic/klinika/1', 'text': {'nagłówek': 'X'}}]
    answers = iter([
        {'findings': [{'id': 'diagnoza:1', 'criterion': 3, 'severity': 'krytyczne', 'quote': 'X', 'problem': 'intencja', 'fix': 'Y'},
                      {'id': 'diagnoza:1', 'criterion': 6, 'severity': 'drobne', 'quote': 'X', 'problem': 'na wyrost', 'fix': 'Z'},
                      {'id': 'obcy:9', 'criterion': 1, 'severity': 'ważne', 'quote': '', 'problem': 'spoza', 'fix': ''}]},
        {'remove': [1], 'reason': 'drugi zarzut przesadzony'}])
    monkeypatch.setattr('news.agents_common.ask', lambda *a, **k: next(answers))
    note = recenzent.step(items=items)
    assert note.agent == 'recenzent' and len(note.scores['findings']) == 1
    assert note.scores['findings'][0]['problem'] == 'intencja' and 'krytyczne' in note.body
    assert recenzent.collect() == []  # nic nowego, a ten sam tekst nie wraca drugi raz


def test_projektant_audit_finds_style_problems(models, monkeypatch):
    html = ('<h1>A</h1><h1>B</h1><a class="x" href="/">Dalej →</a><a class="y" href="/">Więcej →</a><img src="a.png">')
    monkeypatch.setattr(projektant.requests, 'get', lambda *a, **k: type('R', (), {'text': html})())
    answers = iter([{'fixes': [{'page': '/', 'element': 'h1', 'problem': 'dwa h1', 'fix': 'jeden', 'priority': 'wysoki'}]},
                    {'remove': [], 'reason': 'ok'}] * 10)
    monkeypatch.setattr('news.agents_common.ask', lambda *a, **k: next(answers))
    monkeypatch.setattr(projektant, 'PAGES', ['/'])
    note = projektant.audit(force=True, base='http://test')
    checks = ' '.join(c['check'] for c in note.scores['auto_checks'])
    assert 'h1' in checks and 'alt' in checks and 'różne klasy' in checks
    assert note.scores['fixes'][0]['priority'] == 'wysoki'


def test_guide_has_owner_rules_and_canon():
    rules = ' '.join(projektant.guide())
    assert '15 px' in rules and 'WCAG' in rules and AgentNote.objects.count() == 0
