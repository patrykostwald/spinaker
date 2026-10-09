"""Kontrakt drzewa przepływu i wyłączniki prawne, wyłącznie dane testowe."""
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from news import przeszlosc_przeplyw as flow
from news.clinic_models import SpinDiagnosis
from news.models import Source
from news.political_models import PublicFigureArticleReference, PublicFigureOrganisationRelation
from news.test_drzewo_pieniedzy import org, person, rec
from news.test_media_mentions import article
from news.test_przeszlosc_osoba import mp, record, voting, x_account, x_post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    cache.clear()
    yield
    cache.clear()


def get(ident, **params):
    response = APIClient().get(f'/api/przeszlosc/przeplyw/{ident}/', params)
    assert response.status_code == 200, response.content
    return response.json()


def counts(data):
    return {row['key']: row['count'] for row in data['categories']}


def test_contract_and_financial_flow_from_person():
    company = org()
    figure = person(company)
    ted = rec('ted', 'notice', 'ted', {'buyer': ['Gmina'], 'value': 120, 'currency': 'PLN',
              'winners': [{'id': 'PL5260250995'}]}, 'Remont świetlicy', date(2026, 9, 1))
    bzp = rec('bzp', 'notice', 'bzp', {'organizationNationalId': company.nip}, 'Zakup', date(2026, 9, 2))
    grant = rec('fts', 'eu_grant', 'fts', {'vat': 'PL5260250995', 'amount': 400}, 'Dotacja', date(2026, 9, 3))
    data = get(f'osoba:{figure.pk}')
    assert set(data) == {'root', 'nodes', 'edges', 'categories', 'timeline', 'signals', 'limits', 'legal', 'generated_at'}
    assert set(data['root']) == {'id', 'kind', 'label', 'url'}
    assert data['root']['kind'] == 'person'
    assert data['signals'] == [] and data['legal']['narrative'] is False
    assert set(data['legal']) == {'notes', 'narrative'}
    assert set(data['limits']) == {'max_nodes', 'max_edges', 'truncated', 'grouped'}
    assert data['limits']['max_nodes'] == 300 and data['limits']['max_edges'] == 600
    node_fields = {'id', 'kind', 'label', 'short', 'level', 'category', 'date', 'amount', 'currency', 'certainty', 'source', 'url', 'meta'}
    ids = {node['id'] for node in data['nodes']}
    for node in data['nodes']:
        assert set(node) == node_fields
        assert len(node['short']) <= 28 and 0 <= node['level'] <= 3
        assert set(node['source']) == {'key', 'label', 'license', 'url', 'retrieved_at'}
        assert node['source']['license']
    for edge in data['edges']:
        assert set(edge) == {'id', 'from', 'to', 'label', 'date_from', 'date_to', 'amount', 'currency', 'source_key', 'certainty'}
        assert edge['from'] in ids and edge['to'] in ids
    for event in data['timeline']:
        assert set(event) == {'date', 'node_id', 'kind', 'label', 'category'}
        assert event['node_id'] in ids
    assert len(data['categories']) == 6
    for category in data['categories']:
        assert set(category) == {'key', 'label', 'count', 'available'}
        if category['key'] in ('nieruchomosci', 'orzeczenia'):
            assert category['count'] == 0 and category['available'] is False
    pairs = {(edge['from'], edge['to']) for edge in data['edges']}
    assert (f'figure:{figure.pk}', f'org:{company.pk}') in pairs
    assert (f'ted:{ted.pk}', f'org:{company.pk}') in pairs
    assert (f'org:{company.pk}', f'bzp:{bzp.pk}') in pairs
    assert (f'fts:{grant.pk}', f'org:{company.pk}') in pairs
    assert any(start.startswith('authority:') and end == f'ted:{ted.pk}' for start, end in pairs)
    assert '??' not in json.dumps(data, ensure_ascii=False)


def test_company_people_require_confirmed_relation_and_depth_three():
    company = org()
    figure = person(company)
    other = person(company, 'Piotr Nowak')
    PublicFigureOrganisationRelation.objects.filter(public_figure=other).update(verification_status='pending_review')
    assert not any(n['kind'] == 'person' for n in get(f'spolka:{company.krs_number}')['nodes'])
    data = get(f'spolka:{company.nip}', glebokosc='3')
    assert [n['label'] for n in data['nodes'] if n['kind'] == 'person'] == [figure.canonical_name]
    assert data['root']['id'] == f'org:{company.pk}'


