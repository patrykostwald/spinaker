"""Wykaz OPP MF: syntetyczne dane, bez sieci i bez łączenia z dotacjami."""
import hashlib
import json
from io import BytesIO, StringIO
from zipfile import ZipFile

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from news import drzewo_pieniedzy as dp, opp_podatek as opp
from news.test_drzewo_pieniedzy import org, rec
from news import niw_dotacje as niw, test_niw_dotacje as fixtures
from news.public_records_models import PublicRecord


@pytest.mark.django_db
def test_opp_api_exports_keep_tax_separate_and_match_only_exact_krs(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    cache.clear()
    company = org()
    rec('fts', 'eu_grant', 'synthetic-eu', {'vat': company.nip, 'amount': '23.50'})
    rec('niw', 'grant_pl', 'synthetic-pl', {'krs': company.krs_number, 'amount': '12.25',
                                        'file_date': '2026-07-30'})
    client = APIClient()
    url = f'/api/przeszlosc/spolka/{company.krs_number}/'
    before = client.get(url).json()
    record = {'krs': company.krs_number, 'name': 'Syntetyczna fundacja OPP', 'amount': '406577904.79',
              'tax_year': 2025, 'payment_year': 2026, 'file_date': '2026-09-30',
              'file_sha256': 'a' * 64, 'resource_url': 'https://api.dane.gov.pl/synthetic-opp.xlsx'}
    opp.save_records([record])
    opp.save_records([{**record, 'tax_year': 2024, 'payment_year': 2025, 'amount': '17.50'}])
    # Ta sama nazwa, zgodny NIP zamiast KRS i KRS będący podciągiem nie tworzą powiązania.
    for index, fields in enumerate(({'krs': '0000000003'}, {'krs': company.nip},
                                   {'krs': '1' + company.krs_number}, {'krs': '', 'nip': company.nip},
                                   {'krs': f'KRS {company.krs_number}'})):
        rec('mf_opp', 'opp_15', f'foreign-{index}', {**record, **fields, 'name': company.name})
    cache.clear()
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data['grants'] == before['grants']
    assert data['contracts'] == before['contracts']
    assert data['grants']['sums'] == [{'currency': 'EUR', 'total': 23.5}, {'currency': 'PLN', 'total': 12.25}]
    section = data['opp_tax']
    assert section['count'] == 2 and 'sums' not in section
    assert section['note'] == opp.NOTE
    assert [row['tax_year'] for row in section['results']] == [2025, 2024]
    row = section['results'][0]
    assert row['payment_year'] == 2026 and row['amount'] == 406577904.79
    assert row['currency'] == 'PLN' and row['source'] == 'mf_opp'
    assert row['url'] == record['resource_url'] and row['file_date'] == '2026-09-30'
    attribution = ('Źródło: Ministerstwo Finansów, wykaz OPP, rok podatkowy 2025, stan na 2026-09-30. '
                   'Kwota pochodzi z 1,5% podatku wskazanego przez podatników, nie jest dotacją i nie sumuje się z dotacjami.')
    assert row['attribution'] == attribution
    assert dp.SOURCES['mf_opp'] in data['sources']
    assert dp.SOURCES['mf_opp']['license'] == 'CC0 1.0'
    assert data['nodes'] == before['nodes'] and data['edges'] == before['edges']
    full_response = client.get(url, {'eksport': 'json'})
    assert full_response.status_code == 200
    full = full_response.json()
    assert full['opp_tax'] == section['results'] and full['opp_tax_note'] == opp.NOTE
    assert set(full['sums']) == {'contracts', 'grants'}
    assert full['sums']['grants'] == before['grants']['sums']
    assert dp.SOURCES['mf_opp'] in full['sources']
    csv_response = client.get(url, {'eksport': 'csv'})
    assert csv_response.status_code == 200
    csv = csv_response.content.decode('utf-8')
    assert '1,5% podatku (wskazanie podatników)' in csv
    assert attribution in csv and opp.NOTE in csv
    assert 'Ministerstwo Finansów, wykaz OPP (mf_opp)' in csv
    assert 'foreign-' not in csv
    cache.clear()
    flow = client.get(f'/api/przeszlosc/przeplyw/spolka:{company.krs_number}/')
    assert flow.status_code == 200
    assert not any(node['id'].startswith('mf_opp:') for node in flow.json()['nodes'])
    cache.clear()


@pytest.mark.django_db
def test_opp_without_krs_never_matches_nip():
    company = org(krs_number='', nip='5260250995')
    rec('mf_opp', 'opp_15', 'nip-not-krs', {'krs': company.nip, 'amount': '100.00', 'tax_year': 2025})
    assert dp.opp_tax(company, dp.identifiers(company)) == []



RESOURCE = dict(payment_year=2026, tax_year=2025, file_date='2026-09-30',
                resource_url='https://api.dane.gov.pl/resources/123/file')
GOOD = [1, '0000000002', 'Fundacja Żółw', 406577904.79000002]


@pytest.fixture
def workbook(monkeypatch):
    monkeypatch.setattr(fixtures, 'HEADERS', ['L.p.', 'Numer KRS', 'Nazwa organizacji pożytku publicznego', 'Kwota w zł'])
    return lambda rows=None, **kwargs: fixtures.xlsx([GOOD] if rows is None else rows, **kwargs)


@pytest.mark.parametrize('shared', [False, True])
def test_parser_decimal_krs_and_invalid_rows(workbook, shared):
    raw = workbook([GOOD, [2, '2', 'Za krótki KRS', 10], [3, '0000000003', 'Ujemna', -1],
                    [4, '0000000004', 'Nieliczba', 'NaN'], [5, '0000000005', '', 1],
                    [6, '0000000006', 'Zbyt duża', '1e100'], [7, '0000000007', 'Zero', 0]], shared=shared)
    rows, stats = opp.parse_xlsx(raw, RESOURCE)
    assert stats == {'bledne': 5, 'duplikaty': 0}
    assert len(rows) == 2 and rows[0]['krs'] == '0000000002'
    assert rows[0]['name'] == 'Fundacja Żółw' and rows[0]['amount'] == '406577904.79'
    assert rows[1]['amount'] == '0.00'
    assert rows[0]['file_sha256'] == hashlib.sha256(raw).hexdigest()
    assert all(rows[0][k] == v for k, v in RESOURCE.items())


def test_parser_layout_duplicates_dtd_and_limits(workbook, monkeypatch):
    with pytest.raises(ValueError, match='Powtórzony KRS'):
        opp.parse_xlsx(workbook([GOOD, GOOD]), RESOURCE)
    monkeypatch.setattr(fixtures, 'HEADERS', ['Obcy', 'układ'])
    with pytest.raises(ValueError, match='kolumn'):
        opp.parse_xlsx(workbook(), RESOURCE)
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<!DOCTYPE x [<!ENTITY a "aaaa">]><workbook/>')
    with pytest.raises(ValueError, match='DTD'):
        opp.parse_xlsx(stream.getvalue(), RESOURCE)
    monkeypatch.setattr(niw, 'MAX_MEMBER_BYTES', 10)
    with pytest.raises(ValueError, match='200 MB'):
        opp.parse_xlsx(workbook(), RESOURCE)
    monkeypatch.setattr(opp, 'MAX_BYTES', 1)
    with pytest.raises(ValueError, match='20 MB'):
        opp.parse_xlsx(workbook(), RESOURCE)


def resource_item(year, stamp, title=None, fmt='xlsx'):
    return {'attributes': {'title': title or f'Wykaz OPP, które w {year} r. otrzymały środki za {year - 1}',
                           'format': fmt, 'data_date': stamp,
                           'download_url': f'https://api.dane.gov.pl/resources/{year}/file'}}


def test_resources_selection_and_tax_year():
    payload = {'data': [resource_item(2026, '2026-09-30'), resource_item(2026, '2026-08-01'),
                        resource_item(2025, '2025-09-30', 'Wykaz OPP, które w 2025 r. otrzymały środki'),
                        resource_item(2024, '2024-09-30', 'Wykaz OPP, które w 2024 r. otrzymały środki za rok 2022'),
                        resource_item(2027, '2027-09-30', 'Liczba podatników przekazujących środki'),
                        resource_item(2028, '2028-09-30', fmt='pdf')]}
    assert opp.select_resources(payload) == [{**RESOURCE, 'resource_url': 'https://api.dane.gov.pl/resources/2026/file'}]
    assert [(r['payment_year'], r['tax_year']) for r in opp.select_resources(payload, [2024, 2025])] == [(2024, 2022), (2025, 2024)]
    with pytest.raises(ValueError, match='Brak wykazu'):
        opp.select_resources(payload, [2023])
    with pytest.raises(ValueError, match='Nie znaleziono'):
        opp.select_resources({'data': []})


@pytest.mark.parametrize('url', ['http://api.dane.gov.pl/a', 'https://dane.gov.pl/a',
                               'https://api.dane.gov.pl.evil.com/a', 'https://api.dane.gov.pl:8443/a',
                               'https://user:password@api.dane.gov.pl/a'])
def test_foreign_or_unsafe_urls_rejected(url):
    with pytest.raises(ValueError, match='HTTPS'):
        opp.official_url(url)


def test_download_stream_limit_redirect_checks(monkeypatch):
    class Response:
        status_code = 200
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): return iter([b'123', b'456'])
    calls = []
    monkeypatch.setattr(opp.requests, 'get', lambda url, **kwargs: calls.append((url, kwargs)) or Response())
    monkeypatch.setattr(opp, 'MAX_BYTES', 5)
    with pytest.raises(ValueError, match='20 MB'):
        opp.download(RESOURCE['resource_url'])
    assert calls[0][1]['allow_redirects'] is False
    Response.headers = {'Content-Length': '999'}
    with pytest.raises(ValueError, match='20 MB'):
        opp.download(RESOURCE['resource_url'])
    Response.status_code = 302
    Response.headers = {'Location': 'https://example.com/opp.xlsx'}
    calls.clear()
    with pytest.raises(ValueError, match='HTTPS'):
        opp.download(RESOURCE['resource_url'])
    assert len(calls) == 1
    Response.headers = {}
    with pytest.raises(ValueError, match='bez adresu'):
        opp.download(RESOURCE['resource_url'])
    Response.headers = {'Location': '/loop'}
    with pytest.raises(ValueError, match='przekierowań'):
        opp.download(RESOURCE['resource_url'])


