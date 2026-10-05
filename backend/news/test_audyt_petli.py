"""Szybkie naprawy z audytu pętli agentów (5.10): Seba bez blokady, decyzje dla wszystkich rodzajów notatek,
Opiekun bez powtórzeń, Recenzent bez TransactionManagementError, puls bez fałszywej zieleni."""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news import opiekunowie, seba
from news.agent_models import AgentNote, SebaReview

pytestmark = pytest.mark.django_db
COUNCIL = [('groq', 'qwen/qwen3'), ('nim', 'mistralai/mistral-large'), ('gemini', 'gemini-2.5-flash')]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('SEBA_ENABLED', 'true')
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)
    with patch('requests.post', side_effect=AssertionError('Bez sieci')), \
         patch('requests.get', side_effect=AssertionError('Bez sieci')):
        yield
    cache.clear()


def verdict(score=8, word='przepuść'):
    return {'score': score, 'verdict': word, 'reason': 'Bo tak', **{k: 'Opis' for k in seba.DIMENSIONS}}


# --- Seba ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('kind', ['idea', 'experiment', 'finding'])
def test_author_never_blocks_seba(kind):
    note = AgentNote.objects.create(agent='automatyk', kind=kind, title='Bez autora', body='Plan', scores={'audit': 1})
    assert seba.author(note)['company'] == 'local'
    unknown = AgentNote.objects.create(agent='opiekun', kind=kind, title='Nieznany', body='Plan', scores={'author': {'company': 'unknown'}})
    assert seba.author(unknown)['company'] == 'local'
    known = AgentNote.objects.create(agent='strateg', kind=kind, title='Znany', body='Plan',
                                     scores={'author': {'company': 'Alibaba', 'provider': 'groq', 'model': 'qwen'}})
    assert seba.author(known)['company'] == 'Alibaba'


def test_idea_without_author_is_reviewed_not_stuck(monkeypatch):
    note = AgentNote.objects.create(agent='architekt', kind='idea', title='Pomysł', body='Plan', scores={'plan': 1})
    monkeypatch.setattr('news.agents_common.agent_window', lambda member: True)
    with patch('news.clinic_council._members', return_value=COUNCIL), \
         patch('news.agents_common.ask', return_value=verdict()):
        assert seba.process(note.seba_review.pk) == 'passed'
    assert seba.can_show(note)


def test_automatyk_stores_author(monkeypatch):
    from news import automatyk
    monkeypatch.setattr(automatyk, 'loops_state', lambda rows=None: ([], []))
    monkeypatch.setattr(automatyk, 'knowledge', lambda: [])
    monkeypatch.setattr(automatyk, '_canons', lambda: [])
    fix = {'loop': 'Diagnozy', 'change': 'Ponów', 'why': 'limit', 'evidence': 'e', 'kind': 'próg', 'effort': 'S', 'impact': 7, 'brief': 'b'}
    answers = iter([({'summary': 'S', 'issues': [], 'fixes': [fix]}, COUNCIL[0]), ({'remove': [], 'reason': 'ok'}, COUNCIL[1])])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    automatyk.step(force=True)
    idea = AgentNote.objects.get(agent='automatyk', kind='idea')
    assert idea.scores['author']['company'] == 'Alibaba' and idea.scores['author']['provider'] == 'groq'


def test_opiekun_improve_stores_author(monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: {})
    ofix = {'change': 'Lepszy strażnik', 'why': 'w', 'evidence': 'e', 'brief': 'b', 'impact': 6, 'effort': 'S'}
    answers2 = iter([({'summary': 'S', 'fixes': [ofix]}, COUNCIL[2]), ({'remove': [], 'reason': 'ok'}, COUNCIL[0])])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers2))
    [note] = opiekunowie.improve(force=True, count=1)
    assert note.kind == 'idea' and note.scores['author']['company'] == 'Google'


def test_architekt_ideas_store_author(monkeypatch):
    from news import pracownia_osint
    plan = {'title': 'Oś czasu', 'catalog_id': 'x', 'tier': 'darmowe', 'effort': 'S', 'value': 8, 'why': 'w',
            'acceptance': ['a'], 'brief': 'b'}
    answers = iter([({'summary': 'S', 'items': [plan]}, COUNCIL[1]), ({'remove': [], 'reason': 'ok'}, COUNCIL[0])])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    monkeypatch.setattr(pracownia_osint, 'catalog', lambda: [])
    pracownia_osint.architekt(force=True)
    idea = AgentNote.objects.get(agent='architekt', kind='idea')
    assert idea.scores['author']['company'] == 'Mistral AI'


# --- decyzje w panelu -------------------------------------------------------------------------------------------

@pytest.fixture
def staff(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username='staff', is_staff=True))
    return client


