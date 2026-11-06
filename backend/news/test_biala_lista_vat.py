"""Status VAT z Białej listy MF (news/biala_lista_vat.py): nowy adres, wspólny dzienny limit, brak danych o osobach."""
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache

from news import biala_lista_vat as bl
from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicRecord

pytestmark = pytest.mark.django_db

PAYLOAD = {'result': {'entries': [{'identifier': '5771960580', 'subjects': [{
    'name': 'GMINA NIEGOWA', 'nip': '5771960580', 'statusVat': 'Czynny', 'regon': '151398511', 'pesel': None, 'krs': None,
    'residenceAddress': 'SOBIESKIEGO 1', 'representatives': [{'firstName': 'Jan', 'lastName': 'Kowalski'}], 'authorizedClerks': [], 'partners': [],
    'registrationLegalDate': '2010-07-27', 'removalDate': None, 'accountNumbers': ['11111111111111111111111111', '22222222222222222222222222'],
    'hasVirtualAccounts': False}]}, {'identifier': '0000000000', 'subjects': []}]}}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cache.clear()
    monkeypatch.setenv('BIALA_LISTA_ODSTEP', '0')
    yield
    cache.clear()


def org(nip='5771960580', krs='0000123456', name='Gmina Niegowa'):
    return RegisteredOrganisation.objects.create(name=name, krs_number=krs, kind='company', nip=nip)


def response(payload=PAYLOAD, status=200):
    r = Mock(status_code=status)
    r.json.return_value = payload
    return r


def test_uses_new_official_host_and_can_be_overridden(monkeypatch):
    assert bl.search_url(['1', '2']) == 'https://wykazpodatnikowvat.mf.gov.pl/api/search/nips/1,2'
    monkeypatch.setenv('BIALA_LISTA_API', 'https://wykazpodatnikowvat-test.mf.gov.pl/api/')
    assert bl.search_url(['1']).startswith('https://wykazpodatnikowvat-test.mf.gov.pl/api/search/nips/')


def test_reduce_keeps_entity_fields_and_account_count_but_never_persons_or_numbers():
    subject = PAYLOAD['result']['entries'][0]['subjects'][0]
    reduced = bl.reduce(subject)
    assert reduced == {'status_vat': 'Czynny', 'registration_date': '2010-07-27', 'has_virtual_accounts': False, 'accounts': 2}
    text = str(reduced)
    assert 'Kowalski' not in text and '1111' not in text and 'SOBIESKIEGO' not in text and 'pesel' not in text.lower()


def test_daily_budget_is_shared_and_stops_at_limit(monkeypatch):
    monkeypatch.setenv('BIALA_LISTA_LIMIT_DZIENNY', '3')
    assert [bl.reserve_request() for _ in range(5)] == [True, True, True, False, False]
    with patch('news.biala_lista_vat.requests.get') as get:
        assert bl.fetch(['5771960580']) == ({}, 'limit')
    get.assert_not_called()
    from news import krs_pokrycie
    with patch('news.biala_lista_vat.requests.get') as get, patch('news.krs_pokrycie.requests.get') as get2:
        assert krs_pokrycie.biala_lista(['5771960580']) == ({}, 'limit')   # kolejka KRS korzysta z tego samego budżetu
    get.assert_not_called(); get2.assert_not_called()


def test_refresh_saves_status_marks_unknown_nip_and_tracks_changes():
    a, b = org(), org(nip='0000000000', krs='0000999999', name='Brak w wykazie sp. z o.o.')
    with patch('news.biala_lista_vat.requests.get', return_value=response()) as get:
        out = bl.refresh()
    assert out['status'] == 'ok' and out['zapisano'] == 2 and get.call_count == 1
    assert 'wykazpodatnikowvat.mf.gov.pl/api/search/nips/' in get.call_args.args[0]
    rec = PublicRecord.objects.get(source='biala_lista', external_id='5771960580')
    assert rec.data['found'] is True and rec.data['status_vat'] == 'Czynny' and rec.data['accounts'] == 2
    assert PublicRecord.objects.get(source='biala_lista', external_id='0000000000').data['found'] is False
    # zmiana statusu zapisuje wpis w historii
    PublicRecord.objects.filter(external_id='5771960580').update(fetched_at='2000-01-01T00:00:00Z')
    changed = {'result': {'subjects': [{'nip': '5771960580', 'statusVat': 'Wykreślony', 'removalDate': '2026-11-01', 'accountNumbers': []}]}}
    with patch('news.biala_lista_vat.requests.get', return_value=response(changed)):
        out = bl.refresh()
    assert out['zmiana_statusu'] == 1
    view = bl.status_for(a)
    assert view['status'] == 'Wykreślony' and view['changes'][-1]['from'] == 'Czynny' and view['changes'][-1]['to'] == 'Wykreślony'
    assert bl.status_for(org(nip='', krs='0000111111', name='Bez NIP'))['found'] is None   # brak NIP: opis powodu, nie null


def test_errors_and_disabled_do_not_write(monkeypatch):
    org()
    with patch('news.biala_lista_vat.requests.get', return_value=response(status=500)):
        out = bl.refresh()
    assert out['error'] == 1 and not PublicRecord.objects.filter(source='biala_lista').exists()
    monkeypatch.setenv('BIALA_LISTA_VAT_ENABLED', 'false')
    assert bl.refresh() == {'status': 'disabled'}


def test_company_api_exposes_vat_block(monkeypatch):
    from rest_framework.test import APIClient
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    o = org()
    with patch('news.biala_lista_vat.requests.get', return_value=response()):
        bl.refresh()
    body = APIClient().get(f'/api/przeszlosc/spolka/{o.krs_number}/').json()
    assert body['vat']['status'] == 'Czynny' and body['vat']['accounts'] == 2 and 'wykazpodatnikowvat' in body['vat']['url']


def test_status_for_explains_missing_status_instead_of_null():
    o = org()
    pending = bl.status_for(o)
    assert pending['found'] is None and pending['pending'] is True and 'jeszcze go nie pobraliśmy' in pending['note']
    no_nip = bl.status_for(org(nip='', krs='0000222222', name='Bez NIP'))
    assert no_nip['found'] is None and 'Brak numeru NIP' in no_nip['note']
