import pytest

from news import tasks
from news.models import ImportState


@pytest.mark.django_db
def test_live_public_roster_task_runs_each_official_roster_independently(monkeypatch):
    calls = []

    def command(name, *args, **kwargs):
        calls.append((name, kwargs['source']))
        if name == 'sync_parliamentary_roster' and kwargs['source'] == 'senat':
            raise RuntimeError('temporary official endpoint error')

    monkeypatch.setattr(tasks, 'call_command', command)
    result = tasks.sync_live_public_rosters_task()

    assert result['status'] == 'partial'
    assert ('senat-roster', 'RuntimeError') in [(item['roster'], item['error']) for item in result['failed']]
    assert ('ep-profiles') in result['completed']
    state = ImportState.objects.get(name='public-figure:live-rosters')
    assert state.cursor['status'] == 'partial'
    assert calls[-1] == ('sync_public_figures', 'cabinet')