def test_name_only_is_opt_in_and_outside_amounts_and_counts():
    company = org()
    rec('fts', 'eu_grant', 'valid', {'vat': company.nip, 'amount': 100})
    rec('fts', 'eu_grant', 'hint', {'organisation_id': company.pk, 'amount': 999})
    rec('kohesio', 'eu_project', 'hint', {'organisation_id': company.pk, 'eu_budget': 800})
    normal = get(f'spolka:{company.krs_number}')
    expanded = get(f'spolka:{company.krs_number}', pokaz_niepowiazane='1')
    assert not any(n['certainty'] == 'name_only' for n in normal['nodes'])
    uncertain = [n for n in expanded['nodes'] if n['certainty'] == 'name_only']
    assert len(uncertain) == 2 and all(n['amount'] is None for n in uncertain)
    assert counts(normal) == counts(expanded)
    assert sum(n['amount'] or 0 for n in normal['nodes']) == sum(n['amount'] or 0 for n in expanded['nodes']) == 100


def test_private_recipient_is_anonymous_everywhere():
    company = org()
    rec('ted', 'notice', 'private', {'buyer': ['Urząd'], 'winners': [
        {'id': company.nip}, {'name': 'Sekretne Nazwisko', 'id': '90010112345', 'osoba_fizyczna': True}]},
        title='Wynik: Sekretne Nazwisko i spółka')
    data = get(f'spolka:{company.krs_number}', glebokosc='3')
    anonymous = next(n for n in data['nodes'] if n['kind'] == 'person_anon')
    assert anonymous['label'] == 'osoba fizyczna' and anonymous['url'] is None and anonymous['meta'] == {}
    serialized = json.dumps(data, ensure_ascii=False)
    assert 'Sekretne' not in serialized and '90010112345' not in serialized
    assert APIClient().get('/api/przeszlosc/przeplyw/osoba:Sekretne-Nazwisko/').status_code == 404


def test_narrative_is_opt_in_and_documents_votes_are_linked():
    figure = mp('Anna Kowalska', 77)
    account = x_account(figure, 'anna', '7001')
    post = x_post(account, '9001', 'Publiczne wystąpienie')
    diagnosis = SpinDiagnosis.objects.create(post=post, status='approved', verdict='spin', intensity=72,
                                             headline='Ocena wypowiedzi', diagnosed_at=timezone.now())
    record(1, 'Interpelacja', [(77, figure)])
    voting(1, [(77, 'Anna Kowalska', 'KO', 'YES')])
    normal = get(f'osoba:{figure.pk}')
    assert {'document', 'statement', 'vote'} <= {n['kind'] for n in normal['nodes']}
    assert 'intensity' not in json.dumps(normal) and 'diagnosis' not in json.dumps(normal)
    narrative = get(f'osoba:{figure.pk}', narracja='1')
    node = next(n for n in narrative['nodes'] if n['kind'] == 'diagnosis')
    assert node['id'] == f'diagnosis:{diagnosis.pk}' and node['meta']['intensity'] == 72
    assert narrative['legal']['narrative'] is True
    assert any(e['from'] == f'post:{post.pk}' and e['to'] == node['id'] for e in narrative['edges'])


def test_media_is_counted_under_politics_but_automatic_mentions_are_not():
    figure = person(org())
    publisher = Source.objects.create(name='Redakcja', url='https://media.example')
    confirmed = article(publisher, 'Rozmowa z Anną Kowalską')
    automatic = article(publisher, 'Anna Kowalska zabrała głos')
    PublicFigureArticleReference.objects.create(public_figure=figure, article=confirmed,
                                                reference_kind='mentioned', verification_status='confirmed')
    normal = get(f'osoba:{figure.pk}', glebokosc='3', kategorie='polityka')
    expanded = get(f'osoba:{figure.pk}', glebokosc='3', kategorie='polityka', pokaz_niepowiazane='1')
    assert [n['id'] for n in normal['nodes'] if n['kind'] == 'media'] == [f'article:{confirmed.pk}']
    assert any(n['id'] == f'article:{automatic.pk}' and n['certainty'] == 'name_only' for n in expanded['nodes'])
    assert counts(normal)['polityka'] == counts(expanded)['polityka'] == 1


def test_category_date_and_depth_filters():
    company = org()
    figure = person(company)
    rec('fts', 'eu_grant', 'old', {'vat': company.nip}, 'Stara dotacja', date(2025, 1, 1))
    rec('fts', 'eu_grant', 'new', {'vat': company.nip}, 'Nowa dotacja', date(2026, 9, 1))
    rec('bzp', 'notice', 'new', {'organizationNationalId': company.nip}, 'Zamówienie', date(2026, 9, 1))
    data = get(f'osoba:{figure.pk}', kategorie='dotacje', od='2026-09-01', do='2026-09-01')
    assert [n['label'] for n in data['nodes'] if n['kind'] == 'grant'] == ['Nowa dotacja']
    assert not any(n['kind'] == 'contract' for n in data['nodes'])
    shallow = get(f'osoba:{figure.pk}', glebokosc='1')
    assert all(n['level'] <= 1 for n in shallow['nodes'])
    assert not any(n['kind'] in ('grant', 'contract') for n in shallow['nodes'])


