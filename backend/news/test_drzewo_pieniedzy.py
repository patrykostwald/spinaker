"""Drzewo przepływu pieniędzy (właściciel 6.10): powiązania tylko po identyfikatorach, sumy gałęzi, źródła z licencją. Bez sieci."""
from datetime import date
from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from news import drzewo_pieniedzy as dp
from news import krs
from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation
from news.public_records_models import PublicRecord
from scraper import public_record_parsers as parsers

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def rec(source, kind, key, data, title='x', day=None):
    return PublicRecord.objects.create(source=source, kind=kind, external_id=key, data=data, title=title, date=day,
                                       source_url=f'https://example.org/{source}/{key}', response_url='https://example.org/', response_sha256='0')


def org(name='Port Lotniczy SA', krs_number='0000000002', nip='5260250995', regon='012345678'):
    return RegisteredOrganisation.objects.create(name=name, krs_number=krs_number, kind='company', nip=nip, regon=regon,
                                                 legal_form='spółka akcyjna', official_register_url='https://ekrs.ms.gov.pl/')


def person(company, name='Anna Kowalska'):
    figure = PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł na Sejm RP',
                                         evidence_url='https://sejm.gov.pl')
    relation = PublicFigureOrganisationRelation.objects.create(public_figure=figure, organisation=company, public_role='członek zarządu',
                                                               organ='zarząd', relation_status='current', since=date(2024, 1, 2),
                                                               evidence_url='https://api-krs.ms.gov.pl/api/krs/OdpisPelny/0000000002')
    relation.confirm_automatically('krs_register')
    relation.save()
    return figure


