"""Odczyt v2: ściana z migawką i kursorem, 50 ocen w trakcie bez duplikatów i braków, wymiary, szukanie, półka."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from spina3 import ranking
from spina3.models import Box, BoxLink, BoxSpinka, Pin, RankingSnapshot

from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


def seed(n_boxes=120, raters=6):
    boxes = [make_box(f'Box {i}', kind=('post' if i % 3 == 0 else 'article'), topic=('podatki' if i % 2 else 'zdrowie'),
                      persons=[{'id': 1 + i % 4, 'name': f'Osoba {1 + i % 4}'}]) for i in range(n_boxes)]
    users = [make_user(f'r{i}') for i in range(raters)]
    thing = make_box('Rzecz wspólna')
    author = make_user('autor_seed')
    for i, box in enumerate(boxes[:60]):
        p = author_pin(author, box, thing)
        for u in users[: 3 + (i % 4)]:
            rate(u, p, 1 if i % 5 else -1)
    return boxes, users, thing


def collect(api, params):
    seen, cursor, pages = [], None, 0
    while True:
        r = api.get('/api/spina3/wall/', {**params, **({'cursor': cursor} if cursor else {})})
        assert r.status_code == 200, r.content
        body = r.json()
        seen.extend(item['id'] for item in body['items'])
        pages += 1
        cursor = body['next_cursor']
        if not cursor or pages > 50:
            return seen, body


def test_wall_sections_order_and_cursor_roundtrip(api):
    boxes, users, thing = seed()
    ids, last = collect(api, {'sort': 'level', 'limit': 48})
    wall_ids = {b.pk for b in boxes} | {thing.pk}
    assert len(ids) == len(set(ids)) and set(ids) == wall_ids
    assert last['wall_end'] and 'To wszystko' in last['end_message']
    levels = [BoxSpinka.objects.filter(box_id=i).values_list('level', flat=True).first() or 'open' for i in ids]
    order = {'P5': 0, 'P4': 1, 'P3': 2, 'P2': 3, 'P1': 4, 'open': 5}
    assert [order[l] for l in levels] == sorted(order[l] for l in levels)   # sekcje P5..P1, Otwarta na końcu
    first = api.get('/api/spina3/wall/', {'sort': 'level', 'limit': 10}).json()
    assert first['sections'] and first['version'] and 'today' in first


def test_cursor_stable_while_50_pins_arrive(api):
    boxes, users, thing = seed()
    first = api.get('/api/spina3/wall/', {'sort': 'level', 'limit': 24}).json()
    version = first['version']
    ids = [i['id'] for i in first['items']]
    cursor = first['next_cursor']
    # 50 nowych ocen w trakcie przewijania (zmieniają poziomy i last_rating_at) i 10 nowych boxów z przypięciem
    extra = make_user('x0')
    for box in boxes[:50]:
        rate(extra, Pin.objects.get(box=box), -1)
    for box in boxes[60:70]:
        author_pin(extra, box, thing)
    while cursor:
        body = api.get('/api/spina3/wall/', {'sort': 'level', 'limit': 24, 'cursor': cursor}).json()
        assert body['version'] == version                 # klient trzyma wersję migawki
        ids.extend(i['id'] for i in body['items'])
        cursor = body['next_cursor']
    assert len(ids) == len(set(ids)) == len(boxes) + 1       # bez duplikatów i bez braków


def test_expired_snapshot_resumes_by_key(api, spina3_settings):
    boxes, users, thing = seed(n_boxes=60)
    first = api.get('/api/spina3/wall/', {'sort': 'level', 'limit': 20}).json()
    cursor = first['next_cursor']
    RankingSnapshot.objects.filter(pk=first['version']).delete()
    body = api.get('/api/spina3/wall/', {'sort': 'level', 'limit': 20, 'cursor': cursor}).json()
    assert body['version'] != first['version']
    assert not (set(i['id'] for i in body['items']) & set(i['id'] for i in first['items']))


def test_default_sort_newest_until_rated_share(api, spina3_settings):
    boxes = [make_box(f'N{i}') for i in range(20)]
    body = api.get('/api/spina3/wall/').json()
    assert body['sort'] == 'newest' and body['sections'] == []
    ids = [i['id'] for i in body['items']]
    assert ids == sorted(ids, key=lambda i: -Box.objects.get(pk=i).published_at.timestamp())
    thing = make_box('Rzecz')
    users = [make_user(f'ns{i}') for i in range(3)]
    author = make_user('ns_autor')
    for box in boxes[:3]:
        p = author_pin(author, box, thing)
        for u in users:
            rate(u, p, 1)
    RankingSnapshot.objects.all().delete()
    body = api.get('/api/spina3/wall/').json()
    assert body['sort'] == 'level' and body['rated_share'] >= 0.1


def test_filters_type_topic_person_level_with_diagnosis(api):
    boxes, users, thing = seed(n_boxes=40)
    diag = make_box('Diagnoza X', kind='diagnosis')
    BoxLink.objects.create(box=boxes[0], target=diag, kind='diagnosis_of')
    RankingSnapshot.objects.all().delete()
    posts = api.get('/api/spina3/wall/', {'type': 'post', 'limit': 48}).json()['items']
    assert posts and all(i['kind'] == 'post' for i in posts)
    topic = api.get('/api/spina3/wall/', {'topic': 'podatki', 'limit': 48}).json()['items']
    assert topic and all(i['topic'] == 'podatki' for i in topic)
    person = api.get('/api/spina3/wall/', {'person': '2', 'limit': 48}).json()['items']
    assert person and all(any(p['id'] == 2 for p in i['persons']) for i in person)
    lv = api.get('/api/spina3/wall/', {'level': 'P4', 'sort': 'level', 'limit': 48}).json()['items']
    assert lv and all(i['spinka']['level'] == 'P4' for i in lv)
    with_d = api.get('/api/spina3/wall/', {'with_diagnosis': 'true'}).json()['items']
    assert [i['id'] for i in with_d] == [boxes[0].pk] and with_d[0]['has_diagnosis']


def test_facets_counts_and_min_share(api):
    seed(n_boxes=40)
    body = api.get('/api/spina3/facets/').json()
    dims = body['dimensions']
    assert set(dims) >= {'person', 'topic', 'period', 'level'}
    assert 'with_diagnosis' not in dims             # 0% boxów z diagnozą: wymiar nie istnieje
    assert sum(v['count'] for v in dims['topic']['values']) == body['total'] - 1   # "Rzecz wspólna" bez tematu
    assert dims['period']['default'] == '90'


def test_search_normalizes_polish_and_suggests(api):
    make_box('Żyłka wędkarska w Sejmie')
    make_box('Zupełnie inny temat')
    body = api.get('/api/spina3/boxes/search/', {'q': 'zylka'}).json()
    assert [i['title'] for i in body['items']] == ['Żyłka wędkarska w Sejmie']
    assert body['items'][0]['spinka']['level'] == 'open'
    body = api.get('/api/spina3/boxes/search/', {'q': 'wedk'}).json()
    assert 'wędkarska' in body['suggestions']
    assert api.get('/api/spina3/boxes/search/', {'q': 'a'}).json()['items'] == []


def test_box_detail_rights_flags_and_related(api):
    post = make_box('Wpis posła', kind='post', text='Pełna treść wpisu.', author_name='Poseł Przykładowy', author_handle='posel', topic='zdrowie',
                    persons=[{'id': 7, 'name': 'Poseł Przykładowy'}], show_quote=True)
    diag = make_box('Diagnoza: wpis', kind='diagnosis', text='Diagnoza.', topic='zdrowie', persons=post.persons)
    doc = make_box('Druk 123', kind='document', subtype='druk sejmowy', text='Treść druku', topic='zdrowie')
    BoxLink.objects.create(box=post, target=diag, kind='diagnosis_of')
    BoxLink.objects.create(box=post, target=doc, kind='evidence_of')
    same_topic = [make_box(f'Artykuł {i}', topic='zdrowie') for i in range(6)]
    press = make_box('Artykuł bez praw', quote='Lead chroniony', thumbnail_url='https://example.org/t.jpg', show_quote=False, show_thumbnail=False)
    body = api.get(f'/api/spina3/box/{post.pk}/').json()
    assert body['text'] == 'Pełna treść wpisu.' and body['author']['initials'] == 'PP' and body['author']['avatar_url'] == ''
    assert body['portals']['spina3_url'].endswith(f'/box/{post.pk}/') and body['question'] == 'Ten box nie ma jeszcze przypięcia.'
    assert body['has_diagnosis'] and body['diagnosis_history'][0]['current']
    related = api.get(f'/api/spina3/box/{post.pk}/related/').json()['items']
    assert [i['id'] for i in related[:2]] == [diag.pk, doc.pk] and len(related) == 6
    body = api.get(f'/api/spina3/box/{press.pk}/').json()
    assert body['quote'] == '' and body['thumbnail_url'] == '' and body['title'] == 'Artykuł bez praw'
    assert api.get('/api/spina3/box/999999/').status_code == 404


def test_levels_hidden_during_silence_and_calibration(api, spina3_settings):
    boxes, users, thing = seed(n_boxes=10)
    item = api.get('/api/spina3/wall/', {'sort': 'level'}).json()['items'][0]
    assert item['spinka']['level'] != 'open'
    spina3_settings.SPINA3['flags']['levels_visible'] = False
    item = api.get('/api/spina3/wall/', {'sort': 'level'}).json()['items'][0]
    assert item['spinka']['level'] == 'open' and item['spinka']['reason'] == 'calibration' and item['spinka']['n'] > 0
    spina3_settings.SPINA3['flags']['levels_visible'] = True
    now = timezone.now()
    spina3_settings.SPINA3['flags'].update({'election_silence_start': (now - timedelta(hours=1)).isoformat(),
                                            'election_silence_end': (now + timedelta(days=1)).isoformat()})
    body = api.get('/api/spina3/wall/', {'sort': 'level'}).json()
    assert body['sort'] == 'newest' and body['election_silence'] and body['items'][0]['spinka']['label'] == 'cisza wyborcza'
    feed = api.get('/api/spina3/feed/wall.xml')
    assert feed.status_code == 200 and 'wstrzymany' in feed.content.decode()


def test_feed_wall_lists_titles_only(api):
    make_box('Wpis do kanału', kind='post', text='Pełna treść nie trafia do RSS')
    body = api.get('/api/spina3/feed/wall.xml').content.decode()
    assert 'Wpis do kanału' in body and 'Pełna treść nie trafia' not in body


def test_my_rating_and_pin_summary_in_wall_for_logged_user(api):
    user, author, box, thing = make_user('ms'), make_user('ms_autor'), make_box('Box'), make_box('Rzecz')
    p = author_pin(author, box, thing, comment='Druk przeczy tezie.')
    rate(user, p, -1)
    api.force_authenticate(user)
    item = next(i for i in api.get('/api/spina3/wall/').json()['items'] if i['id'] == box.pk)
    assert item['my_rating'] == 'disagree' and item['pin']['author']['nick'] == 'ms_autor'
    assert item['pin']['target_box_id'] == thing.pk and item['pin']['comment'] == 'Druk przeczy tezie.' and item['comment_count'] == 0
    api.force_authenticate(None)
    item = next(i for i in api.get('/api/spina3/wall/').json()['items'] if i['id'] == box.pk)
    assert item['my_rating'] is None


def test_top_cap_per_author_in_p5_section():
    cfg_entries = [{'id': i, 'level': 'P5', 'lp': 100 - i, 'n': 10, 'pub': 0, 'kind': 'post', 'sub': '', 'topic': '', 'persons': [],
                    'diag': False, 'author': 'a' if i < 5 else f'u{i}', 'group': 'Partia A' if i < 5 else '', 'domain': '', 'added': 0, 'by': 'dr_spin'}
                   for i in range(8)]
    from spina3.config import ScoringConfig
    out = ranking.apply_top_cap(cfg_entries, ScoringConfig(first_screen=6))
    assert [e['id'] for e in out[:4]] == [0, 1, 5, 6]     # autor 'a' najwyżej 2 razy na pierwszym ekranie


def test_today_row_prefers_posts_with_diagnosis_and_caps_author(api):
    now = timezone.now()
    since, until = ranking.today_cutoff(now)          # okno: od wczorajszej godziny odcięcia do dzisiejszej
    diag_post = make_box('Wpis z diagnozą', kind='post', added_by='dr_spin', author_handle='a', created_at=until - timedelta(hours=2))
    BoxLink.objects.create(box=diag_post, target=make_box('D', kind='diagnosis', added_by='dr_spin', created_at=until - timedelta(hours=2)), kind='diagnosis_of')
    for i in range(4):
        make_box(f'Wpis {i}', kind='post', added_by='dr_spin', author_handle='b', created_at=until - timedelta(hours=1))
    doc = make_box('Druk', kind='document', added_by='importer', created_at=until - timedelta(hours=3))
    make_box('Po odcięciu', kind='post', added_by='dr_spin', author_handle='c', created_at=until + timedelta(minutes=1))
    row = ranking.today_row(now)
    assert all(r['author'] is None or r['author']['handle'] != 'c' for r in row)   # jutro
    assert row[0]['id'] == diag_post.pk and row[1]['id'] == doc.pk
    assert sum(1 for r in row if r['author'] and r['author']['handle'] == 'b') == 2