@pytest.mark.parametrize('kind', ['finding', 'review', 'audit', 'report'])
def test_read_kinds_can_be_marked_done_or_rejected(staff, kind):
    done = AgentNote.objects.create(agent='opiekun', kind=kind, title='Uwaga', body='Treść')
    rejected = AgentNote.objects.create(agent='opiekun', kind=kind, title='Uwaga 2', body='Treść')
    assert staff.post(f'/api/staff/agents/{done.pk}/decision/', {'decision': 'done'}).status_code == 200
    assert staff.post(f'/api/staff/agents/{rejected.pk}/decision/', {'decision': 'rejected'}).status_code == 200
    assert staff.post(f'/api/staff/agents/{done.pk}/decision/', {'decision': 'rejected'}).status_code == 409
    assert staff.post(f'/api/staff/agents/{rejected.pk}/decision/', {'decision': 'accepted'}).status_code == 400
    assert AgentNote.objects.get(pk=done.pk).status == 'done' and AgentNote.objects.get(pk=rejected.pk).status == 'rejected'


def test_idea_waiting_for_seba_can_be_rejected_not_accepted(staff):
    idea = AgentNote.objects.create(agent='automatyk', kind='idea', title='Pomysł', body='Plan')
    assert staff.post(f'/api/staff/agents/{idea.pk}/decision/', {'decision': 'accepted'}).status_code == 409
    assert staff.post(f'/api/staff/agents/{idea.pk}/decision/', {'decision': 'rejected'}).status_code == 200


def test_agent_map_lists_all_agents_and_notes_filter_accepts_them(staff):
    with patch('news.agent_registry.snapshot', return_value=[]):
        agents = staff.get('/api/staff/agents/map/').data['agents']
    assert {'architekt', 'automatyk', 'opiekun', 'dyrygent', 'prawnik'} <= set(agents)
    for agent in agents:
        assert staff.get(f'/api/staff/agents/?agent={agent}').status_code == 200
    assert staff.get('/api/staff/agents/?agent=obcy').status_code == 400


# --- Opiekun bez powtórzeń --------------------------------------------------------------------------------------

def broken(summary='TransactionManagementError'):
    return {'recenzent': {'enabled': True, 'result': 'error', 'schedule': 'co 2 h', 'summary': summary, 'last_run': '2026-10-06T06:41'}}


def test_same_error_updates_one_open_alarm(monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: broken())
    first = opiekunowie.alarms()
    assert first and all(n.scores['repeats'] == 1 for n in first)
    count = AgentNote.objects.filter(agent='opiekun').count()
    for _ in range(5):
        cache.clear()  # 6.10: cache bez wspólnej pamięci przepuszczał alarm co godzinę
        assert opiekunowie.alarms() == []
    assert AgentNote.objects.filter(agent='opiekun').count() == count
    assert AgentNote.objects.get(pk=first[0].pk).scores['repeats'] == 6
    cache.clear()
    monkeypatch.setattr('news.automatyk.health', lambda: broken('OperationalError: database locked'))
    assert opiekunowie.alarms()  # inny rodzaj błędu = nowy wpis


def test_error_kind_ignores_numbers():
    assert opiekunowie.error_kind('Błąd: TransactionManagementError') == 'TransactionManagementError'
    assert opiekunowie.error_kind('spóźnione 12:41 o 3 min') == opiekunowie.error_kind('spóźnione 14:41 o 7 min')


def test_repair_reuses_open_proposal_for_same_error(monkeypatch):
    monkeypatch.setattr('news.automatyk.health', lambda: broken())
    alarm = opiekunowie.alarms()[0]
    fix = {'change': 'atomic', 'why': 'w', 'evidence': 'e', 'brief': 'b', 'impact': 9, 'effort': 'S'}
    answers = iter([({'summary': 'S', 'fixes': [fix]}, COUNCIL[0]), ({'remove': [], 'reason': 'ok'}, COUNCIL[1])])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    repair = opiekunowie.repair(alarm, force=True)
    assert repair.scores['author']['company'] == 'Alibaba' and repair.scores['key'] == alarm.scores['key']
    twin = AgentNote.objects.create(agent='opiekun', kind='audit', title='kopia', body='b',
                                    scores={'role': 'alarmowy', 'loop': alarm.scores['loop'], 'key': alarm.scores['key'],
                                            'alerts': alarm.scores['alerts']})
    assert opiekunowie.repair(twin) == repair  # bez nowego wywołania modelu (iterator odpowiedzi jest pusty)
    assert twin not in opiekunowie.alarms_without_repair()


