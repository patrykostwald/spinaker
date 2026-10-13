"""Box autora z DOKŁADNIE JEDNYM przypięciem (v2): POST /boxes/, edycja i usunięcie przypięcia, limity, rzecz, która zniknęła."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from spina3 import pins as pin_service
from spina3.models import Box, BoxSpinka, Pin, PinEvent, Rating, Spina3Profile

from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


def post_box(api, user, anchor, target, *, box_kind='box', pin_kind='box', comment='', stance=None, title=''):
    api.force_authenticate(user)
    body = {'box': {'kind': box_kind, 'target': str(anchor), 'title': title},
            'pin': {'kind': pin_kind, 'target': str(target), 'comment': comment}}
    if stance is not None:
        body['pin']['stance'] = stance
    return api.post('/api/spina3/boxes/', body, format='json')


def x_user(name, x_id):
    from news.account_models import UserXConnection
    user = make_user(name, days_old=30)
    UserXConnection.objects.create(user=user, x_user_id=x_id, username=name)
    return user


def test_author_adopts_authorless_box_with_one_pin_and_second_gets_409(api):
    author, other, box, thing, alt = make_user('a'), make_user('b'), make_box('Box'), make_box('Rzecz'), make_box('Inna')
    r = post_box(api, author, box.pk, thing.pk, comment='Dobry kontekst.', stance='disagree')
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body['pin']['target']['box']['id'] == thing.pk and body['pin']['author_stance'] == 'disagree'
    assert body['pin']['author']['nick'] == 'a' and body['pin']['editable'] is True
    assert body['box']['has_pin'] and body['box']['pin']['id'] == body['pin']['id']
    assert body['spinka']['n'] == 0 and body['spinka']['level'] == 'open'
    # drugie przypięcie (też autora) i przypięcie innego użytkownika: 409
    assert post_box(api, author, box.pk, alt.pk).json()['code'] == 'has_pin'
    r = post_box(api, other, box.pk, alt.pk)
    assert r.status_code == 409 and r.json()['code'] == 'has_pin'
    assert Pin.objects.filter(box=box).count() == 1


def test_old_pin_endpoints_are_gone():
    from django.urls import Resolver404, resolve
    for path in ('/api/spina3/box/1/pin/', '/api/spina3/me/pins/'):
        with pytest.raises(Resolver404):
            resolve(path)
    assert resolve('/api/spina3/boxes/').url_name == 'spina3-box-create'


def test_self_pin_409_and_bridge_allowed(api):
    user, a, b = make_user('b1'), make_box('A'), make_box('B')
    assert post_box(api, user, a.pk, a.pk).json()['code'] == 'self'
    assert post_box(api, user, a.pk, b.pk).status_code == 201
    assert post_box(api, user, b.pk, a.pk).status_code == 201   # A->B i B->A to "Most"


def test_box_of_other_user_cannot_be_taken(api):
    owner, intruder, thing = x_user('own3', '31'), make_user('intr'), make_box('Rzecz')
    r = post_box(api, owner, 'https://example.org/nowy-artykul', thing.pk, box_kind='url', title='Nowy artykuł')
    assert r.status_code == 201
    box = Box.objects.get(url='https://example.org/nowy-artykul')
    assert box.added_by == 'user' and box.status == 'published'          # T3: widoczny od razu
    api.force_authenticate(owner)
    api.delete(f"/api/spina3/pin/{r.json()['pin']['id']}/")
    box.refresh_from_db()
    assert box.status == 'hidden' and box.hidden_reason == 'autor usunął przypięcie'


def test_url_anchor_pending_for_t2_then_published_on_accept(api):
    t2, thing, staff = make_user('t2u'), make_box('Rzecz'), make_user('mod', staff=True)
    r = post_box(api, t2, 'https://www.example.org/teza?utm_source=x', thing.pk, box_kind='url', title='Teza posła')
    assert r.status_code == 201, r.json()
    assert r.json()['box']['status'] == 'pending' and 'czeka' in r.json()['message']
    box = Box.objects.get(url='https://example.org/teza')
    api.force_authenticate(None)
    assert api.get(f'/api/spina3/box/{box.pk}/').status_code == 404       # niewidoczny przed decyzją
    from spina3 import url_queue
    from spina3.models import UrlCheck
    url_queue.decide(UrlCheck.objects.get(url_normalized='https://example.org/teza'), staff, 'accept', '')
    box.refresh_from_db()
    assert box.status == 'published'
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['pin']['author']['nick'] == 't2u'


def test_edit_and_delete_recompute(api):
    author, box, thing = make_user('ed'), make_box('Box'), make_box('Rzecz')
    my = author_pin(author, box, thing, stance=1)
    for i in range(3):
        rate(make_user(f'e{i}'), my, 1)
    assert BoxSpinka.objects.get(box=box).level == 'P4'
    api.force_authenticate(author)
    r = api.patch(f'/api/spina3/pin/{my.pk}/', {'stance': 'disagree'}, format='json')
    assert r.status_code == 429 and r.json()['code'] == 'stance_cooldown'   # stanowisko autora: raz na 24 h
    Pin.objects.filter(pk=my.pk).update(created_at=timezone.now() - timedelta(days=2))
    r = api.patch(f'/api/spina3/pin/{my.pk}/', {'stance': 'disagree', 'comment': 'zmieniam zdanie'}, format='json')
    assert r.status_code == 200 and r.json()['pin']['author_stance'] == 'disagree'
    assert PinEvent.objects.filter(kind='stance_changed', pin_id=my.pk).exists()
    # stanowisko autora nie liczy się do S
    assert BoxSpinka.objects.get(box=box).distribution == {'agree': 3, 'disagree': 0}
    r = api.delete(f'/api/spina3/pin/{my.pk}/')
    assert r.status_code == 204
    sp = BoxSpinka.objects.get(box=box)
    assert sp.level == 'open' and sp.level_reason == 'no_pin'
    assert Rating.objects.filter(pin=my).count() == 3                      # oceny zostają w bazie, nie liczą się
    # box importera wraca do puli: nowe przypięcie (też innego użytkownika) jest możliwe
    assert post_box(api, make_user('nowy'), box.pk, thing.pk).status_code == 201


def test_other_user_cannot_edit(api):
    box, thing, owner, intruder = make_box('Box'), make_box('Rzecz'), make_user('own'), make_user('bad')
    my = author_pin(owner, box, thing)
    api.force_authenticate(intruder)
    assert api.patch(f'/api/spina3/pin/{my.pk}/', {'comment': 'x'}, format='json').status_code == 403
    assert api.delete(f'/api/spina3/pin/{my.pk}/').status_code == 403


def test_unverified_account_cannot_publish(api):
    r = post_box(api, make_user('t0', verified=False), make_box('Box').pk, make_box('Rzecz').pk)
    assert r.status_code == 403 and r.json()['code'] == 'tier'


def test_consent_required_then_granted(api):
    user, box, thing = make_user('c1', consent=False), make_box('Box'), make_box('Rzecz')
    assert post_box(api, user, box.pk, thing.pk).json()['code'] == 'consent'
    api.force_authenticate(user)
    assert api.post('/api/spina3/me/consent/', {'accepted': True}, format='json').status_code == 200
    assert post_box(api, user, box.pk, thing.pk).status_code == 201


def test_young_account_daily_limit(api):
    young, thing = make_user('young', days_old=2, tier=''), make_box('Rzecz')
    codes = [post_box(api, young, make_box(f'B{i}').pk, thing.pk).status_code for i in range(6)]
    assert codes == [201] * 5 + [429]      # T1: 5 na dobę (fixture)


def test_burst_limit(api, spina3_settings):
    spina3_settings.SPINA3['scoring']['burst_max_pins'] = 2
    user, thing = make_user('fast'), make_box('Rzecz')
    codes = [post_box(api, user, make_box(f'F{i}').pk, thing.pk).status_code for i in range(3)]
    assert codes == [201, 201, 429]


def test_same_target_limit_30d(api, spina3_settings):
    spina3_settings.SPINA3['scoring']['same_target_30d'] = {'T1': 1, 'T2': 2, 'T3': 2}
    user, thing = make_user('rep'), make_box('Rzecz')
    codes = [post_box(api, user, make_box(f'S{i}').pk, thing.pk).status_code for i in range(3)]
    assert codes == [201, 201, 429]


def test_image_kind_disabled_by_flag(api):
    user, box, thing = make_user('img'), make_box('Box'), make_box('Rzecz')
    r = post_box(api, user, box.pk, 'x', pin_kind='image')
    assert r.status_code == 403 and r.json()['code'] == 'image_disabled'
    r = post_box(api, user, 'x', thing.pk, box_kind='image')
    assert r.status_code == 403 and r.json()['code'] == 'image_disabled'


def test_url_evidence_pending_blocks_ratings_and_tier(api):
    box = make_box('Box')
    r = post_box(api, make_user('t1', days_old=3, tier=''), box.pk, 'https://sejm.gov.pl/druk/1', pin_kind='url')
    assert r.status_code == 403 and r.json()['code'] == 'url_tier'
    t3 = x_user('t3', '1')
    r = post_box(api, t3, box.pk, 'https://www.sejm.gov.pl/druk/1?utm_source=x', pin_kind='url')
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body['pin']['target']['status'] == 'pending' and body['pin']['target'].get('domain') == ''
    p = Pin.objects.get(user=t3)
    assert p.url == 'https://sejm.gov.pl/druk/1' and p.url_check.status == 'queued'
    api.force_authenticate(make_user('rater'))
    r = api.put(f'/api/spina3/pin/{p.pk}/rating/', {'stance': 'agree'}, format='json')
    assert r.status_code == 409 and r.json()['code'] == 'target_pending'
    r = post_box(api, t3, make_box('Box2').pk, 'https://sejm.gov.pl/druk/2', pin_kind='url')
    assert r.status_code == 429 and r.json()['code'] == 'url_pending'


def test_url_already_in_base_becomes_box_pin(api):
    box, existing = make_box('Box'), make_box('Istnieje', url='https://example.org/istnieje')
    r = post_box(api, x_user('t3b', '2'), box.pk, 'https://www.example.org/istnieje/', pin_kind='url')
    assert r.status_code == 201 and r.json()['pin']['kind'] == 'box' and 'To już jest w bazie' in r.json()['message']


def test_rejected_url_by_automatic_check_400(api):
    r = post_box(api, x_user('t3c', '3'), make_box('Box').pk, 'http://127.0.0.1/admin', pin_kind='url')
    assert r.status_code == 400 and r.json()['code'] == 'url_rejected'


def test_comment_prefilter(api):
    user, box, thing = make_user('cm'), make_box('Box'), make_box('Rzecz')
    r = post_box(api, user, box.pk, thing.pk, comment='PESEL 44051401359')
    assert r.status_code == 400 and r.json()['code'] == 'comment'
    r = post_box(api, user, box.pk, thing.pk, comment='pisz na jan@example.org')
    assert r.status_code == 201 and r.json()['comment'] and Pin.objects.get(user=user).comment_status == 'held'
    api.force_authenticate(make_user('viewer'))
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['pin']['comment'] == ''   # wstrzymany komentarz nie jest publiczny


def test_team_pin_is_labelled(api):
    r = post_box(api, make_user('team', team=True), make_box('Box').pk, make_box('Rzecz').pk)
    assert r.status_code == 201 and r.json()['pin']['author']['badge'] == 'team'


def test_dr_spin_diagnosis_is_the_one_pin_and_users_rate_it(api):
    from spina3.importer import dr_spin_user
    box, diag = make_box('Wpis', kind='post'), make_box('Diagnoza', kind='diagnosis')
    p = Pin.objects.create(user=dr_spin_user(), box=box, kind='diagnosis', pinned_box=diag,
                           diagnosis_title='Diagnoza: liczba bez punktu odniesienia', diagnosis_url='https://spin.clinic/klinika/1',
                           technique='fałszywa alternatywa', approved_at=timezone.now())
    for i in range(3):
        rate(make_user(f'd{i}'), p, 1)
    sp = BoxSpinka.objects.get(box=box)
    assert sp.n == 3 and sp.level == 'P4'
    api.force_authenticate(None)
    detail = api.get(f'/api/spina3/box/{box.pk}/').json()
    assert detail['pin']['system'] and detail['pin']['author']['badge'] == 'dr_spin' and detail['pin']['author']['color'] == 'spin'
    assert detail['pin']['label'].startswith('Diagnoza AI, zatwierdzona') and detail['pin']['editable'] is False
    assert detail['question'] == 'Czy zgadzasz się z diagnozą Dr. Spina?'
    assert detail['can_pin'] is False and detail['can_rate'] is False
    api.force_authenticate(make_user('x9'))
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['can_rate'] is True
    # box z diagnozą nie przyjmie przypięcia użytkownika; Dr. Spin nie tworzy boxów ani nie ocenia
    assert post_box(api, make_user('pd'), box.pk, make_box('Rzecz').pk).json()['code'] == 'has_pin'
    assert post_box(api, dr_spin_user(), make_box('Inny').pk, box.pk).status_code == 403
    api.force_authenticate(dr_spin_user())
    assert api.put(f'/api/spina3/pin/{p.pk}/rating/', {'stance': 'agree'}, format='json').status_code == 403


def test_adopt_flag_off_blocks_importer_boxes(api, spina3_settings):
    spina3_settings.SPINA3['flags']['adopt_authorless_boxes'] = False
    r = post_box(api, make_user('ad'), make_box('Box').pk, make_box('Rzecz').pk)
    assert r.status_code == 403 and r.json()['code'] == 'adopt_disabled'


def test_not_pinnable_target_403(api):
    person = make_box('Jan K.', kind='person', public_function=False)
    r = post_box(api, make_user('np'), make_box('Box').pk, person.pk)
    assert r.status_code == 403 and r.json()['detail'] == 'Materiał niedostępny do przypinania.'


def test_target_disappears_seven_days_then_hidden(api):
    author, box, thing = make_user('g'), make_box('Box'), make_box('Rzecz')
    p = author_pin(author, box, thing)
    for i in range(3):
        rate(make_user(f'g{i}'), p, 1)
    assert BoxSpinka.objects.get(box=box).level == 'P4'
    from spina3.moderation import hide_box, restore_box
    hide_box(thing, make_user('mod', staff=True), 'naruszenie')
    p.refresh_from_db()
    assert p.target_status == 'unavailable' and p.status == 'published' and p.replace_deadline
    sp = BoxSpinka.objects.get(box=box)
    assert sp.level == 'open' and sp.level_reason == 'target_unavailable'
    api.force_authenticate(author)
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['pin']['target']['label'] == 'materiał niedostępny'
    # bez wymiany w 7 dni: ukryte; przywrócenie celu przywraca przypięcie i poziom
    assert pin_service.expire_unavailable(timezone.now() + timedelta(days=8)) == 1
    p.refresh_from_db()
    assert p.status == 'hidden'
    restore_box(thing, None)
    p.refresh_from_db()
    assert p.status == 'published' and BoxSpinka.objects.get(box=box).level == 'P4'
    # wymiana dowodu przez autora
    r = api.patch(f'/api/spina3/pin/{p.pk}/', {'kind': 'box', 'target': str(make_box('Nowa').pk)}, format='json')
    assert r.status_code == 200 and r.json()['pin']['target_status'] == 'ok'


def test_frozen_box_blocks_new_pins(api):
    box = make_box('Wpis', kind='post')
    from spina3.importer import mark_post_removed
    mark_post_removed(box)
    r = post_box(api, make_user('fr'), box.pk, make_box('Rzecz').pk)
    assert r.status_code == 409 and r.json()['code'] == 'frozen'


def test_election_silence_pauses_user_boxes_only_with_flag(api, spina3_settings):
    start, end = timezone.now() - timedelta(hours=1), timezone.now() + timedelta(days=1)
    spina3_settings.SPINA3['flags'].update({'election_silence_start': start.isoformat(), 'election_silence_end': end.isoformat()})
    assert api.get('/api/spina3/config/').json()['election_silence']['active'] is True
    thing = make_box('Rzecz')
    assert post_box(api, make_user('es'), make_box('B1').pk, thing.pk).status_code == 201
    spina3_settings.SPINA3['flags']['election_silence_pause_user_pins'] = True
    r = post_box(api, make_user('es2'), make_box('B2').pk, thing.pk)
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'


def test_my_boxes_private_and_anonymize(api):
    user, box, thing = make_user('me'), make_box('Box'), make_box('Rzecz')
    p = author_pin(user, box, thing, comment='mój komentarz')
    rate(make_user('me2'), p, -1)
    api.force_authenticate(user)
    body = api.get('/api/spina3/me/boxes/').json()
    assert len(body['items']) == 1 and body['public_profile'] is False and body['items'][0]['pin']['ratings']['disagree'] == 1
    api.force_authenticate(None)
    assert api.get('/api/spina3/me/boxes/').status_code in (401, 403)
    pin_service.anonymize_user(user)
    p.refresh_from_db()
    assert p.user is None and p.comment == '' and p.anonymized and p.status == 'published'
    assert not Spina3Profile.objects.filter(user=user).exists()
    assert BoxSpinka.objects.get(box=box).n == 1
