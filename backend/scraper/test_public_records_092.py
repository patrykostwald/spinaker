"""092: procesy legislacyjne, komisje, biuletyn KRS, TED, rejestr przejrzystości UE. Bez sieci."""
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from news.models import Article, OfficialRecord, Source
from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicRecord, PublicRecordPerson, PublicCollectionState
from scraper import public_records as collectors
from scraper import public_record_parsers as parsers
from scraper.access_gate import AccessDenied

FIXTURES = Path(__file__).parent / 'fixtures' / 'public_records'
DATA = json.loads((FIXTURES / 'sources_092.json').read_text(encoding='utf-8'))
NEW = ('processes', 'committees', 'krs_changes', 'ted', 'eu_transparency')
pytestmark = pytest.mark.django_db


def body(name, value=None):
    return json.dumps(DATA[name] if value is None else value, ensure_ascii=False).encode()


def job(source, kind, url, context=None):
    state, _ = PublicCollectionState.objects.get_or_create(source=source)
    return collectors.enqueue(state, url, kind, context)[0]


def handle(j, raw):
    with transaction.atomic():
        collectors.handle(j, raw)


def official(external_id):
    source, _ = Source.objects.get_or_create(url='https://api.sejm.gov.pl', defaults={'name': 'Sejm'})
    article = Article.objects.create(source=source, title=external_id, url='https://api.sejm.gov.pl/' + external_id,
                                     published_date=timezone.now())
    return OfficialRecord.objects.create(article=article, provider='sejm', external_id=external_id,
                                         api_url=article.url, raw_data={})


@pytest.mark.parametrize('source', NEW)
def test_new_flags_off_mean_no_run_and_no_jobs(source, monkeypatch):
    monkeypatch.setenv(collectors.SOURCES[source].flag(source), 'false')
    with patch.object(collectors, 'fetch_feed') as transport, patch.object(collectors, 'transparency_download') as download:
        assert collectors.collect(source)['status'] == 'disabled'
    transport.assert_not_called()
    download.assert_not_called()
    assert not PublicCollectionState.objects.filter(source=source, jobs__isnull=False).exists()


def test_flag_names_are_explicit():
    assert [collectors.SOURCES[s].flag(s) for s in NEW] == [
        'PUBLIC_RECORDS_PROCESSES_ENABLED', 'PUBLIC_RECORDS_COMMITTEES_ENABLED', 'PUBLIC_RECORDS_KRS_CHANGES_ENABLED',
        'PUBLIC_RECORDS_TED_ENABLED', 'PUBLIC_RECORDS_EU_TRANSPARENCY_ENABLED']


# --- procesy legislacyjne ------------------------------------------------------------------------------

def test_process_index_pages_and_detail_jobs():
    j = job('processes', 'process_index', collectors.SEJM + '/processes?offset=0&limit=20',
            {'filters': {'modifiedSince': '2023-11-13T00:00:00', 'sort': 'lastModif'}, 'offset': 0})
    handle(j, body('process_index'))
    details = sorted(j.state.jobs.filter(kind='process').values_list('url', flat=True))
    assert details == [collectors.SEJM + '/processes/1', collectors.SEJM + '/processes/18073-z']
    nxt = j.state.jobs.get(kind='process_index', done=False, pk__gt=j.pk)
    assert 'offset=2' in nxt.url and 'sort=lastModif' in nxt.url
    with pytest.raises(ValueError, match='term_mismatch'):
        handle(nxt, body('process_index', [{**DATA['process_index'][0], 'term': 9}]))


def test_process_parser_flattens_stages_prints_and_votings():
    data = parsers.process(DATA['process'], 10)
    assert data['prints'] == ['1', '2']
    assert [s['stageName'] for s in data['stages']][:3] == [
        'Projekt wpłynął do Sejmu', 'Skierowano do I czytania na posiedzeniu Sejmu', 'Skierowanie']
    assert data['votings'][0]['key'] == '10/1/2' and data['votings'][0]['yes'] == 458
    assert data['votings'][0]['stage'] == 'I czytanie na posiedzeniu Sejmu'
    with pytest.raises(ValueError, match='identity'):
        parsers.process({**DATA['process'], 'term': 9}, 10)


