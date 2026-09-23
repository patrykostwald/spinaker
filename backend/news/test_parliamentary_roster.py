import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.parliamentary_roster import EP_CURRENT_URL, SENAT_URL, SEJM_URL, ep_rows, get_rows, senat_rows, sejm_rows
from news.political_models import ParliamentaryRosterEntry, PoliticalAccountCandidate

pytestmark = pytest.mark.django_db


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f'{self.status_code}')
    def json(self): return self.payload


class HtmlResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f'{self.status_code}')


def official_sejm_payload(*, current=440):
    rows = [
        {'id': number, 'firstLastName': f'Aktywny Poseł {number}', 'active': True,
         'club': 'Klub A', 'districtName': 'Warszawa'}
        for number in range(1, current + 1)
    ]
    rows[0]['firstLastName'] = 'Aktywna Posłanka'
    return rows + [{'id': 999, 'firstLastName': 'Były Poseł', 'active': False, 'club': 'Klub B'}]


def official_senat_html(*, current=51, include_inactive=True, term='11'):
    cards = []
    for number in range(current):
        identifier = 900 + number
        cards.append(
            f'<article><a href="/sklad/senatorowie/senator,{identifier},{term},osoba-{number}.html">'
            f'Senator {number}</a><p>Okręg wyborczy nr {number}</p></article>'
        )
    if include_inactive:
        cards.append(
            '<article><a href="/sklad/senatorowie/senator,999,11,byly.html">Były Senator</a>'
            '<p>Mandat wygasł 1.01.2025 r.</p></article>'
        )
    return '<main>' + ''.join(cards) + '</main>'


def official_ep_payload():
    # Official JSON-LD shape from /meps/show-current.
    return {'data': [
        {'id': 'person/257073', 'type': 'Person', 'identifier': '257073',
         'label': 'Tobiasz BOCHEŃSKI', 'givenName': 'Tobiasz', 'familyName': 'Bocheński',
         'api:country-of-representation': 'PL', 'api:political-group': 'ECR'},
        {'id': 'person/99945', 'type': 'Person', 'identifier': '99945',
         'label': 'Lena DÜPONT', 'api:country-of-representation': 'DE', 'api:political-group': 'PPE'},
    ]}


def test_sejm_adapter_imports_only_active_and_profiles():
    rows = sejm_rows(http_get=lambda url, **kwargs: Response(official_sejm_payload()))
    assert len(rows) == 440
    assert rows[0].external_id == '1'
    assert rows[0].full_name == 'Aktywna Posłanka'
    assert rows[0].profile_url.endswith('id=1')
    assert rows[0].source_url == SEJM_URL
    assert rows[0].term == 10


def test_sejm_adapter_fails_closed_on_partial_roster():
    with pytest.raises(CommandError, match='oczekiwano'):
        sejm_rows(http_get=lambda url, **kwargs: Response(official_sejm_payload(current=439)))


def test_senat_adapter_stages_current_profiles_and_skips_expired_mandates():
    rows = senat_rows(http_get=lambda url, **kwargs: HtmlResponse(official_senat_html()))
    assert len(rows) == 51
    assert rows[0].external_id == '900'
    assert rows[0].full_name == 'Senator 0'
    assert rows[0].profile_url == 'https://www.senat.gov.pl/sklad/senatorowie/senator,900,11,osoba-0.html'
    assert rows[0].source_url == SENAT_URL


def test_senat_adapter_fails_closed_on_empty_mixed_term_or_small_roster():
    with pytest.raises(CommandError, match='nie zawiera rozpoznawalnych'):
        senat_rows(http_get=lambda url, **kwargs: HtmlResponse('<main>brak</main>'))
    with pytest.raises(CommandError, match='tylko'):
        senat_rows(http_get=lambda url, **kwargs: HtmlResponse(official_senat_html(current=2, include_inactive=False)))
    mixed = official_senat_html(current=51) + '<a href="/sklad/senatorowie/senator,1234,12,inna.html">Inna</a>'
    with pytest.raises(CommandError, match='więcej niż jednej kadencji'):
        senat_rows(http_get=lambda url, **kwargs: HtmlResponse(mixed))


def test_ep_adapter_stages_only_polish_current_meps_and_group():
    seen = {}

    def fetch(url, **kwargs):
        seen.update(url=url, headers=kwargs['headers'])
        return Response(official_ep_payload())

    rows = ep_rows(http_get=fetch)
    assert len(rows) == 1
    assert rows[0].external_id == '257073'
    assert rows[0].full_name == 'Tobiasz BOCHEŃSKI'
    assert rows[0].club == 'ECR'
    assert rows[0].district == 'PL'
    assert rows[0].profile_url.endswith('/257073')
    assert rows[0].source_url == EP_CURRENT_URL
    assert seen == {'url': EP_CURRENT_URL, 'headers': {'Accept': 'application/ld+json'}}


def test_ep_adapter_refuses_empty_or_incomplete_polish_response():
    with pytest.raises(CommandError, match='nie zwróciło aktywnych'):
        ep_rows(http_get=lambda url, **kwargs: Response({'data': []}))
    with pytest.raises(CommandError, match='bez identifier lub label'):
        ep_rows(http_get=lambda url, **kwargs: Response({'data': [
            {'api:country-of-representation': 'PL', 'label': 'Brak identyfikatora'},
        ]}))


def test_command_dry_run_never_writes_or_creates_x_leads(monkeypatch, capsys):
    candidate_count = PoliticalAccountCandidate.objects.count()
    monkeypatch.setattr('news.management.commands.sync_parliamentary_roster.get_rows',
        lambda source: sejm_rows(http_get=lambda url, **kwargs: Response(official_sejm_payload())))
    call_command('sync_parliamentary_roster', source='sejm', dry_run=True)
    assert not ParliamentaryRosterEntry.objects.exists()
    assert PoliticalAccountCandidate.objects.count() == candidate_count
    assert 'Bez zapisu' in capsys.readouterr().out


def test_command_upserts_and_only_marks_absent_inactive(monkeypatch):
    candidate_count = PoliticalAccountCandidate.objects.count()
    monkeypatch.setattr('news.management.commands.sync_parliamentary_roster.get_rows',
        lambda source: sejm_rows(http_get=lambda url, **kwargs: Response(official_sejm_payload())))
    call_command('sync_parliamentary_roster', source='sejm')
    entry = ParliamentaryRosterEntry.objects.get(source='sejm', external_id='1')
    assert entry.active
    entry.full_name = 'Stara nazwa'; entry.save()
    stale = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='441', full_name='Stara osoba', source_url=SEJM_URL)
    call_command('sync_parliamentary_roster', source='sejm')
    entry.refresh_from_db(); stale.refresh_from_db()
    assert entry.full_name == 'Aktywna Posłanka'
    assert stale.active is False
    assert PoliticalAccountCandidate.objects.count() == candidate_count


def test_empty_roster_refuses_to_change_active_entries(monkeypatch):
    entry = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='1', full_name='Zostaje aktywna', source_url=SEJM_URL)
    monkeypatch.setattr('news.management.commands.sync_parliamentary_roster.get_rows', lambda source: [])
    with pytest.raises(CommandError, match='nie zwróciło aktywnych'):
        call_command('sync_parliamentary_roster', source='sejm')
    entry.refresh_from_db()
    assert entry.active
