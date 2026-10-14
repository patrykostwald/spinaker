"""S2 pkt 4: cisza wyborcza kont kandydatów i komitetów (import CSV, silence_hidden, 423 election_silence)."""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from spina3.models import BoxLink, Pin, SilencedAccount
from spina3.ranking import build_snapshot

from .conftest import author_pin, make_box, make_user, rate, rated_box

pytestmark = pytest.mark.django_db


def silence(handle='kandydat_x', **kwargs):
    now = timezone.now()
    defaults = dict(kind='candidate', starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1), source='obwieszczenie PKW (test)')
    defaults.update(kwargs)
    return SilencedAccount.objects.create(handle=handle, **defaults)


def test_repo_list_is_empty():
    assert not SilencedAccount.objects.exists()


def test_csv_import(tmp_path):
    path = tmp_path / 'cisza.csv'
    path.write_text('konto,rodzaj,od,do,zrodlo\n@Kandydat_X,kandydat,2027-10-10T00:00:00+02:00,2027-10-12T07:00:00+02:00,PKW\n'
                    'komitet_y,komitet,2027-10-10T00:00:00+02:00,2027-10-12T07:00:00+02:00,PKW\n', encoding='utf-8')
    out = StringIO()
    call_command('spina3_silence_import', str(path), '--dry-run', stdout=out)
    assert 'poprawnych wierszy: 2' in out.getvalue() and not SilencedAccount.objects.exists()
    call_command('spina3_silence_import', str(path), stdout=StringIO())
    call_command('spina3_silence_import', str(path), stdout=StringIO())   # bez duplikatów
    rows = list(SilencedAccount.objects.order_by('handle'))
    assert [(r.handle, r.kind) for r in rows] == [('kandydat_x', 'candidate'), ('komitet_y', 'committee')]
    bad = tmp_path / 'zle.csv'
    bad.write_text('konto,rodzaj,od,do,zrodlo\nx,senator,2027-10-10,2027-10-12,PKW\n', encoding='utf-8')
    with pytest.raises(CommandError):
        call_command('spina3_silence_import', str(bad), stdout=StringIO())
    missing = tmp_path / 'brak.csv'
    missing.write_text('konto,rodzaj\nx,kandydat\n', encoding='utf-8')
    with pytest.raises(CommandError):
        call_command('spina3_silence_import', str(missing), stdout=StringIO())


def test_boxes_hidden_and_writes_423(api):
    box, pin = rated_box(1, 1, 1, title='Wpis kandydata', author_handle='Kandydat_X')
    other, _ = rated_box(1, 1, 1, title='Inny box')
    diag = make_box('Diagnoza', kind='diagnosis')
    BoxLink.objects.create(box=box, target=diag, kind='diagnosis_of')
    silence()
    body = api.get(f'/api/spina3/box/{box.pk}/').json()
    assert body['silence_hidden'] is True
    assert body['spinka']['distribution'] is None and body['spinka']['level'] is None and body['spinka']['color'] is None
    assert body['pin']['ratings']['agree'] is None and body['pin']['ratings']['disagree'] is None
    assert api.get(f'/api/spina3/box/{diag.pk}/').json()['silence_hidden'] is True
    assert api.get(f'/api/spina3/box/{other.pk}/').json()['silence_hidden'] is False
    build_snapshot()
    wall = api.get('/api/spina3/wall/?sort=level').json()
    tiles = {item['id']: item for item in wall['items']}
    assert tiles[box.pk]['silence_hidden'] and tiles[box.pk]['spinka']['level'] is None
    assert tiles[other.pk]['spinka']['distribution'] == {'agree': 3, 'disagree': 0}
    level = api.get(f"/api/spina3/wall/?sort=level&level={tiles[other.pk]['spinka']['level']}").json()
    assert box.pk not in [i['id'] for i in level['items']]   # filtr poziomu nie ujawnia wyniku
    user = make_user('glosujacy_s')
    api.force_authenticate(user)
    r = api.put(f'/api/spina3/pin/{pin.pk}/rating/', {'stance': 'disagree'}, format='json')
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'
    r = api.post(f'/api/spina3/box/{box.pk}/comments/', {'text': 'Komentarz w ciszy.'}, format='json')
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'
    anchor = make_box('Kotwica')
    r = api.post('/api/spina3/boxes/', {'box': {'kind': 'box', 'target': str(anchor.pk)}, 'pin': {'kind': 'box', 'target': str(box.pk)}},
                 format='json')
    assert r.status_code == 423 and r.json()['code'] == 'election_silence'
    assert not Pin.objects.filter(box=anchor).exists()
    assert api.put(f"/api/spina3/pin/{Pin.objects.get(box=other).pk}/rating/", {'stance': 'agree'}, format='json').status_code == 200


def test_silence_window_ends():
    box, pin = rated_box(1, title='Wpis kandydata', author_handle='kandydat_x')
    past = timezone.now() - timedelta(days=3)
    silence(starts_at=past, ends_at=past + timedelta(days=1))
    rate(make_user('po_ciszy'), pin, -1)