def test_process_upsert_is_idempotent_and_links_prints_and_votes():
    official('print/10/1')
    official('print/10/2')
    official('vote/10/1/2')
    j = job('processes', 'process', collectors.SEJM + '/processes/1', {'number': '1'})
    handle(j, body('process'))
    handle(j, body('process'))
    record = PublicRecord.objects.get(source='processes')
    assert record.external_id == '10/1' and record.kind == 'process' and record.term == 10
    assert record.official_print.external_id == 'print/10/1'
    assert sorted(record.data['linked_prints']) == ['print/10/1', 'print/10/2']
    assert record.data['linked_votings'] == ['10/1/2']
    assert str(record.date) == '2023-11-13'
    with pytest.raises(ValueError, match='identity'):
        handle(job('processes', 'process', collectors.SEJM + '/processes/7', {'number': '7'}), body('process'))


# --- komisje i posiedzenia -------------------------------------------------------------------------------

def test_committees_store_members_as_mp_ids_and_queue_sittings():
    j = job('committees', 'committee_index', collectors.SEJM + '/committees', {'since': '2024-01-01'})
    handle(j, body('committees'))
    handle(j, body('committees'))
    record = PublicRecord.objects.get(source='committees', kind='committee')
    assert record.external_id == '10/ASW' and record.data['members'][0]['function'] == 'przewodniczący'
    assert sorted(PublicRecordPerson.objects.filter(record=record).values_list('mp_id', flat=True)) == [1, 2]
    sittings = j.state.jobs.get(kind='committee_sittings')
    assert sittings.url == collectors.SEJM + '/committees/ASW/sittings'
    assert sittings.context['since'] == '2024-01-01'


def test_committee_sittings_window_agenda_prints_and_idempotency():
    official('print/10/123')
    j = job('committees', 'committee_sittings', collectors.SEJM + '/committees/ASW/sittings',
            {'since': '2024-01-01', 'code': 'ASW', 'name': 'Komisja Administracji i Spraw Wewnętrznych'})
    handle(j, body('committee_sittings'))
    handle(j, body('committee_sittings'))
    record = PublicRecord.objects.get(source='committees', kind='committee_sitting')  # nr 1 jest przed oknem
    assert record.external_id == '10/ASW/42'
    assert record.data['prints'] == ['123', '1', '2'] and record.data['linked_prints'] == ['print/10/123']
    assert '<p>' not in record.text and 'druk nr 123' in record.text
    assert record.data['jointWith'] == [{'code': 'SPC', 'num': 7}]
    assert record.title.endswith('posiedzenie nr 42')
    with pytest.raises(ValueError, match='identity'):
        parsers.committee_sitting({**DATA['committee_sittings'][0], 'code': 'XYZ'}, 'ASW')


# --- biuletyn KRS ------------------------------------------------------------------------------------------

def organisation(krs='0000123456', register='P'):
    return RegisteredOrganisation.objects.create(name='Testowa Spółka S.A.', krs_number=krs, kind='company',
        register=register, official_register_url='https://prs.ms.gov.pl/krs/' + krs)


def test_krs_seed_needs_tracked_entities(monkeypatch):
    state, _ = PublicCollectionState.objects.get_or_create(source='krs_changes')
    collectors.seed(state, timezone.localdate() - timedelta(days=2))
    assert not state.jobs.exists()
    organisation()
    collectors.seed(state, timezone.localdate() - timedelta(days=40))
    days = list(state.jobs.values_list('context__day', flat=True))
    assert len(days) == 15  # Nigdy więcej niż dwa tygodnie biuletynów naraz.
    assert all(url.startswith(collectors.KRS_API + '/Biuletyn/') for url in state.jobs.values_list('url', flat=True))


def test_krs_bulletin_only_tracked_entities_and_counts_entries():
    org = organisation()
    organisation('0000999999')  # obserwowana, ale bez zmian tego dnia
    j = job('krs_changes', 'krs_bulletin', collectors.KRS_API + '/Biuletyn/2026-10-05', {'day': '2026-10-05'})
    handle(j, body('krs_bulletin'))
    handle(j, body('krs_bulletin'))
    entry = PublicRecord.objects.get(source='krs_changes', kind='krs_bulletin_entry')
    assert entry.external_id == '0000123456/2026-10-05' and entry.data['entries'] == 2
    assert entry.data['organisation_id'] == org.pk
    extract = j.state.jobs.get(kind='krs_extract')
    assert extract.url == collectors.KRS_API + '/OdpisAktualny/0000123456?rejestr=P&format=json'
    with pytest.raises(ValueError, match='krs_bulletin_shape'):
        parsers.krs_bulletin(['12a'])


