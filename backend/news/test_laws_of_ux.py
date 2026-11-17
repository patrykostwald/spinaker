import types

import pytest

from news import laws_of_ux, projektant

pytestmark = pytest.mark.django_db


def test_thirty_laws_in_projektant_guide():
    assert len(laws_of_ux.LAWS) == 30
    assert sum(line.startswith('Laws of UX') for line in projektant.guide()) == 30


def test_weekly_check_detects_new_law(monkeypatch):
    pages = {laws_of_ux.SITE: '<a href="https://lawsofux.com/fittss-law/">x</a>',
             'https://lawsofux.com/fittss-law/': "<h1>Fitts's Law</h1><h2>Key Takeaways</h2><ul><li>Big targets.</li></ul>"}
    monkeypatch.setattr('requests.get', lambda url, **k: types.SimpleNamespace(text=pages[url]))
    assert laws_of_ux.check()[0] == []  # pierwszy przebieg tylko zapisuje
    pages[laws_of_ux.SITE] += '<a href="https://lawsofux.com/new-law/">y</a>'
    pages['https://lawsofux.com/new-law/'] = '<h1>New Law</h1><h2>Key Takeaways</h2><ul><li>Fresh.</li></ul>'
    changes, data = laws_of_ux.check()
    assert changes == ['Nowe prawo: New Law'] and laws_of_ux.takeaways()["Fitts's Law"] == ['Big targets.']