def test_tree_links_only_by_identifiers_and_sums_branches():
    company = org()
    other = org('Inna Spółka sp. z o.o.', '0000000003', nip='1234563218', regon='')
    # TED: identyfikator wykonawcy z przedrostkiem PL; drugie ogłoszenie po KRS; trzecie innej firmy; czwarte tylko ta sama nazwa
    rec('ted', 'notice', '1-2026', {'buyer': ['Gmina Miasto'], 'value': 1500000.5, 'currency': 'PLN', 'notice_type': 'can-standard',
                                   'winners': [{'name': 'PORT LOTNICZY S.A.', 'id': 'PL5260250995'}]}, 'Budowa pasa', date(2026, 3, 1))
    rec('ted', 'notice', '2-2026', {'buyer': ['Ministerstwo'], 'value': 200, 'currency': 'EUR', 'winners': [{'name': 'Port', 'id': 'KRS 0000000002'}]},
        'Doradztwo', date(2026, 2, 1))
    rec('ted', 'notice', '3-2026', {'buyer': ['Gmina'], 'value': 999, 'currency': 'PLN', 'winners': [{'name': 'Inna', 'id': '1234563218'}]}, 'Obca')
    rec('ted', 'notice', '4-2026', {'buyer': ['Gmina'], 'value': 777, 'currency': 'PLN', 'winners': [{'name': 'Port Lotniczy SA'}]}, 'Po nazwie')
    # BZP: podmiot jako zamawiający po NIP
    rec('bzp', 'notice', 'b1', {'organizationName': 'Port Lotniczy SA', 'organizationNationalId': '526-025-09-95', 'noticeType': 'ContractNotice'},
        'Sprzątanie terminalu', date(2026, 4, 5))
    # FTS: VAT = PL + NIP; Kohesio tylko po nazwie (zbieracz) -> niepowiązane
    rec('fts', 'eu_grant', 'f1', {'beneficiary': 'Port Lotniczy SA', 'vat': 'PL5260250995', 'amount': 1000.0, 'subject': 'Badania', 'programme': 'Horyzont',
                                 'year': 2024, 'organisation_id': company.pk}, 'Port: Badania', date(2024, 12, 31))
    rec('fts', 'eu_grant', 'f2', {'beneficiary': 'Port Lotniczy SA', 'vat': '', 'amount': 50.0, 'subject': 'Bez VAT', 'organisation_id': company.pk}, 'Port: Bez VAT')
    rec('kohesio', 'eu_project', 'Q1', {'beneficiary': 'Port Lotniczy SA', 'project': 'Terminal', 'eu_budget': 300.0, 'organisation_id': company.pk,
                                       'krs': '0000000002', 'link': 'nazwa z KRS (do sprawdzenia)'}, 'Terminal - Port Lotniczy SA')
    figure = person(company)

    data = dp.tree(company)
    contracts = data['contracts']
    assert contracts['count'] == 3 and {c['matched_by'] for c in contracts['results']} == {'NIP', 'KRS'}
    assert contracts['sums'] == [{'currency': 'PLN', 'total': 1500000.5}, {'currency': 'EUR', 'total': 200.0}]
    bzp = next(c for c in contracts['results'] if c['source'] == 'bzp')
    assert bzp['role'] == 'zamawiający' and bzp['amount'] is None
    assert 'Po nazwie' not in str(contracts) and 'Obca' not in str(contracts)
    assert data['grants']['count'] == 1 and data['grants']['sums'] == [{'currency': 'EUR', 'total': 1000.0}]
    assert {u['title'] for u in data['unlinked']['results']} == {'Terminal', 'Bez VAT'}
    assert all(u['reason'] == dp.UNLINKED_REASON for u in data['unlinked']['results'])
    people = data['people']['results']
    assert people[0]['name'] == 'Anna Kowalska' and people[0]['profile_url'] == f'/przeszlosc/osoba/{people[0]["slug"]}' and people[0]['since'] == '2024-01-02'
    assert {n['kind'] for n in data['nodes']} == {'organisation', 'contract', 'grant', 'person'}
    assert len(data['edges']) == 3 + 1 + 1 and {e['label'] for e in data['edges']} == {'wykonawca', 'zamawiający', 'dotacja UE', 'funkcja w KRS'}
    licenses = {s['key']: s['license'] for s in data['sources']}
    assert licenses == {'bzp': 'informacja publiczna', 'fts': 'CC BY 4.0', 'kohesio': 'CC0 1.0', 'krs': 'dane publiczne rejestru',
                        'ted': 'ponowne wykorzystanie dozwolone (decyzja KE 2011/833/UE)'}
    assert data['identifiers'] == {'NIP': '5260250995', 'KRS': '0000000002', 'REGON': '012345678'} and not data['identifiers_missing']

    # Odwrotne wejście z profilu osoby: podmioty z sumami gałęzi
    trail = dp.person_companies(figure)
    row = trail['results'][0]
    assert row['url'] == '/przeszlosc/spolka/0000000002' and row['contracts']['count'] == 3 and row['grants']['sums'][0]['total'] == 1000.0
    assert row['people'] == 1 and row['unlinked'] == 2
    # Podmiot bez NIP: tylko KRS może łączyć, FTS i BZP puste, flaga braku identyfikatorów
    bare = dp.tree(other)
    assert bare['contracts']['count'] == 1 and bare['grants']['count'] == 0 and bare['identifiers_missing'] is False
    nothing = org('Trzecia', '0000000004', nip='', regon='')
    assert dp.tree(nothing)['identifiers_missing'] is True and dp.tree(nothing)['contracts']['count'] == 0


