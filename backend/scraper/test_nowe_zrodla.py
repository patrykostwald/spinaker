"""Nowe źródła (raport źródeł 6.10): zbieracze bez sieci, na fixture'ach."""
from datetime import date, timedelta
from io import BytesIO, StringIO
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from news.political_models import ParliamentaryRosterEntry, PublicFigure, RegisteredOrganisation
from news.public_records_models import PublicCollectionState, PublicRecord, PublicRecordPerson
from scraper import nowe_zrodla as nz
from scraper import public_records as collectors
from scraper import zasil_baze as zb
from scraper.access_gate import AccessDenied

DATA = json.loads((Path(__file__).parent / 'fixtures' / 'public_records' / 'nowe_zrodla.json').read_text(encoding='utf-8'))
NEW = ('videos', 'howtheyvote', 'wikidata', 'kohesio', 'fts', 'integrity_watch', 'mileage')
pytestmark = pytest.mark.django_db


def body(name):
    value = DATA[name]
    return value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode()


def job(source, kind, url, context=None):
    state, _ = PublicCollectionState.objects.get_or_create(source=source)
    return collectors.enqueue(state, url, kind, context)[0]


def handle(j, raw):
    with transaction.atomic():
        collectors.handle(j, raw)


def figure(name, source, external_id, term=None):
    entry = ParliamentaryRosterEntry.objects.create(source=source, external_id=str(external_id), full_name=name, term=term,
                                                    club='KO', source_url='https://api.sejm.gov.pl/sejm/term10/MP')
    return PublicFigure.objects.create(canonical_name=name, role_category='parliament' if source == 'sejm' else 'european',
                                       role_title='Poseł', evidence_url='https://api.sejm.gov.pl/', parliamentary_roster_entry=entry)


@pytest.mark.parametrize('source', NEW)
def test_flags_off_mean_no_run_and_no_jobs(source, monkeypatch):
    monkeypatch.delenv(collectors.SOURCES[source].flag(source), raising=False)
    with patch.object(collectors, 'fetch_feed') as transport, patch.object(nz, 'download') as download:
        assert collectors.collect(source)['status'] == 'disabled'
    transport.assert_not_called()
    download.assert_not_called()
    assert not PublicCollectionState.objects.filter(source=source).exists()


def test_every_new_source_is_scheduled_registered_carded_and_in_a_lane():
    from config.celery import app
    from news.agent_registry import REGISTRY
    from scraper import tasks
    from scraper.harvester_coverage import DIRECT_SCHEDULES
    from scraper.management.commands.configure_public_records import cards
    lanes = {s for sources in zb.LANES.values() for s in sources}
    for source in NEW:
        task = 'scraper.tasks.collect_public_' + source
        assert app.conf.beat_schedule['public-records-' + source]['task'] == task
        assert REGISTRY['public-records-' + source]['flag'] == f'PUBLIC_RECORDS_{source.upper()}_ENABLED'
        assert getattr(tasks, 'collect_public_' + source).name == task
        assert cards(source) and source in lanes and source in zb.BACKFILL_CAP
        for root, *_ in cards(source):
            assert root in DIRECT_SCHEDULES or root == collectors.API + '/sejm'
    assert 'zasil-baze-otwarte' in app.conf.beat_schedule


