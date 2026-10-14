"""S2 pkt 6: żaden publiczny endpoint nie ujawnia ocen jednostkowych (kto jak ocenił); my_rating tylko dla właściciela sesji;
public_profiles=false ukrywa u/{nick}/ (404). Test przechodzi po KAŻDEJ trasie z spina3/urls.py jako gość."""
from __future__ import annotations

import json

import pytest
from django.urls import URLPattern

from spina3 import urls as spina3_urls
from spina3.comments import create_comment
from spina3.models import BoxLink
from spina3.ranking import build_snapshot

from .conftest import make_box, make_user, rate, rated_box

pytestmark = pytest.mark.django_db

FORBIDDEN_KEYS = {'raters', 'voters', 'rated_by', 'ratings_list'}
RATING_KEYS = {'stance', 'user'}


def walk(node, path='$'):
    """Zwraca naruszenia: lista ocen, pola raters/voters, ocena z użytkownikiem."""
    problems = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f'{path}.{key}'
            if key in FORBIDDEN_KEYS:
                problems.append(here)
            if key == 'ratings' and isinstance(value, list):
                problems.append(here + ' (lista ocen)')
            if key in ('user', 'user_id') and ('stance' in node or path.endswith('ratings')):
                problems.append(here + ' (użytkownik przy ocenie)')
            problems += walk(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            problems += walk(value, f'{path}[{index}]')
    return problems


def values(node, key):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from values(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from values(v, key)


def fill(pattern: str, ids: dict) -> str:
    out = pattern
    for name, value in ids.items():
        for conv in ('int', 'str'):
            out = out.replace(f'<{conv}:{name}>', str(value))
    return '/api/spina3/' + out


@pytest.fixture
def world():
    rater = make_user('oceniajacy_jawny')
    box, pin = rated_box(1, -1, 1, title='Box z ocenami', persons=[{'id': 5, 'name': 'Osoba Publiczna'}], topic='zdrowie',
                         raters=[rater, make_user('drugi_o'), make_user('trzeci_o')])
    diag = make_box('Diagnoza', kind='diagnosis')
    BoxLink.objects.create(box=box, target=diag, kind='diagnosis_of')
    comment, _ = create_comment(rater, box, 'Komentarz oceniającego.')
    build_snapshot()
    return {'box_id': box.pk, 'pin_id': pin.pk, 'comment_id': comment.pk, 'nick': pin.user.username, 'decision_id': 1,
            'report_id': 1, 'appeal_id': 1, 'check_id': 1, 'correction_id': 1, 'topic': 'zdrowie', 'person_id': 5}, rater


def test_every_route_as_guest_reveals_no_individual_ratings(api, world):
    ids, rater = world
    checked = 0
    for entry in spina3_urls.urlpatterns:
        assert isinstance(entry, URLPattern)
        url = fill(str(entry.pattern), ids)
        response = api.get(url)
        assert response.status_code in (200, 401, 403, 404, 405), (url, response.status_code)
        if response.status_code != 200:
            continue
        checked += 1
        content = response.content.decode('utf-8')
        assert 'oceniajacy_jawny' not in content or url.endswith('/comments/'), url   # nick oceniającego tylko jako autor komentarza
        if response['Content-Type'].startswith('application/json'):
            body = json.loads(content)
            assert walk(body) == [], (url, walk(body))
            assert all(value is None for value in values(body, 'my_rating')), url   # gość nie ma "mojej oceny"
    assert checked >= 10
    comments = api.get(f"/api/spina3/box/{ids['box_id']}/comments/").json()
    assert all('stance' not in item and 'rating' not in json.dumps(item['author']) for item in comments['items'])


def test_my_rating_only_for_session_owner(api, world):
    ids, rater = world
    api.force_authenticate(rater)
    assert api.get(f"/api/spina3/box/{ids['box_id']}/").json()['my_rating'] == 'agree'
    api.force_authenticate(make_user('obcy_o'))
    body = api.get(f"/api/spina3/box/{ids['box_id']}/").json()
    assert body['my_rating'] is None and body['pin']['my_rating'] is None
    assert all(item['my_rating'] is None for item in api.get('/api/spina3/wall/').json()['items'])
    api.force_authenticate(None)
    assert api.get('/api/spina3/me/ratings/').status_code in (401, 403)


def test_public_profiles_flag(api, world, spina3_settings):
    ids, rater = world
    assert api.get(f"/api/spina3/u/{ids['nick']}/").status_code == 404
    spina3_settings.SPINA3 = {**spina3_settings.SPINA3, 'flags': {**spina3_settings.SPINA3['flags'], 'public_profiles': True}}
    response = api.get(f"/api/spina3/u/{ids['nick']}/")
    assert response.status_code == 200
    body = response.json()
    assert body['nick'] == ids['nick'] and len(body['boxes']) == 1 and walk(body) == []
    assert 'oceniajacy_jawny' not in response.content.decode('utf-8')
    assert api.get('/api/spina3/u/nie_ma_takiego/').status_code == 404
