from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from news.clinic_interview import interview_data
from news.clinic_models import ClinicDailyMessage, ClinicInterview, WeeklyReport
from news.test_clinic import account, post

pytestmark = pytest.mark.django_db


def interview(number=1, **kwargs):
    fields = dict(day=date(2026, 9, 29), video_id=f'{number:011d}',
                  url=f'https://www.youtube.com/watch?v={number:011d}', status='approved',
                  title='Rozmowa o gospodarce', channel='Kanał testowy', guest_name='Anna Nowak',
                  guest_role='posłanka KO', host_name='Jan Kowalski', diagnosed_at=timezone.now())
    fields.update(kwargs)
    return ClinicInterview.objects.create(**fields)


def test_interview_visibility_and_detail():
    visible = interview()
    hidden = interview(2, hidden_at=timezone.now())
    unpublished = [interview(index, status=status) for index, status in enumerate(
        ['queued', 'pending_review', 'rejected', 'failed'], start=3)]
    client = APIClient()
    response = client.get('/api/clinic/interviews/')
    assert response.status_code == 200
    assert response.json()['count'] == 1
    assert [row['id'] for row in response.json()['results']] == [visible.pk]
    detail = client.get(f'/api/clinic/interviews/{visible.pk}/')
    assert detail.status_code == 200
    assert detail.data == interview_data(visible)
    for row in [hidden, *unpublished]:
        assert client.get(f'/api/clinic/interviews/{row.pk}/').status_code == 404
    assert client.get('/api/clinic/interviews/999999/').status_code == 404


def test_interviews_pagination_includes_current_and_breaks_ties():
    stamp = timezone.now()
    rows = [interview(index, diagnosed_at=stamp) for index in range(21)]
    client = APIClient()
    first = client.get('/api/clinic/interviews/').json()
    second = client.get('/api/clinic/interviews/?page=2').json()
    assert first['count'] == second['count'] == 21
    assert first['next_page'] == 2 and second['next_page'] is None
    assert len(first['results']) == 20
    assert [row['id'] for row in first['results'] + second['results']] == [row.pk for row in reversed(rows)]
    assert client.get('/api/clinic/interviews/?page=3').json()['results'] == []


@pytest.mark.parametrize('query', ['anna', 'kowalski', 'gospodarce'])
def test_interview_search_and_channel(query):
    match = interview()
    interview(2, channel='Inny kanał')
    interview(3, guest_name='Inny gość', host_name='Inny prowadzący', title='Inny tytuł')
    interview(4, channel='Ukryty kanał', hidden_at=timezone.now())
    result = APIClient().get('/api/clinic/interviews/', {'q': query, 'channel': 'Kanał testowy'}).json()
    assert result['count'] == 1
    assert [row['id'] for row in result['results']] == [match.pk]
    assert result['channels'] == ['Inny kanał', 'Kanał testowy']
    assert APIClient().get('/api/clinic/interviews/', {'q': 'brak'}).json()['count'] == 0


def test_messages_group_by_approved_days_and_paginate():
    latest = date(2026, 9, 29)
    for offset in range(15):
        for camp in ['government', 'opposition']:
            ClinicDailyMessage.objects.create(day=latest - timedelta(days=offset), camp=camp,
                                              status='approved', message=f'{camp} {offset}', analysis='Analiza')
    ClinicDailyMessage.objects.filter(day=latest, camp='opposition').update(status='pending_review')
    ClinicDailyMessage.objects.create(day=latest + timedelta(days=1), camp='government', status='rejected', message='Ukryty')
    client = APIClient()
    first = client.get('/api/clinic/messages/').json()
    second = client.get('/api/clinic/messages/?page=2').json()
    assert first['count'] == second['count'] == 15
    assert first['next_page'] == 2 and second['next_page'] is None
    assert len(first['results']) == 14 and len(second['results']) == 1
    assert first['results'][0]['day'] == str(latest)
    assert first['results'][0]['opposition'] is None
    assert first['results'][0]['government']['analysis'] == 'Analiza'
    assert first['results'][1]['government'] and first['results'][1]['opposition']
    assert [row['day'] for row in first['results'] + second['results']] == [str(latest - timedelta(days=i)) for i in range(15)]
    assert client.get('/api/clinic/messages/?page=3').json()['results'] == []


