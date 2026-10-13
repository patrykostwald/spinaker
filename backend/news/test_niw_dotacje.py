"""Lista dotacji NIW-CRSO: parser XLSX (stdlib), bezpieczeństwo pobierania, warunki Prawnika 13.10.2026, bez sieci."""
from datetime import date
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from news import drzewo_pieniedzy as dp, niw_dotacje as niw
from news.public_records_models import PublicRecord
from news.test_drzewo_pieniedzy import org, person, rec

NAME = 'Lista-dotacji-NIW-CRSO-na-dzien-30-07-2026.xlsx'
HEADERS = ['TYTUŁ ZADANIA', 'Program', 'konkurs', 'Kwota dotacji', 'Numer umowy',
           'Data umowy', 'Nazwa oferenta', 'NIP', 'Rejestr', 'kRs']
GOOD = ['Działania społeczne', 'NOWEFIO', '2026', 1250.50, '1/FIO', 45000, 'Fundacja', '526-025-09-95', 'KRS', 2]
DEFAULT_ROWS = [
    GOOD,
    ['Bez identyfikatorów', 'PROO', '2026', 999, '2/PROO', 45000, 'Osoba', '', '', ''],
    ['Ewidencja', 'Korpus', '2026', 500, '3/K', 45000, 'Koło', '', 'KRZGW', 2],
    ['Prywatny oferent', 'Korpus', '2026', 300, '4/K', 45000, 'Jan K.', '5260250995', 'osoba fizyczna', ''],
    ['Tylko NIP', 'PROO', '2026', 700, '5/PROO', 45000, 'Klub', '5260250995', 'ewidencja starosty', ''],
]


