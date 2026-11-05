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
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(answers), ('groq', 'a')))
    note = recenzent.step(items=items)
    assert note.agent == 'recenzent' and len(note.scores['findings']) == 1
    assert note.scores['findings'][0]['problem'] == 'intencja' and 'krytyczne' in note.body
    assert recenzent.collect() == []  # nic nowego, a ten sam tekst nie wraca drugi raz


def test_projektant_audit_finds_style_problems(models, monkeypatch):
    html = ('<h1>A</h1><h1>B</h1><a class="x" href="/">Dalej →</a><a class="y" href="/">Więcej →</a><img src="a.png">')
    monkeypatch.setattr(projektant.requests, 'get', lambda *a, **k: type('R', (), {'text': html})())
    answers = iter([{'fixes': [{'page': '/', 'element': 'h1', 'problem': 'dwa h1', 'fix': 'jeden', 'priority': 'wysoki'}]},
                    {'remove': [], 'reason': 'ok'}] * 10)
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(answers), ('groq', 'a')))
    monkeypatch.setattr(projektant, 'PAGES', ['/'])
    note = projektant.audit(force=True, base='http://test')
    checks = ' '.join(c['check'] for c in note.scores['auto_checks'])
    assert 'h1' in checks and 'alt' in checks and 'różne klasy' in checks
    assert note.scores['fixes'][0]['priority'] == 'wysoki'


def test_guide_has_owner_rules_and_canon():
    rules = ' '.join(projektant.guide())
    assert '15 px' in rules and 'WCAG' in rules and AgentNote.objects.count() == 0


def test_audit_pages_reads_visible_text(models, monkeypatch):
    html = '<html><script>x</script><h1>O nas i nasza misja w serwisie</h1><p>Oceniasz całą spinkę jednym kliknięciem, to bardzo proste.</p></html>'
    monkeypatch.setattr('requests.get', lambda *a, **k: type('R', (), {'text': html})())
    monkeypatch.setattr('news.projektant.PAGES', ['/o-nas'])
    answers = iter([{'findings': [{'id': 'x', 'criterion': 1, 'severity': 'krytyczne', 'quote': 'Oceniasz całą spinkę',
                     'problem': '(rzetelność) oceny dotyczą połączeń', 'fix': 'Oceniasz połączenia'}]}, {'remove': [], 'reason': 'ok'}])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(answers), ('groq', 'a')))
    note = recenzent.audit_pages(base='http://test')
    assert note.kind == 'audit' and note.scores['findings'][0]['id'] == 'strona:/o-nas'
    assert 'x' not in ''.join(recenzent.page_texts('http://test')[0]['text']['akapity'][0])


def test_polish_diagnosis_keeps_meaning_and_original(models, monkeypatch):
    from news.test_diagnosis_threads import diagnosis as make
    d = make(key='501')
    d.summary = 'Wpis twierdzi, że podatki spadły o 50%, co jest, jak wynika z danych GUS, nieprawdą, ponieważ spadły o 10%.'
    d.save()
    answers = iter([{'headline': 'Podatki', 'summary': 'Wpis twierdzi, że podatki spadły o 50%. Według danych GUS spadły o 10%.', 'analysis': ''},
                    {'headline': True, 'summary': True, 'analysis': True, 'reason': 'ten sam sens'}])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(answers), ('groq', 'a')))
    assert recenzent.polish_diagnosis(d) == ['summary']
    d.refresh_from_db()
    assert d.summary.startswith('Wpis twierdzi') and 'GUS' in d.summary
    assert d.usage['original_text']['summary'].endswith('o 10%.')


def test_rewrite_rejected_when_numbers_change():
    assert not recenzent.safe_rewrite('Spadek o 50% według GUS.', 'Spadek o 40% według GUS.')
    assert not recenzent.safe_rewrite('Krótko.', 'Bardzo długi tekst ' * 10)
    assert recenzent.safe_rewrite('Według GUS spadek wyniósł 10%.', 'GUS podaje spadek o 10%.')


def test_ask_any_skips_rate_limited_model(monkeypatch):
    from news import agents_common
    from news.clinic_ai import ClinicAIError
    monkeypatch.setattr('news.clinic_council._members', lambda *a: [('groq', 'qwen/qwen3-32b'), ('openrouter', 'google/gemma-3:free')])
    monkeypatch.setattr(agents_common, 'free_member', lambda m: True)
    monkeypatch.setattr(agents_common.registry, 'available', lambda m: True)
    def fake(member, *a, **k):
        if member[0] == 'groq':
            raise ClinicAIError('groq: http_429')
        return {'ok': True}
    monkeypatch.setattr(agents_common, 'ask', fake)
    assert agents_common.ask_any('p', {}, {}, force=True) == ({'ok': True}, ('openrouter', 'google/gemma-3:free'))


def test_polish_message_keeps_original(models, monkeypatch):
    from datetime import date
    from news.clinic_models import ClinicDailyMessage
    m = ClinicDailyMessage.objects.create(day=date(2026, 10, 3), camp='government', status='approved', thesis='Obronność',
        message='Rządzący podkreślają postępy w obronności, prezentując drony i AI, oraz inwestują w edukację młodzieży poprzez szkolenia.')
    answers = iter([{'thesis': 'Obronność', 'message': 'Rządzący podkreślają postępy w obronności, prezentując drony i AI. Inwestują też w edukację młodzieży poprzez szkolenia.', 'analysis': ''},
                    {'message': True, 'reason': 'ten sam sens'}])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (next(answers), ('groq', 'a')))
    assert recenzent.polish_message(m) == ['message']
    m.refresh_from_db()
    assert m.message.count('.') == 2 and 'oraz inwestują' in m.usage['original_text']['message']
