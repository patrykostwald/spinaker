"""Parser stron RCL na zapisanych kopiach (scraper/fixtures/rcl).  Bez sieci i bez bazy."""
from datetime import date

import pytest

from scraper import rcl_parser as parser
from scraper.rcl_parser import RclParseError
from scraper.rcl_testsupport import fixture_text


def test_list_page_rows_and_total():
    page = parser.parse_list(fixture_text('lista_typ2.html'))
    assert page.total == 2619
    assert [row['rcl_id'] for row in page.rows] == [12411600, 12413507, 12409656]
    first = page.rows[0]
    assert first['applicant'] == 'Minister Finansów' and first['applicant_id'] == '35'
    assert first['wykaz_number'] == 'UC132' and first['wykaz_url'] == 'https://www.gov.pl/web/premier/wplip-rm'
    assert first['created_on'] == date(2026, 6, 22) and first['modified_on'] == date(2026, 9, 8)
    # numer w wykazie RCL pokazuje czasem ze spacją ("UD 247")
    assert page.rows[2]['wykaz_number'] == 'UD247'


def test_list_columns_are_read_by_header_not_position():
    html = fixture_text('lista_typ2.html')
    # zamiana kolejności kolumn Utworzony i Zmodyfikowany w nagłówku i w wierszach
    swapped = html.replace('>Utworzony<', '>@@<').replace('>Zmodyfikowany<', '>Utworzony<').replace('>@@<', '>Zmodyfikowany<')
    page = parser.parse_list(swapped)
    assert page.rows[0]['created_on'] == date(2026, 9, 8) and page.rows[0]['modified_on'] == date(2026, 6, 22)


def test_project_page_fields_and_timeline():
    page = parser.parse_project(fixture_text('projekt_12414050.html'), 12414050)
    assert page['title'].startswith('Projekt ustawy o zmianie ustawy o szczególnych rozwiązaniach')
    assert page['applicant'] == 'Minister Finansów i Gospodarki' and page['applicant_id'] == '4100'
    assert page['created_on'] == date(2026, 8, 31) and page['status'] == 'otwarty' and page['term'] == 'X'
    assert page['wykaz_number'] == 'UD463' and page['wykaz_name'] == 'Rady Ministrów'
    assert page['departments'] == ['budżet', 'finanse publiczne', 'instytucje finansowe']
    assert page['keywords'] == ['FINANSE PUBLICZNE']
    assert page['rm_number'] == 'RM-0610-139-26' and 'sejm.gov.pl' in page['sejm_url']
    assert page['notes'] == ['Projekt zwolniony na podstawie Planu Prac Rządu']
    assert page['changelog_url'] == 'https://legislacja.rcl.gov.pl/projekt/rejestr/projekt/12414050'
    assert page['types'] == {1: 'Projekty założeń projektów ustaw', 2: 'Projekty ustaw',
                             10: 'Projekty rozporządzeń', 6: 'OSR ex post'}
    stages = page['stages']
    assert [s['number'] for s in stages] == list(range(1, 15))
    assert stages[0]['kind'] == 'lobbing' and stages[0]['state'] == 'not_started' and not stages[0]['catalog_url']
    council = next(s for s in stages if s['name'] == 'Rada Ministrów')
    assert council['state'] == 'reached' and council['modified_on'] == date(2026, 9, 1)
    assert council['catalog_url'] == 'https://legislacja.rcl.gov.pl/projekt/12414050/katalog/13223700'
    assert stages[-1]['state'] == 'active' and stages[-1]['kind'] == 'sejm'


