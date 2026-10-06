"""Ruch 6 i 9 planu finansowego: raport tygodniowy (PDF + CSV), próbka publiczna, zapytania z podwójnym potwierdzeniem,
oferta prywatna i pilot. Sieć i SMTP zablokowane; maile podmienione."""
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.test import Client

from news import raport_tygodniowy as weekly, sales
from news.clinic_models import SpinDiagnosis
from news.newsletter_models import NewsletterSubscriber
from news.political_models import PoliticalAccount, PoliticalPost
from news.sales_models import SalesLead, WeeklyReportIssue

pytestmark = pytest.mark.django_db
WARSAW = ZoneInfo('Europe/Warsaw')
NOW = datetime(2026, 10, 12, 6, 40, tzinfo=WARSAW)  # poniedziałek


@pytest.fixture(autouse=True)
def isolated(settings, monkeypatch):
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    monkeypatch.delenv('WEEKLY_SAMPLE_AUTO_PUBLIC', raising=False)
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('No network')), \
         patch('smtplib.SMTP_SSL', side_effect=AssertionError('No delivery')):
        yield
    cache.clear()


def diagnoses(day0, n_per_camp=4):
    rows = []
    for camp in ('government', 'opposition'):
        account = PoliticalAccount.objects.get_or_create(user_id=camp, defaults=dict(handle=camp, camp=camp, enabled=True))[0]
        for i in range(n_per_camp):
            k = PoliticalPost.objects.count() + 1
            at = datetime.combine(day0 + timedelta(days=i), datetime.min.time(), WARSAW) + timedelta(hours=10)
            post = PoliticalPost.objects.create(account=account, post_id=str(k), url=f'https://x.example/{k}', text='cudzy tekst',
                                                published_at=at, camp_at_collection=camp)
            rows.append(SpinDiagnosis.objects.create(post=post, status='approved', verdict=('spin', 'partial', 'no_spin')[i % 3],
                                                     intensity=20 + 10 * i, diagnosed_at=at, headline=f'Nagłówek {k}',
                                                     techniques=[{'name': 'Apel do emocji'}, {'name': 'Straszenie'}]))
    return rows


def test_week_bounds_previous_full_week():
    assert weekly.week_bounds(date(2026, 10, 12)) == (date(2026, 10, 5), date(2026, 10, 12))
    assert weekly.week_bounds(date(2026, 10, 15)) == (date(2026, 10, 5), date(2026, 10, 12))


def test_generate_pdf_csv_same_measure_and_idempotent():
    diagnoses(date(2026, 10, 5))
    diagnoses(date(2026, 9, 28), 2)  # poprzedni tydzień do trendu
    result = weekly.generate(date(2026, 10, 12))
    issue = WeeklyReportIssue.objects.get(pk=result['issue'])
    assert result['produced'] == 1 and issue.status == 'ready' and bytes(issue.pdf).startswith(b'%PDF')
    data = issue.data
    assert data['total'] == 8 and data['total_before'] == 4
    # ten sam wzór dla obu stron: (spin + 0,5 × częściowy) / liczba
    assert data['camps']['government']['weighted_spin_percent'] == data['camps']['opposition']['weighted_spin_percent'] == 62.5
    assert 'rows' not in data and len(data['top']) == 8
    text = bytes(issue.csv).decode('utf-8-sig')
    assert text.splitlines()[0].startswith('sekcja,id,data') and 'cudzy tekst' not in text
    assert text.count('wypowiedź') == 8 and 'https://spin.clinic/klinika/' in text
    assert weekly.generate(date(2026, 10, 12))['status'] == 'already_done'


def test_failed_issue_is_repaired_on_next_run(monkeypatch):
    diagnoses(date(2026, 10, 5))
    monkeypatch.setattr(weekly, 'render_pdf', lambda data: (_ for _ in ()).throw(OSError('font')))
    assert weekly.generate(date(2026, 10, 12))['status'] == 'error'
    monkeypatch.undo()
    assert weekly.generate(date(2026, 10, 12))['produced'] == 1
    assert WeeklyReportIssue.objects.get().status == 'ready'