def xlsx(rows=None, shared=False, epoch1904=False, merges=(), refs=True):
    rows = rows if rows is not None else DEFAULT_ROWS
    strings, xmlrows = [], []
    for number, row in enumerate([HEADERS] + rows, 1):
        cells = []
        for col, value in enumerate(row):
            ref = f' r="{chr(65 + col)}{number}"' if refs else ''
            if value is None:
                cells.append(f'<c{ref}/>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c{ref}><v>{value}</v></c>')
            elif shared:
                strings.append(str(value))
                cells.append(f'<c{ref} t="s"><v>{len(strings)-1}</v></c>')
            else:
                cells.append(f'<c{ref} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xmlrows.append(f'<row r="{number}">' + ''.join(cells) + '</row>')
    merged = ('<mergeCells>' + ''.join(f'<mergeCell ref="{m}"/>' for m in merges) + '</mergeCells>') if merges else ''
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{niw.NS["s"]}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="{int(epoch1904)}"/><sheets><sheet name="Dotacje" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{niw.NS["s"]}"><sheetData>{"".join(xmlrows)}</sheetData>{merged}</worksheet>')
        if shared:
            archive.writestr('xl/sharedStrings.xml', f'<sst xmlns="{niw.NS["s"]}">' + ''.join(f'<si><t>{escape(s)}</t></si>' for s in strings) + '</sst>')
    return stream.getvalue()


@pytest.mark.parametrize('shared', [False, True])
def test_parser_only_krs_rows_headers_dates_identifiers(shared):
    records, stats = niw.parse_xlsx(xlsx(shared=shared), NAME)
    # Warunek 1: bez KRS (pusty rejestr, KRZGW, osoba fizyczna, sama ewidencja z NIP) poza zbiorem, policzone.
    assert stats == {'bez_krs': 4, 'osoby_fizyczne': 1, 'bledne': 0, 'duplikaty': 0}
    assert len(records) == 1
    row = records[0]
    assert row['signed'] == '2023-03-15' and row['file_date'] == '2026-07-30'
    assert row['krs'] == '0000000002' and row['nip'] == '5260250995'
    assert row['amount'] == '1250.50' and row['subject'] == 'Działania społeczne'
    assert row['external_id'] == '1/FIO' and len(row['file_sha256']) == 64
    assert niw.signed_date('1') == '1900-01-01' and niw.signed_date('61') == '1900-03-01'
    assert niw.signed_date('0', True) == '1904-01-01'
    assert niw.signed_date('30.07.2026') == '2026-07-30' and niw.signed_date('2026-07-30T00:00:00') == '2026-07-30'
    assert niw.signed_date('') is None
    with pytest.raises(ValueError):
        niw.signed_date('-5')
    assert niw.file_date('lista-dotacji-2026-07-30.xlsx') == '2026-07-30'


def test_identifiers_nip_checksum_and_amount_formats():
    assert niw.identifier('526-025-09-95', 'nip') == '5260250995'
    assert niw.identifier('PL 5260250995', 'nip') == '5260250995'
    assert niw.identifier('1234567890', 'nip') == ''  # zła suma kontrolna
    assert niw.identifier('2.0', 'krs') == '0000000002' and niw.identifier('KRS 12345', 'krs') == '0000012345'
    assert niw.identifier('12345678901', 'krs') == '' and niw.identifier('abc', 'krs') == ''
    for text in ('1 250,50 zł', '1.250,50', '1,250.50 PLN', '1250.5', '1 250,5'):
        assert str(niw.amount_value(text)) == '1250.50', text
    assert str(niw.amount_value('1,250,500')) == '1250500.00'
    for bad in ('nieznana', '-1', 'inf', ''):
        with pytest.raises(ValueError):
            niw.amount_value(bad)


def test_invalid_rows_counted_not_fatal_and_duplicates():
    rows = [
        GOOD,
        [*GOOD[:3], 'nieznana', '9/X', 45000, *GOOD[6:]],            # zła kwota
        [*GOOD[:5], 'kiedyś', *GOOD[6:]],                            # zła data (ten sam numer umowy, inny wiersz)
        GOOD,                                                        # identyczny duplikat
        [*GOOD[:3], 2000, '1/FIO', 45001, 'Inna Fundacja', '5260250995', 'KRS', 7],  # ten sam numer, inny podmiot
        [*GOOD[:3], 2000, '1/FIO', 45001, 'Inna Fundacja', '5260250995', 'KRS', 7],  # i jego duplikat
    ]
    records, stats = niw.parse_xlsx(xlsx(rows), NAME)
    assert stats == {'bez_krs': 0, 'osoby_fizyczne': 0, 'bledne': 2, 'duplikaty': 2}
    assert [r['external_id'] for r in records] == ['1/FIO', '1/FIO|nowefio|0000000007']


def test_merged_cells_cells_without_refs_and_empty_cells():
    rows = [GOOD, ['Drugie zadanie', 'NOWEFIO', '2026', 10, '2/FIO', 45000, None, None, None, None]]
    # Nazwa, NIP, rejestr i KRS scalone w dół (G2:G3 ... J2:J3): drugi wiersz dziedziczy wartości.
    records, stats = niw.parse_xlsx(xlsx(rows, merges=('G2:G3', 'H2:H3', 'I2:I3', 'J2:J3')), NAME)
    assert [r['external_id'] for r in records] == ['1/FIO', '2/FIO'] and records[1]['krs'] == '0000000002'
    records, stats = niw.parse_xlsx(xlsx(rows), NAME)
    assert len(records) == 1 and stats['bez_krs'] == 1
    records, _ = niw.parse_xlsx(xlsx([GOOD], refs=False), NAME)
    assert len(records) == 1 and records[0]['krs'] == '0000000002'


def test_unknown_layout_dtd_and_unpacked_limit(monkeypatch):
    monkeypatch.setitem(niw.ALIASES, 'subject', ('nieistniejaca kolumna',))
    with pytest.raises(ValueError, match='kolumn'):
        niw.parse_xlsx(xlsx(), NAME)
    monkeypatch.undo()
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<!DOCTYPE x [<!ENTITY a "aaaa">]><workbook/>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships/>')
    with pytest.raises(ValueError, match='DTD'):
        niw.parse_xlsx(stream.getvalue(), NAME)
    monkeypatch.setattr(niw, 'MAX_MEMBER_BYTES', 10)
    with pytest.raises(ValueError, match='200 MB'):
        niw.parse_xlsx(xlsx(), NAME)


def test_latest_file_skips_foreign_hosts_and_bad_names():
    old = '/wp-content/Lista-dotacji-31-12-2025.xlsx'
    new = '/wp-content/' + NAME
    html = (f'<a href="https://example.com/Lista-dotacji-01-01-2030.xlsx">obca</a><a href="{new}">nowa</a>'
            f'<a href="{old}">stara</a><a href="/wp-content/Lista-dotacji-bez-daty.xlsx">x</a>')
    assert niw.latest_file(html) == 'https://niw.gov.pl' + new
    with pytest.raises(ValueError, match='nie znaleziono'):
        niw.latest_file('<a href="https://example.com/Lista-dotacji-01-01-2030.xlsx">obca</a>')


def test_download_limit_redirects_and_hosts(monkeypatch):
    class Response:
        status_code = 200
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): return iter([b'123', b'456'])
    calls = []
    monkeypatch.setattr(niw.requests, 'get', lambda url, **k: calls.append((url, k)) or Response())
    monkeypatch.setattr(niw, 'MAX_BYTES', 5)
    with pytest.raises(ValueError, match='20 MB'):
        niw.download(niw.PAGE_URL)
    assert calls[0][1]['allow_redirects'] is False and 'przeszlosc.today' in calls[0][1]['headers']['User-Agent']
    Response.headers = {'Content-Length': '999'}
    with pytest.raises(ValueError, match='20 MB'):
        niw.download(niw.PAGE_URL)
    Response.status_code = 302
    Response.headers = {'Location': 'https://example.com/file.xlsx'}
    with pytest.raises(ValueError, match='niw.gov.pl'):
        niw.download(niw.PAGE_URL)
    Response.headers = {'Location': 'http://niw.gov.pl/file.xlsx'}
    with pytest.raises(ValueError, match='niw.gov.pl'):
        niw.download(niw.PAGE_URL)
    Response.headers = {}
    with pytest.raises(ValueError, match='bez adresu'):
        niw.download(niw.PAGE_URL)
    Response.headers = {'Location': '/wp-content/' + NAME}
    with pytest.raises(ValueError, match='przekierowań'):
        niw.download(niw.PAGE_URL)
    for url in ('http://niw.gov.pl/x.xlsx', 'https://niw.gov.pl.evil.com/x.xlsx', 'https://niw.gov.pl:8443/x.xlsx', 'ftp://niw.gov.pl/x'):
        with pytest.raises(ValueError):
            niw.official_url(url)