def test_node_limits_group_overflow_without_dangling_edges():
    company = org()
    from news.public_records_models import PublicRecord
    PublicRecord.objects.bulk_create([PublicRecord(source='bzp', kind='notice', external_id=str(n),
        data={'organizationNationalId': company.nip}, title=f'Zamówienie {n}',
        source_url='https://example.org/', response_url='https://example.org/', response_sha256='0') for n in range(320)])
    data = get(f'spolka:{company.krs_number}')
    assert len(data['nodes']) == 300 and len(data['edges']) <= 600
    assert data['limits']['truncated'] is True
    assert sum(g['count'] for g in data['limits']['grouped']) == 21
    ids = {n['id'] for n in data['nodes']}
    assert all(e['from'] in ids and e['to'] in ids for e in data['edges'])


def test_edge_limit_is_independent_of_node_limit():
    graph = flow.Graph(flow.options({}))
    provenance = flow.source('krs')
    for number in range(30):
        graph.node(str(number), 'organisation', 'Podmiot', 0 if not number else 1, 'spolki', provenance, structural=True)
    for first in range(30):
        for second in range(30):
            graph.edge(str(first), str(second), 'powiązanie', provenance)
    data = graph.finish('0')
    assert len(data['edges']) == 600 and data['limits']['truncated']
    assert sum(g['count'] for g in data['limits']['grouped']) == 270


@pytest.mark.parametrize('ident', ['osoba:999999', 'spolka:9999999999', 'osoba:anonim', 'inne:123',
                                   'spolka:9999999999999999999999999'])
def test_missing_root_returns_detail(ident):
    response = APIClient().get(f'/api/przeszlosc/przeplyw/{ident}/')
    assert response.status_code == 404 and set(response.json()) == {'detail'}


@pytest.mark.parametrize('params', [{'glebokosc': '4'}, {'narracja': 'yes'}, {'kategorie': 'media'},
    {'od': '2026-13-01'}, {'od': '2026-10-01', 'do': '2026-09-01'}])
def test_invalid_parameters_return_400(params):
    company = org()
    assert APIClient().get(f'/api/przeszlosc/przeplyw/spolka:{company.krs_number}/', params).status_code == 400


def test_cache_reuses_response_and_separates_parameters():
    company = org()
    ident = f'spolka:{company.krs_number}'
    with patch.object(flow, 'build', wraps=flow.build) as build:
        first = get(ident)
        assert get(ident) == first and build.call_count == 1
        get(ident, narracja='1')
        get(ident, pokaz_niepowiazane='1')
        get(ident, glebokosc='1')
        get(ident, kategorie='dotacje')
        get(ident, od='2026-01-01')
        get(ident, do='2026-01-01')
        assert build.call_count == 7
    assert flow.CACHE_SECONDS == 86400


def test_source_has_no_broken_polish_literals():
    assert '??' not in Path(flow.__file__).read_text(encoding='utf-8')


def test_bulk_revocation_cannot_resurrect_cached_diagnosis_or_relation():
    company = org()
    figure = person(company)
    account = x_account(figure, 'anna', '7001')
    post = x_post(account, '9001', 'Wypowiedź')
    diagnosis = SpinDiagnosis.objects.create(post=post, status='approved', verdict='spin', intensity=30,
                                             headline='Ocena', diagnosed_at=timezone.now())
    ident = f'osoba:{figure.pk}'
    assert any(n['kind'] == 'diagnosis' for n in get(ident, narracja='1')['nodes'])
    SpinDiagnosis.objects.filter(pk=diagnosis.pk).update(hidden_at=timezone.now())
    assert not any(n['kind'] == 'diagnosis' for n in get(ident, narracja='1')['nodes'])
    PublicFigureOrganisationRelation.objects.filter(public_figure=figure).update(verification_status='rejected')
    assert not any(n['kind'] == 'organisation' for n in get(ident, narracja='1')['nodes'])


def test_local_midnight_date_filter():
    from datetime import datetime, timezone as dt_timezone
    from django.test import override_settings
    from news.political_models import PoliticalPost
    figure = mp('Anna Kowalska', 77)
    post = x_post(x_account(figure, 'anna', '7001'), '9001', 'Wieczorny wpis')
    PoliticalPost.objects.filter(pk=post.pk).update(published_at=datetime(2026, 10, 8, 22, 30, tzinfo=dt_timezone.utc))
    with override_settings(TIME_ZONE='Europe/Warsaw'):
        data = get(f'osoba:{figure.pk}', od='2026-10-09', do='2026-10-09')
    node = next(n for n in data['nodes'] if n['id'] == f'post:{post.pk}')
    assert node['date'] == '2026-10-09'


