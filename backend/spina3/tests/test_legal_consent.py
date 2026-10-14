"""S2 pkt 7 i 9: zgoda art. 9 RODO z oświadczeniem 16+; wycofanie zgody: oceny bez wagi i autora (agregat zostaje),
komentarze odpięte od nicku i oznaczone do przeglądu; brak zgody: 403 consent; zgoda sprzed S2: 403 age tylko przy publikacji."""
from __future__ import annotations

import pytest

from spina3.comments import create_comment
from spina3.models import BoxSpinka, Comment, Rating, Spina3Profile

from .conftest import author_pin, make_box, make_user, rate, rated_box

pytestmark = pytest.mark.django_db


def test_consent_requires_age_16_plus(api):
    user = make_user('bez_zgody', consent=False)
    api.force_authenticate(user)
    r = api.post('/api/spina3/me/consent/', {'accepted': True}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'age'
    r = api.post('/api/spina3/me/consent/', {'accepted': True, 'age_16_plus': False}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'age'
    r = api.post('/api/spina3/me/consent/', {'accepted': True, 'age_16_plus': True}, format='json')
    assert r.status_code == 200 and r.json() == {'consent_art9': True, 'age_16_plus': True}
    profile = Spina3Profile.objects.get(user=user)
    assert profile.consent_art9_at and profile.age_16_plus_at
    assert api.get('/api/spina3/me/profile/').json()['age_16_plus'] is True


def test_no_consent_gives_403_consent_for_rating_and_comment(api):
    box, pin = rated_box(title='Box')
    user = make_user('bez_zgody_2', consent=False)
    api.force_authenticate(user)
    r = api.put(f'/api/spina3/pin/{pin.pk}/rating/', {'stance': 'agree'}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'consent'
    r = api.post(f'/api/spina3/box/{box.pk}/comments/', {'text': 'Komentarz bez zgody.'}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'consent'


def test_pre_s2_consent_without_age_blocks_only_new_publication(api):
    box, pin = rated_box(1, title='Box')
    user = make_user('stara_zgoda')
    rate(user, pin, -1)
    Spina3Profile.objects.filter(user=user).update(age_16_plus_at=None)
    api.force_authenticate(user)
    assert api.get(f'/api/spina3/box/{box.pk}/').status_code == 200
    assert api.get('/api/spina3/me/ratings/').status_code == 200
    r = api.post(f'/api/spina3/box/{box.pk}/comments/', {'text': 'Nowy komentarz.'}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'age'
    r = api.post('/api/spina3/boxes/', {'box': {'kind': 'box', 'target': str(make_box('Kotwica').pk)},
                                         'pin': {'kind': 'box', 'target': str(make_box('Dowód').pk)}}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'age'


def test_withdraw_consent_zeroes_weight_detaches_and_flags_comments(api):
    box, pin = rated_box(1, 1, 1, title='Box')
    user = make_user('wycofujacy')
    rating = rate(user, pin, -1)
    comment, _ = create_comment(user, box, 'Mój komentarz zostaje do przeglądu.')
    before = BoxSpinka.objects.get(box=box)
    assert before.n == 4 and before.weighted_n == 4
    api.force_authenticate(user)
    r = api.post('/api/spina3/me/consent/', {'accepted': False}, format='json')
    assert r.status_code == 200 and r.json()['ratings_detached'] == 1 and r.json()['comments_detached'] == 1
    rating.refresh_from_db()
    comment.refresh_from_db()
    assert rating.user is None and rating.account_weight == 0 and rating.anonymized and rating.status == 'active'
    after = BoxSpinka.objects.get(box=box)
    assert after.n == 4 and after.weighted_n == 3 and after.distribution == {'agree': 3, 'disagree': 1}
    assert comment.user is None and comment.needs_review and comment.text == 'Mój komentarz zostaje do przeglądu.'
    assert comment.status == 'visible'
    api.force_authenticate(None)
    items = api.get(f'/api/spina3/box/{box.pk}/comments/').json()['items']
    assert items[0]['author']['nick'] == 'Użytkownik usunięty' and 'wycofujacy' not in str(items)
    assert not Rating.objects.filter(user=user).exists() and not Comment.objects.filter(user=user).exists()
    profile = Spina3Profile.objects.get(user=user)
    assert profile.consent_art9_at is None and profile.age_16_plus_at is None
    api.force_authenticate(make_user('zespol_k', staff=True))
    queue = api.get('/api/spina3/moderation/queue/').json()
    assert queue['counts']['review_comments'] == 1 and queue['review_comments'][0]['id'] == comment.pk


def test_team_still_publishes_without_age(api):
    team = make_user('zespol_t', team=True, consent=False)
    pin = author_pin(team, make_box('Box zespołu'), make_box('Dowód zespołu'))
    assert pin.pk
