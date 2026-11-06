from hashlib import sha256

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news import przeszlosc_pkw as pk
from news.public_records_models import PublicRecord

pytestmark = pytest.mark.django_db
ROWS = [
    ('Polska Partia Piratów (EwP 328)', 'https://pkw.gov.pl/uploaded_files/1763540629_ewp-328-polska-partia-piratow.pdf'),
    ('Komitet Wyborczy Wyborców Nasza Lewica', 'https://pkw.gov.pl/uploaded_files/1709097157_kww-nasza-lewica.pdf'),
    ('9) Załącznik nr 9 Komitet Wyborczy Kandydata', 'https://pkw.gov.pl/uploaded_files/1758166452_17581108189.pdf'),
    ('Dokument bez daty', 'https://pkw.gov.pl/inny/plik.pdf'),
]


@pytest.fixture(autouse=True)
def _data(monkeypatch):
    cache.clear(); monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    for i, (title, url) in enumerate(ROWS):
        PublicRecord.objects.create(source='pkw', kind='financial_document', external_id=f'd{i}', title=title, source_url=url,
                                    response_url=url, response_sha256='0', data={})
    PublicRecord.objects.create(source='pkw', kind='financial_row', external_id='r', title='x', source_url='https://pkw.gov.pl/x',
                                response_url='https://pkw.gov.pl/x', response_sha256='0', data={})   # inne rodzaje nie wchodzą do spisu
    yield
    cache.clear()


def test_published_date_comes_from_upload_timestamp_and_kind_from_title():
    assert str(pk._published(ROWS[0][1])) == '2025-11-19' and pk._published(ROWS[3][1]) is None
    assert [pk._kind(t) for t, _ in ROWS] == ['partia', 'komitet', 'zalacznik', 'inne']


def test_catalogue_sorted_newest_first_and_search_by_name_words():
    titles = [r['title'] for r in pk.catalogue()]
    assert titles[0].startswith('Polska Partia') and titles[-1] == 'Dokument bez daty' and len(titles) == 4
    assert [r['title'] for r in pk.search('lewica')] == ['Komitet Wyborczy Wyborców Nasza Lewica']
    assert [r['title'] for r in pk.search('komitet wyborczy')] == ['9) Załącznik nr 9 Komitet Wyborczy Kandydata', 'Komitet Wyborczy Wyborców Nasza Lewica']
    assert pk.search('', 'partia')[0]['kind'] == 'partia' and pk.search('nic takiego') == []


def test_api_pages_counts_note_and_validation(monkeypatch):
    client = APIClient()
    body = client.get('/api/przeszlosc/pkw/?na_strone=2').json()
    assert body['total'] == 4 and body['all'] == 4 and body['pages'] == 2 and len(body['results']) == 2
    assert {k['key']: k['count'] for k in body['kinds']} == {'partia': 1, 'komitet': 1, 'zalacznik': 1, 'inne': 1}
    assert 'bez OCR' in body['note'] and body['source']['url'].startswith('https://pkw.gov.pl/')
    assert client.get('/api/przeszlosc/pkw/?rodzaj=zly').status_code == 400 and client.get('/api/przeszlosc/pkw/?strona=x').status_code == 400
    monkeypatch.delenv('PRZESZLOSC_ENABLED')
    assert client.get('/api/przeszlosc/pkw/').status_code == 404


def test_report_summary_is_attached_and_unreadable_scans_say_why(monkeypatch):
    def report(url, data):
        PublicRecord.objects.create(source='pkw', kind='financial_report', external_id=sha256(url.encode()).hexdigest(), source_url=url,
                                    response_url=url, response_sha256='0', data=data)
    # dokumenty z fixture mają external_id d0..d3, więc zakładamy raporty pod tymi kluczami
    PublicRecord.objects.filter(source='pkw', kind='financial_document', external_id='d0').update(external_id=sha256(ROWS[0][1].encode()).hexdigest())
    PublicRecord.objects.filter(source='pkw', kind='financial_document', external_id='d1').update(external_id=sha256(ROWS[1][1].encode()).hexdigest())
    report(ROWS[0][1], {'readable': True, 'resolution': '272/2025', 'resolution_date': '2025-11-14', 'report_year': 2024, 'name': 'Polska Partia Piratów',
                        'decision': 'przyjete', 'with_irregularity': True, 'currency': 'PLN',
                        'amounts': {'income_total': '4138.33', 'individuals_total': '940.00', 'ukryte_pole': '1.00'},
                        'evidence': {'income_total': 'pozyskała przychody o łącznej wartości 4138,33 zł'}})
    report(ROWS[1][1], {'readable': False, 'reason': 'skan_bez_warstwy_tekstowej'})
    cache.clear()
    rows = {r['title']: r['report'] for r in pk.catalogue()}
    pirates = rows['Polska Partia Piratów (EwP 328)']
    assert pirates['readable'] and pirates['year'] == 2024 and pirates['decision'] == 'przyjete' and pirates['with_irregularity'] is True
    assert [a['key'] for a in pirates['amounts']] == ['income_total', 'individuals_total']          # tylko znane, opisane pola
    assert pirates['amounts'][0]['label'] == 'Przychody ogółem' and 'łącznej wartości' in pirates['amounts'][0]['quote']
    scan = rows['Komitet Wyborczy Wyborców Nasza Lewica']
    assert scan == {'readable': False, 'reason': 'skan formularza bez warstwy tekstowej (nie stosujemy OCR)'}
    assert rows['Dokument bez daty'] is None                                                        # jeszcze nieczytany
    body = APIClient().get('/api/przeszlosc/pkw/?z_danymi=1').json()
    assert body['total'] == 1 and body['with_data'] == 1 and body['results'][0]['title'].startswith('Polska Partia')
    assert 'bez OCR' in body['note'] and 'nazwisk darczyńców' in body['note']