def test_consultation_catalog_documents_authors_and_categories():
    catalog = parser.parse_stage_catalog(fixture_text('katalog_13223895_konsultacje_z_uwagami.html'), 13223895)
    assert catalog['stage']['name'] == 'Konsultacje publiczne' and catalog['stage']['kind'] == 'konsultacje'
    assert [f['name'] for f in catalog['folders']][:4] == [
        'Projekt', 'Pisma kierujące projekt do konsultacji publicznych',
        'Stanowiska zgłoszone w ramach konsultacji publicznych', 'Odniesienie się wnioskodawcy do uwag']
    docs = {d['rcl_doc_id']: d for d in catalog['documents']}
    assert docs[794885]['category'] == 'project' and docs[794885]['file_ext'] == 'docx'
    assert docs[794887]['category'] == 'osr' and docs[794886]['category'] == 'justification'
    assert docs[794888]['category'] == 'other'  # tabela zgodności to nie wersja projektu
    assert docs[794894]['category'] == 'cover_letter'
    position = docs[795001]
    assert position['category'] == 'position' and position['author'] == 'Stowarzyszenie Przykładowe'
    assert position['created_on'] == date(2026, 9, 10)
    assert position['file_url'] == 'https://legislacja.rcl.gov.pl/docs//2/12414100/13223895/13223898/dokument795001.pdf'
    assert docs[795010]['category'] == 'comment_table'
    # imię i nazwisko osoby wprowadzającej dokument nie trafia do danych
    assert 'pracownik' not in str(catalog['documents']).lower() and 'wprowadzony' not in str(catalog['documents'])


def test_loose_documents_without_folder():
    catalog = parser.parse_stage_catalog(fixture_text('katalog_13179001_komisja.html'), 13179001)
    assert catalog['stage']['kind'] == 'komisja' and catalog['stage']['state'] == 'active'
    assert len(catalog['documents']) == 3 and all(d['folder_name'] == '' for d in catalog['documents'])
    assert {d['author'] for d in catalog['documents']} == {'Prezes Rządowego Centrum Legislacji'}


def test_lobbying_stage_documents_are_lobbying_notifications_with_name_and_date():
    catalog = parser.parse_stage_catalog(fixture_text('katalog_lobbing_syntetyczny.html'), 13223651)
    assert catalog['stage']['kind'] == 'lobbing'
    assert [(d['category'], d['author'], d['created_on']) for d in catalog['documents']] == [
        ('lobbying', 'Fundacja Przykładowa', date(2026, 9, 14)), ('lobbying', 'Izba Wzorcowa', date(2026, 9, 15))]


def test_waf_rejection_page_is_not_a_page():
    html = fixture_text('odrzucone_przez_zapore.html')
    assert parser.is_rejected(html) and parser.is_rejected(html.encode())
    for call in (lambda: parser.parse_list(html), lambda: parser.parse_project(html, 1),
                 lambda: parser.parse_stage_catalog(html, 1)):
        with pytest.raises(RclParseError, match='request_rejected'):
            call()
    assert not parser.is_rejected(fixture_text('lista_typ2.html'))


@pytest.mark.parametrize('html', ['', '<html><body><p>Brak</p></body></html>', '<div class="rcl-title">Tytuł</div>'])
def test_unexpected_markup_raises_instead_of_inventing_data(html):
    with pytest.raises(RclParseError):
        parser.parse_project(html, 5)
    with pytest.raises(RclParseError):
        parser.parse_list(html)
    with pytest.raises(RclParseError):
        parser.parse_stage_catalog(html, 5)


def test_stage_missing_on_catalog_page():
    with pytest.raises(RclParseError, match='stage_not_on_page'):
        parser.parse_stage_catalog(fixture_text('katalog_13179001_komisja.html'), 999)


def test_list_with_announced_total_but_no_rows_is_a_markup_change():
    html = fixture_text('lista_typ2.html')
    start, end = html.index('<tbody>'), html.index('</tbody>')
    with pytest.raises(RclParseError, match='list_rows_missing'):
        parser.parse_list(html[:start] + '<tbody>' + html[end:])


@pytest.mark.parametrize('folder, name, kind, expected', [
    ('Stanowiska zgłoszone w ramach opiniowania', 'pismo.pdf', 'opiniowanie', 'position'),
    ('Odniesienie się wnioskodawcy do uwag', 'x.docx', 'konsultacje', 'comment_table'),
    ('Projekt', 'Projekt ustawy+uzasadnienie+OSR.pdf', 'uzgodnienia', 'project'),
    ('', 'cokolwiek.pdf', 'lobbing', 'lobbying'),
    ('Różne', 'plik.pdf', 'inne', 'other'),
])
def test_document_category_heuristics(folder, name, kind, expected):
    assert parser.document_category(folder, name, kind) == expected