def test_company_endpoint_gated_resolves_krs_and_id(monkeypatch):
    monkeypatch.setattr(krs, 'fetch', lambda *a, **k: None)
    company = org()
    client = APIClient()
    assert client.get('/api/przeszlosc/spolka/0000000002/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    by_krs = client.get('/api/przeszlosc/spolka/0000000002/').json()
    assert by_krs['organisation']['name'] == 'Port Lotniczy SA' and by_krs['note'] == dp.NOTE and by_krs['access']['beta'] is True
    assert client.get(f'/api/przeszlosc/spolka/{company.pk}/').json()['organisation']['id'] == company.pk
    assert client.get('/api/przeszlosc/spolka/0000009999/').status_code == 404
    assert client.get('/api/przeszlosc/spolka/abc/').status_code == 404
    with override_settings(PRZESZLOSC_BETA_ALL_FEATURES=False):
        locked = client.get('/api/przeszlosc/spolka/0000000002/')
        assert locked.status_code == 403 and locked.json()['feature'] == 'money_trail'


def test_person_profile_carries_money_trail(monkeypatch):
    company = org()
    figure = person(company)
    rec('fts', 'eu_grant', 'f1', {'beneficiary': 'Port', 'vat': 'PL5260250995', 'amount': 20.0, 'subject': 'X', 'year': 2024}, 'Port: X')
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    client = APIClient()
    data = client.get(f'/api/przeszlosc/osoba/{figure.pk}/').json()
    assert data['money_trail']['results'][0]['grants']['count'] == 1
    with override_settings(PRZESZLOSC_BETA_ALL_FEATURES=False):
        cache.clear()
        assert client.get(f'/api/przeszlosc/osoba/{figure.pk}/').json()['money_trail'] is None


def test_krs_identifiers_from_extract_header_and_agent_save():
    payload = {'odpis': {'naglowekA': {'rejestr': 'P', 'numerKRS': '0000000002', 'stanZDnia': '01.10.2026', 'numerOstatniegoWpisu': 7,
                                       'dataOstatniegoWpisu': '30.09.2026'},
                         'dane': {'dzial1': {'danePodmiotu': {'nazwa': 'PORT LOTNICZY S.A.',
                                                               'identyfikatory': {'regon': '012345678', 'nip': '526-025-09-95'}}}}}}
    header = parsers.krs_header(payload, '0000000002')
    assert header['nip'] == '5260250995' and header['regon'] == '012345678'
    assert parsers.krs_header({'odpis': {'naglowekA': {'numerKRS': '2'}, 'dane': {}}}, '0000000002')['nip'] == ''
    extract = krs.parse('0000000002', 'P', {'odpis': {'naglowekP': {}, 'dane': {'dzial1': {'danePodmiotu': {
        'nazwa': [{'nazwa': 'PORT LOTNICZY S.A.'}], 'formaPrawna': [{'formaPrawna': 'SPÓŁKA AKCYJNA'}],
        'identyfikatory': {'regon': '123', 'nip': '5260250995'}}}}}})
    assert extract.nip == '5260250995' and extract.regon == ''  # REGON ma 9 albo 14 cyfr
    assert krs.identifiers({}) == {'nip': '', 'regon': ''}


def test_command_plan_offline_and_identifiers_with_mocked_api(monkeypatch):
    company = org(nip='')
    org('Z NIP', '0000000003')
    out = StringIO()
    call_command('drzewo_pieniedzy', '--plan', stdout=out)
    assert 'bez NIP: 1' in out.getvalue() and 'rekordy w bazie' in out.getvalue()
    calls = []

    def fake_fetch(number, full=True):
        calls.append((number, full))
        return krs.Extract(krs=number, register='P', name='PORT', legal_form='SPÓŁKA AKCYJNA', kind='company', nip='5260250995', regon='012345678')
    monkeypatch.setattr(krs, 'fetch', fake_fetch)
    out = StringIO()
    call_command('drzewo_pieniedzy', '--identyfikatory', '--pauza', '0', stdout=out)
    company.refresh_from_db()
    assert company.nip == '5260250995' and company.regon == '012345678' and calls == [('0000000002', False)]
    assert 'uzupełnione: 1' in out.getvalue()
    out = StringIO()
    call_command('drzewo_pieniedzy', '--identyfikatory', '--pauza', '0', stdout=out)
    assert len(calls) == 1  # idempotentne: podmioty z NIP pomijane


def test_nierealna_kwota_ted_jest_oznaczona_i_poza_sumami():
    """Śledczy R1, P0-1: Orlen 1,086 bln zł z jednego ogłoszenia nie może wejść do sumy spółki."""
    company = org('Orlen SA', '0000028860', nip='7740001454', regon='610188201')
    rec('ted', 'notice', '157377-2026', {'buyer': ['2. RBLog'], 'value': 1086150000000.0, 'currency': 'PLN',
        'winners': [{'name': 'ORLEN', 'id': 'PL7740001454'}]}, 'Olej napędowy', date(2026, 5, 1))
    rec('ted', 'notice', '2-2026', {'buyer': ['Gmina'], 'value': 2500000, 'currency': 'PLN',
        'winners': [{'name': 'ORLEN', 'id': '7740001454'}]}, 'Paliwo', date(2026, 5, 2))
    data = dp.tree(company)['contracts']
    assert data['count'] == 2 and data['suspect_count'] == 1
    assert data['sums'] == [{'currency': 'PLN', 'total': 2500000.0}]
    flags = {x['title']: x['amount_suspect'] for x in data['results']}
    assert flags == {'Olej napędowy': True, 'Paliwo': False}


def test_wzgledna_kwota_ponad_100x_mediany_jest_podejrzana():
    rows = [{'amount': 1000000.0 + i, 'currency': 'PLN'} for i in range(5)]
    rows.append({'amount': 1012825380.0, 'currency': 'PLN'})
    rows.append({'amount': 900000000.0, 'currency': 'EUR'})  # za mała próba w EUR i poniżej 1 mld
    dp.mark_suspect(rows)
    assert [r['amount_suspect'] for r in rows] == [False] * 5 + [True, False]
    assert dp._sums(rows) == [{'currency': 'EUR', 'total': 900000000.0}, {'currency': 'PLN', 'total': 5000010.0}]


def _extract(number='0000026438', name='BANK TESTOWY SPÓŁKA AKCYJNA', nip='5250007738'):
    return krs.Extract(krs=number, register='P', name=name, legal_form='SPÓŁKA AKCYJNA', kind='company', nip=nip, regon='016298263')


def test_search_by_name_nip_regon_and_krs_with_scope_message(monkeypatch):
    from news import przeszlosc_spolki as ps
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    monkeypatch.setattr(krs, 'fetch', lambda *a, **k: None)
    org('PKO Bank Polski SA', '0000026438', nip='5250007738', regon='016298263')
    client = APIClient()
    get = lambda q: client.get('/api/przeszlosc/spolki/', {'q': q}).json()
    assert get('PKO')['results'][0]['url'] == '/przeszlosc/spolka/0000026438'
    assert get('525-000-77-38')['results'][0]['krs_number'] == '0000026438'
    assert get('016298263')['results'][0]['krs_number'] == '0000026438'
    assert get('KRS 26438')['results'][0]['krs_number'] == '0000026438'
    miss = get('Nieistniejąca')
    assert miss['results'] == [] and miss['status'] == 'missing' and miss['message'].startswith('Brak w naszych danych') and miss['coverage']['organisations'] == 1
    assert get('ab')['status'] == 'short'
    assert ps.classify('7740001454') == ('nip', '7740001454') and ps.classify('0000026438')[0] == 'krs'


def test_search_and_company_fetch_unknown_krs_on_demand_with_cache_and_limits(monkeypatch):
    from news import przeszlosc_spolki as ps
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    calls = []
    def fake(number, full=True, timeout=30):
        calls.append(number)
        return _extract(number) if number == '0000026438' else None
    monkeypatch.setattr(krs, 'fetch', fake)
    client = APIClient()
    data = client.get('/api/przeszlosc/spolki/', {'q': '0000026438'}).json()
    assert data['fetched'] is True and data['results'][0]['name'].startswith('BANK') and RegisteredOrganisation.objects.get(krs_number='0000026438').nip == '5250007738'
    assert client.get('/api/przeszlosc/spolka/0000026438/').status_code == 200 and calls == ['0000026438']
    # NIP z dociągniętego podmiotu działa jak adres strony
    assert client.get('/api/przeszlosc/spolka/5250007738/').json()['organisation']['krs_number'] == '0000026438'
    # brak w rejestrze: komunikat z zakresem, ponowne zapytanie nie idzie do sieci
    miss = client.get('/api/przeszlosc/spolka/0000099999/')
    assert miss.status_code == 404 and miss.json()['detail'].startswith('Brak w naszych danych')
    client.get('/api/przeszlosc/spolka/0000099999/')
    assert calls.count('0000099999') == 1
    # limit na adres IP
    cache.clear()
    monkeypatch.setattr(ps, 'FETCH_PER_IP_MINUTE', 2)
    codes = [client.get(f'/api/przeszlosc/spolka/00000999{i:02d}/').status_code for i in range(4)]
    assert codes == [404, 404, 503, 503]


def test_fetch_on_demand_survives_network_errors(monkeypatch):
    from news import przeszlosc_spolki as ps
    def boom(*a, **k):
        raise RuntimeError('net')
    monkeypatch.setattr(krs, 'fetch', boom)
    assert ps.fetch_on_demand('0000012345') == (None, 'error')
    assert ps.fetch_on_demand('0000012345') == (None, 'error')  # z pamięci, bez drugiego wywołania