def test_krs_extract_keeps_header_only_and_no_person_data():
    org = organisation()
    j = job('krs_changes', 'krs_extract', collectors.KRS_API + '/OdpisAktualny/0000123456?rejestr=P&format=json',
            {'krs': '0000123456', 'day': '2026-10-05', 'organisation_id': org.pk})
    handle(j, body('krs_extract'))
    handle(j, body('krs_extract'))
    record = PublicRecord.objects.get(source='krs_changes', kind='krs_change')
    assert record.external_id == '0000123456/49' and str(record.date) == '2026-10-05'
    assert record.data['case_reference'] == 'WA.XII NS-REJ.KRS/1/26/1' and record.title == 'TESTOWA SPÓŁKA S.A.'
    stored = json.dumps(record.data, ensure_ascii=False) + record.text
    assert 'PREZES' not in stored and 'K*******' not in stored and 'pesel' not in stored
    with pytest.raises(ValueError, match='identity'):
        parsers.krs_header(DATA['krs_extract'], '0000000001')


# --- TED --------------------------------------------------------------------------------------------------

def test_ted_seed_is_post_with_polish_buyers_and_recent_window(monkeypatch):
    state, _ = PublicCollectionState.objects.get_or_create(source='ted')
    collectors.seed(state, timezone.localdate() - timedelta(days=14))
    j = state.jobs.get()
    assert j.url == collectors.TED_SEARCH and j.kind == 'ted_page'
    assert j.context['body']['query'].startswith('buyer-country=POL AND publication-date>=')
    assert 'winner-name' in j.context['body']['fields']


def test_ted_notices_upsert_and_page_identity():
    j = job('ted', 'ted_page', collectors.TED_SEARCH, {'body': {'query': 'q', 'limit': 2, 'page': 1}})
    payload = {**DATA['ted_page'], 'totalNoticeCount': 5}
    handle(j, body('ted_page', payload))
    handle(j, body('ted_page', payload))
    assert PublicRecord.objects.filter(source='ted', kind='notice').count() == 2
    award = PublicRecord.objects.get(source='ted', external_id='674307-2026')
    assert award.data['buyer'] == ['Sąd Apelacyjny Testowy'] and award.data['value'] == 6133530.3
    assert award.data['cpv'] == ['30200000', '30213100'] and award.data['currency'] == 'PLN'
    assert [w['name'] for w in award.data['winners']] == ['Firma A Sp. z o.o.', 'Firma B Sp. z o.o.']
    assert not any(w['osoba_fizyczna'] for w in award.data['winners'])
    assert award.title.startswith('Polska') and award.source_url.endswith('/674307-2026')
    pages = list(j.state.jobs.filter(kind='ted_page').order_by('pk'))
    assert len(pages) == 2 and pages[1].context['body']['page'] == 2 and pages[0].identity != pages[1].identity
    handle(pages[1], body('ted_page', {**payload, 'notices': DATA['ted_page']['notices'][:1]}))
    assert j.state.jobs.filter(kind='ted_page').count() == 2  # Krótsza strona kończy stronicowanie.
    with pytest.raises(ValueError, match='ted_response_shape'):
        handle(pages[1], b'{"error": "x"}')