@pytest.mark.parametrize('endpoint', ['interviews', 'messages'])
def test_empty_archives_and_invalid_pages(endpoint):
    client = APIClient()
    result = client.get(f'/api/clinic/{endpoint}/').json()
    assert result['results'] == [] and result['count'] == 0 and result['next_page'] is None
    assert client.get(f'/api/clinic/{endpoint}/?page=invalid').status_code == 400
    assert client.get(f'/api/clinic/{endpoint}/?page=0').status_code == 200


def test_message_detail_both_camps_scope_and_all_sources():
    day = date(2026, 9, 27)
    acc = account()
    sources = [post(acc, str(4000 + index), hours_ago=index) for index in range(61)]
    for camp in ('government', 'opposition'):
        message = ClinicDailyMessage.objects.create(day=day, camp=camp, status='approved',
            message=f'Przekaz {camp}', analysis='Pełna analiza', model_name='model-test', themes=['Temat'])
        message.posts.add(*sources)
    response = APIClient().get(f'/api/clinic/messages/{day}/')
    assert response.status_code == 200
    assert response.data['day'] == day
    for camp in ('government', 'opposition'):
        value = response.data[camp]
        assert value['message'] == f'Przekaz {camp}' and value['analysis'] == 'Pełna analiza'
        assert value['posts_count'] == len(value['posts']) == 61  # bez limitu 60 ze starego podglądu
        assert value['scope']['date_from'] == sources[-1].published_at
        assert value['scope']['date_to'] == sources[0].published_at
        assert value['posts'][0]['url'] == sources[0].url
        assert value['posts'][0]['handle'] == acc.handle
        assert value['created_at'] and value['model'] == 'model-test'


def test_message_detail_links_to_neighbouring_published_days():
    for day, status in [(date(2026, 9, 25), 'approved'), (date(2026, 9, 26), 'pending_review'),
                        (date(2026, 9, 27), 'approved'), (date(2026, 9, 28), 'rejected'), (date(2026, 9, 29), 'approved')]:
        ClinicDailyMessage.objects.create(day=day, camp='government', status=status, message='Przekaz')
    middle = APIClient().get('/api/clinic/messages/2026-09-27/').json()
    assert middle['previous_day'] == '2026-09-25' and middle['next_day'] == '2026-09-29'
    assert APIClient().get('/api/clinic/messages/2026-09-25/').json()['previous_day'] is None
    assert APIClient().get('/api/clinic/messages/2026-09-29/').json()['next_day'] is None


@pytest.mark.parametrize('status', ['pending_review', 'rejected'])
def test_message_detail_missing_camp_does_not_expose_unpublished(status):
    day = date(2026, 9, 27)
    ClinicDailyMessage.objects.create(day=day, camp='government', status='approved', message='Jawny')
    ClinicDailyMessage.objects.create(day=day, camp='opposition', status=status, message='Nieopublikowany')
    value = APIClient().get(f'/api/clinic/messages/{day}/').json()
    assert value['government']['message'] == 'Jawny' and value['opposition'] is None
    assert value['government']['scope']['date_from'] is None
    assert value['government']['posts'] == []


@pytest.mark.parametrize('day', ['2026-09-27', '2026-02-30', '20260927', '2026-9-27', 'brak'])
def test_message_detail_404(day):
    ClinicDailyMessage.objects.create(day=date(2026, 9, 27), camp='government', status='pending_review', message='Ukryty')
    assert APIClient().get(f'/api/clinic/messages/{day}/').status_code == 404


def test_message_unavailable_source_retains_reference_without_text():
    source = post(account())
    source.available = False
    source.save()
    message = ClinicDailyMessage.objects.create(day=date(2026, 9, 27), camp='government', status='approved', message='Jawny')
    message.posts.add(source)
    value = APIClient().get('/api/clinic/messages/2026-09-27/').json()['government']['posts'][0]
    assert value['url'] == source.url and value['available'] is False and value['text'] == ''


def test_report_archive_keeps_all_weeks_and_historical_data():
    client = APIClient()
    assert client.get('/api/clinic/report/').json() == {'report': None, 'archive': []}
    last = date(2026, 9, 27)
    for index in range(28):
        end = last - timedelta(weeks=index)
        WeeklyReport.objects.create(week_start=end - timedelta(days=6), week_end=end,
            summary=f'Tydzień {index}', data={'techniques': {'opposition': [{'name': 'Dawna nazwa', 'count': 1}]}})
    data = client.get('/api/clinic/report/').json()
    assert data['report']['week_end'] == str(last) and len(data['archive']) == 28
    assert data['archive'][0]['week_end'] == str(last)
    week = data['archive'][-1]['week_end']
    detail = client.get(f'/api/clinic/report/{week}/').json()['report']
    assert detail['week_end'] == week and detail['summary'] == 'Tydzień 27'
    assert detail['techniques']['opposition'] == [{'name': 'Dawna nazwa', 'count': 1}]
    assert client.get('/api/clinic/report/2026-09-28/').status_code == 404


