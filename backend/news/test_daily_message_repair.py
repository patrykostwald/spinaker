"""Przekaz dnia po 6.10 (brak przekazu rządzących, błąd tylko w logu): Mercury jako trzeci darmowy zapas, zapisany powód
niepowodzenia (wiersz failed, nigdy publiczny, nadpisywany), naprawa co godzinę tylko brakujących, mail do właściciela
dopiero po przebiegu 21:30. Bez sieci."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from news import clinic, clinic_ai, daily_schedule as schedule, inception
from news.clinic_models import ClinicDailyMessage
from news.political_models import PoliticalAccount, PoliticalPost

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 22, 0, tzinfo=ZoneInfo('Europe/Warsaw'))
DAY = NOW.date()
TEXT = 'Na program edukacyjny przeznaczono 20 mln zł.'
MERCURY = {'camp': 'government', 'thesis': '', 'points': [], 'tone': [], 'analysis': '', 'themes': ['edukacja'],
           'message': 'Rządzący podkreślają, że program edukacyjny dostał 20 mln zł.'}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for name in ('INCEPTION_API_KEY', 'INCEPTION_FREE_TOKENS', 'INCEPTION_ALLOW_PAID', 'GROQ_API_KEY', 'NIM_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'false')
    monkeypatch.setenv('COUNCIL_RECRUITER_EMAIL', 'owner@example.org')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('Bez prawdziwego HTTP')), \
         patch('news.social_publish._mail', return_value=True) as mail, \
         patch('news.push_events._enqueue_staff'), \
         patch('config.celery.app.send_task'):
        yield SimpleNamespace(mail=mail)
    cache.clear()


def post(camp='government'):
    n = PoliticalPost.objects.count() + 1
    account = PoliticalAccount.objects.create(user_id=str(n), handle='konto' + str(n), camp=camp, enabled=True)
    return PoliticalPost.objects.create(account=account, post_id=str(n), text=TEXT, camp_at_collection=camp,
                                        published_at=NOW - timedelta(hours=2), fetched_at=NOW - timedelta(hours=1))


class Response:
    def __init__(self, status=200, data=None, text=''):
        self.status_code, self._data, self.text, self.headers = status, data, text, {}

    def json(self):
        return self._data


# --- 1. Mercury po Groq i NIM --------------------------------------------------------------------------------------

def test_daily_message_falls_back_to_mercury_when_free_models_fail(monkeypatch):
    monkeypatch.setenv('INCEPTION_API_KEY', 'inc-test')
    sent = []

    def inception_post(url, **kwargs):
        sent.append({'url': url, 'body': kwargs['json'], 'headers': kwargs['headers']})
        return Response(200, {'model': 'mercury-2.5', 'choices': [{'message': {'content': json.dumps(MERCURY)}}],
                              'usage': {'total_tokens': 1500}})
    monkeypatch.setattr(inception.requests, 'post', inception_post)
    with patch.object(clinic_ai, '_free_chat', side_effect=clinic_ai.ClinicAIError('free_models_unavailable')) as free, \
         patch('news.daily_message_fallback.generate') as paid:
        result = clinic_ai.daily_message('obóz rządzący', DAY.isoformat(), [{'author': 'Jan Nowak', 'text': TEXT}])
    assert free.call_count == 2  # Groq i NIM próbowane przed Mercury
    paid.assert_not_called()  # płatny Gemini nadal tylko u Ratownika
    assert result['usage']['model'] == 'mercury-2.5' and result['message'].startswith('Rządzący')
    assert result['themes'] == ['edukacja']
    request = sent[0]
    assert request['url'] == 'https://api.inceptionlabs.ai/v1/chat/completions'
    assert request['headers']['Authorization'] == 'Bearer inc-test'
    assert request['body']['response_format'] == {'type': 'json_object'}
    assert request['body']['max_completion_tokens'] == 2500
    assert inception.usage()['today'] == 1500  # tokeny policzone w darmowej puli


def test_mercury_without_key_is_skipped_and_free_reason_stays():
    with patch.object(clinic_ai, '_free_chat', side_effect=clinic_ai.ClinicAIError('free_models_unavailable')), \
         patch.object(inception, 'chat') as chat:
        with pytest.raises(clinic_ai.ClinicAIError) as error:
            clinic_ai.daily_message('obóz rządzący', DAY.isoformat(), [{'author': 'Jan Nowak', 'text': TEXT}])
    assert error.value.code == 'free_models_unavailable'
    chat.assert_not_called()


def test_mercury_respects_free_pool_without_network(monkeypatch):
    monkeypatch.setenv('INCEPTION_API_KEY', 'inc-test')
    monkeypatch.setenv('INCEPTION_FREE_TOKENS', '1000')  # próg stopu 90% = 900 tokenów
    inception.record(950)
    with patch.object(clinic_ai, '_free_chat', side_effect=clinic_ai.ClinicAIError('free_models_unavailable')), \
         patch.object(inception.requests, 'post') as http:
        with pytest.raises(clinic_ai.ClinicAIError) as error:
            clinic_ai.daily_message('obóz rządzący', DAY.isoformat(), [{'author': 'Jan Nowak', 'text': TEXT}])
    assert error.value.code == 'inception_free_budget'
    http.assert_not_called()
    assert clinic.message_error_label(error.value.code) == 'Wyczerpana darmowa pula Inception (Mercury).'


# --- 2. powód zapisany, nigdy publiczny, nadpisywany -----------------------------------------------------------------

def test_failed_run_is_stored_and_later_overwritten(monkeypatch):
    for _ in range(3):
        post('government')
    monkeypatch.setattr(clinic_ai, 'daily_message', Mock(side_effect=clinic_ai.ClinicAIError('free_models_unavailable')))
    result = clinic.run_daily_messages(DAY, camps=('government',))
    assert result['status'] == 'error' and result['errors'] == {f'{DAY}:government': 'Darmowe modele nie odpowiedziały.'}
    row = ClinicDailyMessage.objects.get(day=DAY, camp='government')
    assert row.status == 'failed' and row.message == ''
    assert row.error == 'free_models_unavailable: Darmowe modele nie odpowiedziały.'
    assert clinic.daily_message_data('government') is None  # nic publicznego
    status, detail = schedule.check_message('government', NOW.replace(hour=13))
    assert status == 'late' and 'Ostatni błąd: free_models_unavailable' in detail['detail']
    # kolejny przebieg nadpisuje wiersz failed zamiast go omijać
    monkeypatch.setattr(clinic_ai, 'daily_message', lambda label, day, posts, **kw: {
        'message': 'Rządzący podkreślają program edukacyjny.', 'themes': ['edukacja'], 'usage': {'model': 'mercury-2.5'}})
    result = clinic.repair_daily_messages(DAY)
    assert result['created'] == {'government': row.pk} and result['errors'] == {}
    row.refresh_from_db()
    assert row.status == 'pending_review' and row.error == '' and row.message.startswith('Rządzący')
    assert row.model_name == 'mercury-2.5'
    assert ClinicDailyMessage.objects.filter(day=DAY, camp='government').count() == 1


def test_failure_never_replaces_an_existing_message(monkeypatch):
    for _ in range(3):
        post('opposition')
    row = ClinicDailyMessage.objects.create(day=DAY, camp='opposition', message='Gotowy przekaz.', status='pending_review')
    monkeypatch.setattr(clinic_ai, 'daily_message', Mock(side_effect=clinic_ai.ClinicAIError('not_polish')))
    result = clinic.run_daily_messages(DAY, camps=('opposition',))
    assert result['errors'] == {f'{DAY}:opposition': 'Model nie odpowiedział po polsku.'}
    row.refresh_from_db()
    assert row.status == 'pending_review' and row.message == 'Gotowy przekaz.' and row.error == ''


def test_catch_up_retries_yesterday_after_failed_row():
    yesterday = DAY - timedelta(days=1)
    ClinicDailyMessage.objects.create(day=yesterday, camp='opposition', message='', status='failed', error='x')
    ClinicDailyMessage.objects.create(day=yesterday, camp='government', message='Przekaz.', status='approved')
    with patch.object(clinic, '_daily_messages_for', return_value={}) as run, \
         patch.object(clinic, 'send_review_alert', return_value='nothing'):
        clinic.run_daily_messages()
    assert run.call_args_list[0] == call(yesterday, ['opposition'])


# --- 3. naprawa co godzinę -------------------------------------------------------------------------------------------

def test_repair_beat_entry_and_task():
    assert schedule.BEAT_PLAN['clinic-daily-messages-repair'] == ('clinic_daily_messages_repair_task', {'hour': '10-23', 'minute': 40})
    from news import tasks
    assert tasks.clinic_daily_messages_repair_task.name == 'news.tasks.clinic_daily_messages_repair_task'


def test_hourly_repair_skips_when_both_messages_exist():
    for camp in clinic.CAMPS:
        ClinicDailyMessage.objects.create(day=DAY, camp=camp, message='Przekaz.', status='pending_review')
    with patch.object(clinic, 'run_daily_messages') as run, patch.object(clinic_ai, 'daily_message') as model:
        assert clinic.repair_daily_messages(DAY) == {'status': 'ok', 'created': {}, 'skipped': 'complete'}
    run.assert_not_called()
    model.assert_not_called()


def test_hourly_repair_runs_only_missing_or_failed_camp():
    staff = get_user_model().objects.create_user(username='staff')
    ClinicDailyMessage.objects.create(day=DAY, camp='government', message='Przekaz.', status='rejected', reviewed_by=staff)
    ClinicDailyMessage.objects.create(day=DAY, camp='opposition', message='', status='failed', error='x')
    with patch.object(clinic, 'run_daily_messages', return_value={'status': 'ok', 'created': {}, 'errors': {}}) as run:
        clinic.repair_daily_messages(DAY)
    assert run.call_args == call(DAY, camps=['opposition'], only_missing=True)  # odrzucony ręcznie zostaje odrzucony


# --- 4. właściciel dopiero po 21:30 ----------------------------------------------------------------------------------

def test_owner_alert_only_after_evening_run(isolated):
    row = ClinicDailyMessage.objects.create(day=DAY, camp='government', message='', status='failed',
                                            error='free_models_unavailable: Darmowe modele nie odpowiedziały.')
    assert clinic.alert_owner_missing_messages(DAY, now=NOW.replace(hour=21, minute=29)) == []
    isolated.mail.assert_not_called()
    assert clinic.alert_owner_missing_messages(DAY, now=NOW.replace(hour=21, minute=40)) == ['government']
    isolated.mail.assert_called_once()
    to, subject, body = isolated.mail.call_args.args
    assert to == 'owner@example.org' and 'brak przekazu dnia (rządzący)' in subject
    assert 'Darmowe modele nie odpowiedziały.' in body and isolated.mail.call_args.kwargs == {'important': True}
    row.refresh_from_db()
    assert row.alert_sent_at is not None
    assert clinic.alert_owner_missing_messages(DAY, now=NOW) == []  # jeden mail na obóz i dzień


def test_repair_after_evening_mails_owner_once(isolated, monkeypatch):
    for _ in range(3):
        post('opposition')
    monkeypatch.setattr(clinic_ai, 'daily_message', Mock(side_effect=clinic_ai.ClinicAIError('free_models_unavailable')))
    assert clinic.repair_daily_messages(DAY)['owner_alerts'] == ['opposition']
    assert clinic.repair_daily_messages(DAY)['owner_alerts'] == []
    assert isolated.mail.call_count == 1
    assert ClinicDailyMessage.objects.get(day=DAY, camp='opposition').status == 'failed'