def test_archive_file_named_by_state_fetch_date_and_hash(tmp_path, settings, monkeypatch):
    raw = xlsx()
    path = niw.archive_file(raw, NAME, tmp_path)
    assert path.parent == tmp_path and path.read_bytes() == raw
    assert path.name.startswith('Lista-dotacji-NIW-CRSO-stan-2026-07-30-pobrano-') and path.suffix == '.xlsx'
    assert niw.archive_file(raw, NAME, tmp_path) == path and len(list(tmp_path.iterdir())) == 1
    monkeypatch.setenv('NIW_ARCHIWUM_DIR', str(tmp_path / 'env'))
    assert niw.archive_file(raw, NAME).parent == tmp_path / 'env'
    monkeypatch.delenv('NIW_ARCHIWUM_DIR')
    settings.BASE_DIR = tmp_path / 'base'
    assert niw.archive_file(raw, NAME).parent == tmp_path / 'base' / 'reports' / 'niw'


@pytest.mark.django_db
def test_command_dry_run_upsert_stale_removal(tmp_path):
    path = tmp_path / NAME
    path.write_bytes(xlsx())
    out = StringIO()
    call_command('przeszlosc_niw_dotacje', plik=str(path), dry_run=True, archiwum=str(tmp_path / 'arch'), stdout=out)
    assert not PublicRecord.objects.exists()
    text = out.getvalue()
    assert 'umowy z KRS: 1' in text and 'pominięte bez KRS: 4 (w tym osoby fizyczne wg rejestru: 1)' in text
    assert 'Archiwum: ' in text and 'Dry-run' in text and (tmp_path / 'arch').exists()
    call_command('przeszlosc_niw_dotacje', plik=str(path), archiwum=str(tmp_path / 'arch'), stdout=out)
    first = PublicRecord.objects.get()
    assert first.date == date(2023, 3, 15) and first.source_url == niw.PAGE_URL
    assert first.response_sha256 == first.data['file_sha256'] and first.response_url == niw.PAGE_URL
    out = StringIO()
    call_command('przeszlosc_niw_dotacje', plik=str(path), archiwum=str(tmp_path / 'arch'), stdout=out)
    assert PublicRecord.objects.count() == 1 and 'bez zmian: 1' in out.getvalue()
    # Nowszy plik: zmieniona kwota = aktualizacja, brak umowy w pliku = usunięcie.
    newer = tmp_path / 'Lista-dotacji-NIW-CRSO-na-dzien-31-08-2026.xlsx'
    newer.write_bytes(xlsx([[*GOOD[:3], 2000, '7/FIO', *GOOD[5:]]]))
    out = StringIO()
    call_command('przeszlosc_niw_dotacje', plik=str(newer), archiwum=str(tmp_path / 'arch'), stdout=out)
    assert 'Utworzone: 1' in out.getvalue() and 'usunięte (brak w nowym pliku): 1' in out.getvalue()
    assert list(PublicRecord.objects.values_list('external_id', flat=True)) == ['7/FIO']
    # Starszy plik nie usuwa nowszych danych; --bez-usuwania też nie.
    counts = niw.save_records(niw.parse_xlsx(xlsx(), NAME)[0], '')
    assert counts == {'created': 1, 'updated': 0, 'unchanged': 0, 'removed': 0}
    counts = niw.save_records(niw.parse_xlsx(newer.read_bytes(), newer.name)[0], '', remove_stale=False)
    assert counts['removed'] == 0 and PublicRecord.objects.count() == 2
    records, _ = niw.parse_xlsx(newer.read_bytes(), newer.name)
    records[0]['amount'] = '2500.00'
    assert niw.save_records(records, '')['updated'] == 1
    assert PublicRecord.objects.get(external_id='7/FIO').data['amount'] == '2500.00'


