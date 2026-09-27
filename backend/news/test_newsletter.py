import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from news import newsletter
from news.newsletter_models import NewsletterSubscriber

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_mail(monkeypatch):
    cache.clear()
    sent = []
    monkeypatch.setattr(newsletter, '_queue_confirmation', lambda pk: sent.append(pk))
    return sent


def subscribe(client, **data):
    return client.post('/api/newsletter/subscribe/', {'email': 'Jan@Example.org', 'consent': True, 'source': 'home', **data}, format='json')


def test_double_opt_in_confirm_and_unsubscribe(no_mail):
    client = APIClient()
    response = subscribe(client)
    assert response.status_code == 200 and response.data['status'] == 'check_email'
    row = NewsletterSubscriber.objects.get()
    assert row.email == 'jan@example.org' and row.status == 'pending' and no_mail == [row.pk]
    assert row.consent_version == newsletter.CONSENT_VERSION

    confirmed = client.post('/api/newsletter/confirm/', {'token': row.token}, format='json')
    row.refresh_from_db()
    assert confirmed.status_code == 200 and row.status == 'confirmed' and row.confirmed_at

    # Ponowny zapis potwierdzonego adresu: ta sama odpowiedź, bez nowego maila (nie zdradzamy, kto jest na liście).
    assert subscribe(client).data['status'] == 'check_email' and len(no_mail) == 1

    client.post('/api/newsletter/unsubscribe/', {'token': row.token}, format='json')
    row.refresh_from_db()
    assert row.status == 'unsubscribed' and row.unsubscribed_at
    assert client.post('/api/newsletter/confirm/', {'token': row.token}, format='json').status_code == 404


def test_requires_consent_valid_email_and_ignores_bots(no_mail):
    client = APIClient()
    assert subscribe(client, consent=False).status_code == 400
    assert subscribe(client, email='nie-mail').status_code == 400
    assert subscribe(client, website='http://spam').data['status'] == 'check_email'
    assert not NewsletterSubscriber.objects.exists() and no_mail == []


def test_stats_are_staff_only():
    NewsletterSubscriber.objects.create(email='a@example.org', token='a' * 43, consent_version='x', status='confirmed')
    client = APIClient()
    assert client.get('/api/staff/newsletter/').status_code in (401, 403)
    staff = get_user_model().objects.create_user('szef', password='x', is_staff=True)
    client.force_authenticate(staff)
    data = client.get('/api/staff/newsletter/').data
    assert data['confirmed'] == 1 and data['pending'] == 0
