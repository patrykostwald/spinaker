"""Profil osoby i temat: bloki z nowych otwartych źródeł (raport źródeł 6.10). Bez sieci."""
import pytest

from news.political_models import ParliamentaryRosterEntry, PublicFigure
from news.public_records_models import PublicRecord, PublicRecordPerson
from news.zrodla_profil import open_data
from scraper.public_records import EP_TERM

pytestmark = pytest.mark.django_db


def rec(source, kind, key, data, title='x', **extra):
    return PublicRecord.objects.create(source=source, kind=kind, external_id=key, data=data, title=title,
                                       source_url='https://example.org/' + key, response_url='https://example.org/', response_sha256='0', **extra)


def test_open_data_blocks_for_mep_with_attribution():
    entry = ParliamentaryRosterEntry.objects.create(source='ep', external_id='197490', full_name='Magdalena Adamowicz',
                                                    source_url='https://www.europarl.europa.eu/meps/pl/full-list/xml')
    mep = PublicFigure.objects.create(canonical_name='Magdalena Adamowicz', role_category='european', role_title='Posłanka do PE',
                                      evidence_url='https://www.europarl.europa.eu/', parliamentary_roster_entry=entry)
    vote = rec('howtheyvote', 'ep_vote', '1', {'votes': [{'ep_id': 197490, 'position': 'AGAINST'}], 'polish': {'AGAINST': 1}},
               title='Nadzór budżetowy')
    PublicRecordPerson.objects.create(record=vote, term=EP_TERM, mp_id=197490)
    income = rec('integrity_watch', 'mep_income', '197490', {'total_eur': 12000, 'paid_activities': 1,
                                                             'activities': [{'activity': 'Wykłady', 'total_eur': 12000}]})
    PublicRecordPerson.objects.create(record=income, term=EP_TERM, mp_id=197490)
    person = rec('wikidata', 'person', 'Q555', {'wikipedia': 'https://pl.wikipedia.org/wiki/X', 'x_hints': ['tajne'],
                                                'parties': [{'name': 'Partia', 'start': '2010-01-01'}]})
    PublicRecordPerson.objects.create(record=person, term=EP_TERM, mp_id=197490, figure=mep)
    data = open_data(mep, [])
    assert data['ep_votes']['results'][0]['position'] == 'przeciw'
    assert data['ep_integrity']['income']['total_eur'] == 12000
    assert data['identity']['parties'][0]['name'] == 'Partia'
    assert 'tajne' not in str(data)  # wskazówki kont X nie są publiczne
    licenses = {s['key']: s['license'] for s in data['sources']}
    assert licenses == {'howtheyvote': 'ODbL 1.0', 'integrity_watch': 'ODbL 1.0', 'wikidata': 'CC0 1.0'}


def test_topic_eu_funds_and_org_edge(settings):
    from news.political_models import RegisteredOrganisation
    from news.przeszlosc import eu_funds, topic_graph
    org = RegisteredOrganisation.objects.create(name='Port Lotniczy SA', krs_number='0000000002', kind='company',
                                                official_register_url='https://ekrs.ms.gov.pl/')
    rec('kohesio', 'eu_project', 'Q1', {'beneficiary': 'Port Lotniczy SA', 'project': 'Rozbudowa terminalu lotniska',
                                        'eu_budget': 1000.0, 'organisation_id': org.pk, 'krs': '0000000002'},
        title='Rozbudowa terminalu lotniska - Port Lotniczy SA')
    funds = eu_funds('terminal lotniska')
    assert funds['results'][0]['amount_eur'] == 1000.0 and funds['sources'][0]['license'] == 'CC0 1.0'
    graph = topic_graph('terminal lotniska')
    assert any(e['label'] == 'dotacja UE' and e['source'] == f'org:{org.pk}' for e in graph['edges'])