def test_joint_contract_does_not_assign_total_to_each_winner():
    first = org()
    second = org('Druga SA', '0000000003', '1234567890')
    figure = person(first)
    rel = PublicFigureOrganisationRelation(public_figure=figure, organisation=second,
        public_role='zarząd', evidence_url='https://example.org')
    rel.confirm_automatically('krs_register')
    rel.save()
    notice = rec('ted', 'notice', 'joint', {'buyer': ['Urząd'], 'value': 100, 'currency': 'PLN',
        'winners': [{'id': first.nip}, {'id': second.nip}]})
    data = get(f'osoba:{figure.pk}')
    outgoing = [e for e in data['edges'] if e['from'] == f'ted:{notice.pk}']
    assert len(outgoing) == 2 and all(e['amount'] is None for e in outgoing)


def test_depth_one_query_count_does_not_grow_with_companies():
    from time import perf_counter
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    figure = person(org())
    opts = flow.options({'glebokosc': '1', 'kategorie': 'spolki'})
    with CaptureQueriesContext(connection) as single:
        flow.build(figure, True, opts)
    for n in range(10, 30):
        company = org(f'Spółka {n}', f'{n:010d}', '')
        relation = PublicFigureOrganisationRelation(public_figure=figure, organisation=company,
            public_role='zarząd', evidence_url='https://example.org')
        relation.confirm_automatically('krs_register')
        relation.save()
    started = perf_counter()
    with CaptureQueriesContext(connection) as many:
        data = flow.build(figure, True, opts)
    elapsed = (perf_counter() - started) * 1000
    assert len(single) == len(many) == 1 and len(data['nodes']) == 22
    print(f'Głębokość 1, 21 spółek: {len(many)} SQL, {elapsed:.1f} ms (SQLite, build).')


def test_public_record_ballot_and_feature_gate(monkeypatch):
    figure = mp('Anna Kowalska', 77)
    from news.public_records_models import PublicRecordPerson
    ballot = rec('votes', 'ballot', 'one', {}, 'Głosowanie imienne', date(2026, 9, 1))
    PublicRecordPerson.objects.create(record=ballot, figure=figure, term=10, mp_id=77)
    assert any(n['kind'] == 'vote' for n in get(f'osoba:{figure.pk}')['nodes'])
    assert not any(n['kind'] == 'vote' for n in get(f'osoba:{figure.pk}', glebokosc='1')['nodes'])
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'false')
    assert APIClient().get(f'/api/przeszlosc/przeplyw/osoba:{figure.pk}/').status_code == 404


def test_depth_one_contains_authorities_and_defers_channels():
    company = org()
    rec('ted', 'notice', 'one', {'buyer': ['Gmina'], 'winners': [{'id': company.nip}], 'value': 100})
    data = get(f'spolka:{company.krs_number}', glebokosc='1')
    assert {n['kind'] for n in data['nodes']} == {'organisation', 'authority'}
    edge = data['edges'][0]
    assert edge['from'].startswith('authority:') and edge['to'] == data['root']['id']
    assert edge['amount'] is None


def test_many_identifiers_use_batched_union_without_duplicate_contracts():
    from time import perf_counter
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    figure = mp('Anna Kowalska', 77)
    companies = []
    for n in range(40):
        company = org(f'Podmiot {n}', f'{100 + n:010d}', f'{1000000000 + n}', '')
        companies.append(company)
        rel = PublicFigureOrganisationRelation(public_figure=figure, organisation=company,
            public_role='zarząd', evidence_url='https://example.org')
        rel.confirm_automatically('krs_register')
        rel.save()
    rec('ted', 'notice', 'joint', {'buyer': ['Gmina'], 'winners': [
        {'id': companies[0].nip}, {'id': companies[-1].krs_number}], 'value': 100})
    deep = get(f'osoba:{figure.pk}', kategorie='spolki,zamowienia')
    assert len([n for n in deep['nodes'] if n['kind'] == 'contract']) == 1
    cache.clear()
    started = perf_counter()
    with CaptureQueriesContext(connection) as queries:
        get(f'osoba:{figure.pk}', glebokosc='1', kategorie='spolki,zamowienia')
    print(f'API stopień 1, 40 spółek i TED: {len(queries)} SQL, {(perf_counter() - started) * 1000:.1f} ms.')
