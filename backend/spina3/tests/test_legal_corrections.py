"""S2 pkt 2: sprostowanie diagnozy (prawo prasowe): 21 dni, 2x objętość, oświadczenie, 3 dni robocze, odmowa z art. 33."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from spina3 import corrections, legal
from spina3.models import BoxLink, Correction

from .conftest import make_box, make_user

pytestmark = pytest.mark.django_db

BODY = {'name': 'Jan Kowalski', 'email': 'jan@example.org', 'text': 'Nie powiedziałem tego w tym kontekście.', 'statement': True}


def diagnosis_box(**kwargs):
    return make_box('Diagnoza: wpis', kind='diagnosis', text='Diagnoza wpisu: liczba bez punktu odniesienia.', **kwargs)


def aware(*args):
    return timezone.make_aware(datetime(*args), timezone.get_current_timezone())


def test_working_days_skip_weekends_and_holidays():
    assert legal._easter(2026) == date(2026, 4, 5) and legal._easter(2027) == date(2027, 3, 28)
    assert date(2026, 12, 24) in legal.holidays(2026) and date(2024, 12, 24) not in legal.holidays(2024)
    # środa 23.12.2026: Wigilia, święta i weekend -> 28, 29, 30 grudnia
    assert legal.add_working_days(aware(2026, 12, 23, 10), 3).date() == date(2026, 12, 30)
    # piątek 30.10.2026: weekend, 2.11 poniedziałek, 3.11, 4.11 (1.11 święto w niedzielę)
    assert legal.add_working_days(aware(2026, 10, 30, 9), 3).date() == date(2026, 11, 4)
    # Boże Ciało 2026: czwartek 4.06
    assert legal.add_working_days(aware(2026, 6, 2, 12), 3).date() == date(2026, 6, 8)


def test_submit_returns_due_at_and_validates(api):
    box = diagnosis_box(published_at=timezone.now() - timedelta(days=2))
    r = api.post(f'/api/spina3/box/{box.pk}/correction/', BODY, format='json')
    assert r.status_code == 201
    body = r.json()
    row = Correction.objects.get()
    assert body['status'] == 'pending' and parse_datetime(body['due_at']) == row.due_at
    assert row.due_at == legal.add_working_days(row.created_at, 3) and not row.consent_public_name
    assert api.post(f'/api/spina3/box/{box.pk}/correction/', {**BODY, 'statement': False}, format='json').json()['code'] == 'statement'
    too_long = 'x' * (2 * len(box.text) + 1)
    r = api.post(f'/api/spina3/box/{box.pk}/correction/', {**BODY, 'text': too_long}, format='json')
    assert r.status_code == 400 and r.json()['code'] == 'length'
    article = make_box('Artykuł')
    assert api.post(f'/api/spina3/box/{article.pk}/correction/', BODY, format='json').status_code == 404


def test_deadline_21_days():
    box = diagnosis_box(published_at=timezone.now() - timedelta(days=22))
    with pytest.raises(corrections.CorrectionError) as exc:
        corrections.submit(box, name='Jan', email='jan@example.org', text='Tekst', statement=True)
    assert exc.value.code == 'deadline'


def test_team_decision_publish_and_public_name_only_with_consent(api):
    post = make_box('Wpis', kind='post', author_handle='posel')
    box = diagnosis_box()
    BoxLink.objects.create(box=post, target=box, kind='diagnosis_of')
    row = corrections.submit(box, name='Jan Kowalski', email='jan@example.org', text='Sprostowanie.', statement=True)
    staff, user = make_user('zespol_c', staff=True), make_user('zwykly_c')
    api.force_authenticate(user)
    assert api.post(f'/api/spina3/moderation/corrections/{row.pk}/', {'decision': 'publish'}, format='json').status_code == 403
    api.force_authenticate(staff)
    assert api.get('/api/spina3/moderation/queue/').json()['corrections'][0]['id'] == row.pk
    assert api.post(f'/api/spina3/moderation/corrections/{row.pk}/', {'decision': 'publish'}, format='json').json()['status'] == 'published'
    assert api.post(f'/api/spina3/moderation/corrections/{row.pk}/', {'decision': 'publish'}, format='json').status_code == 409
    api.force_authenticate(None)
    for target in (box, post):
        correction = api.get(f'/api/spina3/box/{target.pk}/').json()['correction']
        assert correction['text'] == 'Sprostowanie.' and correction['author'] == legal.CORRECTION_PUBLIC_NAME_FALLBACK
        assert 'email' not in correction and 'Kowalski' not in str(correction)
    row.refresh_from_db()
    row.consent_public_name = True
    row.save()
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['correction']['author'] == 'Jan Kowalski'


def test_rejection_requires_art33_reason(api):
    box = diagnosis_box()
    row = corrections.submit(box, name='Jan', email='jan@example.org', text='Sprostowanie.', statement=True)
    api.force_authenticate(make_user('zespol_r', staff=True))
    assert api.post(f'/api/spina3/moderation/corrections/{row.pk}/', {'decision': 'reject'}, format='json').status_code == 400
    r = api.post(f'/api/spina3/moderation/corrections/{row.pk}/', {'decision': 'reject', 'rejection_reason': 'unlawful'}, format='json')
    assert r.status_code == 200 and r.json()['rejection_label'].startswith('art. 33')
    row.refresh_from_db()
    assert row.status == 'rejected' and row.rejection_reason == 'unlawful'
    assert api.get(f'/api/spina3/box/{box.pk}/').json()['correction'] is None
