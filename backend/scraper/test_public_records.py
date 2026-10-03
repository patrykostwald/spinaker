from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest
from django.core.management import call_command, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Article, OfficialRecord, PublicFigure, ParliamentaryRosterEntry, Source, SourceAccessInstruction
from news.public_records_models import PublicRecord, PublicRecordPerson, PublicCollectionState
from scraper import public_records as collectors
from scraper import public_record_parsers as parsers
from scraper.access_gate import AccessDenied
from scraper.utils import HostRateLimited

FIXTURES = Path(__file__).parent / 'fixtures' / 'public_records'
API = json.loads((FIXTURES / 'api.json').read_text(encoding='utf-8'))
pytestmark = pytest.mark.django_db


def raw(name):
    return (FIXTURES / name).read_bytes()


def payload(name):
    return json.dumps(API[name], ensure_ascii=False).encode()


def job(source, kind, url=None, context=None):
    state, _ = PublicCollectionState.objects.get_or_create(source=source)
    return collectors.enqueue(state, url or collectors.SEJM + '/test', kind, context)[0]


def handle(j, body):
    with transaction.atomic():
        collectors.handle(j, body)


def test_ballots_idempotency_corrections_and_private_storage():
    j = job('votes', 'vote', context={'sitting': 1, 'number': 2})
    handle(j, payload('vote'))
    handle(j, payload('vote'))
    assert PublicRecord.objects.count() == 2
    assert PublicRecordPerson.objects.count() == 2
    record = PublicRecord.objects.get(external_id='10/1/2/1')
    assert record.data['club'] == 'A'
    assert record.response_sha256 == sha256(payload('vote')).hexdigest()
    changed = deepcopy(API['vote'])
    changed['votes'][0]['club'] = 'C'
    handle(j, json.dumps(changed).encode())
    assert PublicRecord.objects.get(pk=record.pk).data['club'] == 'C'
    assert not Article.objects.exists()
    assert not OfficialRecord.objects.exists()
    changed['votes'].pop()
    with pytest.raises(ValueError, match='incomplete'):
        handle(j, json.dumps(changed).encode())
    assert PublicRecord.objects.count() == 2


def test_figure_matching_is_id_and_term_only():
    namesake = PublicFigure.objects.create(canonical_name='Jan Przykładowy')
    roster = ParliamentaryRosterEntry.objects.create(source='sejm', external_id='001', term=10,
        full_name='Different spelling', source_url=collectors.SEJM + '/MP/1')
    correct = PublicFigure.objects.create(canonical_name='Different spelling', parliamentary_roster_entry=roster)
    j = job('votes', 'vote', context={'sitting': 1, 'number': 2})
    handle(j, payload('vote'))
    assert PublicRecordPerson.objects.get(mp_id=1).figure == correct
    assert PublicRecordPerson.objects.get(mp_id=2).figure is None
    assert not PublicRecordPerson.objects.filter(figure=namesake).exists()
    roster.term = 9
    roster.save()
    handle(j, payload('vote'))
    assert PublicRecordPerson.objects.get(mp_id=1).figure is None


@pytest.mark.parametrize('source,resource', [('interpellations', 'interpellations'), ('questions', 'writtenQuestions')])
def test_questions_keep_authors_replies_and_do_not_download_documents(source, resource):
    j = job(source, 'question_index', context={'resource': resource, 'filters': {'sort_by': 'num'}, 'offset': 0})
    body = json.dumps([API['question']]).encode()
    handle(j, body)
    handle(j, body)
    record = PublicRecord.objects.get(source=source)
    assert record.people.count() == 2
    assert record.data['replies'][0]['attachments'][0]['URL'].endswith('.pdf')
    assert j.state.jobs.count() == 2
    assert not j.state.jobs.filter(url__endswith='.pdf').exists()
    next_job = j.state.jobs.exclude(pk=j.pk).get()
    assert 'offset=1' in next_job.url
    with pytest.raises(ValueError, match='repeated_api_page'):
        handle(next_job, body)


def test_statements_preserve_speaker_agenda_dates_and_provenance():
    j = job('statements', 'proceedings', context={'since': '2023-11-13'})
    handle(j, payload('proceedings'))
    index = j.state.jobs.get(kind='transcript_index')
    handle(index, payload('transcripts'))
    speech = j.state.jobs.get(kind='statement')
    handle(speech, raw('speech.html'))
    handle(speech, raw('speech.html'))
    r = PublicRecord.objects.get()
    assert r.data['agenda'] == 'Punkt 2. Projekt ustawy testowej.'
    assert r.text == 'Popieram projekt ustawy.\nProszę o przyjęcie poprawki.'
    assert r.data['name'] == 'Jan Przykładowy'
    assert r.data['index_sha256'] == sha256(payload('transcripts')).hexdigest()
    assert r.people.get().mp_id == 1


