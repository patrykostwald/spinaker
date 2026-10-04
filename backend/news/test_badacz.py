import types

import pytest

from news import badacz

pytestmark = pytest.mark.django_db


def test_discovers_judges_and_serves_new_sources(monkeypatch):
    pages = {'https://nowe.pl/': '<html><head><title>Nowe Automaty</title><link rel="alternate" type="application/rss+xml" href="/feed"></head></html>',
             'https://sklep.pl/': '<html><head><link rel="alternate" type="application/rss+xml" href="https://sklep.pl/rss"></head></html>'}
    monkeypatch.setattr('requests.get', lambda url, **k: types.SimpleNamespace(text=pages.get(url, ''), content=url.encode()))

    def read(url, limit=5):
        if url in ('https://nowe.pl/feed', 'https://sklep.pl/rss'):
            return [{'title': 'wpis', 'url': url + '#1', 'summary': ''}]
        return [{'title': 't', 'url': 'https://nowe.pl/a', 'summary': 'zobacz https://sklep.pl/promo'}]
    monkeypatch.setattr(badacz, 'read', read)
    monkeypatch.setattr(badacz, '_seeds', lambda: {'https://seed.example/feed': {'name': 'Seed', 'topic': 'automatyzacja', 'status': 'nasiono', 'fails': 0, 'added': None}})
    monkeypatch.setattr('news.agents_common.ask_any', lambda prompt, data, *a, **k: (
        {'keep': [n['n'] for n in data['candidates'] if 'nowe' in n['site']], 'reason': 'ok'}, ('groq', 'a')))
    out = badacz.step(force=True)
    assert out['kandydaci'] == 2 and out['przyjęte'] == 1
    assert list(badacz.feeds('automatyzacja').values()) == ['https://nowe.pl/feed']
    data = badacz.load()
    assert data['https://sklep.pl/rss']['status'] == 'odrzucone'


def test_dead_feed_sleeps_after_three_failures(monkeypatch):
    monkeypatch.setattr(badacz, '_seeds', lambda: {'https://martwe.example/feed': {'name': 'M', 'topic': 'ux', 'status': 'nasiono', 'fails': 0, 'added': None}})
    monkeypatch.setattr(badacz, 'read', lambda url, limit=5: (_ for _ in ()).throw(RuntimeError('404')))
    for _ in range(3):
        badacz.step(force=True)
    assert badacz.load()['https://martwe.example/feed']['status'] == 'uśpione'
