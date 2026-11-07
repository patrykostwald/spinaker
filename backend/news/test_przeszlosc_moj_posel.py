import pytest
from rest_framework.test import APIClient

from news.political_models import ParliamentaryRosterEntry, PublicFigure


def entry(ext, name, club, district, active=True, source='sejm'):
    return ParliamentaryRosterEntry.objects.create(source=source, external_id=ext, full_name=name, club=club, district=district,
                                                   profile_url=f'https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id={ext}',
                                                   source_url='https://api.sejm.gov.pl/sejm/term10/MP', term=10, active=active)


@pytest.fixture
def roster(db):
    a = entry('1', 'Jan Kowalski', 'KO', 'Kraków')
    entry('2', 'Anna Nowak', 'PiS', 'Kraków')
    entry('3', 'Piotr Zieliński', 'PSL', 'Warszawa')
    entry('4', 'Były Poseł', 'KO', 'Kraków', active=False)
    entry('5', 'Europoseł Testowy', 'EPP', 'Kraków', source='ep')
    entry('6', 'Bez Okręgu', 'KO', '')
    figure = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='sejm', role_title='Poseł na Sejm RP',
                                         parliamentary_roster_entry=a)
    return figure


def test_disabled_and_districts_list(roster, monkeypatch):
    client = APIClient()
    monkeypatch.delenv('PRZESZLOSC_ENABLED', raising=False)
    assert client.get('/api/przeszlosc/moj-posel/').status_code == 404
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    body = client.get('/api/przeszlosc/moj-posel/').json()
    assert body['districts'] == [{'name': 'Kraków', 'mps': 2}, {'name': 'Warszawa', 'mps': 1}]   # tylko aktywni posłowie Sejmu z okręgiem


def test_district_members_with_profile_links_and_missing_figures(roster, monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    client = APIClient()
    body = client.get('/api/przeszlosc/moj-posel/?okreg=krak%C3%B3w').json()   # bez względu na wielkość liter
    assert body['district'] == 'Kraków' and body['total'] == 2
    by_name = {m['name']: m for m in body['members']}
    assert by_name['Jan Kowalski']['slug'] == f'{roster.pk}-jan-kowalski' and by_name['Jan Kowalski']['club'] == 'KO'
    assert by_name['Anna Nowak']['slug'] is None and by_name['Anna Nowak']['sejm_url'].startswith('https://www.sejm.gov.pl/')
    assert client.get('/api/przeszlosc/moj-posel/?okreg=Atlantyda').status_code == 404
