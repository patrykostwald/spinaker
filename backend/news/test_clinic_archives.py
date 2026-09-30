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
