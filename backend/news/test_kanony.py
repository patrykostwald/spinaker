import types

import pytest

from news import kanony, projektant

pytestmark = pytest.mark.django_db


def test_start_canons_reach_agents():
    lines = ' '.join(projektant.guide())
    assert 'Kanon: GoodUI' in lines and 'Kanon: WCAG' in lines
    assert any('SRE' in c for c in kanony.canons('automatyzacja'))


def test_hunt_adds_only_live_and_approved(monkeypatch):
    monkeypatch.setattr(kanony, 'CANONS', {'ux': [('Laws of UX', 'https://lawsofux.com/', 'x')]})
    monkeypatch.setattr('requests.get', lambda url, **k: types.SimpleNamespace(status_code=200 if 'dobre' in url else 404, text='<title>Zasady</title>'))
    answers = iter([({'canons': [{'name': 'Dobre zasady', 'url': 'https://dobre.example/', 'what': 'zasady'},
                                 {'name': 'Martwe', 'url': 'https://martwe.example/', 'what': '-'}]}, ('groq', 'a')),
                    ({'keep': [0], 'reason': 'ok'}, ('nim', 'b'))])
    monkeypatch.setattr('news.agents_common.ask_any', lambda *a, **k: next(answers))
    assert kanony.hunt(force=True) == {'ux': ['Dobre zasady']}
    assert any('Dobre zasady' in c for c in kanony.canons('ux'))
