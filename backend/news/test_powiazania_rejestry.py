import pytest

from news import powiazania_rejestry as pr
from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation
from news.public_records_models import PublicRecord


def test_identifiers_extract_nip_and_krs_only():
    nips, krs = pr.identifiers('Firma X, NIP: 123-456-32-18, KRS 0000123456, REGON 1234')
    assert nips == {'1234563218'} and krs == {'0000123456'}
    assert pr.identifiers('brak numerów') == (set(), set())


@pytest.mark.django_db
def test_report_matches_by_number_never_by_name():
    org = RegisteredOrganisation.objects.create(name='Lobby Sp. z o.o.', krs_number='0000123456', kind='company', nip='1234563218')
    RegisteredOrganisation.objects.create(name='Inna', krs_number='0000999999', kind='company', nip='')
    fig = PublicFigure.objects.create(canonical_name='Jan Testowy')
    PublicFigureOrganisationRelation.objects.create(public_figure=fig, organisation=org, public_role='członek zarządu', evidence_url='https://x.pl')
    PublicRecord.objects.create(source='lobby_mswia', kind='lobby_entity', external_id='00001', source_url='https://gov.pl/r.pdf',
                                response_sha256='a', response_url='https://gov.pl/r.pdf', text='Lobby Sp. z o.o. NIP 123-456-32-18')
    PublicRecord.objects.create(source='lobby_mswia', kind='lobby_entity', external_id='00002', source_url='https://gov.pl/r.pdf',
                                response_sha256='b', response_url='https://gov.pl/r.pdf', text='Inna sp. z o.o. bez numerów')
    r = pr.lobbying_report()
    assert (r['entries'], r['with_ids'], r['matched_orgs']) == (2, 1, 1)
    assert [x['figure'] for x in r['rows']] == ['Jan Testowy'] and r['rows'][0]['lobby_entry'] == '00001'


@pytest.mark.django_db
def test_diagnosis_counts_words_and_recognised_numbers():
    base = dict(source='lobby_mswia', kind='lobby_entity', source_url='https://gov.pl/r.pdf', response_sha256='a', response_url='https://gov.pl/r.pdf')
    PublicRecord.objects.create(external_id='1', text='Firma NIP 123-456-32-18', **base)
    PublicRecord.objects.create(external_id='2', text='Firma NIP w osobnej linii', **base)
    PublicRecord.objects.create(external_id='3', text='Jan Kowalski, ul. Prosta 1', **base)
    d = pr.diagnosis()
    assert d['counts']['entries'] == 3 and d['counts']['nip_ok'] == 1 and d['counts']['word_but_no_number'] == 1
    assert d['word_but_no_number'][0][0] == '2' and d['no_words'][0][0] == '3'
