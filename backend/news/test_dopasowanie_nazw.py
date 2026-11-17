"""Dopasowanie po nazwie z drugim danym (news/dopasowanie_nazw.py), siedziba z odpisu KRS (news/krs.py::seat), klient news/krs_nazwa.py."""
import os
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache

from news import dopasowanie_nazw as dn, krs, krs_nazwa
from news.political_models import RegisteredOrganisation

RESPONSE = {'liczbaPodmiotow': 4, 'listaPodmiotow': [
    {'czyOPP': True, 'dataPrzyznaniaStatutuOPP': None, 'czyUpadlosc': False, 'miejscowosc': 'PŁOCK', 'nazwa': 'FUNDACJA ORLEN', 'numer': '37031', 'typRejestru': 'S'},
    {'czyOPP': True, 'czyUpadlosc': False, 'miejscowosc': 'GDAŃSK', 'nazwa': 'FUNDACJA ORLEN DLA POMORZA', 'numer': '563005', 'typRejestru': 'S'},
    {'czyOPP': False, 'czyUpadlosc': False, 'miejscowosc': 'WARSZAWA', 'nazwa': 'FUNDACJA ORLEN IM. IGNACEGO ŁUKASIEWICZA', 'numer': '210832', 'typRejestru': 'P'},
    {'czyOPP': False, 'czyUpadlosc': False, 'miejscowosc': 'WARSZAWA', 'nazwa': 'FUNDACJA ORLEN IM. IGNACEGO ŁUKASIEWICZA', 'numer': '210832', 'typRejestru': 'S'}]}


def test_normalize_name_ignores_case_diacritics_quotes_and_legal_form_spelling():
    assert dn.normalize_name('Fundacja „Łukasiewicz”') == dn.normalize_name('FUNDACJA LUKASIEWICZ')
    assert dn.normalize_name('Orlen spółka z ograniczoną odpowiedzialnością') == dn.normalize_name('ORLEN sp. z o.o.') == 'orlen spzoo'
    assert dn.normalize_name('Orlen S.A.') == dn.normalize_name('Orlen spółka akcyjna') == 'orlen sa'
    assert dn.normalize_name('Orlen SA') != dn.normalize_name('Orlen sp. z o.o.')   # inna forma prawna to inny podmiot


def test_choose_requires_exact_name_and_one_candidate_and_uses_place_to_disambiguate():
    cands = [{'name': 'Fundacja Dobro', 'city': 'Kraków', 'voivodeship': 'MAŁOPOLSKIE'}, {'name': 'FUNDACJA DOBRO', 'city': 'Gdańsk', 'voivodeship': 'POMORSKIE'}]
    assert dn.choose(cands, 'Fundacja Dobro') == (None, None, False)                            # dwóch kandydatów, brak drugiego danego
    kind, hit, conflict = dn.choose(cands, 'fundacja dobro', city='Gdańsk')
    assert (kind, hit['city'], conflict) == ('nazwa_i_siedziba', 'Gdańsk', False)               # siedziba rozstrzyga
    one = [cands[0]]
    assert dn.choose(one, 'Fundacja Dobro')[0] == 'nazwa'                                        # sama nazwa, jeden kandydat
    kind, hit, conflict = dn.choose(one, 'Fundacja Dobro', city='Warszawa')
    assert (kind, conflict) == ('nazwa', True)                                                   # sprzeczna siedziba: tylko „nazwa” z flagą
    assert dn.choose(one, 'Fundacja Inna') == (None, None, False)                                # inna nazwa nie pasuje
    assert dn.choose([{'name': 'A B'}, {'name': 'A B'}], 'a b', city='X') == (None, None, False)  # nadal dwóch bez rozstrzygnięcia


@pytest.mark.django_db
def test_match_own_uses_seat_and_ignores_ambiguous():
    RegisteredOrganisation.objects.create(name='Fundacja Dobro', krs_number='0000000001', kind='foundation', nip='1111111111', seat_city='Kraków')
    RegisteredOrganisation.objects.create(name='Fundacja Dobro', krs_number='0000000002', kind='foundation', nip='2222222222', seat_city='Gdańsk')
    assert dn.match_own('Fundacja Dobro') is None                                                # niejednoznaczne
    hit = dn.match_own('FUNDACJA DOBRO', city='Gdańsk')
    assert hit['class'] == 'nazwa_i_siedziba' and hit['krs_number'] == '0000000002' and hit['nip'] == '2222222222'
    assert dn.match_own('Nieznana Fundacja') is None and dn.match_own('ab') is None