def test_cards_apply_and_gate_each_host(monkeypatch):
    out = StringIO()
    for source in NEW:
        call_command('configure_public_records', source=source, apply=True, reviewed_by='test',
                     evidence_url='https://example.org/doc', terms_url='https://example.org/terms', stdout=out)
    checks = [
        ('videos', 'video_index', collectors.SEJM + '/videos?since=2026-01-01&offset=0&limit=20', 'metadata'),
        ('videos', 'committee_transcript', collectors.SEJM + '/committees/ASW/sittings/7/html', 'content'),
        ('howtheyvote', 'htv_vote', nz.HTV + '/197352', 'metadata'),
        ('wikidata', 'wd_query', nz.wikidata_url('sejm'), 'metadata'),
        ('kohesio', 'kohesio_page', nz.kohesio_url(0), 'metadata'),
        ('fts', 'fts_year', nz.FTS.format(year=2024), 'metadata'),
        ('integrity_watch', 'iw_meetings', nz.IW_MEETINGS, 'metadata'),
        ('mileage', 'mileage_export', nz.MILEAGE, 'metadata'),
        ('mileage', 'office_pdf', DATA['offices']['records'][0]['pdf_url'], 'metadata'),
    ]
    for source, kind, url, scope in checks:
        _, card = collectors.source_access(job(source, kind, url))
        assert card.allowed_scope == scope, (source, kind)
    # Karta komisji (committees) nie otwiera zapisu przebiegu, a karta transmisji nie otwiera listy posiedzeń.
    with pytest.raises(AccessDenied):
        collectors.source_access(job('videos', 'video_index', collectors.SEJM + '/committees/ASW/sittings'))
    with pytest.raises(AccessDenied):
        collectors.source_access(job('mileage', 'mileage_export', 'https://jakglosuja.pl/api/eksport/oswiadczenia?format=json'))
    with pytest.raises(AccessDenied):
        collectors.source_access(job('integrity_watch', 'iw_meps', 'https://www.integritywatch.eu/data/other/x.json'))


# --- Sejm wideo ------------------------------------------------------------------------------------------------

def test_videos_saved_and_committee_transcript_linked_by_unid():
    PublicRecord.objects.create(source='committees', kind='committee_sitting', external_id='10/ASW/7', date=date(2026, 10, 5),
                                source_url='https://api.sejm.gov.pl/x', response_url='https://api.sejm.gov.pl/x', response_sha256='0',
                                data={'num': 7, 'code': 'ASW', 'committee': 'Komisja Administracji',
                                      'video': ['https://sejm.c.blueonline.tv/stream/ENC11/1356434EE1FC0BFEC1258A6E003C313B/playlist.m3u8']})
    j = job('videos', 'video_index', collectors.SEJM + '/videos?offset=0&limit=20', {'filters': {'since': '2026-10-01'}, 'offset': 0})
    handle(j, body('videos'))
    videos = PublicRecord.objects.filter(source='videos', kind='video')
    assert videos.count() == 2 and videos.get(external_id__startswith='1356').term == 10
    transcript = j.state.jobs.get(kind='committee_transcript')
    assert transcript.url.endswith('/committees/ASW/sittings/7/html') and transcript.context['unid'].startswith('1356')
    assert j.state.jobs.filter(kind='video_index', done=False).exclude(pk=j.pk).exists()  # następna strona


def test_committee_speeches_only_mps_with_unique_official_match():
    PublicRecord.objects.create(source='committees', kind='committee', external_id='10/ASW', source_url='https://api.sejm.gov.pl/x',
                                response_url='https://api.sejm.gov.pl/x', response_sha256='0',
                                data={'members': [{'id': 82, 'lastFirstName': 'Frysztak Konrad', 'club': 'KO'},
                                                  {'id': 83, 'lastFirstName': 'Hreniak Paweł', 'club': 'KO'}]})
    j = job('videos', 'committee_transcript', collectors.SEJM + '/committees/ASW/sittings/7/html',
            {'code': 'ASW', 'num': 7, 'unid': 'U' * 32, 'day': '2026-10-05', 'start': '2026-10-05T10:00:00',
             'end': '2026-10-05T12:00:00', 'player': 'https://sejm.gov.pl/p', 'committee': 'Komisja Administracji'})
    handle(j, body('committee_transcript'))
    rows = {r.data['name']: r for r in PublicRecord.objects.filter(source='videos', kind='committee_speech')}
    assert set(rows) == {'Tomasz Szymański', 'Konrad Frysztak', 'Paweł Hreniak'}  # sekretarz komisji pominięta
    assert 'Wszyscy eksperci są za.' in rows['Konrad Frysztak'].text
    assert list(rows['Konrad Frysztak'].people.values_list('mp_id', flat=True)) == [82]
    assert not rows['Paweł Hreniak'].people.exists()  # inny klub w składzie komisji: bez dopięcia
    assert 0 < rows['Konrad Frysztak'].data['position'] < rows['Paweł Hreniak'].data['position'] < 1
    empty = job('videos', 'committee_transcript', collectors.SEJM + '/committees/ASW/sittings/8/html', {**j.context, 'num': 8})
    handle(empty, b'<html></html>')  # zapis jeszcze nie gotowy: bez błędu i bez rekordów