def test_archive_has_state_download_date_and_hash(workbook, tmp_path):
    raw = workbook()
    path = opp.archive_file(raw, RESOURCE, tmp_path)
    assert path.read_bytes() == raw
    assert path.name.startswith('OPP-2026-stan-2026-09-30-pobrano-')
    assert hashlib.sha256(raw).hexdigest() in path.name
    assert opp.archive_file(raw, RESOURCE, tmp_path) == path
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.django_db
def test_upsert_year_isolation_stale_and_empty_import(workbook):
    base = opp.parse_xlsx(workbook(), RESOURCE)[0][0]
    assert opp.save_records([base])['created'] == 1
    row = PublicRecord.objects.get()
    assert row.external_id == '0000000002:2025'
    assert row.source == 'mf_opp' and row.kind == 'opp_15'
    assert row.response_sha256 == base['file_sha256'] and row.response_url == RESOURCE['resource_url']
    assert opp.save_records([base]) == dict(created=0, updated=0, unchanged=1, removed=0)
    previous = {**base, 'payment_year': 2025, 'tax_year': 2024, 'file_date': '2025-09-30'}
    opp.save_records([previous])
    extra = {**base, 'krs': '0000000003'}
    opp.save_records([base, extra])
    newer = {**base, 'amount': '2.00', 'file_date': '2026-10-01'}
    assert opp.save_records([newer]) == dict(created=0, updated=1, unchanged=0, removed=1)
    assert PublicRecord.objects.filter(data__tax_year=2024).count() == 1
    assert opp.save_records([base]) == dict(created=0, updated=0, unchanged=1, removed=0)
    row.refresh_from_db()
    assert row.data['amount'] == '2.00'
    assert opp.save_records([])['removed'] == 0 and PublicRecord.objects.count() == 2


