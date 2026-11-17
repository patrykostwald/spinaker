import pytest
from rest_framework.test import APIClient

from news import przeszlosc_podmiot_nip as pn, przeszlosc_spolki as sp
from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicRecord

pytestmark = pytest.mark.django_db
NIP = '5771960580'   # Gmina Niegowa (poprawna suma kontrolna)


def bzp(ext, nip, title, day, name='GMINA NIEGOWA', city='Niegowa'):
    return PublicRecord.objects.create(source='bzp', kind='notice', external_id=ext, title=title, date=day, source_url=f'https://ezamowienia.gov.pl/{ext}',
                                       response_url='https://ezamowienia.gov.pl/', response_sha256='0',
                                       data={'organizationNationalId': nip, 'organizationName': name, 'organizationCity': city, 'organizationProvince': 'PL24',
                                             'noticeType': 'ContractNotice'})


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')


def test_nip_checksum():
    assert pn.valid_nip(NIP) == NIP and pn.valid_nip('577-19-60-580') == NIP and pn.valid_nip('PL 5771960580') == NIP
    assert pn.valid_nip('5771960581') is None and pn.valid_nip('123') is None and pn.valid_nip('') is None


def test_entity_without_krs_gets_contracts_by_nip_only_with_identity_from_notices():
    bzp('a', NIP, 'Modernizacja boisk', '2026-07-26')
    bzp('b', '5771960581', 'Inny zamawiający', '2026-07-25', name='INNA GMINA')          # inny NIP: nie wchodzi
    bzp('c', 'PL577-196-05-80', 'Dostawa wyposażenia', '2026-07-20')                       # inny zapis tego samego NIP-u
    body = pn.build(NIP)
    assert body['status'] == 'found' and body['name'] == 'GMINA NIEGOWA' and body['city'] == 'Niegowa' and body['province'] == 'PL24'
    assert body['contracts']['count'] == 2 and {x['title'] for x in body['contracts']['results']} == {'Modernizacja boisk', 'Dostawa wyposażenia'}
    assert all(x['matched_by'] == 'NIP' for x in body['contracts']['results']) and 'bez wpisu z KRS' not in body['note']
    assert 'Łączymy wyłącznie po numerze NIP' in body['rules'] and body['grants']['count'] == 0


def test_unknown_nip_is_empty_and_entity_with_krs_points_to_company_page():
    empty = pn.build('7962958767')
    assert empty['status'] == 'empty' and empty['contracts']['count'] == 0 and 'BZP zbieramy od września 2025' in empty['note']
    RegisteredOrganisation.objects.create(name='Orlen S.A.', krs_number='0000028860', kind='company', nip='7740001454')
    with_krs = pn.build('7740001454')
    assert with_krs['status'] == 'krs' and with_krs['url'] == '/przeszlosc/spolka/0000028860'


def test_api_validates_nip_and_flag(monkeypatch):
    client = APIClient()
    assert client.get(f'/api/przeszlosc/podmiot/{NIP}/').json()['status'] == 'empty'
    assert client.get('/api/przeszlosc/podmiot/1234567890/').status_code == 400
    monkeypatch.delenv('PRZESZLOSC_ENABLED')
    assert client.get(f'/api/przeszlosc/podmiot/{NIP}/').status_code == 404


def test_company_search_points_a_missing_nip_to_the_nip_view_and_explains_jst_without_krs():
    bzp('a', NIP, 'Modernizacja boisk', '2026-07-26')
    hit = sp.search(NIP)
    assert hit['results'] == [] and hit['nip_page'] == {'url': f'/przeszlosc/podmiot/{NIP}', 'has_data': True} and 'Mamy jednak ogłoszenia' in hit['message']
    none = sp.search('7962958767')
    assert none['nip_page']['has_data'] is False and 'Nie mamy też ogłoszeń' in none['message']
    assert 'nip_page' not in sp.search('5771960581')                                           # zły NIP (suma kontrolna): bez widoku
    name = sp.search('gmina niegowa')
    assert 'nie mają numeru KRS' in name['message'] and 'NIP' in name['message']