@pytest.fixture
def fresh_throttle():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


def test_source_suggestion_is_stored_for_review_and_deduplicated(fresh_throttle):
    from news.clinic_models import SourceSuggestion
    client = APIClient()
    created = client.post('/api/source-suggestions/', {'url': 'https://Www.Przyklad.pl/wiadomosci?x=1#frag', 'note': 'RSS jest jawny'}, format='json')
    assert created.status_code == 201 and created.json() == {'status': 'received', 'host': 'www.przyklad.pl'}
    again = client.post('/api/source-suggestions/', {'url': 'https://www.przyklad.pl/wiadomosci?x=1'}, format='json')
    assert again.status_code == 200 and again.json()['status'] == 'already_suggested'
    row = SourceSuggestion.objects.get()
    assert row.url == 'https://www.przyklad.pl/wiadomosci?x=1' and row.status == 'new' and row.note == 'RSS jest jawny'


@pytest.mark.parametrize('url', ['', 'brak', 'javascript:alert(1)', 'ftp://przyklad.pl', 'https://localhost/', 'https://127.0.0.1/',
                                 'https://user:haslo@przyklad.pl/', 'https://przyklad', 'https://serwer.local/',
                                 'file:///etc/passwd', 'JavaScript:alert(1)', 'HTTPS://przyklad.pl:99999/', 'https://przyklad.pl/' + 'a' * 300])
def test_source_suggestion_rejects_unsafe_or_incomplete_addresses(url, fresh_throttle):
    from news.clinic_models import SourceSuggestion
    assert APIClient().post('/api/source-suggestions/', {'url': url}, format='json').status_code == 400
    assert not SourceSuggestion.objects.exists()