@pytest.mark.django_db
def test_command_download_mocked_and_bad_rows_not_fatal(monkeypatch, tmp_path):
    url = 'https://niw.gov.pl/wp-content/' + NAME
    calls = []

    def download(location):
        calls.append(location)
        return (f'<a href="{url}">XLSX</a>'.encode(), location) if location == niw.PAGE_URL else (xlsx(), url)

    monkeypatch.setattr(niw, 'download', download)
    monkeypatch.setenv('NIW_ARCHIWUM_DIR', str(tmp_path / 'a'))
    call_command('przeszlosc_niw_dotacje', dry_run=True, stdout=StringIO())
    assert calls == [niw.PAGE_URL, url] and not PublicRecord.objects.exists()
    assert len(list((tmp_path / 'a').iterdir())) == 1
    path = tmp_path / NAME
    path.write_bytes(xlsx([GOOD, ['Błędny', 'PROO', '2026', 'nieznana', '2', 45000, 'Fundacja', '5260250995', 'KRS', 2]]))
    out = StringIO()
    call_command('przeszlosc_niw_dotacje', plik=str(path), stdout=out)
    assert 'błędne (kwota lub data): 1' in out.getvalue() and PublicRecord.objects.count() == 1
    with pytest.raises(CommandError):
        call_command('przeszlosc_niw_dotacje', plik=str(tmp_path / 'brak.xlsx'))
    bad = tmp_path / 'Lista-dotacji-01-01-2026.xlsx'
    bad.write_bytes(b'nie zip')
    with pytest.raises(CommandError):
        call_command('przeszlosc_niw_dotacje', plik=str(bad))


