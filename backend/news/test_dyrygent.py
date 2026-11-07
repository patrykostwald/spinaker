import pytest
from django.core.cache import cache

from news import agents_common, dyrygent
from news.agent_models import AgentNote, BuildTicket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    cache.clear()
    monkeypatch.setattr('news.agents_common.notify', lambda note: True)


@pytest.mark.parametrize('free,mode', [(.9, 'pełny'), (.3, 'oszczędny'), (.1, 'strażnicy')])
def test_mode_follows_free_capacity_and_hierarchy(monkeypatch, free, mode):
    monkeypatch.setattr(dyrygent, 'capacity', lambda: free)
    assert dyrygent.decide()[0] == mode
    assert dyrygent.allowed('strażnicy') and dyrygent.allowed('nauka') == (mode == 'pełny')
    assert dyrygent.allowed('rozwój') == (mode != 'strażnicy')


def test_ask_any_waits_for_learning_in_saving_mode(monkeypatch):
    monkeypatch.setattr(dyrygent, 'capacity', lambda: .3)
    dyrygent.decide()
    with dyrygent.tier('nauka'):
        with pytest.raises(agents_common.WindowClosed, match='Dyrygent'):
            agents_common.ask_any('p', {}, {})


def test_plan_lists_collisions_and_queue(monkeypatch):
    monkeypatch.setattr(dyrygent, 'capacity', lambda: .8)
    monkeypatch.setattr('news.daily_schedule.BEAT_PLAN', {'a': ('automatyk_task', {'hour': 6, 'minute': 30}),
                                                          'b': ('badacz_task', {'hour': 6, 'minute': 35})})
    source = AgentNote.objects.create(agent='architekt', kind='idea', title='Profil osoby', body='', score=90, scores={'effort': 'M'})
    BuildTicket.objects.create(note=source, title='Profil osoby', effort='M', status='approved')
    note = dyrygent.plan(force=True)
    assert note.scores['collisions'] == [{'okno': '06:30', 'zadania': ['automatyk_task', 'badacz_task']}]
    assert note.scores['queue'][0]['title'] == 'Profil osoby' and 'Kolejka budowy' in note.body
