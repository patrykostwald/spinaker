"""API danych RCL: wyłączone domyślnie, a po włączeniu każdy rekord ma źródło, link i datę pobrania."""
from datetime import date, datetime, timezone as dt_timezone

import pytest
from rest_framework.test import APIClient

from news.models import LegislativeChange, LegislativeDocument, LegislativeProject, LegislativeStage

pytestmark = pytest.mark.django_db

FETCHED = datetime(2026, 10, 22, 2, 30, tzinfo=dt_timezone.utc)
SOURCE_LINE = 'Źródło: Rządowe Centrum Legislacji, legislacja.rcl.gov.pl'


@pytest.fixture
def data():
    project = LegislativeProject.objects.create(
        rcl_id=12414100, act_type_id=2, act_type='Projekty ustaw', title='Projekt ustawy o przykładzie',
        applicant='Minister Przykładowy', wykaz_number='UD1', status='otwarty', list_modified_on=date(2026, 9, 1),
        source_url='https://legislacja.rcl.gov.pl/projekt/12414100', fetched_at=FETCHED, list_fetched_at=FETCHED)
    stage = LegislativeStage.objects.create(project=project, rcl_id=13223895, number=3, name='Konsultacje publiczne',
                                            kind='konsultacje', state='reached')
    for doc_id, category, author, name in ((1, 'position', 'Izba Wzorcowa', 'Stanowisko.pdf'),
                                           (2, 'comment_table', 'Minister Przykładowy', 'Tabela uwag.xlsx'),
                                           (3, 'lobbying', 'Fundacja Przykładowa', 'Zgłoszenie.pdf'),
                                           (4, 'project', 'Minister Przykładowy', 'projekt.docx')):
        LegislativeDocument.objects.create(
            project=project, stage=stage, rcl_doc_id=doc_id, category=category, author=author, name=name,
            file_url=f'https://legislacja.rcl.gov.pl/docs//2/1/2/dokument{doc_id}.pdf', created_on=date(2026, 9, 10),
            source_page_url='https://legislacja.rcl.gov.pl/projekt/12414100/katalog/13223895', fetched_at=FETCHED)
    LegislativeChange.objects.create(project=project, entity='project', entity_key='12414100', kind='created',
                                     changes={'title': [None, 'Projekt ustawy o przykładzie']}, fetched_at=FETCHED,
                                     source_url=project.source_url)
    return project


def test_api_is_closed_until_the_owner_enables_it(data, monkeypatch):
    monkeypatch.delenv('RCL_API_ENABLED', raising=False)
    assert APIClient().get('/api/legislacja/projekty/').status_code == 404
    assert APIClient().get('/api/legislacja/projekty/12414100/').status_code == 404


def test_list_carries_source_link_and_fetch_date(data, monkeypatch):
    monkeypatch.setenv('RCL_API_ENABLED', 'true')
    body = APIClient().get('/api/legislacja/projekty/', {'q': 'przykładzie'}).json()
    assert body['count'] == 1 and body['source']['attribution'] == SOURCE_LINE
    item = body['results'][0]
    assert item['source'] == {'attribution': SOURCE_LINE, 'url': 'https://legislacja.rcl.gov.pl/projekt/12414100',
                              'fetched_at': '2026-10-22T02:30:00+00:00', 'processing': item['source']['processing']}
    assert 'iapply' in item['source']['processing']
    assert APIClient().get('/api/legislacja/projekty/', {'typ': 10}).json()['count'] == 0
    assert APIClient().get('/api/legislacja/projekty/', {'typ': 'x'}).status_code == 400


def test_detail_separates_positions_comment_tables_and_lobbying_each_with_source(data, monkeypatch):
    monkeypatch.setenv('RCL_API_ENABLED', 'true')
    body = APIClient().get('/api/legislacja/projekty/12414100/').json()
    assert [d['author'] for d in body['consultation_positions']] == ['Izba Wzorcowa']
    assert [d['name'] for d in body['comment_tables']] == ['Tabela uwag.xlsx']
    assert [d['author'] for d in body['lobbying_notifications']] == ['Fundacja Przykładowa']
    assert [d['name'] for d in body['documents']] == ['projekt.docx']
    for card in body['consultation_positions'] + body['comment_tables'] + body['lobbying_notifications']:
        assert card['source']['attribution'] == SOURCE_LINE and card['source']['url'].startswith('https://legislacja.rcl.gov.pl/')
        assert card['source']['fetched_at'] == '2026-10-22T02:30:00+00:00' and card['created_on'] == '2026-09-10'
    assert body['stages'][0]['name'] == 'Konsultacje publiczne' and body['changes'][0]['kind'] == 'created'
    assert 'brak w naszych danych' in body['completeness']['note']


def test_unknown_project_says_not_in_our_data(data, monkeypatch):
    monkeypatch.setenv('RCL_API_ENABLED', 'true')
    response = APIClient().get('/api/legislacja/projekty/999/')
    assert response.status_code == 404 and 'Brak w naszych danych' in response.json()['detail']