# --- HowTheyVote ----------------------------------------------------------------------------------------------

def test_howtheyvote_pages_stop_at_since_and_keep_only_polish_meps():
    meps = figure('Magdalena Adamowicz', 'ep', 197490)
    j = job('howtheyvote', 'htv_index', nz.htv_url(1), {'page': 1, 'since': '2026-09-01'})
    handle(j, body('htv_index'))
    assert sorted(x.context['id'] for x in j.state.jobs.filter(kind='htv_vote')) == ['197351', '197352']
    assert not j.state.jobs.filter(kind='htv_index').exclude(pk=j.pk).exists()  # starsze głosowanie = koniec stron
    v = job('howtheyvote', 'htv_vote', nz.HTV + '/197352', {'id': '197352'})
    handle(v, body('htv_vote'))
    record = PublicRecord.objects.get(source='howtheyvote', kind='ep_vote')
    assert [x['ep_id'] for x in record.data['votes']] == [197490, 124877]
    assert record.data['polish'] == {'AGAINST': 1, 'FOR': 1} and record.data['license'] == 'ODbL 1.0'
    linked = PublicRecordPerson.objects.get(record=record, mp_id=197490)
    assert linked.term == collectors.EP_TERM and linked.figure == meps
    assert PublicRecordPerson.objects.get(record=record, mp_id=124877).figure is None
    with pytest.raises(ValueError, match='identity'):
        handle(job('howtheyvote', 'htv_vote', nz.HTV + '/1', {'id': '1'}), body('htv_vote'))


# --- Wikidata -------------------------------------------------------------------------------------------------

def test_wikidata_identity_parties_and_x_only_as_hint():
    mp = figure('Konrad Frysztak', 'sejm', 82, term=10)
    j = job('wikidata', 'wd_query', nz.wikidata_url('sejm'), {'which': 'sejm'})
    handle(j, body('wikidata'))
    person = PublicRecord.objects.get(source='wikidata', external_id='Q123177555')
    assert person.data['sejm_ids'] == [[10, 82]] or person.data['sejm_ids'] == [(10, 82)]
    assert [p['name'] for p in person.data['parties']] == ['Partia Testowa', 'Platforma Obywatelska']
    assert person.data['x_hints'] == ['KFrysztak'] and 'nie jest potwierdzone' in person.data['x_note']
    assert person.people.get().figure == mp
    other = PublicRecord.objects.get(source='wikidata', external_id='Q555')
    assert other.data['x_hints'] == [] and other.data['ep_ids'] == [197490]
    from news.political_models import PoliticalAccount
    assert not PoliticalAccount.objects.exists()  # żadne konto X nie powstaje ani nie jest potwierdzane


# --- Kohesio i FTS --------------------------------------------------------------------------------------------