@pytest.mark.django_db
def test_command_dry_run_write_and_invalid_rows_preserve_records(workbook, tmp_path):
    path = tmp_path / 'opp.xlsx'
    path.write_bytes(workbook([GOOD, [2, '0000000003', 'Druga', 10]]))
    options = dict(plik=str(path), lata='2026', data_pliku='2026-09-30', archiwum=str(tmp_path / 'arch'))
    out = StringIO()
    call_command('przeszlosc_opp_podatek', **options, dry_run=True, stdout=out)
    assert not PublicRecord.objects.exists() and 'Dry-run' in out.getvalue()
    call_command('przeszlosc_opp_podatek', **options, stdout=StringIO())
    assert PublicRecord.objects.count() == 2
    path.write_bytes(workbook([GOOD, [2, '0000000003', 'Druga', 'błąd']]))
    options['data_pliku'] = '2026-10-01'
    out = StringIO()
    call_command('przeszlosc_opp_podatek', **options, stdout=out)
    assert 'pominięte błędne: 1' in out.getvalue() and 'usuwanie nieobecnych rekordów wyłączone' in out.getvalue()
    assert PublicRecord.objects.count() == 2
    path.write_bytes(workbook([]))
    call_command('przeszlosc_opp_podatek', **options, stdout=StringIO())
    assert PublicRecord.objects.count() == 2
    with pytest.raises(CommandError, match='wymaga'):
        call_command('przeszlosc_opp_podatek', plik=str(path))


@pytest.mark.django_db
def test_command_download_and_pagination_offline(workbook, tmp_path, monkeypatch):
    next_url = 'https://api.dane.gov.pl/1.4/datasets/171/resources?page=2'
    calls = []

    def download(url):
        calls.append(url)
        if url == opp.RESOURCES_URL:
            return json.dumps({'data': [resource_item(2026, '2026-09-30')],
                               'links': {'next': next_url}}).encode(), url
        if url == next_url:
            return json.dumps({'data': [resource_item(2025, '2025-09-30')],
                               'links': {'next': None}}).encode(), url
        assert url in ('https://api.dane.gov.pl/resources/2026/file',
                       'https://api.dane.gov.pl/resources/2025/file')
        return workbook(), url

    monkeypatch.setattr(opp, 'download', download)
    call_command('przeszlosc_opp_podatek', lata='2025,2026', archiwum=str(tmp_path), stdout=StringIO())
    assert len(calls) == 4
    assert set(PublicRecord.objects.values_list('data__tax_year', flat=True)) == {2024, 2025}
    calls.clear()
    call_command('przeszlosc_opp_podatek', dry_run=True, archiwum=str(tmp_path), stdout=StringIO())
    assert calls[-1] == 'https://api.dane.gov.pl/resources/2026/file' and len(calls) == 3