@pytest.mark.django_db
def test_identifier_matching_company_view_notes_and_export(monkeypatch):
    company = org()
    figure = person(company)
    records, _ = niw.parse_xlsx(xlsx(), NAME)
    base = records[0]
    niw.save_records([
        {**base, 'contract_no': 'KRS', 'external_id': 'KRS', 'nip': ''},
        {**base, 'contract_no': 'BOTH', 'external_id': 'BOTH'},
        {**base, 'contract_no': 'NAME', 'external_id': 'NAME', 'beneficiary': company.name, 'nip': '', 'krs': ''},
        {**base, 'contract_no': 'NIP_ONLY', 'external_id': 'NIP_ONLY', 'krs': ''},
        {**base, 'contract_no': 'WRONG_TYPE', 'external_id': 'WRONG_TYPE', 'nip': company.krs_number, 'krs': ''},
    ], niw.PAGE_URL, remove_stale=False)
    rows = dp.grants(company, dp.identifiers(company))
    # Warunek 1: sama nazwa i sam NIP (bez KRS) nie są pokazywane.
    assert {r['contract_no'] for r in rows} == {'KRS', 'BOTH'} and {r['matched_by'] for r in rows} == {'KRS'}
    assert all(r['attribution'].startswith('Źródło: NIW-CRSO, Lista dotacji, stan na 2026-07-30, pobrano ') for r in rows)
    assert all('Opracowanie iapply, nie jest publikacją NIW. Kwota wynika z umowy i nie oznacza wypłaty.' in r['attribution'] for r in rows)
    assert all(r['currency'] == 'PLN' and r['beneficiary'] == 'Fundacja' for r in rows)
    rec('fts', 'eu_grant', 'fts1', {'vat': company.nip, 'amount': 10}, day=date(2024, 1, 1))
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    response = APIClient().get(f'/api/przeszlosc/spolka/{company.krs_number}/')
    assert response.status_code == 200
    data = response.json()
    # Warunek 3: PLN i EUR osobno, nigdy jedna suma.
    assert data['grants']['sums'] == [{'currency': 'PLN', 'total': 2501.0}, {'currency': 'EUR', 'total': 10.0}]
    assert data['grants']['sums_note'] == niw.SUMS_NOTE and niw.SUMS_NOTE in data['note']
    assert 'Kwoty z listy dotacji NIW-CRSO (umowy), stan na 2026-07-30.' in data['note']
    assert data['grants']['sources'] == ['fts', 'niw'] and dp.SOURCES['niw'] in data['sources']
    assert 'oficjaln' not in dp.SOURCES['niw']['label'].lower() and 'oficjaln' not in data['note'].lower()
    niw_nodes = [n for n in data['nodes'] if n.get('source') == 'niw']
    assert niw_nodes and all(n['currency'] == 'PLN' and n['attribution'] for n in niw_nodes)
    assert all(e['label'] == 'dotacja krajowa' for e in data['edges'] if e['target'].startswith('niw:'))
    # Warunek 5: osoba publiczna w KRS + dotacja krajowa = zastrzeżenie, daty roli obok (since) i umowy (date).
    assert data['people']['note'].startswith('Powiązanie osoby z organizacją wynika z jawnych rejestrów (stan na ')
    assert 'Nie oceniamy osób ani decyzji.' in data['people']['note']
    assert data['people']['results'][0]['since'] == '2024-01-02' and niw_nodes[0]['date'] == '2023-03-15'
    for word in ('zależny', 'związany z', '->', '=>'):
        assert word not in data['people']['note']
    full = dp.export_data(company)
    assert full['people_note'] == data['people']['note'] and full['sums_note'] == niw.SUMS_NOTE
    csv = dp.export_csv(company, full)
    assert 'dotacja krajowa' in csv and 'Źródło: NIW-CRSO, Lista dotacji, stan na 2026-07-30' in csv
    assert 'Nie oceniamy osób ani decyzji.' in csv and niw.SUMS_NOTE in csv
    # Bez osoby publicznej: brak zastrzeżenia; bez NIW: zwykła notatka.
    from news.political_models import PublicFigureOrganisationRelation
    PublicFigureOrganisationRelation.objects.filter(public_figure=figure).delete()
    assert dp.branches(company)['people']['note'] == ''
    PublicRecord.objects.filter(source='niw').delete()
    assert dp.branches(company)['grants']['note'] == dp.NOTE


