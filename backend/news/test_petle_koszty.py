"""Koszty pętli (właściciel 7.10): licznik zapytań na zadanie, znak wodny wejścia, tania trasa i jeden autor biletów."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from news import petle_koszty as koszty
from news.agent_models import AgentNote, BuildTicket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    koszty.end()
    yield
    koszty.end()


def test_calls_are_counted_per_running_task_and_reported():
    token = koszty.begin('news.tasks.recenzent_task')
    koszty.count_call()
    koszty.count_call()
    koszty.end(token)
    koszty.count_call()  # poza zadaniem (komenda, panel)
    koszty.begin('news.tasks.opiekunowie_task')
    assert koszty.skipped('bez zmian')['unchanged'] == 1
    koszty.end()
    rows = koszty.usage()
    assert rows['recenzent_task'] == {'dzis': 2, 'tydzien': 2, 'pominiete_dzis': 0, 'pominiete_tydzien': 0}
    assert rows[koszty.OTHER]['dzis'] == 1 and rows['opiekunowie_task']['pominiete_dzis'] == 1
    lines = koszty.report_lines()
    assert lines[0].startswith('Zapytania do modeli: dziś 3, 7 dni 3; przebiegi pominięte') and 'dziś 1' in lines[0]
    assert lines[1] == '- recenzent_task: 2 / 2' and any(l.startswith('- opiekunowie_task: 0 / 0, pominięte 1 / 1') for l in lines)


def test_watermark_detects_change_and_counts_skip():
    assert koszty.changed('x', {'a': 1})
    koszty.mark('x', {'a': 1})
    assert not koszty.changed('x', {'a': 1}) and koszty.changed('x', {'a': 2})
    assert koszty.unchanged_since('x', {'a': 1}) and not koszty.unchanged_since('x', {'a': 2})
    assert koszty.usage()[koszty.OTHER]['pominiete_dzis'] == 1


def test_registry_reserve_and_inception_count_on_task_account(monkeypatch):
    from news import council_registry as registry
    monkeypatch.setenv('GROQ_API_KEY', 'x')
    koszty.begin('news.tasks.zmiana_zdania_task')
    with registry.for_content():
        assert registry.reserve(('groq', 'model'))
    monkeypatch.setattr('news.inception._state', lambda lock=False: type('S', (), {'cursor': {}, 'save': lambda self, **k: None})())
    from news import inception
    inception.record(100)
    assert koszty.usage()['zmiana_zdania_task']['dzis'] == 2


def test_heartbeat_sets_and_clears_task_account(monkeypatch):
    from news import task_heartbeat
    monkeypatch.setattr(task_heartbeat, 'record', lambda *a, **k: None)
    sender = type('T', (), {'name': 'news.tasks.badacz_task'})()
    task_heartbeat.started(sender=sender, task_id='1')
    assert koszty.current() == 'badacz_task'
    task_heartbeat.succeeded(sender=sender, result={'status': 'ok'})
    assert koszty.current() == koszty.OTHER


def test_report_has_costs_section_and_flow(monkeypatch):
    from news import raport_petli
    now = timezone.now()
    koszty.begin('news.tasks.recenzent_task')
    koszty.count_call()
    koszty.end()
    note = AgentNote.objects.create(agent='architekt', kind='idea', title='Pomysł', body='x', status='accepted', score=90)
    BuildTicket.objects.create(note=note, title='Pomysł', rank=50, brief='b', acceptance=[], effort='S', executor='claude',
                               status='done', due_date=now.date(), created_at=now, decided_at=now)
    body = raport_petli.text(raport_petli.build(now))
    assert '== Koszty pętli (zapytania do modeli) ==' in body and '- recenzent_task: 1 / 1' in body
    assert 'Przepływ 30 dni: propozycje agentów 1 -> bilety 1 -> zbudowane 1' in body


def test_sprint_single_author_and_evidence(monkeypatch):
    from news import sprint
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    now = timezone.now()
    assert sprint.SOURCES == ('architekt',)
    AgentNote.objects.create(agent='strateg', kind='idea', title='Pomysł Stratega', body='x', status='new', score=95)
    AgentNote.objects.create(agent='architekt', kind='idea', title='Plan bez dowodu', body='x', status='new', score=95, scores={'plan': 1})
    AgentNote.objects.create(agent='architekt', kind='idea', title='Plan z dowodem', body='x', status='new', score=95,
                             scores={'plan': 1, 'evidence': ['raport Kontrolera 6.10']})
    AgentNote.objects.create(agent='pielgrzym', kind='experiment', title='Eksperyment przyjęty', body='x', status='accepted', score=60)
    assert {c['title'] for c in sprint.candidates(now)} == {'Plan z dowodem', 'Eksperyment przyjęty'}
    from news.pracownia_osint import proposals_for_architekt
    assert [p['agent'] for p in proposals_for_architekt()] == ['strateg', 'pielgrzym']


def test_recenzent_audit_pages_batches_and_skips_unchanged(monkeypatch):
    from news import recenzent
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)
    items = [{'id': f'strona:/p{i}', 'kind': 'stały tekst strony', 'url': f'https://spin.clinic/p{i}', 'text': {'akapity': [f'Tekst {i}']}}
             for i in range(3)]
    monkeypatch.setattr(recenzent, 'page_texts', lambda base=None: items)
    calls = []

    def ask_any(prompt, data, schema, force=False, exclude=()):
        calls.append(len(data['items']))
        if 'findings' in data:
            return {'remove': [], 'reason': 'ok'}, ('nim', 'b')
        return {'findings': [{'id': data['items'][0]['id'], 'criterion': 1, 'severity': 'ważne', 'quote': 'q', 'problem': 'p', 'fix': 'f'}]}, ('groq', 'a')
    monkeypatch.setattr('news.agents_common.ask_any', ask_any)
    note = recenzent.audit_pages(base='http://test')
    assert calls == [3, 3] and note.scores['pages'] == [i['id'] for i in items] and note.scores['findings'][0]['url'] == 'https://spin.clinic/p0'
    assert recenzent.audit_pages(base='http://test') is None and calls == [3, 3]
    items[1]['text'] = {'akapity': ['Nowy tekst']}
    second = recenzent.audit_pages(base='http://test')
    assert second.scores['pages'] == ['strona:/p1'] and second.scores['unchanged'] == 2 and calls == [3, 3, 1, 1]


def test_opiekunowie_improve_skips_unchanged_loops(monkeypatch):
    from news import opiekunowie
    monkeypatch.setattr('news.automatyk.health', lambda: {})
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)
    calls = []
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: (calls.append(1) or ({'summary': 'S', 'fixes': []}, ('groq', 'a'))))
    first = opiekunowie.improve(count=99)  # pierwsza wizyta w każdej pętli: model pytany
    assert len(first) == len(opiekunowie.automatyk.LOOPS) == len(calls)
    AgentNote.objects.filter(agent='opiekun').update(created_at=timezone.now() - timedelta(hours=21))
    assert opiekunowie.improve(count=1) == []  # te same pętle, nic się nie zmieniło: bez zapytania
    assert len(calls) == len(first) and koszty.usage()[koszty.OTHER]['pominiete_dzis'] >= 1
    assert len(opiekunowie.improve(force=True, count=1)) == 1 and len(calls) == len(first) + 1


def test_mechanik_probe_backoff(monkeypatch):
    from news import mechanik
    from news.clinic_models import CouncilSeat
    monkeypatch.setenv('GROQ_API_KEY', 'x')
    CouncilSeat.objects.create(provider='groq', model='m1', status='suspended', last_error='groq: http_503')
    monkeypatch.setattr(mechanik, 'provider_models', lambda s: {'m1'})
    probes = []
    monkeypatch.setattr(mechanik, 'probe', lambda s, m: (probes.append(m), (False, 'http_503'))[1])
    monkeypatch.setattr('news.inception.health', lambda now=None: None)
    assert mechanik.step()['results'] == [('m1', 'http_503')]
    assert mechanik.step()['results'] == [('m1', 'sprawdzony niedawno')] and probes == ['m1']


def test_zmiana_zdania_asks_inception_first(monkeypatch):
    from news import zmiana_zdania as zz
    monkeypatch.setattr('news.dyrygent.allowed', lambda name=None: True)
    monkeypatch.setattr('news.agents_common.inception_member', lambda: ('inception', 'mercury-2.5'))
    monkeypatch.setattr('news.inception.side_json', lambda *a, **k: ({'relation': 'to samo stanowisko'}, 'mercury-2.5'))
    monkeypatch.setattr('news.clinic_council._members', lambda name, default: (_ for _ in ()).throw(AssertionError('Konsylium nie pytane')))
    assert zz.ask({'x': 1}) == ({'relation': 'to samo stanowisko'}, 'mercury-2.5')


def test_agents_default_daily_steps_is_four():
    from news import agents_common
    assert agents_common.DEFAULT_DAILY_STEPS == 4
