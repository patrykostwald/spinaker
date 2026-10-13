"""Kontrakt frontu z 14.10: API, migracja i dane prywatne, wyłącznie offline."""
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from spina3 import pins, url_queue
from spina3.models import Pin, Report
from spina3.public import box_item, pin_summary
from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('field,length,valid', [
    ('title', 0, True), ('title', 14, False), ('title', 15, True),
    ('title', 80, True), ('title', 81, False),
    ('subtitle', 0, True), ('subtitle', 160, True), ('subtitle', 161, False),
    ('comment', 280, True), ('comment', 281, False),
])
def test_heading_create_and_patch(api, field, length, valid):
    user = make_user('heading')
    box, target = make_box(), make_box('Dowód')
    api.force_authenticate(user)
    payload = {'box': {'target': str(box.pk)}, 'pin': {'target': str(target.pk), field: 'ą' * length}}
    response = api.post('/api/spina3/boxes/', payload, format='json')
    assert response.status_code == (201 if valid else 400)
    if valid:
        pin_id = response.json()['pin']['id']
        assert response.json()['pin'][field] == 'ą' * length
        assert response.json()['box']['pin'][field] == 'ą' * length
    else:
        assert not Pin.objects.exists()
        pin_id = author_pin(user, box, target).pk
    response = api.patch(f'/api/spina3/pin/{pin_id}/', {field: 'ą' * length}, format='json')
    assert response.status_code == (200 if valid else 400)


def test_heading_independent_optional_and_patch_preserves(api):
    user = make_user('optional')
    box, target = make_box(), make_box('Dowód')
    api.force_authenticate(user)
    response = api.post('/api/spina3/boxes/', {'box': {'target': str(box.pk)},
        'pin': {'target': str(target.pk), 'comment': 'Komentarz zgodności'}}, format='json')
    pin = response.json()['pin']
    assert pin['title'] == pin['subtitle'] == ''
    path = f"/api/spina3/pin/{pin['id']}/"
    response = api.patch(path, {'title': 'Teza o dostatecznej długości', 'subtitle': 'Podtytuł'}, format='json')
    assert response.json()['pin']['comment'] == 'Komentarz zgodności'
    response = api.patch(path, {'comment': 'Nowy komentarz'}, format='json')
    assert response.json()['pin']['subtitle'] == 'Podtytuł'
    assert response.json()['pin']['title'] == 'Teza o dostatecznej długości'
    response = api.patch(path, {'title': '', 'subtitle': ''}, format='json')
    assert response.json()['pin']['title'] == response.json()['pin']['subtitle'] == ''


@pytest.mark.parametrize('kind', ['box', 'url', 'image', 'diagnosis'])
@pytest.mark.parametrize('status', ['ok', 'pending', 'unavailable'])
def test_target_summary(kind, status):
    target = make_box('Tytuł celu', kind='document', subtype='raport')
    pin = Pin.objects.create(box=make_box(), pinned_box=target, kind=kind, target_status=status, url='https://example.org/evidence',
                             title='Teza o dostatecznej długości', diagnosis_title='Diagnoza')
    data = pin_summary(pin)
    card = data['target']
    assert set(card) == {'box_id', 'title', 'kind', 'subtype', 'status'}
    assert card['status'] == data['target_status'] == status
    if kind in ('url', 'image'):
        assert card == {'box_id': None, 'title': pin.title, 'kind': kind, 'subtype': '', 'status': status}
    else:
        assert card['box_id'] == target.pk and card['kind'] == 'document' and card['subtype'] == 'raport'
        assert card['title'] == data['target_title']
    assert 'box' not in card


def test_config_colors_csrf_and_silence(api, spina3_settings):
    response = api.get('/api/spina3/config/')
    data = response.json()
    assert response['Cache-Control'] == 'no-store'
    assert len(data['csrf_token']) == 64 and 'csrftoken' in response.cookies
    assert data['colors'] == {'P5': '#62E8A3', 'P4': '#8BBF48', 'P3': '#D49A33',
                              'P2': '#E07A3C', 'P1': '#E45A5A', 'open': '#8E959E'}
    assert data['nick_colors'] == {'lila': '#AB91F3', 'wrzos': '#D991F3', 'fuksja': '#F391E1',
        'roz': '#F391B5', 'brzoskwinia': '#F3BF91', 'piasek': '#F3E291', 'cytryna': '#DFF391', 'pistacja': '#BFF391'}
    assert data['nick_color_default'] in data['nick_colors']
    assert 'spin' not in data['nick_colors'] and 'spin' in data['nick_colors_reserved']
    assert data['election_silence'] == {'active': False, 'start': None, 'end': None,
                                      'pause': {'user_pins': False, 'ratings': False, 'comments': False}}
    now = timezone.now()
    start, end = (now - timedelta(hours=1)).isoformat(), (now + timedelta(hours=1)).isoformat()
    spina3_settings.SPINA3['flags'].update(election_silence_start=start, election_silence_end=end,
        election_silence_pause_user_pins=True, election_silence_pause_ratings=True, election_silence_pause_comments=True)
    data = api.get('/api/spina3/config/').json()
    state = {'active': True, 'start': start, 'end': end,
             'pause': {'user_pins': True, 'ratings': True, 'comments': True}}
    assert data['election_silence'] == state
    assert api.get('/api/spina3/silence/').json() == {'election_silence': state}
    assert not any(key.startswith('election_silence_') for key in data['flags'])


