from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from news import account_warden as w
from news import warden_second_key as k
from news.political_models import PoliticalAccount, WardenReview
from news.test_account_warden import add, offline, report, target, user_data  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db
UNAVAILABLE = {'errors': [{'resource_id': '1234', 'type': 'https://api.x.com/2/problems/resource-unavailable'}]}


@pytest.fixture(autouse=True)
def budget(monkeypatch):
    monkeypatch.setenv('WARDEN_SECOND_KEY_ENABLED', 'true')
    monkeypatch.setenv('WARDEN_SECOND_KEY_AI', 'false')
    monkeypatch.setenv('WARDEN_SECOND_KEY_DAILY_X_USD', '1')


def first_key(monkeypatch, payload):
    a = add(target())
    PoliticalAccount.objects.filter(pk=a.pk).update(last_verified_at=None)
    monkeypatch.setattr(w, 'x_lookup', lambda **kw: payload)
    w.verify_accounts(report(), 100)
    a.refresh_from_db()
    return a, WardenReview.objects.get(account=a)


def later(review, hours=7):
    WardenReview.objects.filter(pk=review.pk).update(created_at=timezone.now() - timedelta(hours=hours),
                                                     due_at=timezone.now() - timedelta(minutes=1))


@pytest.mark.parametrize('payload', [UNAVAILABLE, {'data': [user_data(protected=True)]}])
def test_first_key_alone_never_disables(payload, monkeypatch):
    a, review = first_key(monkeypatch, payload)
    assert a.enabled and review.status == 'pending' and review.category in ('unavailable', 'protected')


def test_two_keys_agree_disable(monkeypatch):
    a, review = first_key(monkeypatch, UNAVAILABLE)
    later(review)
    assert k.verify(review.pk) == 'disabled'
    a.refresh_from_db()
    assert not a.enabled and a.last_error.startswith('warden:')


def test_keys_differ_go_to_owner(monkeypatch):
    a, review = first_key(monkeypatch, UNAVAILABLE)
    later(review)
    monkeypatch.setattr(w, 'x_lookup', lambda **kw: {'data': [user_data()]})
    assert k.verify(review.pk) == 'owner'
    a.refresh_from_db()
    assert a.enabled


def test_second_key_waits_six_hours(monkeypatch):
    a, review = first_key(monkeypatch, UNAVAILABLE)
    assert k.verify(review.pk) == 'waiting'


def test_no_budget_keeps_request_queued(monkeypatch):
    monkeypatch.setenv('WARDEN_SECOND_KEY_DAILY_X_USD', '0')
    a, review = first_key(monkeypatch, UNAVAILABLE)
    later(review)
    assert k.verify(review.pk) == 'queued'
    a.refresh_from_db()
    assert a.enabled


@pytest.mark.parametrize('shown,expected,ok', [
    ('Jan Kowalski | Poseł', 'Jan Kowalski', True),
    ('J. Kowalski', 'Jan Kowalski', True),
    ('Kancelaria Premiera', 'KPRM', True),
    ('Kowalski', 'Jan Kowalski', False),
    ('Anna Nowak', 'Jan Kowalski', False),
])
def test_tolerant_name(shown, expected, ok):
    assert k.tolerant_name(shown, expected) is ok


def legacy(error, suffix='1'):
    a = add(target(suffix=suffix), user_data(handle='Konto' + suffix, uid='12' + suffix))
    PoliticalAccount.objects.filter(pk=a.pk).update(enabled=False, last_error=error, last_verified_at=timezone.now())
    return a


def test_recheck_preview_does_not_write():
    a = legacy('warden: nazwa wyświetlana nie pasuje do osoby lub partii')
    rows = k.recheck(apply=False)
    a.refresh_from_db()
    assert rows[0]['restore'] and not a.enabled


def test_recheck_apply_restores_name_only_disable():
    a = legacy('warden: nazwa wyświetlana nie pasuje do osoby lub partii')
    b = legacy('warden: konto chronione', suffix='2')
    k.recheck(apply=True)
    a.refresh_from_db(); b.refresh_from_db()
    assert a.enabled and a.last_error == ''
    assert not b.enabled
