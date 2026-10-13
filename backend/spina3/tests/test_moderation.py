"""Zgłoszenia z SLA i uzasadnieniem (DSA), ukrycie, apelacja, sankcje, metryki (v2: przypięcie autora z oceną)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from spina3 import metrics, moderation
from spina3.models import Appeal, BoxSpinka, Pin, Report, Spina3Profile

from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


def setup_pin():
    author, reporter, staff = make_user('author'), make_user('reporter'), make_user('staff', staff=True)
    box, thing = make_box('Box'), make_box('Rzecz')
    p = author_pin(author, box, thing, comment='komentarz')
    rate(reporter, p, 1)
    return author, reporter, staff, box, p


def test_report_sla_and_decision_with_reason(api):
    author, reporter, staff, box, p = setup_pin()
    api.force_authenticate(reporter)
    r = api.post('/api/spina3/report/', {'pin': p.pk, 'reason': 'private_data', 'details': 'dane'}, format='json')
    assert r.status_code == 201
    row = Report.objects.get()
    assert row.sla_deadline - row.created_at == timedelta(hours=24)
    assert api.post('/api/spina3/report/', {'pin': p.pk, 'reason': 'spam'}, format='json').status_code == 409
    api.force_authenticate(author)
    assert api.post('/api/spina3/report/', {'pin': p.pk, 'reason': 'spam'}, format='json').status_code == 400
    api.force_authenticate(staff)
    queue = api.get('/api/spina3/moderation/queue/').json()
    assert queue['counts']['reports'] == 1 and queue['reports'][0]['pin_id'] == p.pk
    assert api.post(f'/api/spina3/moderation/reports/{row.pk}/', {'decision': 'hide', 'reason': ''}, format='json').status_code == 400
    r = api.post(f'/api/spina3/moderation/reports/{row.pk}/', {'decision': 'hide', 'reason': 'Dane osoby prywatnej w komentarzu.', 'sanction': 'weight_zero_30d'}, format='json')
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.status == 'hidden' and p.hidden_reason.startswith('Dane osoby')
    profile = Spina3Profile.objects.get(user=author)
    assert profile.hidden_count == 1 and profile.weight_zero_until > timezone.now()
    sp = BoxSpinka.objects.get(box=box)
    assert sp.level == 'open' and sp.level_reason == 'no_pin'
    assert api.post(f'/api/spina3/moderation/reports/{row.pk}/', {'decision': 'dismiss', 'reason': 'x'}, format='json').status_code == 409


def test_reporter_not_staff_cannot_decide(api):
    author, reporter, staff, box, p = setup_pin()
    row = moderation.report(reporter, pin=p, reason='spam')
    api.force_authenticate(reporter)
    assert api.post(f'/api/spina3/moderation/reports/{row.pk}/', {'decision': 'hide', 'reason': 'x'}, format='json').status_code == 403


def test_appeal_once_and_accept_restores(api):
    author, reporter, staff, box, p = setup_pin()
    moderation.hide_pin(p, staff, 'test')
    api.force_authenticate(author)
    assert api.post(f'/api/spina3/pin/{p.pk}/appeal/', {'text': 'To pomyłka.'}, format='json').status_code == 201
    assert api.post(f'/api/spina3/pin/{p.pk}/appeal/', {'text': 'Jeszcze raz.'}, format='json').status_code == 409
    api.force_authenticate(reporter)
    assert api.post(f'/api/spina3/pin/{p.pk}/appeal/', {'text': 'x'}, format='json').status_code == 403
    row = Appeal.objects.get()
    api.force_authenticate(staff)
    r = api.post(f'/api/spina3/moderation/appeals/{row.pk}/', {'decision': 'accept', 'reason': 'Komentarz nie narusza zasad.'}, format='json')
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.status == 'published' and Spina3Profile.objects.get(user=author).hidden_count == 0
    sp = BoxSpinka.objects.get(box=box)
    assert sp.n == 1 and sp.level_reason != 'no_pin'


def test_hidden_pin_cannot_be_edited_and_mod_pin_endpoint(api):
    author, reporter, staff, box, p = setup_pin()
    api.force_authenticate(staff)
    assert api.post(f'/api/spina3/moderation/pins/{p.pk}/', {'decision': 'hide', 'reason': 'spam'}, format='json').status_code == 200
    api.force_authenticate(author)
    assert api.patch(f'/api/spina3/pin/{p.pk}/', {'comment': 'x'}, format='json').status_code == 409
    api.force_authenticate(staff)
    assert api.post(f'/api/spina3/moderation/pins/{p.pk}/', {'decision': 'restore', 'reason': 'pomyłka'}, format='json').status_code == 200
    p.refresh_from_db()
    assert p.status == 'published'


def test_hide_box_as_anchor_hides_nothing_but_freezes(api):
    author, reporter, staff, box, p = setup_pin()
    moderation.hide_box(box, staff, 'na żądanie')
    assert api.get(f'/api/spina3/box/{box.pk}/').status_code == 404
    assert BoxSpinka.objects.get(box=box).frozen
    moderation.restore_box(box, staff)
    assert api.get(f'/api/spina3/box/{box.pk}/').status_code == 200
    assert not BoxSpinka.objects.get(box=box).frozen


def test_withdraw_box_rodo():
    author, reporter, staff, box, p = setup_pin()
    thing = p.pinned_box
    moderation.withdraw_box(thing, staff, 'art. 17 RODO')
    p.refresh_from_db()
    thing.refresh_from_db()
    assert thing.source_status == 'withdrawn' and p.target_status == 'unavailable'


def test_reports_daily_limit(spina3_settings):
    spina3_settings.SPINA3['scoring']['reports_per_day'] = 1
    author, reporter, staff, box, p = setup_pin()
    moderation.report(reporter, box=box, reason='spam')
    with pytest.raises(moderation.ModerationError) as exc:
        moderation.report(reporter, pin=p, reason='spam')
    assert exc.value.status == 429


def test_metrics_compute_without_tracking(api):
    author, reporter, staff, box, p = setup_pin()
    api.get(f'/api/spina3/box/{box.pk}/')
    out = metrics.compute()
    assert out['m4_5_stances'] == {'agree': 1, 'disagree': 0}
    assert out['m4_1_ratings_per_100_views'] == 100.0 and out['alarms'] == []
    api.force_authenticate(staff)
    assert api.get('/api/spina3/moderation/metrics/').status_code == 200


def test_comment_report_hide_with_reason_and_appeal(api):
    from spina3.comments import create_comment
    author, reporter, staff, box, p = setup_pin()
    commenter = make_user('commenter')
    comment, _ = create_comment(commenter, box, 'To nieprawda, sprawdź druk.')
    api.force_authenticate(reporter)
    r = api.post('/api/spina3/report/', {'comment': comment.pk, 'reason': 'threat'}, format='json')
    assert r.status_code == 201
    row = Report.objects.get(comment=comment)
    api.force_authenticate(staff)
    queue = api.get('/api/spina3/moderation/queue/').json()
    assert any(item.get('comment_id') == comment.pk for item in queue['reports'])
    r = api.post(f'/api/spina3/moderation/reports/{row.pk}/', {'decision': 'hide', 'reason': 'Obraźliwe sformułowanie wobec osoby.'}, format='json')
    assert r.status_code == 200
    comment.refresh_from_db()
    assert comment.status == 'hidden' and comment.hidden_reason.startswith('Obraźliwe')
    api.force_authenticate(commenter)
    listing = api.get(f'/api/spina3/box/{box.pk}/comments/').json()
    assert listing['items'][0]['status'] == 'hidden' and listing['items'][0]['hidden_reason']   # autor widzi powód
    api.force_authenticate(make_user('obcy'))
    assert api.get(f'/api/spina3/box/{box.pk}/comments/').json()['items'] == []
    api.force_authenticate(commenter)
    assert api.post(f'/api/spina3/comment/{comment.pk}/appeal/', {'text': 'To była krytyka, nie obraza.'}, format='json').status_code == 201
    appeal = Appeal.objects.get(comment=comment)
    api.force_authenticate(staff)
    r = api.post(f'/api/spina3/moderation/appeals/{appeal.pk}/', {'decision': 'accept', 'reason': 'Krytyka mieści się w zasadach.'}, format='json')
    assert r.status_code == 200
    comment.refresh_from_db()
    assert comment.status == 'visible'