def test_assets_follow_observed_link_and_index_only():
    j = job('assets', 'members', context={'since': '2023-11-13'})
    handle(j, payload('members'))
    profile = j.state.jobs.get(kind='asset_profile')
    handle(profile, b'<a href="?id=001&amp;type=F">O\xc5\x9bwiadczenia maj\xc4\x85tkowe</a>')
    index = j.state.jobs.get(kind='asset_index')
    assert 'type=F' in index.url
    handle(index, raw('assets.html'))
    handle(index, raw('assets.html'))
    assert set(PublicRecord.objects.values_list('data__year', flat=True)) == {2023, 2024}
    assert PublicRecord.objects.count() == 2
    assert not j.state.jobs.filter(url__endswith='.pdf').exists()
    assert all(r.people.get().mp_id == 1 for r in PublicRecord.objects.all())


def test_lobby_indexes_and_register_extraction():
    mswia = job('lobby_mswia', 'mswia_index', collectors.MSWIA)
    handle(mswia, raw('mswia.html'))
    assert mswia.state.jobs.filter(kind='register_pdf').count() == 1
    doc = mswia.state.jobs.get(kind='register_pdf')
    with patch.object(parsers, 'pdf_text', return_value=raw('register.txt').decode('utf-8')):
        handle(doc, b'%PDF-fixture')
        handle(doc, b'%PDF-fixture')
    assert PublicRecord.objects.filter(kind='lobby_entity').count() == 2
    assert PublicRecord.objects.get(kind='lobby_entity', external_id='00633').data['registration_date'] == '17.09.2025'
    lobby = job('lobby_sejm', 'lobby_index', collectors.LOBBY, {'since': '2023-11-13'})
    handle(lobby, raw('lobby.html'))
    assert PublicRecord.objects.filter(kind='lobby_document').count() == 1
    people = lobby.state.jobs.get(kind='lobby_people')
    handle(people, raw('lobby_people.html'))
    handle(people, raw('lobby_people.html'))
    assert PublicRecord.objects.filter(kind='lobby_activity').count() == 1
    assert not PublicRecordPerson.objects.exists()


def test_osr_pilot_parser_and_print_relation():
    j = job('consultations', 'prints', context={'since': '2023-11-13'})
    handle(j, payload('prints'))
    assert j.state.jobs.filter(kind='osr_text').count() == 2
    doc = j.state.jobs.filter(kind='osr_text').first()
    with patch.object(collectors, 'document_text', return_value=raw('osr.txt').decode('utf-8')):
        handle(doc, b'%PDF-fixture')
        handle(doc, b'%PDF-fixture')
    rows = PublicRecord.objects.filter(kind='consultation')
    assert rows.count() == 2
    assert set(rows.values_list('data__stanowisko', flat=True)) == {'uwzględniona', 'nieuwzględniona'}
    assert set(rows.values_list('print_number', flat=True)) == {'123'}
    assert all(r.source_url == doc.url and r.data['pewność'] == 'heurystyczna' for r in rows)
    assert PublicRecord.objects.get(kind='osr_document', source_url=doc.url).data['quality'] == 'heuristic'


def test_pkw_metadata_and_machine_amounts():
    j = job('pkw', 'pkw_page', collectors.PKW + 'finansowanie-partii-politycznych', {'since': '2023-11-13', 'depth': 0})
    handle(j, raw('pkw.html'))
    handle(j, raw('pkw.html'))
    assert PublicRecord.objects.filter(kind='financial_document').count() == 3
    assert not j.state.jobs.filter(url__endswith='.pdf').exists()
    assert j.state.jobs.filter(kind='pkw_xlsx').count() == 1
    record = PublicRecord.objects.get(kind='financial_row')
    assert record.data['amounts'] == {'Przychody (zł)': '1234.56'}
    handle(j.state.jobs.get(kind='pkw_csv'), raw('pkw.csv'))
    assert PublicRecord.objects.filter(kind='financial_row').count() == 2