def test_empty_week_and_club_threshold():
    assert weekly.generate(date(2026, 10, 12))['produced'] == 0
    assert WeeklyReportIssue.objects.get().status == 'empty'
    rows = [{'club': 'A', 'camp': 'government', 'verdict': 'spin', 'intensity': 50, 'techniques': ['X']}] * 2
    rows += [{'club': 'B', 'camp': 'opposition', 'verdict': 'no_spin', 'intensity': 10, 'techniques': ['Y']}] * 3
    result = {c['club']: c for c in weekly.clubs(rows, rows)}
    assert result['A']['weighted_spin_percent'] is None  # poniżej progu: bez wskaźnika
    assert result['B']['weighted_spin_percent'] == 0.0 and result['B']['trend_pp'] == 0.0


def test_public_sample_only_after_approval_and_without_statements(monkeypatch):
    diagnoses(date(2026, 10, 5))
    weekly.generate(date(2026, 10, 12))
    client = Client()
    assert client.get('/api/raporty/probka/').json() == {'available': False}
    WeeklyReportIssue.objects.update(public_approved_at=NOW)
    body = client.get('/api/raporty/probka/').json()
    assert body['available'] and body['total'] == 8 and body['summary']
    assert 'top' not in body and 'rows' not in body and 'x.example' not in str(body)
    assert 'zł' not in str(body)  # bez cen na stronie


def test_auto_public_flag(monkeypatch):
    monkeypatch.setenv('WEEKLY_SAMPLE_AUTO_PUBLIC', 'true')
    diagnoses(date(2026, 10, 5))
    weekly.generate(date(2026, 10, 12))
    assert WeeklyReportIssue.objects.get().public_approved_at


def post(path, **data):
    payload = {'name': 'Anna Nowak', 'organisation': 'Agencja X', 'email': 'anna@example.org', 'org_type': 'agencja',
               'privacy': True, 'newsletter': True, **data}
    return Client().post(path, payload, content_type='application/json')


def test_inquiry_double_opt_in_notifies_owner_and_newsletter(monkeypatch, django_capture_on_commit_callbacks):
    sent, owner = [], []
    monkeypatch.setattr('news.account_mail.send_account_mail', lambda to, subject, body, headers=None: sent.append((to, body)) or True)
    monkeypatch.setattr('news.social_publish._mail', lambda to, subject, body, **kw: owner.append((to, subject, kw)) or True)
    monkeypatch.setenv('SALES_LEAD_EMAIL', 'wlasciciel@example.org')
    monkeypatch.setattr('news.tasks.sales_lead_confirmation_task.delay', lambda pk: sales.send_confirmation(pk))
    with django_capture_on_commit_callbacks(execute=True):
        response = post('/api/raporty/zapytanie/')
    assert response.status_code == 200 and response.json()['status'] == 'check_email'
    lead = SalesLead.objects.get()
    assert lead.status == 'pending' and lead.kind == 'raporty' and not owner
    assert sent and f'/dla-redakcji?potwierdz={lead.token}' in sent[0][1]
    assert not NewsletterSubscriber.objects.exists()  # zgoda czeka na kliknięcie
    confirmed = Client().post('/api/leady/potwierdz/', {'token': lead.token}, content_type='application/json')
    assert confirmed.status_code == 200 and confirmed.json()['kind'] == 'raporty'
    lead.refresh_from_db()
    assert lead.status == 'confirmed' and lead.owner_notified_at
    assert owner[0][0] == 'wlasciciel@example.org' and owner[0][2] == {'important': True}
    subscriber = NewsletterSubscriber.objects.get()
    assert subscriber.status == 'confirmed' and subscriber.source == 'raporty-instytucje' and len(subscriber.consent_version) <= 16
    # drugi klik nie wysyła drugiego maila do właściciela
    Client().post('/api/leady/potwierdz/', {'token': lead.token}, content_type='application/json')
    assert len(owner) == 1


