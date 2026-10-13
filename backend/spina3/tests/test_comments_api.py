"""Komentarze pod parą box + przypięcie (v2): jeden poziom odpowiedzi, "przydatny", sortowanie, kursor, antyspam, cisza, znaczki."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from spina3.models import Comment, CommentVote

from .conftest import author_pin, make_box, make_user

pytestmark = pytest.mark.django_db


def post_comment(api, user, box, text, parent=None):
    api.force_authenticate(user)
    body = {'text': text}
    if parent is not None:
        body['parent'] = parent
    return api.post(f'/api/spina3/box/{box.pk}/comments/', body, format='json')


def test_create_list_reply_one_level_and_badges(api):
    author, box, thing = make_user('autor'), make_box('Box'), make_box('Rzecz')
    author_pin(author, box, thing)
    reader = make_user('czytelnik')
    r = post_comment(api, reader, box, 'Druk mówi coś innego niż wpis.')
    assert r.status_code == 201, r.json()
    root = r.json()['comment']
    assert root['status'] == 'visible' and root['author']['badge'] == '' and root['author']['color'] == 'ash'
    reply = post_comment(api, author, box, 'Dlatego przypiąłem ten druk.', parent=root['id'])
    assert reply.status_code == 201 and reply.json()['comment']['author']['badge'] == 'author'
    # odpowiedź do odpowiedzi: 400 (jeden poziom)
    r = post_comment(api, reader, box, 'A jednak.', parent=reply.json()['comment']['id'])
    assert r.status_code == 400 and r.json()['code'] == 'parent'
    team = post_comment(api, make_user('zespol', team=True), box, 'Kontekst: druk z 2024 r.')
    assert team.json()['comment']['author']['badge'] == 'team'
    api.force_authenticate(None)
    body = api.get(f'/api/spina3/box/{box.pk}/comments/').json()
    assert body['total'] == 3 and body['sort'] == 'newest'
    first = next(i for i in body['items'] if i['id'] == root['id'])
    assert first['reply_count'] == 1 and first['replies'][0]['text'] == 'Dlatego przypiąłem ten druk.'
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['comment_count'] == 3


def test_dr_spin_badge_and_cannot_comment(api):
    from spina3.importer import dr_spin_user
    from spina3.public import author_info
    spin = dr_spin_user()
    info = author_info(spin)
    assert info['badge'] == 'dr_spin' and info['color'] == 'spin'
    r = post_comment(api, spin, make_box('Box'), 'Komentarz systemowy.')
    assert r.status_code == 403


def test_helpful_once_not_own_and_top_sort(api):
    box = make_box('Box')
    a, b, c = make_user('ka'), make_user('kb'), make_user('kc')
    first = post_comment(api, a, box, 'Pierwszy komentarz.').json()['comment']
    second = post_comment(api, b, box, 'Drugi komentarz.').json()['comment']
    api.force_authenticate(a)
    assert api.put(f"/api/spina3/comment/{first['id']}/helpful/").status_code == 403      # własny
    for voter in (a, c):
        api.force_authenticate(voter)
        r = api.put(f"/api/spina3/comment/{second['id']}/helpful/")
        assert r.status_code == 200 and r.json()['my_helpful'] is True
    api.force_authenticate(c)
    assert api.put(f"/api/spina3/comment/{second['id']}/helpful/").json()['helpful_count'] == 2   # drugi raz bez zmian
    assert CommentVote.objects.filter(comment_id=second['id']).count() == 2
    top = api.get(f'/api/spina3/box/{box.pk}/comments/', {'sort': 'top'}).json()['items']
    assert [i['id'] for i in top] == [second['id'], first['id']] and top[0]['my_helpful'] is True
    newest = api.get(f'/api/spina3/box/{box.pk}/comments/').json()['items']
    assert newest[0]['id'] == second['id']
    r = api.delete(f"/api/spina3/comment/{second['id']}/helpful/")
    assert r.status_code == 200 and r.json()['helpful_count'] == 1


def test_cursor_pagination_without_duplicates(api):
    box = make_box('Box')
    users = [make_user(f'p{i}') for i in range(7)]
    now = timezone.now()
    for i, u in enumerate(users):
        Comment.objects.create(box=box, user=u, text=f'Komentarz {i}', created_at=now - timedelta(minutes=i))
    seen, cursor = [], None
    while True:
        params = {'limit': 3, **({'cursor': cursor} if cursor else {})}
        body = api.get(f'/api/spina3/box/{box.pk}/comments/', params).json()
        seen.extend(i['id'] for i in body['items'])
        cursor = body['next_cursor']
        if not cursor:
            break
    assert len(seen) == 7 == len(set(seen))
    assert api.get(f'/api/spina3/box/{box.pk}/comments/', {'cursor': '***'}).status_code == 400


def test_edit_and_remove_own_only(api):
    box, owner, other = make_box('Box'), make_user('own'), make_user('oth')
    c = post_comment(api, owner, box, 'Pierwsza wersja.').json()['comment']
    api.force_authenticate(other)
    assert api.patch(f"/api/spina3/comment/{c['id']}/", {'text': 'cudza'}, format='json').status_code == 403
    assert api.delete(f"/api/spina3/comment/{c['id']}/").status_code == 403
    api.force_authenticate(owner)
    r = api.patch(f"/api/spina3/comment/{c['id']}/", {'text': 'Druga wersja.'}, format='json')
    assert r.status_code == 200 and r.json()['comment']['text'] == 'Druga wersja.' and r.json()['comment']['edited_at']
    assert api.delete(f"/api/spina3/comment/{c['id']}/").status_code == 204
    assert Comment.objects.get(pk=c['id']).status == 'removed'
    assert api.get(f'/api/spina3/box/{box.pk}/comments/').json()['total'] == 0


def test_antispam_prefilter_link_duplicate_and_limits(api, spina3_settings):
    box, user = make_box('Box'), make_user('spam')
    r = post_comment(api, user, box, 'PESEL 44051401359')
    assert r.status_code == 400
    r = post_comment(api, user, box, 'pisz na jan@example.org')
    assert r.status_code == 201 and r.json()['comment_status'] == 'held' and r.json()['message']
    young = make_user('mlody', days_old=2, tier='')
    r = post_comment(api, young, box, 'Zobacz https://example.org/x')
    assert r.json()['comment_status'] == 'held'                           # T1 z linkiem: czeka na sprawdzenie
    api.force_authenticate(None)
    assert api.get(f'/api/spina3/box/{box.pk}/comments/').json()['items'] == []   # wstrzymane niewidoczne publicznie
    assert post_comment(api, user, box, 'Ten sam tekst.').status_code == 201
    r = post_comment(api, user, box, 'Ten sam tekst.')
    assert r.status_code == 409 and r.json()['code'] == 'duplicate'
    spina3_settings.SPINA3['scoring']['burst_max_comments'] = 100
    spina3_settings.SPINA3['scoring']['daily_comments'] = {'T0': 0, 'T1': 1, 'T2': 2, 'T3': 2, 'team': 10}
    limited = make_user('limit')
    codes = [post_comment(api, limited, box, f'Komentarz {i}.').status_code for i in range(3)]
    assert codes == [201, 201, 429]
    assert post_comment(api, make_user('t0k', verified=False), box, 'Bez e-maila.').json()['code'] == 'tier'
    assert post_comment(api, make_user('bezzgody', consent=False), box, 'Bez zgody.').json()['code'] == 'consent'


def test_burst_limit(api, spina3_settings):
    spina3_settings.SPINA3['scoring']['burst_max_comments'] = 2
    box, user = make_box('Box'), make_user('fast')
    assert [post_comment(api, user, box, f'Szybki {i}.').status_code for i in range(3)] == [201, 201, 429]


def test_election_silence_and_flag(api, spina3_settings):
    box, user = make_box('Box'), make_user('cisza')
    now = timezone.now()
    spina3_settings.SPINA3['flags'].update({'election_silence_start': (now - timedelta(hours=1)).isoformat(),
                                            'election_silence_end': (now + timedelta(days=1)).isoformat()})
    assert post_comment(api, user, box, 'W ciszy, flaga wyłączona.').status_code == 201
    spina3_settings.SPINA3['flags']['election_silence_pause_comments'] = True
    r = post_comment(api, user, box, 'W ciszy, flaga włączona.')
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'
    spina3_settings.SPINA3['flags']['comments_enabled'] = False
    assert post_comment(api, user, box, 'Wyłączone.').json()['code'] == 'comments_disabled'


def test_moderation_hide_requires_reason_and_restore_held(api):
    box, user, staff = make_box('Box'), make_user('mk'), make_user('staffk', staff=True)
    held = post_comment(api, user, box, 'kontakt jan@example.org').json()['comment']
    api.force_authenticate(staff)
    queue = api.get('/api/spina3/moderation/queue/').json()
    assert any(c['id'] == held['id'] for c in queue['held_comments'])
    assert api.post(f"/api/spina3/moderation/comments/{held['id']}/", {'decision': 'hide', 'reason': ''}, format='json').status_code == 400
    r = api.post(f"/api/spina3/moderation/comments/{held['id']}/", {'decision': 'restore', 'reason': 'Adres instytucji, nie osoby.'}, format='json')
    assert r.status_code == 200 and Comment.objects.get(pk=held['id']).status == 'visible'
    r = api.post(f"/api/spina3/moderation/comments/{held['id']}/", {'decision': 'hide', 'reason': 'Spam.'}, format='json')
    assert r.status_code == 200 and Comment.objects.get(pk=held['id']).hidden_reason == 'Spam.'
    api.force_authenticate(user)
    assert api.post(f"/api/spina3/moderation/comments/{held['id']}/", {'decision': 'restore', 'reason': 'x'}, format='json').status_code == 403


def test_anonymize_removes_comment_text():
    from spina3.comments import create_comment
    from spina3.pins import anonymize_user
    box, user = make_box('Box'), make_user('anonk')
    comment, _ = create_comment(user, box, 'Mój komentarz.')
    anonymize_user(user)
    comment.refresh_from_db()
    assert comment.user is None and comment.text == '' and comment.status == 'removed'