def test_kohesio_skips_natural_people_and_links_known_organisations():
    org = RegisteredOrganisation.objects.create(name='TESTOWA SP. Z O.O.', krs_number='0000000001', kind='company',
                                                official_register_url='https://ekrs.ms.gov.pl/')
    nz.org_index(refresh=True)
    rows = DATA['kohesio'] * 1
    j = job('kohesio', 'kohesio_page', nz.kohesio_url(0), {'offset': 0})
    handle(j, json.dumps(rows).encode())
    names = set(PublicRecord.objects.filter(source='kohesio').values_list('data__beneficiary', flat=True))
    assert names == {'WYŻSZA SZKOŁA BANKOWA WE WROCŁAWIU', 'Testowa Spółka z ograniczoną odpowiedzialnością'}
    linked = PublicRecord.objects.get(source='kohesio', external_id='Q100')
    assert linked.data['organisation_id'] == org.pk and linked.data['krs'] == '0000000001'
    assert j.state.jobs.get(pk=j.pk).context['skipped_people'] == 1
    assert not j.state.jobs.filter(kind='kohesio_page').exclude(pk=j.pk).exists()  # krótka strona = koniec


def xlsx(rows):
    def cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    sheet = ''.join('<row>' + ''.join(cell(chr(65 + i) + str(r + 1), v) for i, v in enumerate(row)) + '</row>'
                    for r, row in enumerate(rows))
    out = BytesIO()
    with ZipFile(out, 'w') as z:
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   f'<sheetData>{sheet}</sheetData></worksheet>')
    return out.getvalue()


def test_fts_streams_xlsx_and_keeps_polish_organisations_only():
    raw = xlsx([['Year', 'Name of beneficiary', 'VAT Number of beneficiary', 'City', 'Country / Territory',
                 "Beneficiary's contracted amount (EUR)", 'Subject of grant or contract', 'Programme name'],
                ['2024', 'Fundacja Testowa', 'PL5260000000', 'Warszawa', 'Poland', '1200.50', 'Projekt A', 'Horizon'],
                ['2024', 'Jan Kowalski', '', 'Kraków', 'Poland', '100', 'Stypendium', 'Erasmus'],
                ['2024', 'Natural person', '', '', 'Poland', '50', 'x', 'y'],
                ['2024', 'Firma GmbH', '', 'Berlin', 'Germany', '10', 'x', 'y']])
    rows = nz.fts_polish([raw[:100], raw[100:]])
    assert [r['name'] for r in rows] == ['Fundacja Testowa']
    j = job('fts', 'fts_year', nz.FTS.format(year=2024), {'year': 2024})
    handle(j, json.dumps(rows).encode())
    grant = PublicRecord.objects.get(source='fts')
    assert grant.data['amount'] == 1200.5 and grant.data['vat'] == 'PL5260000000' and grant.data['license'] == 'CC BY 4.0'
    assert nz.fts_years(date(2021, 1, 1), date(2026, 10, 6)) == [2021, 2022, 2023, 2024, 2025]
    assert nz.fts_years(date(2021, 1, 1), date(2026, 3, 6))[-1] == 2024
    with pytest.raises(ValueError, match='too large'):
        nz.fts_polish([raw], limit=10)


# --- Integrity Watch EU ---------------------------------------------------------------------------------------

def test_integrity_watch_polish_meps_income_and_meetings_without_private_fields():
    mep = figure('Magdalena Adamowicz', 'ep', 197490)
    handle(job('integrity_watch', 'iw_meps', nz.IW_MEPS), body('iw_meps'))
    record = PublicRecord.objects.get(source='integrity_watch', kind='mep')
    assert record.external_id == '197490' and 'email' not in json.dumps(record.data) and 'birthdate' not in json.dumps(record.data)
    handle(job('integrity_watch', 'iw_income', nz.IW_INCOME), body('iw_income'))
    income = PublicRecord.objects.get(source='integrity_watch', kind='mep_income')
    assert income.data['total_eur'] == 12000 and income.data['paid_activities'] == 1 and len(income.data['activities']) == 2
    rows = nz.meetings_polish([body('iw_meetings')])
    assert [r['epid'] for r in rows] == ['197490']
    handle(job('integrity_watch', 'iw_meetings', nz.IW_MEETINGS), json.dumps(rows).encode())
    meeting = PublicRecord.objects.get(source='integrity_watch', kind='mep_meeting')
    assert meeting.date == date(2025, 4, 10) and meeting.people.get().figure == mep