def test_guest_only_profile_is_public(api):
    response = api.get('/api/spina3/me/profile/')
    assert response.status_code == 200
    assert response.json() == {'nick': None, 'anonymous': True, 'consent': False}
    assert api.get('/api/spina3/me/boxes/').status_code == 401
    assert api.get('/api/spina3/me/ratings/').status_code == 401
    assert api.patch('/api/spina3/me/profile/', {'nick_color': 'lila'}, format='json').status_code == 401
    assert api.post('/api/spina3/me/consent/', {'accepted': True}, format='json').status_code == 401


def test_private_lists_shapes_and_ownership(api):
    author, reader = make_user('author'), make_user('reader')
    box, target = make_box(), make_box('Dowód')
    pin = author_pin(author, box, target)
    rating = rate(reader, pin)
    api.force_authenticate(author)
    assert api.get('/api/spina3/me/boxes/').json()['items'][0]['id'] == box.pk
    assert api.get('/api/spina3/me/ratings/').json() == {'items': []}
    api.force_authenticate(reader)
    assert api.get('/api/spina3/me/boxes/').json() == {'items': []}
    row = api.get('/api/spina3/me/ratings/').json()['items'][0]
    assert set(row) == {'box_id', 'pin_id', 'stance', 'created_at', 'box'}
    assert row['box_id'] == box.pk and row['pin_id'] == pin.pk and row['stance'] == 'agree'
    assert row['created_at'] == rating.created_at.isoformat() and row['box']['id'] == box.pk


def test_reader_link_dates():
    author, staff = make_user('author'), make_user('staff', staff=True)
    now = timezone.now() - timedelta(days=2)
    box, pin, _ = pins.create_box_with_pin(author, box_kind='url', box_target='https://example.org/anchor',
                                          pin_target=make_box().pk, now=now)
    assert box.published_at == pin.created_at == now
    box.published_at = None
    assert box_item(box)['published_at'] == now.isoformat()
    box.reader_link = False
    assert box_item(box)['published_at'] is None
    box.published_at = now - timedelta(days=1)
    assert box_item(box)['published_at'] == box.published_at.isoformat()
    check = url_queue.enqueue('https://example.org/evidence')
    pin = Pin.objects.create(box=make_box(), kind='url', url=check.url_normalized, url_check=check, created_at=now, target_status='pending')
    url_queue.decide(check, staff, 'accept', 'ok', now=timezone.now())
    assert check.box.published_at == pin.created_at


@pytest.mark.parametrize('change', [{}, {'good_faith': False}, {'good_faith': None}])
def test_report_requires_good_faith(api, change):
    api.force_authenticate(make_user('reporter'))
    data = {'box': make_box().pk, 'reason': 'illegal', 'name': 'Jan Kowalski', 'email': 'jan@example.org', **change}
    response = api.post('/api/spina3/report/', data, format='json')
    assert response.status_code == 400 and response.json()['code'] == 'good_faith'
    assert not Report.objects.exists()


@pytest.mark.parametrize('field,value', [('name', ''), ('email', 'nie-email'), ('explanation', 'a' * 2001)])
def test_report_validation(api, field, value):
    api.force_authenticate(make_user('reporter'))
    data = {'box': make_box().pk, 'reason': 'illegal', 'name': 'Jan Kowalski', 'email': 'jan@example.org', 'good_faith': True}
    data[field] = value
    assert api.post('/api/spina3/report/', data, format='json').status_code == 400
    assert not Report.objects.exists()


def test_report_private_fields_saved_not_public(api):
    box = make_box()
    api.force_authenticate(make_user('reporter'))
    data = {'box': box.pk, 'reason': 'illegal', 'name': 'Jan Kowalski', 'email': 'jan@example.org',
            'good_faith': True, 'location': 'https://example.org/content', 'explanation': 'Uzasadnienie zgłoszenia'}
    response = api.post('/api/spina3/report/', data, format='json')
    assert response.status_code == 201
    row = Report.objects.get()
    for key in ('name', 'email', 'good_faith', 'location', 'explanation'):
        assert getattr(row, key) == data[key]
        assert key not in response.json()
    api.force_authenticate(None)
    for path in (f'/api/spina3/box/{box.pk}/', '/api/spina3/wall/', '/api/spina3/boxes/search/?q=Box'):
        response = api.get(path)
        assert response.status_code == 200
        for key in ('name', 'email', 'location', 'explanation'):
            assert data[key] not in response.content.decode()


@pytest.mark.django_db(transaction=True)
def test_nick_color_data_migration():
    old = ('spina3', '0003_contract_20261014')
    new = ('spina3', '0004_nick_colors_front')
    executor = MigrationExecutor(connection)
    executor.migrate([old])
    try:
        apps = executor.loader.project_state([old]).apps
        User = apps.get_model('auth', 'User')
        Profile = apps.get_model('spina3', 'Spina3Profile')
        mapping = {'lilac': 'lila', 'plum': 'wrzos', 'rose': 'fuksja', 'coral': 'roz', 'amber': 'brzoskwinia',
                   'sand': 'piasek', 'olive': 'cytryna', 'moss': 'pistacja', 'ash': 'piasek', 'slate': 'lila',
                   'teal': 'pistacja', 'spin': 'spin', '': '', 'lila': 'lila'}
        ids = {}
        for i, color in enumerate(mapping):
            user = User.objects.create(username=f'migration{i}')
            ids[color] = Profile.objects.create(user_id=user.pk, pseudonym=f'migration{i}', nick_color=color).pk
        executor = MigrationExecutor(connection)
        executor.migrate([new])
        Profile = executor.loader.project_state([new]).apps.get_model('spina3', 'Spina3Profile')
        assert {color: Profile.objects.get(pk=pk).nick_color for color, pk in ids.items()} == mapping
    finally:
        MigrationExecutor(connection).migrate([new])