def test_xlsx_values_and_formula_rejection():
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as z:
        z.writestr('xl/worksheets/sheet1.xml', '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
          <row><c r="A1" t="inlineStr"><is><t>Podmiot</t></is></c><c r="B1" t="inlineStr"><is><t>Kwota PLN</t></is></c></row>
          <row><c r="A2" t="inlineStr"><is><t>Test</t></is></c><c r="B2"><v>123.45</v></c></row>
          <row><c r="B3"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>''')
    rows = parsers.financial_tables(buffer.getvalue(), xlsx_file=True)
    assert len(rows) == 1 and rows[0]['amounts'] == {'Kwota PLN': '123.45'}


def test_meta_fields_and_pagination_never_store_token_or_follow_next():
    base = 'https://graph.facebook.com/v24.0/ads_archive'
    j = job('meta_ads', 'meta_page', base, {'base': base, 'filters': {'limit': 20}})
    handle(j, payload('meta'))
    handle(j, payload('meta'))
    record = PublicRecord.objects.get()
    assert record.data['spend']['upper_bound'] == '199'
    assert record.data['impressions']['lower_bound'] == '1000'
    assert record.data['bylines'] == 'Komitet testowy'
    assert record.text == 'Treść testowej reklamy'
    assert 'DO_NOT_STORE' not in json.dumps(record.data)
    next_job = j.state.jobs.exclude(pk=j.pk).get()
    assert next_job.url.startswith(base) and 'after=CURSOR' in next_job.url
    assert 'evil' not in next_job.url and 'token' not in next_job.url
    with pytest.raises(ValueError, match='invalid_meta_cursor'):
        handle(next_job, payload('meta'))


@pytest.mark.parametrize('source', tuple(collectors.SOURCES))
def test_flags_deny_network_and_do_not_seed_jobs(source, monkeypatch):
    monkeypatch.setenv(collectors.SOURCES[source].flag(source), 'false')
    with patch.object(collectors, 'fetch_feed') as transport:
        assert collectors.collect(source)['status'] == 'disabled'
    transport.assert_not_called()


def test_meta_no_token_cannot_call_any_network(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_META_ADS_ENABLED', 'true')
    monkeypatch.delenv('META_AD_LIBRARY_TOKEN', raising=False)
    with patch.object(collectors, 'fetch_feed') as transport:
        assert collectors.collect('meta_ads')['reason'] == 'meta_token_required'
    transport.assert_not_called()


def approve(j):
    source = Source.objects.create(name='Test Sejm', url=collectors.API + '/sejm',
                                   is_active=True, scrape_enabled=True, catalog_stage='configured')
    instruction = SourceAccessInstruction.objects.create(source=source, version=1, status='approved', channel='api',
        allowed_scope='metadata', endpoint=collectors.API + '/sejm', terms_url='https://api.sejm.gov.pl/',
        evidence={'test': True}, reviewed_at=timezone.now(), reviewed_by='fixture',
        valid_until=timezone.now() + timedelta(days=3), minimum_interval_seconds=3, daily_request_cap=100)
    j.state.lease_token = 'test'
    j.state.lease_until = timezone.now() + timedelta(minutes=5)
    j.state.save()
    return instruction


def test_independent_daily_limit_and_interval_before_transport(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_DAILY_CAP', '1')
    j = job('votes', 'vote', collectors.SEJM + '/votings/1/2')
    approve(j)
    with patch.object(collectors, 'fetch_feed', return_value=(payload('vote'), None)) as transport:
        collectors.fetch(j, 'test')
        with pytest.raises(HostRateLimited):
            collectors.fetch(j, 'test')
        assert transport.call_count == 1
        assert transport.call_args.kwargs['budget_share'] == 0.6
    state = PublicCollectionState.objects.get(pk=j.state_id)
    state.requests_today = 0
    state.save()
    with patch.object(collectors, 'fetch_feed') as transport:
        with pytest.raises(HostRateLimited):
            collectors.fetch(j, 'test')
        transport.assert_not_called()


def test_access_gate_and_scope_deny_before_network(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    j = job('votes', 'vote', collectors.SEJM + '/votings/1/2')
    with patch.object(collectors, 'fetch_feed') as transport:
        with pytest.raises(AccessDenied, match='no_approved_instruction'):
            collectors.fetch(j, 'test')
        j.url = 'https://evil.example/sejm/term10/votings/1/2'
        with pytest.raises(AccessDenied, match='out_of_scope'):
            collectors.fetch(j, 'test')
        transport.assert_not_called()


def test_resume_bounded_page_then_vote_without_replaying_index(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())
    index = json.dumps([{'term': 10, 'sitting': 1, 'votingNumber': 2}]).encode()
    with patch.object(collectors, 'fetch', side_effect=[(index, None), (payload('vote'), None), (b'[]', None)]) as fetch:
        first = collectors.collect('votes', since='2023-11-13', max_requests=1)
        assert first['status'] == 'partial' and first['pending'] == 2
        second = collectors.collect('votes', since='2023-11-13', max_requests=1)
        assert second['completed'] == 1
        assert PublicRecord.objects.count() == 2
        third = collectors.collect('votes', since='2023-11-13', max_requests=1)
        assert third['status'] == 'ok'
        assert fetch.call_count == 3
    state = PublicCollectionState.objects.get(source='votes')
    assert state.record_count == 2 and state.last_complete_at and state.last_success_at
    assert not state.lease_token


def test_bad_response_keeps_job_pending_and_releases_lease(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())
    with patch.object(collectors, 'fetch', return_value=(b'<captcha>', None)):
        result = collectors.collect('votes', max_requests=1)
    assert result['status'] == 'error'
    state = PublicCollectionState.objects.get(source='votes')
    assert state.jobs.get().failures == 1 and not state.jobs.get().done
    assert not state.lease_token and not state.last_complete_at


def test_lease_prevents_overlap_and_flags_are_rechecked(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    state, _ = PublicCollectionState.objects.get_or_create(source='votes')
    state.lease_until = timezone.now() + timedelta(minutes=1)
    state.save()
    with patch.object(collectors, 'fetch') as transport:
        assert collectors.collect('votes')['status'] == 'already_running'
        transport.assert_not_called()


def test_backfill_rejects_changed_start_until_pending_cycle_finishes(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    with patch.object(collectors, 'fetch', side_effect=HostRateLimited(100)):
        assert collectors.collect('votes', since='2023-11-13', max_requests=1)['status'] == 'deferred'
    with pytest.raises(ValueError, match='different_backfill'):
        collectors.collect('votes', since='2024-01-01')
    with pytest.raises(ValueError, match='since_outside'):
        collectors.collect('votes', since='2020-01-01')


def test_command_is_bounded_and_disabled_is_an_error(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'false')
    out = StringIO()
    with pytest.raises(CommandError):
        call_command('public_records_backfill', source='votes', since=collectors.START, stdout=out)
    assert 'disabled' in out.getvalue()


def test_every_source_has_distinct_schedule_registry_and_admin():
    from config.celery import app
    from news.agent_registry import REGISTRY
    from news.admin import site
    from scraper import tasks
    for source, spec in collectors.SOURCES.items():
        key = 'public-records-' + source
        task = 'scraper.tasks.collect_public_' + source
        assert REGISTRY[key]['task'] == task
        assert REGISTRY[key]['flag'] == spec.flag(source)
        assert app.conf.beat_schedule[key]['task'] == task
        assert getattr(tasks, 'collect_public_' + source).name == task
    assert PublicCollectionState in site._registry
    assert PublicRecord in site._registry


def test_pdf_text_limits_and_no_ocr():
    with patch('pypdf.PdfReader') as reader:
        reader.return_value.is_encrypted = False
        reader.return_value.pages = [Mock(extract_text=Mock(return_value=''))]
        assert parsers.pdf_text(b'%PDF-test') == ''
        reader.return_value.pages = [None] * 501
        with pytest.raises(ValueError, match='manual_review'):
            parsers.pdf_text(b'%PDF-test')
    with pytest.raises(ValueError, match='large_pdf'):
        parsers.pdf_text(b'%PDF-' + b'x' * 5_000_000)


def test_configure_plan_does_not_write_or_fetch():
    before = Source.objects.count()
    with patch.object(collectors, 'fetch_feed') as fetch:
        call_command('configure_public_records', source='statements', stdout=StringIO())
    assert Source.objects.count() == before
    fetch.assert_not_called()
    with pytest.raises(CommandError, match='wymaga'):
        call_command('configure_public_records', source='statements', apply=True, stdout=StringIO())


def test_configure_reviewed_card_matches_transcript_and_checks_content_scope():
    call_command('configure_public_records', source='statements', apply=True,
        reviewed_by='fixture', evidence_url='https://api.sejm.gov.pl/sejm.html',
        terms_url='https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright', stdout=StringIO())
    j = job('statements', 'statement', collectors.SEJM + '/proceedings/1/2023-11-13/transcripts/1')
    _, card = collectors.source_access(j)
    assert card.allowed_scope == 'content'
    card.allowed_scope = 'metadata'
    card.save()
    with pytest.raises(AccessDenied, match='content_scope_required'):
        collectors.source_access(j)
    card.status = 'suspended'
    card.save()
    with pytest.raises(CommandError, match='nadpisuję'):
        call_command('configure_public_records', source='statements', apply=True,
            reviewed_by='fixture', evidence_url='https://api.sejm.gov.pl/sejm.html',
            terms_url='https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright', stdout=StringIO())


def test_meta_seed_batches_page_ids_and_accepts_older_archive(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_META_ADS_ENABLED', 'true')
    monkeypatch.setenv('META_AD_LIBRARY_TOKEN', 'fixture-token')
    monkeypatch.setenv('META_AD_LIBRARY_API_VERSION', 'v24.0')
    monkeypatch.setenv('META_AD_LIBRARY_PAGE_IDS', ','.join(str(i) for i in range(1, 23)))
    with patch.object(collectors, 'fetch', side_effect=HostRateLimited(100)):
        result = collectors.collect('meta_ads', since='2020-01-01', max_requests=1)
    assert result['status'] == 'deferred'
    state = PublicCollectionState.objects.get(source='meta_ads')
    assert state.jobs.count() == 3
    assert sorted(len(json.loads(j.context['filters']['search_page_ids'])) for j in state.jobs.all()) == [2, 10, 10]
    assert all('fixture-token' not in j.url and 'fixture-token' not in json.dumps(j.context) for j in state.jobs.all())


def test_one_binary_document_per_tick(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_CONSULTATIONS_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())
    monkeypatch.setattr(collectors, 'sleep', Mock())
    monkeypatch.setattr(collectors, 'document_text', Mock(return_value=raw('osr.txt').decode('utf-8')))
    first = job('consultations', 'osr_text', collectors.SEJM + '/prints/123/a.pdf', {'number': '123', 'title': 'Test'})
    job('consultations', 'osr_text', collectors.SEJM + '/prints/123/b.pdf', {'number': '123', 'title': 'Test'})
    first.state.next_request_at = timezone.now()
    first.state.save()
    with patch.object(collectors, 'fetch', return_value=(b'%PDF-fixture', None)) as fetch:
        result = collectors.collect('consultations', max_requests=4)
    assert fetch.call_count == 1 and result['pending'] == 1


def test_killed_worker_replays_uncommitted_parent_without_duplicate_children(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())
    j = job('votes', 'vote', collectors.SEJM + '/votings/1/2', {'sitting': 1, 'number': 2})
    # Simulate an expired lease left by a killed worker after a committed write.
    handle(j, payload('vote'))
    j.state.lease_token = 'old-worker'
    j.state.lease_until = timezone.now() - timedelta(seconds=1)
    j.state.save()
    with patch.object(collectors, 'fetch', return_value=(payload('vote'), None)):
        result = collectors.collect('votes', max_requests=1)
    assert result['status'] == 'ok'
    assert PublicRecord.objects.count() == 2


def test_public_heartbeat_deferral_is_skipped_and_block_is_error():
    from news import task_heartbeat
    task = Mock(name='task')
    task.name = 'scraper.tasks.collect_public_votes'
    with patch.object(task_heartbeat, 'record') as record:
        task_heartbeat.succeeded(sender=task, result={'status': 'deferred', 'error': 'request_limit_or_host_interval'})
        assert record.call_args.args[1] == 'skipped'
        task_heartbeat.succeeded(sender=task, result={'status': 'blocked_access_review', 'error': 'no_approved_instruction'})
        assert record.call_args.args[1] == 'error'


def test_oversized_document_does_not_stall_forever_or_claim_completion(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_CONSULTATIONS_ENABLED', 'true')
    j = job('consultations', 'osr_text', collectors.SEJM + '/prints/123/a.pdf', {'number': '123', 'title': 'Test'})
    with patch.object(collectors, 'fetch', side_effect=ValueError('Source response too large')):
        result = collectors.collect('consultations', max_requests=1)
    assert result['status'] == 'needs_review'
    j.refresh_from_db()
    assert j.done and j.last_error == 'source_response_too_large'
    j.state.refresh_from_db()
    assert j.state.last_complete_at is None


def test_docx_text_layer_only():
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body></w:document>')
    assert collectors.document_text(buffer.getvalue(), collectors.SEJM + '/prints/123/a.docx') == 'Test'


def test_revoked_card_after_fetch_prevents_database_write(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    j = job('votes', 'vote', collectors.SEJM + '/votings/1/2', {'sitting': 1, 'number': 2})
    with patch.object(collectors, 'fetch', return_value=(payload('vote'), None)), \
         patch.object(collectors, 'source_access', side_effect=AccessDenied('no_approved_instruction')):
        result = collectors.collect('votes', max_requests=1)
    assert result['status'] == 'blocked_access_review'
    assert not PublicRecord.objects.exists()
    j.refresh_from_db()
    assert not j.done


@pytest.mark.parametrize('name', ['<html>Please enable JavaScript</html>', '<html>Human Verification</html>'])
def test_unavailable_asset_index_is_never_successful_empty(name):
    with pytest.raises(ValueError, match='asset_index'):
        parsers.assets(name, 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id=001')
