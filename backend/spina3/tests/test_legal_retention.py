"""S2 pkt 5: DELETE me/ (nick od razu anonimowy), spina3_retention: treści po 30 dniach, oceny w agregacie bez przypisania,
zgłoszenia i decyzje po 12 miesiącach, dziennik zdarzeń według SPINA3_EVENT_RETENTION_DAYS (domyślnie 90)."""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from spina3 import legal, moderation, retention
from spina3.comments import create_comment
from spina3.models import Appeal, BoxSpinka, Comment, ModerationDecision, Pin, PinEvent, Rating, Report, Spina3Profile

from .conftest import author_pin, make_box, make_user, rate

pytestmark = pytest.mark.django_db


def test_settings_default_event_retention():
    from django.conf import settings
    assert settings.SPINA3_EVENT_RETENTION_DAYS == 90


def test_delete_me_anonymizes_nick_now_and_purges_after_30_days(api):
    user, other = make_user('do_usuniecia'), make_user('autor_r')
    box, thing = make_box('Box'), make_box('Dowód')
    own = author_pin(user, box, thing, comment='mój komentarz autora')
    pin = author_pin(other, make_box('Box 2'), make_box('Dowód 2'))
    rating = rate(user, pin, 1)
    comment, _ = create_comment(user, pin.box, 'Mój komentarz.')
    api.force_authenticate(user)
    r = api.delete('/api/spina3/me/')
    assert r.status_code == 202 and r.json()['nick'] == legal.DELETED_NICK and r.json()['scope'] == 'spina3'
    api.force_authenticate(None)
    comments = api.get(f'/api/spina3/box/{pin.box_id}/comments/').json()['items']
    assert comments[0]['author']['nick'] == 'Użytkownik usunięty' and 'do_usuniecia' not in str(comments)
    assert 'do_usuniecia' not in str(api.get(f'/api/spina3/box/{box.pk}/').json())
    api.force_authenticate(user)
    r = api.put(f'/api/spina3/pin/{pin.pk}/rating/', {'stance': 'disagree'}, format='json')
    assert r.status_code == 403 and r.json()['code'] == 'deleted'
    weight = Rating.objects.get(pk=rating.pk).account_weight
    assert retention.run()['accounts_purged'] == 0   # przed upływem 30 dni nic nie znika
    later = timezone.now() + timedelta(days=31)
    assert retention.run(now=later)['accounts_purged'] == 1
    rating.refresh_from_db()
    own.refresh_from_db()
    comment.refresh_from_db()
    assert rating.user is None and rating.anonymized and rating.account_weight == weight and rating.status == 'active'
    assert BoxSpinka.objects.get(box=pin.box).n == 1   # agregat zostaje
    assert own.status == 'removed' and own.comment == '' and own.user is None
    assert comment.text == '' and comment.user is None
    assert not Spina3Profile.objects.filter(user=user).exists()
    assert get_user_model().objects.filter(pk=user.pk).exists()   # wspólne konto spin.clinic zostaje


def test_reports_decisions_and_events_retention():
    author, reporter, staff = make_user('a_ret'), make_user('r_ret'), make_user('s_ret', staff=True)
    pin = author_pin(author, make_box('Box'), make_box('Dowód'))
    report = moderation.report(reporter, pin=pin, reason='spam', name='R', email='r@example.org', good_faith=True)
    moderation.decide_report(report, staff, 'hide', 'Spam.')
    Appeal.objects.create(pin=pin, decision=ModerationDecision.objects.get(), author=author, text='x', status='rejected')
    old_event = PinEvent.objects.create(kind='system', box=pin.box, created_at=timezone.now() - timedelta(days=91))
    out = retention.run(now=timezone.now() + timedelta(days=200))
    assert Report.objects.exists() and ModerationDecision.objects.exists() and not PinEvent.objects.filter(pk=old_event.pk).exists()
    out = retention.run(now=timezone.now() + timedelta(days=366))
    assert out['reports_deleted'] == 1 and out['decisions_deleted'] >= 1
    assert not Report.objects.exists() and not ModerationDecision.objects.exists() and not Appeal.objects.exists()


def test_event_retention_setting(settings):
    settings.SPINA3_EVENT_RETENTION_DAYS = 10
    box = make_box('Box')
    PinEvent.objects.create(kind='system', box=box, created_at=timezone.now() - timedelta(days=11))
    fresh = PinEvent.objects.create(kind='system', box=box, created_at=timezone.now() - timedelta(days=9))
    out = StringIO()
    call_command('spina3_retention', stdout=out)
    assert 'events_deleted: 1' in out.getvalue() and list(PinEvent.objects.all()) == [fresh]