def test_ted_fetch_uses_post_body(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_TED_ENABLED', 'true')
    j = job('ted', 'ted_page', collectors.TED_SEARCH, {'body': {'query': 'q', 'limit': 2, 'page': 1}})
    j.state.lease_token, j.state.lease_until = 't', timezone.now() + timedelta(minutes=5)
    j.state.save()
    card = Mock(minimum_interval_seconds=3, channel='api')
    monkeypatch.setattr(collectors, 'source_access', Mock(return_value=(Mock(), card)))
    with patch.object(collectors, 'fetch_feed', return_value=(b'{}', None)) as transport:
        collectors.fetch(j, 't')
    kwargs = transport.call_args.kwargs
    assert kwargs['method'] == 'POST' and json.loads(kwargs['body'])['page'] == 1
    assert kwargs['request_headers']['Content-Type'] == 'application/json'


# --- rejestr przejrzystości UE ------------------------------------------------------------------------------

def chunks(raw, size=97):
    return [raw[i:i + size] for i in range(0, len(raw), size)]


def test_transparency_stream_filters_polish_and_drops_people_and_phones():
    raw = (FIXTURES / 'transparency.xml').read_bytes()
    rows = parsers.transparency_polish(chunks(raw))  # małe kawałki: odwołania znakowe rozcięte między nimi
    assert [r['id'] for r in rows] == ['405662547431-63', '123456789012-34']
    first = rows[0]
    assert first['match'] == 'siedziba' and rows[1]['match'] == 'wzmianka'
    assert first['goals'] == 'Doradztwoprawne w sprawach podatkowych.'
    assert first['finance']['cost_max'] == '24999' and first['finance']['grants'][0]['amount'] == '82484'
    assert first['finance']['clients'] == ['Klient Testowy S.A.'] and first['finance']['contributors'] == 1
    stored = json.dumps(rows, ensure_ascii=False)
    assert 'Kowalski' not in stored and '220000000' not in stored and 'Testowa 1' not in stored


def test_transparency_rejects_entities_and_empty_exports():
    with pytest.raises(ValueError, match='unsafe_xml'):
        parsers.transparency_polish([b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>'])
    with pytest.raises(ValueError, match='empty'):
        parsers.transparency_polish([b'<?xml version="1.0"?><x></x>'])
    with pytest.raises(ValueError, match='too large'):
        parsers.transparency_polish([b'x' * 10], max_bytes=5)


def test_transparency_upsert_idempotent_and_marks_absent():
    raw = (FIXTURES / 'transparency.xml').read_bytes()
    rows = parsers.transparency_polish([raw])
    j = job('eu_transparency', 'tr_export', collectors.TR_EXPORT, {'since': '1970-01-01'})
    handle(j, json.dumps(rows).encode())
    handle(j, json.dumps(rows).encode())
    assert PublicRecord.objects.filter(source='eu_transparency', kind='organisation').count() == 2
    handle(j, json.dumps(rows[:1]).encode())
    gone = PublicRecord.objects.get(source='eu_transparency', external_id='123456789012-34')
    assert gone.data['status'] == 'brak_w_eksporcie'
    handle(j, json.dumps(rows).encode())
    gone.refresh_from_db()
    assert 'status' not in gone.data


def test_transparency_collect_one_tick_via_stream(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_EU_TRANSPARENCY_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())
    rows = parsers.transparency_polish([(FIXTURES / 'transparency.xml').read_bytes()])
    with patch.object(collectors, 'fetch', return_value=(json.dumps(rows).encode(), None)) as fetch:
        result = collectors.collect('eu_transparency', max_requests=1)
        assert result['status'] == 'ok' and fetch.call_count == 1
        assert collectors.collect('eu_transparency')['status'] == 'idle'  # raz w tygodniu
    assert PublicRecord.objects.filter(source='eu_transparency').count() == 2


# --- dostęp, karty i harmonogram -----------------------------------------------------------------------------

@pytest.mark.parametrize('source,kind,url', [
    ('krs_changes', 'krs_bulletin', 'https://api-krs.ms.gov.pl/api/krs/Biuletyn/2026-10-05'),
    ('ted', 'ted_page', collectors.TED_SEARCH),
    ('eu_transparency', 'tr_export', collectors.TR_EXPORT),
])
def test_external_sources_need_their_own_card(source, kind, url):
    j = job(source, kind, url, {'body': {'page': 1}} if kind == 'ted_page' else {'day': '2026-10-05'})
    with pytest.raises(AccessDenied, match='no_approved_instruction'):
        collectors.source_access(j)
    j.url = collectors.SEJM + '/votings/1/2'  # nie pożycza karty Sejmu
    with pytest.raises(AccessDenied, match='out_of_scope'):
        collectors.source_access(j)


@pytest.mark.parametrize('source,url', [
    ('processes', collectors.SEJM + '/processes/18073-z'),
    ('committees', collectors.SEJM + '/committees/ASW/sittings'),
    ('krs_changes', collectors.KRS_API + '/OdpisAktualny/0000123456?rejestr=P&format=json'),
    ('ted', collectors.TED_SEARCH),
    ('eu_transparency', collectors.TR_EXPORT),
])
def test_configure_cards_authorise_exact_endpoints(source, url):
    call_command('configure_public_records', source=source, apply=True, reviewed_by='fixture',
                 evidence_url='https://example.org/docs', terms_url='https://example.org/terms', stdout=StringIO())
    j = job(source, 'x', url, {'body': {}} if source == 'ted' else {})
    _, card = collectors.source_access(j)
    assert card.allowed_scope == 'metadata'


def test_new_sources_are_scheduled_and_registered():
    from config.celery import app
    from news.agent_registry import REGISTRY
    from scraper import tasks
    from scraper.harvester_coverage import DIRECT_SCHEDULES
    for source in NEW:
        task = 'scraper.tasks.collect_public_' + source
        assert app.conf.beat_schedule['public-records-' + source]['task'] == task
        assert REGISTRY['public-records-' + source]['flag'] == collectors.SOURCES[source].flag(source)
        assert getattr(tasks, 'collect_public_' + source).name == task
    for root in ('https://api-krs.ms.gov.pl', 'https://api.ted.europa.eu', 'https://ec.europa.eu/transparencyregister'):
        assert root in DIRECT_SCHEDULES


def test_first_cycle_windows(monkeypatch):
    for source, days in (('ted', 14), ('krs_changes', 3)):
        monkeypatch.setenv(collectors.SOURCES[source].flag(source), 'true')
        with patch.object(collectors, 'fetch', side_effect=collectors.HostRateLimited(100)):
            collectors.collect(source, max_requests=1)
        state = PublicCollectionState.objects.get(source=source)
        assert state.since == timezone.localdate() - timedelta(days=days)


def test_ted_natural_person_winner_kept_only_in_notice_without_nip():
    """LEGAL: wykonawca bez formy prawnej to osoba fizyczna prowadząca działalność - tylko nazwa w ogłoszeniu, bez NIP."""
    row = {**DATA['ted_page']['notices'][0], 'winner-name': {'pol': ['Usługi Remontowe Jan Kowalski', 'Budimex S.A.']},
           'winner-identifier': ['5260000000', '5260250995']}
    data = parsers.ted_notice(row)
    person, company = data['winners']
    assert person == {'name': 'Usługi Remontowe Jan Kowalski', 'osoba_fizyczna': True, 'label': 'wykonawca - osoba fizyczna prowadząca działalność'}
    assert company == {'name': 'Budimex S.A.', 'osoba_fizyczna': False, 'id': '5260250995'}
    assert '5260000000' not in json.dumps(data) and 'winner_ids' not in data
    # niejednoznaczne przypisanie identyfikatorów: żadnego nie zapisujemy
    data = parsers.ted_notice({**row, 'winner-identifier': ['5260000000']})
    assert all('id' not in w for w in data['winners'])
    # nie trafia do wyszukiwania ani do osób: tytuł i tekst rekordu to przedmiot i zamawiający
    j = job('ted', 'ted_page', collectors.TED_SEARCH, {'body': {'query': 'q', 'limit': 50, 'page': 1}})
    handle(j, body('ted_page', {'notices': [row], 'totalNoticeCount': 1}))
    record = PublicRecord.objects.get(source='ted', external_id=row['publication-number'])
    assert 'Kowalski' not in record.title and 'Kowalski' not in record.text and not record.people.exists()


@pytest.mark.parametrize('name,natural', [('Jan Kowalski', True), ('Kowalski i Nowak s.c.', True), ('PHU Marek Nowak', True),
    ('Firma Sp. z o.o.', False), ('ABC S.A.', False), ('Spółka Akcyjna X', False), ('Fundacja Y', False), ('Stowarzyszenie Z', False),
    ('Nowak Sp.k.', False), ('Kowalski Sp. j.', False), ('Comarch P.S.A.', False), ('Gmina Wrocław', False),
    ('Przedsiębiorstwo Państwowe Porty Lotnicze', False), ('Siemens AG', False), ('Agnieszka Sas', True)])
def test_ted_legal_form_markers(name, natural):
    assert parsers.is_natural_person(name) is natural
    assert parsers.is_natural_person('Firma Sp. z o.o.', {'natural_person': True}) is True