@pytest.mark.django_db
def test_flow_tree_niw_channel_institution_and_legal_notes(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    cache.clear()
    company = org()
    figure = person(company)
    records, _ = niw.parse_xlsx(xlsx(), NAME)
    grant = {**records[0], 'signed': '2024-06-01'}  # w okresie funkcji osoby (od 2024-01-02), P0-2
    niw.save_records([{**grant, 'contract_no': 'NIP_ONLY', 'external_id': 'NIP_ONLY', 'krs': ''}, grant], niw.PAGE_URL)
    row = PublicRecord.objects.get(external_id='1/FIO')
    data = APIClient().get(f'/api/przeszlosc/przeplyw/osoba:{figure.pk}/').json()
    nodes = {n['id']: n for n in data['nodes']}
    channel = nodes[f'niw:{row.pk}']
    assert channel['currency'] == 'PLN' and channel['amount'] == 1250.5 and channel['date'] == '2024-06-01'
    assert channel['meta']['file_date'] == '2026-07-30' and channel['meta']['attribution'].startswith('Źródło: NIW-CRSO')
    assert channel['source']['key'] == 'niw' and 'oficjaln' not in channel['source']['label'].lower()
    assert nodes['authority:niw']['label'] == 'NIW-CRSO (Narodowy Instytut Wolności)'
    pairs = {(e['from'], e['to'], e['label']) for e in data['edges']}
    assert ('authority:niw', f'niw:{row.pk}', 'finansuje') in pairs and (f'niw:{row.pk}', f'org:{company.pk}', 'beneficjent') in pairs
    assert f'niw:{PublicRecord.objects.get(external_id="NIP_ONLY").pk}' not in nodes
    notes = data['legal']['notes']
    assert any('stan na 2026-07-30' in n and niw.SUMS_NOTE in n for n in notes)
    assert any(n.startswith('Powiązanie osoby z organizacją wynika z jawnych rejestrów') for n in notes)
    cache.clear()
    company_tree = APIClient().get(f'/api/przeszlosc/przeplyw/spolka:{company.krs_number}/').json()
    assert not any(n.startswith('Powiązanie osoby') for n in company_tree['legal']['notes'])
    assert 'authority:niw' in {n['id'] for n in company_tree['nodes']}
    cache.clear()


def test_real_niw_file_headers_and_repeated_contract_numbers(monkeypatch):
    """Układ pliku NIW z 30.07.2026: „Tytuł wniosku”, „Numer wniosku”, KRS w „Numerze w rejestrze” bez zer wiodących;
    numer umowy powtarza się między konkursami, więc kluczem jest numer wniosku."""
    import sys
    headers = ['Numer wniosku', 'Tytuł wniosku', 'Program', 'Konkurs', 'Priorytet', 'Kwota dotacji', 'Rozpoczęcie zadania',
               'Zakończenie zadania', 'Numer umowy', 'Data zawarcia umowy', 'Nazwa oferenta', 'NIP', 'Nazwa rejestru',
               'Numer w rejestrze', 'Kod pocztowy', 'Miejscowość', 'Województwo', 'Powiat']
    rows = [
        ['3_FIO2018', 'Zadanie A', 'Program Fundusz Inicjatyw Obywatelskich', 'Konkurs FIO 2018', '', 36770, 43283, 43465, '75', 43285,
         'Stowarzyszenie A', '5260250995', 'KRS', '336434', '05-306', 'Miasto', 'MAZOWIECKIE', 'miński'],
        ['9_FIO2019', 'Zadanie B', 'Program Fundusz Inicjatyw Obywatelskich', 'Konkurs FIO 2019', '', 20000, 43700, 43800, '75', 43650,
         'Stowarzyszenie A', '5260250995', 'KRS', '336434', '05-306', 'Miasto', 'MAZOWIECKIE', 'miński'],
    ]
    monkeypatch.setattr(sys.modules[__name__], 'HEADERS', headers)
    records, stats = niw.parse_xlsx(xlsx(rows), NAME)
    assert len(records) == 2 and stats['bez_krs'] == 0 and stats['bledne'] == 0
    assert {r['krs'] for r in records} == {'0000336434'}
    assert {r['external_id'] for r in records} == {'3_FIO2018', '9_FIO2019'}
    assert records[0]['subject'] == 'Zadanie A' and records[0]['contract_no'] == '75'


def test_missing_contract_date_is_kept_without_date(monkeypatch):
    """142 wiersze prawdziwego pliku NIW mają KRS i kwotę, ale pustą datę umowy: nie są błędne, tylko bez daty."""
    import sys
    rows = [GOOD, ['Bez daty', 'FIO', '2026', 100, '7/FIO', 'brak danych', 'Fundacja B', '5260250995', 'KRS', 7]]
    records, stats = niw.parse_xlsx(xlsx(rows), NAME)
    assert len(records) == 2 and stats['bledne'] == 0 and stats['bez_daty'] == 1
    assert [r['signed'] for r in records if r['contract_no'] == '7/FIO'] == [None]