def test_cleanup_command_keeps_newest_per_key(monkeypatch):
    alerts = list(broken().values())
    alerts[0]['step'] = 'Recenzent'
    old = [AgentNote.objects.create(agent='opiekun', kind='audit', title=f'Diagnozy · alarmowy: {n} krok(i)', body='b',
                                    scores={'role': 'alarmowy', 'loop': 'Diagnozy', 'alerts': alerts}) for n in range(4)]
    fixes = [AgentNote.objects.create(agent='opiekun', kind='finding', title='Diagnozy · naprawiacz: 2 propozycji', body='b',
                                      scores={'role': 'naprawiacz', 'loop': 'Diagnozy', 'alarm': a.pk}) for a in old]
    other = AgentNote.objects.create(agent='opiekun', kind='idea', title='Spinki · usprawniacz: 3 usprawnień', body='b',
                                     scores={'role': 'usprawniacz', 'loop': 'Spinki'})
    stuck = AgentNote.objects.create(agent='architekt', kind='idea', title='Pomysł', body='b')
    SebaReview.objects.filter(note=stuck).update(last_error='Nieznana firma autora. Potrzebne dane modelu.')
    out = StringIO()
    call_command('porzadki_petli', stdout=out)
    assert 'duplikaty Opiekuna 6' in out.getvalue() and AgentNote.objects.filter(status='rejected').count() == 0
    call_command('porzadki_petli', '--wykonaj', stdout=StringIO())
    open_ids = set(AgentNote.objects.filter(agent='opiekun', status='new').values_list('pk', flat=True))
    assert open_ids == {old[-1].pk, fixes[-1].pk, other.pk}
    assert SebaReview.objects.get(note=fixes[0]).status == 'rejected'
    assert SebaReview.objects.get(note=stuck).last_error == ''


# --- Recenzent: TransactionManagementError ---------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_thread_review_enqueue_runs_in_own_transaction(monkeypatch):
    """6.10: Recenzent wołał enqueue() poza atomic(); select_for_update rzucał TransactionManagementError.
    SQLite nie rzuca tego błędu, więc sprawdzamy, że select_for_update dzieje się w otwartej transakcji."""
    from django.db import connection
    from news import thread_review
    seen = []

    class Rows:
        def select_for_update(self):
            seen.append(connection.in_atomic_block)
            return self

        def get_or_create(self, **kwargs):
            return SimpleNamespace(fingerprint='f', status='approved'), False

    monkeypatch.setattr(thread_review, 'snapshot', lambda thread, evidence: {'texts': {}})
    monkeypatch.setattr(thread_review, 'digest', lambda payload: 'f')
    monkeypatch.setattr(thread_review, '_apply', lambda review, visible: None)
    monkeypatch.setattr(thread_review.ThreadReview, 'objects', Rows())
    assert connection.get_autocommit()
    thread_review.enqueue(SimpleNamespace(signal_kind='x', refresh_from_db=lambda: None), {})
    assert seen == [True]


def test_failed_action_does_not_lose_review(monkeypatch):
    from news import recenzent
    items = [{'id': 'spinka:1', 'kind': 'spinka', 'url': 'https://spin.clinic/spinki/1', 'text': {'tytuł': 'X'}}]
    answers = iter([({'findings': [{'id': 'spinka:1', 'criterion': 2, 'severity': 'ważne', 'quote': 'X', 'problem': 'p', 'fix': 'f'}]}, COUNCIL[0]),
                    ({'remove': [], 'reason': 'ok'}, COUNCIL[1])])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))

    def boom(finding, item):
        from django.db.transaction import TransactionManagementError
        raise TransactionManagementError('select_for_update cannot be used outside of a transaction.')
    monkeypatch.setattr(recenzent, '_act', boom)
    note = recenzent.step(items=items)
    assert note.scores['findings'][0]['action'] == 'błąd akcji: TransactionManagementError'


# --- puls zadań ---------------------------------------------------------------------------------------------------

def sender(task):
    return SimpleNamespace(name=f'news.tasks.{task}', request=SimpleNamespace(id='1', args=(), kwargs={}))


def test_waiting_is_not_success_and_output_time_is_recorded():
    from news import task_heartbeat
    from news.daily_schedule import pulse
    task_heartbeat.succeeded(sender=sender('recenzent_task'), result={'status': 'waiting', 'reason': 'okno'})
    data = pulse('recenzent-2h')
    assert data['result'] == 'skipped' and 'last_success' not in data and 'last_output_at' not in data
    task_heartbeat.succeeded(sender=sender('recenzent_task'), result={'status': 'ok', 'note': None, 'produced': 0})
    data = pulse('recenzent-2h')
    assert data['result'] == 'ok' and data['last_produced'] == 0 and 'last_output_at' not in data
    task_heartbeat.succeeded(sender=sender('recenzent_task'), result={'status': 'ok', 'note': 5, 'produced': 1})
    assert pulse('recenzent-2h')['last_output_at'] and pulse('recenzent-2h')['last_produced'] == 1


def test_role_status_waiting_only_when_nothing_made():
    from news.tasks import role_status
    assert role_status({'alarmy': 0, 'usprawnienia': 'czeka: okno'}, counts=True)['status'] == 'waiting'
    assert role_status({'alarmy': 2, 'usprawnienia': 'czeka: okno'}, counts=True) == {'status': 'ok', 'failed': 0, 'waiting': 1, 'produced': 2}
    assert role_status({'kontroler': 41, 'prawnik': None})['produced'] == 1
    assert role_status({'kontroler': 'błąd: X'})['status'] == 'error'
