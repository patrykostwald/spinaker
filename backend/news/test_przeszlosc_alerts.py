"""Sprint 1 przeszłość.today: alerty e-mail (podwójne potwierdzenie, dzienny list, wypisanie jednym kliknięciem)."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_alerts
from news.przeszlosc_alerts import send_digests
from news.przeszlosc_models import PrzeszloscAlert
from news.test_przeszlosc_osoba import mp, record, x_account, x_post

pytestmark = pytest.mark.django_db


@pytest.fixture
def mails(monkeypatch):
    sent = []

    def fake(recipient, subject, body, headers=None):
        sent.append({'to': recipient, 'subject': subject, 'body': body, 'headers': headers or {}})
        return True
    monkeypatch.setattr('news.account_mail.send_account_mail', fake)
    monkeypatch.setattr(przeszlosc_alerts, '_queue', lambda pk: przeszlosc_alerts.send_confirmation(pk))
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    cache.clear()
    yield sent
    cache.clear()


def subscribe(client, **data):
    return client.post('/api/przeszlosc/alerty/', {'email': 'red@example.pl', 'consent': True, **data}, format='json')


def test_double_opt_in_confirm_and_one_click_unsubscribe(mails):
    client = APIClient()
    r = subscribe(client, kind='topic', q='CPK')
    assert r.status_code == 200 and r.json()['status'] == 'check_email'
    alert = PrzeszloscAlert.objects.get()
    assert alert.status == 'pending' and alert.key == 'topic:cpk' and alert.confirmation_sent_at
    assert len(mails) == 1 and f'potwierdz={alert.token}' in mails[0]['body'] and '—' not in mails[0]['body']
    # ponowny zapis w ciągu 10 minut: ta sama odpowiedź, bez drugiego listu
    assert subscribe(client, kind='topic', q='CPK').json()['status'] == 'check_email' and len(mails) == 1
    r = client.post('/api/przeszlosc/alerty/potwierdz/', {'token': alert.token}, format='json')
    assert r.json() == {'status': 'confirmed', 'kind': 'topic', 'label': 'CPK', 'url': '/przeszlosc?q=CPK'}
    alert.refresh_from_db()
    assert alert.status == 'confirmed' and alert.confirmed_at
    # RFC 8058: POST z nagłówka List-Unsubscribe, token w adresie
    r = client.post(f'/api/przeszlosc/alerty/wypisz/?t={alert.token}&wszystkie=1', 'List-Unsubscribe=One-Click',
                    content_type='application/x-www-form-urlencoded')
    assert r.json()['status'] == 'unsubscribed' and r.json()['count'] == 1
    assert client.post('/api/przeszlosc/alerty/potwierdz/', {'token': alert.token}, format='json').status_code == 404


def test_validation_honeypot_and_limits(mails):
    client = APIClient()
    figure = mp('Anna Kowalska', 77)
    assert subscribe(client, kind='topic', q='CPK', email='zly').status_code == 400
    assert subscribe(client, kind='topic', q='CPK', consent=False).status_code == 400
    assert subscribe(client, kind='topic', q='a').status_code == 400
    assert subscribe(client, kind='person', figure='999999').status_code == 400
    assert subscribe(client, kind='coś').status_code == 400
    cache.clear()  # limit 5 zapisów na godzinę z jednego adresu IP
    assert subscribe(client, kind='topic', q='CPK', website='bot').json()['status'] == 'check_email'
    assert not PrzeszloscAlert.objects.exists()
    assert subscribe(client, kind='person', figure=f'{figure.pk}-anna-kowalska').status_code == 200
    assert PrzeszloscAlert.objects.get().figure == figure
    for i in range(przeszlosc_alerts.MAX_PER_EMAIL + 2):
        PrzeszloscAlert.objects.create(email='pelny@example.pl', kind='topic', key=f'topic:t{i}', query=f'temat {i}', token=f'tok{i:030d}',
                                       consent_version='x', status='confirmed')
    cache.clear()
    before = PrzeszloscAlert.objects.filter(email='pelny@example.pl').count()
    assert subscribe(client, kind='topic', q='Nowy temat', email='pelny@example.pl').json()['status'] == 'check_email'
    assert PrzeszloscAlert.objects.filter(email='pelny@example.pl').count() == before


def test_disabled_returns_404(mails, monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'false')
    assert subscribe(APIClient(), kind='topic', q='CPK').status_code == 404


def test_rate_limit_on_subscribe(mails):
    client = APIClient()
    codes = [subscribe(client, kind='topic', q=f'Temat numer {i}').status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[-1] == 429


def confirmed(**kw):
    defaults = dict(email='red@example.pl', consent_version='x', status='confirmed', confirmed_at=timezone.now() - timedelta(days=1))
    defaults.update(kw)
    return PrzeszloscAlert.objects.create(**defaults)


def test_daily_digest_topic_and_person_one_mail_per_address(mails):
    figure = mp('Anna Kowalska', 77)
    account = x_account(figure, 'AnnaKowalska', '7001')
    x_post(account, '9001', 'Budowa CPK ruszy w terminie.', days_ago=0)
    record(3, 'Interpelacja w sprawie lotniska', [(77, None)])
    topic = confirmed(kind='topic', key='topic:cpk', query='CPK', token='t' * 40)
    person = confirmed(kind='person', key=f'person:{figure.pk}', figure=figure, token='p' * 40)
    confirmed(kind='topic', key='topic:nic', query='Turów', token='n' * 40, email='inny@example.pl')
    report = send_digests()
    assert report == {'emails': 2, 'sent': 1, 'empty': 1, 'failed': 0, 'skipped': 0}
    assert len(mails) == 1
    body = mails[0]['body']
    assert '== Temat: CPK' in body and '== Osoba: Anna Kowalska' in body and 'Interpelacja w sprawie lotniska' in body
    assert 'https://x.com/AnnaKowalska/status/9001' in body and f'wypisz={topic.token}' in body and 'wszystkie=1' in body
    assert 'utm_' not in body and '—' not in body
    assert mails[0]['headers']['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'
    assert '/api/przeszlosc/alerty/wypisz/?t=' in mails[0]['headers']['List-Unsubscribe']
    person.refresh_from_db()
    topic.refresh_from_db()
    assert person.last_sent_at and any(i.startswith('record:') for i in person.sent_ids) and topic.sent_ids
    # drugi przebieg tego samego dnia nic nie wysyła
    assert send_digests()['sent'] == 0 and len(mails) == 1
    # następnego dnia: te same pozycje się nie powtarzają
    assert send_digests(now=timezone.now() + timedelta(days=1))['sent'] == 0


def test_digest_command_dry_run(mails, capsys):
    figure = mp('Anna Kowalska', 77)
    record(4, 'Zapytanie o ceny energii', [(77, figure)], kind='questions')
    confirmed(kind='person', key=f'person:{figure.pk}', figure=figure, token='d' * 40)
    call_command('przeszlosc_alerts_digest', '--dry-run')
    out = capsys.readouterr().out
    assert '"sent": 1' in out and 'Zapytanie o ceny energii' in out and not mails
    assert PrzeszloscAlert.objects.get().last_sent_at is None


def test_pending_and_unsubscribed_alerts_get_nothing(mails):
    figure = mp('Anna Kowalska', 77)
    record(6, 'Interpelacja', [(77, figure)])
    confirmed(kind='person', key=f'person:{figure.pk}', figure=figure, token='q' * 40, status='pending')
    confirmed(kind='topic', key='topic:interpelacja', query='Interpelacja', token='u' * 40, status='unsubscribed')
    assert send_digests()['emails'] == 0 and not mails
