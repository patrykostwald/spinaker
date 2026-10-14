"""S2 pkt 8: wpis z X zawsze z autorem (nazwa i uchwyt) i source_url, treść niezmieniona; usunięty u źródła (oEmbed X,
najwyżej 60 wpisów na przebieg, podstawiony transport) traci treść w odpowiedziach."""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from spina3 import x_source
from spina3.models import Box

from .conftest import make_box

pytestmark = pytest.mark.django_db

TEXT = 'Oryginalna treść wpisu, bez zmian: 100% & "cudzysłów".'


def post_box(n=1, **kwargs):
    defaults = dict(kind='post', text=TEXT, quote=TEXT, author_name='Poseł Przykładowy', author_handle='posel',
                    url=f'https://x.com/posel/status/{1000 + n}', source_name='X', source_domain='x.com', added_by='dr_spin')
    defaults.update(kwargs)
    return make_box(f'Wpis {n}', **defaults)


def test_post_always_has_author_and_source_url_and_unchanged_text(api):
    box = post_box()
    nameless = post_box(2, author_name='')
    body = api.get(f'/api/spina3/box/{box.pk}/').json()
    assert body['author']['name'] == 'Poseł Przykładowy' and body['author']['handle'] == 'posel'
    assert body['source_url'] == box.url and body['text'] == TEXT and body['quote'] == TEXT
    assert api.get(f'/api/spina3/box/{nameless.pk}/').json()['author'] == {'name': '@posel', 'handle': 'posel', 'initials': '',
                                                                           'avatar_url': ''}


def test_oembed_404_removes_content_and_keeps_author(api):
    gone, alive = post_box(1), post_box(2)
    seen = []

    def transport(url):
        seen.append(url)
        return 404 if url == gone.url else 200
    out = x_source.check_posts(transport=transport)
    assert out == {'x_checked': 2, 'x_removed': 1, 'x_errors': 0} and set(seen) == {gone.url, alive.url}
    body = api.get(f'/api/spina3/box/{gone.pk}/').json()
    assert body['source_status'] == 'removed_at_source' and body['text'] == '' and body['quote'] == ''
    assert body['author']['handle'] == 'posel' and body['source_url'] == gone.url
    assert TEXT not in str(api.get('/api/spina3/boxes/search/?q=posel').json())
    assert api.get(f'/api/spina3/box/{alive.pk}/').json()['text'] == TEXT


def test_limit_60_per_run_oldest_checked_first():
    boxes = [post_box(i) for i in range(65)]
    calls = []
    assert x_source.check_posts(limit=500, transport=lambda url: calls.append(url) or 200)['x_checked'] == 60
    second = []
    x_source.check_posts(transport=lambda url: second.append(url) or 200)
    assert len(set(calls) | set(second)) == 65   # drugi przebieg zaczyna od niesprawdzonych
    assert Box.objects.filter(kind='post', source_checked_at__isnull=True).count() == 0 and len(boxes) == 65


def test_errors_do_not_remove(api):
    box = post_box()

    def broken(url):
        raise OSError('sieć')
    assert x_source.check_posts(transport=broken)['x_errors'] == 1
    assert x_source.check_posts(transport=lambda url: 429)['x_removed'] == 0
    box.refresh_from_db()
    assert box.source_status == 'active' and box.text == TEXT


def test_sync_command_runs_check_with_flag(monkeypatch):
    post_box()
    monkeypatch.setattr(x_source, 'oembed_status', lambda url: 404)
    out = StringIO()
    call_command('spina3_sync', '--bez-x', stdout=out)
    assert 'x_checked' not in out.getvalue()
    out = StringIO()
    call_command('spina3_sync', stdout=out)
    assert 'x_removed: 1' in out.getvalue()