def test_integrity_watch_income_needs_meps_first():
    with pytest.raises(ValueError, match='meps_first'):
        handle(job('integrity_watch', 'iw_income', nz.IW_INCOME), body('iw_income'))


# --- Kilometrówki i biura -------------------------------------------------------------------------------------

def test_mileage_roster_check_and_office_pdf_verification():
    mp = figure('Konrad Frysztak', 'sejm', 82, term=10)
    handle(job('mileage', 'mileage_export', nz.MILEAGE), body('mileage'))
    rows = {r.data['mp_id']: r for r in PublicRecord.objects.filter(source='mileage', kind='mileage')}
    assert rows[82].data['check'] == 'zgodne z listą posłów Sejmu' and rows[82].people.get().figure == mp
    assert rows[999].data['check'].startswith('brak posła')
    assert rows[82].data['origin'] == 'skrotpolityczny.pl'
    j = job('mileage', 'office_export', nz.OFFICES)
    handle(j, body('offices'))
    report = PublicRecord.objects.get(source='mileage', kind='office_report')
    assert report.data['pdf_check'].startswith('oczekuje') and report.source_url.startswith('https://orka.sejm.gov.pl/')
    pdf_job = j.state.jobs.get(kind='office_pdf')
    with patch.object(nz.parsers, 'pdf_text', return_value='Razem wydatki 274 377,74 zł'):
        handle(pdf_job, b'%PDF-1.4 test')
    report.refresh_from_db()
    assert report.data['pdf_check'] == 'zgodne z PDF Kancelarii Sejmu' and len(report.data['pdf_sha256']) == 64
    with patch.object(nz.parsers, 'pdf_text', side_effect=ValueError('pdf_requires_manual_review')):
        handle(pdf_job, b'%PDF-1.4 skan')
    report.refresh_from_db()
    assert 'bez warstwy tekstu' in report.data['pdf_check']


# --- meta_ads: tylko archiwum sprzed TTPA ---------------------------------------------------------------------

def test_meta_ads_archive_ends_before_ttpa(monkeypatch):
    monkeypatch.setenv('META_AD_LIBRARY_API_VERSION', 'v21.0')
    monkeypatch.setenv('META_AD_LIBRARY_PAGE_IDS', '123')
    state, _ = PublicCollectionState.objects.get_or_create(source='meta_ads')
    collectors.seed(state, date(2025, 9, 1))
    url = state.jobs.get().url
    assert 'ad_delivery_date_max=2025-10-05' in url
    state.jobs.all().delete()
    collectors.seed(state, date(2025, 11, 1))
    assert not state.jobs.exists()  # po 6.10.2025 Meta nie emituje reklam politycznych w UE


def test_otwarte_lane_links_people(monkeypatch):
    assert zb.link_after('otwarte') is not None
    assert zb.link_after('inne') is None
    from news.public_record_people import link_people
    mep = figure('Magdalena Adamowicz', 'ep', 197490)
    state, _ = PublicCollectionState.objects.get_or_create(source='howtheyvote')
    record = PublicRecord.objects.create(source='howtheyvote', kind='ep_vote', external_id='1', source_url='https://howtheyvote.eu/votes/1',
                                         response_url='https://howtheyvote.eu/api/votes/1', response_sha256='0')
    PublicRecordPerson.objects.create(record=record, term=collectors.EP_TERM, mp_id=197490)
    assert link_people()['linked'] == 1
    assert record.people.get().figure == mep


def test_backfill_targets_for_new_sources(monkeypatch):
    assert zb.target('videos') == collectors.START
    assert zb.target('fts') == date(2021, 1, 1)
    monkeypatch.setenv('PUBLIC_RECORDS_FTS_FIRST_YEAR', '2016')
    assert zb.target('fts') == date(2016, 1, 1)