def test_source_suggestion_is_rate_limited(fresh_throttle):
    client = APIClient()
    codes = [client.post('/api/source-suggestions/', {'url': f'https://zrodlo{index}.pl/'}, format='json').status_code for index in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_source_suggestion_limit_is_separate_from_x_suggestions(fresh_throttle):
    from news.political_models import PublicFigure
    figure = PublicFigure.objects.create(canonical_name='Anna Test', role_category='parliamentary', role_title='Posłanka',
                                         evidence_url='https://www.sejm.gov.pl')
    client = APIClient()
    for index in range(11):
        client.post('/api/source-suggestions/', {'url': f'https://zrodlo{index}.pl/'}, format='json')
    # Wyczerpany limit sugestii źródeł nie blokuje sugestii kont X (osobny scope).
    assert client.post(f'/api/public-figures/{figure.pk}/x-suggestions/', {'url': 'https://x.com/Anna_Test'}, format='json').status_code == 201


def test_source_suggestion_limits_logged_in_users_too(fresh_throttle):
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user(username='czytelnik')
    client = APIClient()
    client.force_authenticate(user)
    codes = [client.post('/api/source-suggestions/', {'url': f'https://zalogowany{index}.pl/'}, format='json').status_code for index in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def _published_diagnosis():
    from news.clinic_models import SpinDiagnosis
    return SpinDiagnosis.objects.create(post=post(account()), status='approved', verdict='spin', intensity=70,
                                        headline='Teza', diagnosed_at=timezone.now())


def _correction(target, **extra):
    body = {'target_kind': 'diagnosis', 'target_id': target, 'request_type': 'correction', 'relation': 'subject',
            'name': 'Anna Test', 'email': 'anna@example.org', 'message': 'To zdanie zostało wyrwane z kontekstu wypowiedzi.'}
    body.update(extra)
    return APIClient().post('/api/corrections/', body, format='json')


def test_correction_is_stored_for_review_and_nothing_is_published(fresh_throttle):
    from django.core import mail
    from news.clinic_models import CorrectionRequest, SpinDiagnosis
    diagnosis = _published_diagnosis()
    response = _correction(diagnosis.pk)
    assert response.status_code == 201 and response.json()['reference'].startswith('ZG-')
    row = CorrectionRequest.objects.get()
    assert (row.status, row.target_kind, row.request_type, row.relation) == ('new', 'diagnosis', 'correction', 'subject')
    assert row.email == 'anna@example.org' and 'wyrwane' in row.message
    assert mail.outbox == []  # nic nie jest wysyłane automatycznie
    diagnosis.refresh_from_db()
    assert diagnosis.status == 'approved' and diagnosis.hidden_at is None  # ani nie zmienia diagnozy
    assert SpinDiagnosis.objects.count() == 1


@pytest.mark.parametrize('changes', [
    {'email': 'nie-email'}, {'message': 'za krótko'}, {'message': 'x' * 2001}, {'target_kind': 'nieznany'},
    {'request_type': 'objection'}, {'target_id': 999999}, {'relation': 'szef'},
])
def test_correction_rejects_invalid_input(changes, fresh_throttle):
    from news.clinic_models import CorrectionRequest
    diagnosis = _published_diagnosis()
    changes = {**changes}
    if 'target_id' not in changes:
        changes['target_id'] = diagnosis.pk
    assert _correction(**{'target': changes.pop('target_id')}, **changes).status_code == 400
    assert not CorrectionRequest.objects.exists()


def test_correction_for_unpublished_diagnosis_is_rejected(fresh_throttle):
    from news.clinic_models import SpinDiagnosis
    hidden = SpinDiagnosis.objects.create(post=post(account(), '777'), status='pending_review', verdict='spin', intensity=70)
    assert _correction(hidden.pk).status_code == 400


def test_correction_honeypot_and_rate_limit(fresh_throttle):
    from news.clinic_models import CorrectionRequest
    diagnosis = _published_diagnosis()
    assert _correction(diagnosis.pk, website='http://spam.example').status_code == 201
    assert not CorrectionRequest.objects.exists()
    codes = [_correction(diagnosis.pk).status_code for _ in range(5)]  # pułapka też liczy się do limitu 5/h
    assert codes[:4] == [201] * 4 and codes[4] == 429


def test_correction_honeypot_wins_over_target_validation(fresh_throttle):
    from news.clinic_models import CorrectionRequest
    assert _correction(999999, website='x', target_kind='nieznany').status_code == 201  # bot nie dowiaduje się, że cel był zły
    assert not CorrectionRequest.objects.exists()


def test_correction_for_daily_message_only_when_published(fresh_throttle):
    from news.clinic_models import CorrectionRequest
    published = ClinicDailyMessage.objects.create(day=date(2026, 9, 28), camp='government', status='approved', message='Przekaz')
    draft = ClinicDailyMessage.objects.create(day=date(2026, 9, 28), camp='opposition', status='pending_review', message='Szkic')
    assert _correction(published.pk, target_kind='message').status_code == 201
    assert _correction(draft.pk, target_kind='message').status_code == 400
    assert _correction(published.pk, target_kind='message', request_type='objection').status_code == 400
    assert CorrectionRequest.objects.get().target_kind == 'message'


def test_correction_admin_is_read_only_for_content_and_cannot_delete():
    from django.contrib import admin
    from news.clinic_models import CorrectionRequest
    model_admin = admin.site._registry[CorrectionRequest]
    assert {'message', 'email', 'target_kind', 'target_id'} <= set(model_admin.readonly_fields)
    assert model_admin.has_delete_permission(None) is False and model_admin.has_add_permission(None) is False


def test_objection_is_allowed_for_public_figures_only(fresh_throttle):
    from news.clinic_models import CorrectionRequest
    from news.political_models import PublicFigure
    figure = PublicFigure.objects.create(canonical_name='Anna Test', role_category='parliamentary', role_title='Posłanka',
                                         evidence_url='https://www.sejm.gov.pl')
    assert _correction(figure.pk, target_kind='figure', request_type='objection').status_code == 201
    assert CorrectionRequest.objects.get().target_kind == 'figure'


def test_message_reports_whether_it_was_published_automatically():
    auto = ClinicDailyMessage.objects.create(day=date(2026, 9, 27), camp='government', status='approved',
                                             message='Auto', reviewed_at=timezone.now())
    from django.contrib.auth import get_user_model
    editor = get_user_model().objects.create_user(username='redaktor', is_staff=True)
    manual = ClinicDailyMessage.objects.create(day=date(2026, 9, 27), camp='opposition', status='approved',
                                               message='Ręcznie', reviewed_at=timezone.now(), reviewed_by=editor)
    value = APIClient().get('/api/clinic/messages/2026-09-27/').json()
    assert value['government']['auto_published'] is True and value['opposition']['auto_published'] is False
    assert auto.pk != manual.pk
