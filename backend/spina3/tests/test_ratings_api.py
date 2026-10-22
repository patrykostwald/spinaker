"""Oceny przypięcia autora (v2): dwa stany, jedna na użytkownika, zmiana i wycofanie, S z ocen, limity, antysybil, profil."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from spina3 import spinka
from spina3.models import BoxSpinka, PinEvent, Rating, Spina3Profile

from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


def put_rating(api, user, pin, stance):
    api.force_authenticate(user)
    return api.put(f'/api/spina3/pin/{pin.pk}/rating/', {'stance': stance}, format='json')


def setup():
    author, box, thing = make_user('autor'), make_box('Box'), make_box('Rzecz')
    return author, box, author_pin(author, box, thing)


def test_three_agree_make_p4_and_response_has_spinka(api):
    author, box, p = setup()
    for i in range(3):
        r = put_rating(api, make_user(f'u{i}'), p, 'agree')
        assert r.status_code == 200, r.json()
    body = r.json()
    assert body['my_rating'] == 'agree' and body['changed'] is True
    assert body['spinka']['level'] == 'P4' and body['spinka']['n'] == 3 and body['spinka']['score'] == 0.5
    assert body['pin']['ratings'] == {'n': 3, 'agree': 3, 'disagree': 0} and body['pin']['my_rating'] == 'agree'
    sp = BoxSpinka.objects.get(box=box)
    assert sp.distribution == {'agree': 3, 'disagree': 0} and sp.level_reason == 'ok'


def test_only_two_states_accepted(api):
    author, box, p = setup()
    user = make_user('two')
    assert put_rating(api, user, p, 'doubt').status_code == 400
    assert put_rating(api, user, p, 0).status_code == 400
    assert put_rating(api, user, p, -1).json()['my_rating'] == 'disagree'


def test_one_rating_per_user_change_after_cooldown_and_withdraw(api):
    author, box, p = setup()
    user = make_user('ch')
    assert put_rating(api, user, p, 'agree').status_code == 200
    again = put_rating(api, user, p, 'agree')
    assert again.status_code == 200 and again.json()['changed'] is False
    assert Rating.objects.filter(user=user, pin=p).count() == 1
    r = put_rating(api, user, p, 'disagree')
    assert r.status_code == 429 and r.json()['code'] == 'rating_cooldown'
    Rating.objects.filter(user=user).update(created_at=timezone.now() - timedelta(hours=2))
    r = put_rating(api, user, p, 'disagree')
    assert r.status_code == 200 and r.json()['my_rating'] == 'disagree'
    assert PinEvent.objects.filter(kind='rating_changed', pin_id=p.pk).exists()
    r = api.delete(f'/api/spina3/pin/{p.pk}/rating/')
    assert r.status_code == 200 and r.json()['my_rating'] is None and r.json()['spinka']['n'] == 0
    assert Rating.objects.get(user=user).status == 'withdrawn'
    assert api.delete(f'/api/spina3/pin/{p.pk}/rating/').status_code == 404
    # ponowna ocena przeciwna zaraz po zmianie: odstęp obowiązuje także po wycofaniu
    assert put_rating(api, user, p, 'agree').json()['code'] == 'rating_cooldown'
    assert put_rating(api, user, p, 'disagree').status_code == 200
    assert Rating.objects.filter(user=user, pin=p).count() == 1


def test_author_cannot_rate_own_pin(api):
    author, box, p = setup()
    r = put_rating(api, author, p, 'agree')
    assert r.status_code == 403 and r.json()['code'] == 'own'


def test_unverified_and_consent_and_team_weight(api):
    author, box, p = setup()
    assert put_rating(api, make_user('t0', verified=False), p, 'agree').json()['code'] == 'tier'
    assert put_rating(api, make_user('nc', consent=False), p, 'agree').json()['code'] == 'consent'
    r = put_rating(api, make_user('tm', team=True), p, 'agree')
    assert r.status_code == 200
    sp = BoxSpinka.objects.get(box=box)
    assert sp.n == 1 and sp.weighted_n == 0.0                      # zespół: kontekst, nie głos


def test_young_accounts_hold_level_and_daily_limit(api, spina3_settings):
    author, box, p = setup()
    for i in range(3):
        rate(make_user(f'y{i}', days_old=1, tier=''), p, 1)
    sp = BoxSpinka.objects.get(box=box)
    assert sp.n == 3 and sp.level == 'open' and sp.level_reason == 'hold_new_accounts'   # n_w = 1,5 < min_n 3
    spina3_settings.SPINA3['scoring']['daily_ratings'] = {'T0': 0, 'T1': 2, 'T2': 2, 'T3': 2, 'team': 0}
    user, thing = make_user('lim'), make_box('Dowód')
    pins = [author_pin(author, make_box(f'L{i}'), thing) for i in range(3)]
    codes = [put_rating(api, user, x, 'agree').status_code for x in pins]
    assert codes == [200, 200, 429]


def test_burst_limit(api, spina3_settings):
    spina3_settings.SPINA3['scoring']['burst_max_ratings'] = 2
    author, thing, user = make_user('ba'), make_box('Dowód'), make_user('bu')
    pins = [author_pin(author, make_box(f'B{i}'), thing) for i in range(3)]
    assert [put_rating(api, user, x, 1).status_code for x in pins] == [200, 200, 429]


def test_election_silence_pauses_ratings_only_with_flag(api, spina3_settings):
    author, box, p = setup()
    now = timezone.now()
    spina3_settings.SPINA3['flags'].update({'election_silence_start': (now - timedelta(hours=1)).isoformat(),
                                            'election_silence_end': (now + timedelta(days=1)).isoformat()})
    assert put_rating(api, make_user('s1'), p, 'agree').status_code == 200
    spina3_settings.SPINA3['flags']['election_silence_pause_ratings'] = True
    r = put_rating(api, make_user('s2'), p, 'agree')
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'
    assert api.get('/api/spina3/silence/').json()['election_silence']['pause']['ratings'] is True


def test_ratings_disabled_flag(api, spina3_settings):
    author, box, p = setup()
    spina3_settings.SPINA3['flags']['ratings_enabled'] = False
    assert put_rating(api, make_user('off'), p, 'agree').json()['code'] == 'ratings_disabled'


def test_frozen_box_blocks_ratings(api):
    author, box, p = setup()
    box.source_status = 'withdrawn'
    box.save()
    r = put_rating(api, make_user('fz'), p, 'agree')
    assert r.status_code == 409 and r.json()['code'] == 'frozen'


def test_hysteresis_and_min_n_from_ratings(api):
    author, box, p = setup()
    users = [make_user(f'h{i}') for i in range(4)]
    for u in users[:3]:
        rate(u, p, 1)
    assert BoxSpinka.objects.get(box=box).level == 'P4'
    rate(users[3], p, -1)                                   # S = 2/7 = 0,286: nadal P4
    assert BoxSpinka.objects.get(box=box).level == 'P4'
    Rating.objects.filter(user__in=users[:2]).update(status='withdrawn')
    spinka.recompute(box)
    sp = BoxSpinka.objects.get(box=box)
    assert sp.n == 2 and sp.level == 'open' and sp.level_reason == 'open'   # n_w 2 < min_n 3


def test_cluster_divides_weight():
    from spina3.config import ScoringConfig
    from spina3 import scoring
    author, thing = make_user('cl_a'), make_box('Dowód')
    sock = [make_user(f'sock{i}') for i in range(3)]
    pins = [author_pin(author, make_box(f'C{i}'), thing) for i in range(5)]
    for p in pins:
        for u in sock:
            rate(u, p, 1)
    out = spinka.refresh_clusters()
    assert set(out.values()) == {3}
    sp = BoxSpinka.objects.get(box=pins[0].box)
    assert sp.n == 3 and abs(sp.weighted_n - 1.0) < 1e-9 and sp.level == 'open'   # trzy konta-klony = jeden głos
    assert scoring.rating_weight(1.0, 3, cfg=ScoringConfig()) == pytest.approx(1 / 3)


def test_my_ratings_private(api):
    author, box, p = setup()
    user = make_user('mine')
    rate(user, p, -1)
    api.force_authenticate(user)
    body = api.get('/api/spina3/me/ratings/').json()
    assert len(body['items']) == 1 and body['items'][0]['stance'] == 'disagree'
    api.force_authenticate(None)
    assert api.get('/api/spina3/me/ratings/').status_code in (401, 403)


def test_anonymized_rating_keeps_aggregate():
    from spina3.pins import anonymize_user
    author, box, p = setup()
    user = make_user('anon')
    rate(user, p, 1)
    anonymize_user(user)
    row = Rating.objects.get(pin=p)
    assert row.user is None and row.anonymized and BoxSpinka.objects.get(box=box).n == 1


def test_profile_nick_color_whitelist_and_reserved_spin(api):
    user = make_user('nick')
    api.force_authenticate(user)
    body = api.get('/api/spina3/me/profile/').json()
    assert body['nick_color'] == 'piasek' and 'spin' not in body['nick_colors'] and len(body['nick_colors']) == 8
    assert api.patch('/api/spina3/me/profile/', {'nick_color': 'pistacja'}, format='json').json()['nick_color'] == 'pistacja'
    r = api.patch('/api/spina3/me/profile/', {'nick_color': 'spin'}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'reserved'
    assert api.patch('/api/spina3/me/profile/', {'nick_color': '#4F8CFF'}, format='json').status_code == 400
    assert api.patch('/api/spina3/me/profile/', {'nick_color': 'blue'}, format='json').status_code == 400
    assert Spina3Profile.objects.get(user=user).nick_color == 'pistacja'
    cfg = api.get('/api/spina3/config/').json()
    assert 'spin' in cfg['nick_colors_reserved'] and 'spin' not in cfg['nick_colors']
    # kolor widoczny przy przypięciu autora
    author, box, p = make_user('kolor'), make_box('KB'), None
    Spina3Profile.objects.filter(user=author).update(nick_color='coral')
    p = author_pin(author, box, make_box('KD'))
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['pin']['author']['color'] == 'coral'