def test_inquiry_validation_honeypot_and_no_newsletter(monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr('news.tasks.sales_lead_confirmation_task.delay', lambda pk: None)
    assert post('/api/raporty/zapytanie/', email='zly').status_code == 400
    assert post('/api/raporty/zapytanie/', privacy=False).status_code == 400
    assert post('/api/raporty/zapytanie/', name='').status_code == 400
    assert post('/api/raporty/zapytanie/', website='bot').status_code == 200 and not SalesLead.objects.exists()
    with django_capture_on_commit_callbacks(execute=True):
        post('/api/raporty/zapytanie/', newsletter=False, org_type='partia')
    lead = SalesLead.objects.get()
    assert lead.org_type == 'partia' and not lead.newsletter  # partie na tych samych warunkach
    monkeypatch.setattr('news.social_publish._mail', lambda *a, **k: True)
    Client().post('/api/leady/potwierdz/', {'token': lead.token}, content_type='application/json')
    assert not NewsletterSubscriber.objects.exists()
    assert Client().post('/api/leady/potwierdz/', {'token': 'x' * 30}, content_type='application/json').status_code == 404


def test_pilot_signup_grant_and_flag(monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr('news.account_mail.send_account_mail', lambda to, subject, body, headers=None: sent.append(body) or True)
    monkeypatch.setattr('news.tasks.sales_lead_confirmation_task.delay', lambda pk: sales.send_confirmation(pk))
    with django_capture_on_commit_callbacks(execute=True):
        post('/api/przeszlosc/pilot/', org_type='redakcja')
    lead = SalesLead.objects.get(kind='pilot')
    assert '/przeszlosc/pilot?potwierdz=' in sent[0] and '60 dni' in sent[0]
    assert not sales.is_pilot_pro('anna@example.org')
    lead.status = 'confirmed'
    lead.save()
    until = sales.grant_pilot(lead, today=date(2026, 10, 12))
    assert until == date(2026, 12, 11) and sales.is_pilot_pro('Anna@Example.org ', today=date(2026, 12, 11))
    assert not sales.is_pilot_pro('anna@example.org', today=date(2026, 12, 12))


def test_loop_repairs_mail_and_expires_pending(monkeypatch):
    lead = SalesLead.objects.create(kind='raporty', name='A', email='a@example.org', token='t' * 30, consent_version='v',
                                    created_at=NOW - timedelta(hours=2))
    old = SalesLead.objects.create(kind='pilot', name='B', email='b@example.org', token='u' * 30, consent_version='v',
                                   created_at=NOW - timedelta(days=31))
    done = SalesLead.objects.create(kind='raporty', name='C', email='c@example.org', token='w' * 30, consent_version='v',
                                    status='confirmed', confirmed_at=NOW)
    monkeypatch.setattr('news.account_mail.send_account_mail', lambda *a, **k: True)
    monkeypatch.setattr('news.social_publish._mail', lambda *a, **k: True)
    result = sales.run(NOW)
    assert result['resent'] == 1 and result['notified'] == 1 and result['expired'] == 1
    assert not SalesLead.objects.filter(pk=old.pk).exists()
    lead.refresh_from_db()
    done.refresh_from_db()
    assert lead.confirmation_sent_at and done.owner_notified_at


def test_private_offer_pdf_has_prices_only_in_pdf():
    from news.oferta_raportow import render, TIERS
    pdf = render('Agencja X', today=date(2026, 10, 12))
    assert pdf.startswith(b'%PDF') and [price for _, price, _ in TIERS] == [490, 990]


def test_admin_offer_and_weekly_download(admin_client):
    diagnoses(date(2026, 10, 5))
    issue = WeeklyReportIssue.objects.get(pk=weekly.generate(date(2026, 10, 12))['issue'])
    response = admin_client.get(f'/admin/news/weeklyreportissue/{issue.pk}/plik/pdf/')
    assert response.status_code == 200 and response.content.startswith(b'%PDF')
    lead = SalesLead.objects.create(kind='raporty', name='A', organisation='Org', email='a@example.org', token='z' * 30,
                                    consent_version='v', status='confirmed')
    response = admin_client.post('/admin/news/saleslead/', {'action': 'offer_pdf', '_selected_action': [lead.pk]})
    assert response.status_code == 200 and response.content.startswith(b'%PDF')
    admin_client.post('/admin/news/weeklyreportissue/', {'action': 'approve_public', '_selected_action': [issue.pk]})
    issue.refresh_from_db()
    assert issue.public_approved_at
