"""Przepływy pieniędzy v1: skąd do kogo, tylko po identyfikatorach, kwoty podejrzane poza sumami. Bez sieci."""
from datetime import date

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news import przeszlosc_przeplywy as pp
from news.test_drzewo_pieniedzy import org, person, rec

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _data():
    company = org()
    rec('ted', 'notice', '1-2026', {'buyer': ['Gmina Miasto'], 'value': 1500000.5, 'currency': 'PLN',
                                   'winners': [{'name': 'PORT LOTNICZY S.A.', 'id': 'PL5260250995'}]}, 'Budowa pasa', date(2026, 3, 1))
    # podmiot jako zamawiający (jawny NIP zamawiającego), dwóch wykonawców, w tym osoba fizyczna
    rec('ted', 'notice', '5-2026', {'buyer': ['Port Lotniczy SA'], 'buyer_nip': '5260250995', 'value': 300000, 'currency': 'PLN',
                                   'winners': [{'name': 'Jan Kowalski', 'osoba_fizyczna': True},
                                               {'name': 'Inna sp. z o.o.', 'id': '1234563218', 'osoba_fizyczna': False}]},
        'Ochrona', date(2026, 5, 1))
    rec('ted', 'notice', '6-2026', {'buyer': ['Gmina'], 'value': 9_000_000_000, 'currency': 'PLN',
                                   'winners': [{'name': 'Port', 'id': '5260250995'}]}, 'Błąd kwoty', date(2026, 6, 1))
    rec('ted', 'notice', '7-2026', {'buyer': ['Gmina'], 'value': 777, 'currency': 'PLN', 'winners': [{'name': 'Port Lotniczy SA'}]}, 'Po nazwie')
    rec('bzp', 'notice', 'b1', {'organizationName': 'Port', 'organizationNationalId': '5260250995'}, 'Sprzątanie', date(2026, 4, 5))
    rec('fts', 'eu_grant', 'f1', {'vat': 'PL5260250995', 'amount': 1000, 'subject': 'Projekt', 'year': 2024}, 'Projekt', date(2024, 12, 31))
    return company


def test_org_flows_directions_and_sums():
    company = _data()
    data = pp.for_org(company)
    kinds = {r['kind'] for r in data['results']}
    assert kinds == {'ted_in', 'ted_out', 'bzp', 'fts'}
    assert data['count'] == 5  # ogłoszenie dopasowane tylko po nazwie nie wchodzi
    out = next(r for r in data['results'] if r['kind'] == 'ted_out')
    assert out['from']['url'] == '/przeszlosc/spolka/0000000002' and 'Jan Kowalski' not in out['to']['label']
    assert 'osoba fizyczna' in out['to']['label']
    incoming = next(r for r in data['results'] if r['kind'] == 'ted_in' and not r['amount_suspect'])
    assert incoming['from']['label'] == 'Gmina Miasto' and incoming['source']['url'].startswith('https://')
    assert data['suspect_count'] == 1
    pln_in = next(s for s in data['sums']['in'] if s['currency'] == 'PLN')
    assert pln_in['total'] == 1500000.5  # 9 mld do weryfikacji poza sumą
    assert data['sums']['out'][0]['total'] == 300000
    s = data['sankey']
    assert s['currency'] == 'PLN' and s['other_currencies'] == ['EUR']
    assert sum(link['value'] for link in s['links']) == 1800000.5


def test_person_flows_only_in_tenure_and_empty_reason():
    company = _data()
    figure = person(company)  # funkcja od 2024-01-02
    data = pp.for_person(figure)
    assert all(r['via']['url'] == '/przeszlosc/spolka/0000000002' for r in data['results'])
    assert data['count'] == 5 and data['outside_tenure'] == 0
    from news.political_models import PublicFigureOrganisationRelation
    PublicFigureOrganisationRelation.objects.filter(public_figure=figure).update(until=date(2025, 1, 1))
    cut = pp.for_person(figure)
    assert cut['count'] == 1 and cut['outside_tenure'] == 4  # tylko FTS z 2024
    full = pp.for_person(figure, whole_history=True)
    assert full['count'] == 5 and sum(1 for r in full['results'] if r.get('outside_tenure')) == 4
    from news.political_models import PublicFigure
    lonely = PublicFigure.objects.create(canonical_name='Ewa Nowak', role_category='parliamentary', role_title='Posłanka',
                                         evidence_url='https://sejm.gov.pl')
    assert pp.for_person(lonely)['empty_reason']


def test_endpoint(monkeypatch):
    company = _data()
    client = APIClient()
    assert client.get('/api/przeszlosc/przeplywy/spolka:0000000002/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    body = client.get('/api/przeszlosc/przeplywy/spolka:0000000002/').json()
    assert body['subject']['krs_number'] == company.krs_number and body['count'] == 5
    assert client.get('/api/przeszlosc/przeplywy/spolka:0000000099/').status_code == 404
    assert client.get('/api/przeszlosc/przeplywy/spolka:0000000002/?cala_historia=5').status_code == 400


def test_shared_notice_amount_outside_sums():
    """Śledczy R3 P0-11: ogłoszenie z kilkoma wykonawcami - wartość całego ogłoszenia nie jest wpływem podmiotu."""
    company = org()
    rec('ted', 'notice', '8-2026', {'buyer': ['Gmina'], 'value': 1000, 'currency': 'PLN',
                                   'winners': [{'name': 'Port', 'id': '5260250995'}, {'name': 'Inna', 'id': '1234563218'}]}, 'Dwóch', date(2026, 1, 1))
    data = pp.for_org(company)
    assert data['results'][0]['amount_shared'] and data['shared_count'] == 1
    assert data['sums']['in'] == [] and data['sankey']['nodes'] == []