def test_seat_from_odpis_has_no_street_and_tolerates_other_layouts():
    d1 = {'siedzibaIAdres': {'siedziba': {'kraj': 'POLSKA', 'wojewodztwo': 'MAZOWIECKIE', 'miejscowosc': 'WARSZAWA'},
                              'adres': {'ulica': 'UL. TAJNA', 'nrDomu': '5', 'kodPocztowy': '00-001', 'miejscowosc': 'WARSZAWA'}}}
    assert krs.seat(d1) == {'seat_city': 'WARSZAWA', 'seat_postal_code': '00-001', 'seat_voivodeship': 'MAZOWIECKIE'}
    assert krs.seat({}) == {'seat_city': '', 'seat_postal_code': '', 'seat_voivodeship': ''}
    assert krs.seat({'siedzibaIAdres': {'adres': {'kodPocztowy': 'zły'}}})['seat_postal_code'] == ''


def test_client_parse_merges_p_and_s_registers_and_pads_krs():
    rows = {r['krs']: r for r in krs_nazwa.parse(RESPONSE)}
    assert len(rows) == 3 and rows['0000210832']['registers'] == ['P', 'S'] and rows['0000037031']['name'] == 'FUNDACJA ORLEN'


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cache.clear(); monkeypatch.delenv('KRS_NAME_SEARCH_URL', raising=False); monkeypatch.delenv('KRS_NAME_SEARCH_APIKEY', raising=False)
    yield
    cache.clear()


def test_client_disabled_without_url_and_never_calls_network(monkeypatch):
    with patch('news.krs_nazwa.requests.post') as post:
        assert krs_nazwa.search('Fundacja Orlen') == ([], 'disabled') and krs_nazwa.resolve('Fundacja Orlen') == {'status': 'disabled'}
    post.assert_not_called()


def test_client_uses_configured_url_key_honest_headers_and_caches(monkeypatch):
    monkeypatch.setenv('KRS_NAME_SEARCH_URL', 'https://example.test/krs/szukaj'); monkeypatch.setenv('KRS_NAME_SEARCH_APIKEY', 'klucz-od-urzedu')
    monkeypatch.setattr('news.krs_nazwa.time.sleep', lambda s: None)
    response = Mock(status_code=200); response.json.return_value = RESPONSE
    with patch('news.krs_nazwa.requests.post', return_value=response) as post:
        out = krs_nazwa.resolve('Fundacja Orlen', city='Płock')
        again = krs_nazwa.resolve('Fundacja Orlen', city='Płock')
    assert out['class'] == 'nazwa_i_siedziba' and out['krs_number'] == '0000037031' and out['opp'] is True and out == again
    assert post.call_count == 1                                                                   # drugi raz z cache
    headers = post.call_args.kwargs['headers']
    assert headers['apikey'] == 'klucz-od-urzedu' and 'przeszlosc.today' in headers['User-Agent']
    assert 'origin' not in {k.lower() for k in headers} and 'referer' not in {k.lower() for k in headers}   # bez podszywania się pod aplikację urzędu
    assert post.call_args.kwargs['json']['podmiot']['nazwa'] == 'Fundacja Orlen' and post.call_args.kwargs['json']['podmiot']['miejscowosc'] == 'Płock'


def test_client_error_paths_do_not_raise(monkeypatch):
    monkeypatch.setenv('KRS_NAME_SEARCH_URL', 'https://example.test/krs/szukaj'); monkeypatch.setattr('news.krs_nazwa.time.sleep', lambda s: None)
    with patch('news.krs_nazwa.requests.post', return_value=Mock(status_code=403)):
        assert krs_nazwa.search('X')[1] == 'error'
    with patch('news.krs_nazwa.requests.post', side_effect=__import__('requests').ConnectionError()):
        assert krs_nazwa.search('Y')[1] == 'error'
