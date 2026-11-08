"""Zasilanie bazy: kursory, idempotencja, osobny limit, automatyczne zakończenie. Bez sieci."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO
import json
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicCollectionState, PublicRecord
from scraper import public_records as collectors
from scraper import zasil_baze as zb
from scraper.utils import HostRateLimited

pytestmark = pytest.mark.django_db


def vote(sitting, number, mps=(1, 2)):
    return json.dumps({'term': 10, 'sitting': sitting, 'votingNumber': number, 'date': '2024-01-10T10:00:00',
                       'title': 'Głosowanie', 'votes': [{'MP': mp, 'vote': 'YES', 'club': 'K'} for mp in mps]}).encode()


def index(*pairs):
    return json.dumps([{'term': 10, 'sitting': s, 'votingNumber': n} for s, n in pairs]).encode()


def fake(responses):
    """Zastępuje fetch: kolejne odpowiedzi i odstęp, który zapisuje prawdziwy fetch (tu: bez czekania)."""
    items = list(responses)

    def run(job, token, mode=None):
        PublicCollectionState.objects.filter(pk=job.state_id).update(next_request_at=timezone.now())
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return Mock(side_effect=run)


@pytest.fixture
def votes_on(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setattr(collectors, 'source_access', Mock())


def test_reserve_separate_cap_resets_daily_and_resztka_ignores_cap(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_BACKFILL_CAP', '2')
    assert zb.reserve('votes', 'noc') and zb.reserve('votes', 'noc')
    assert not zb.reserve('votes', 'noc')
    assert zb.reserve('votes', 'resztka')  # przed północą: tylko karta dostępu jest granicą
    data = zb.info('votes')
    assert data['requests_today'] == 3 and data['requests_total'] == 3
    tomorrow = timezone.now() + timedelta(days=1)
    with patch('scraper.zasil_baze.timezone.localdate', return_value=timezone.localdate(tomorrow)):
        assert zb.reserve('votes', 'noc')
    assert zb.info('votes')['requests_today'] == 1 and zb.info('votes')['requests_total'] == 4
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_BACKFILL_CAP', '0')
    with pytest.raises(ValueError):
        zb.cap('votes')


def approve(state):
    source = Source.objects.create(name='Test Sejm', url=collectors.API + '/sejm',
                                   is_active=True, scrape_enabled=True, catalog_stage='configured')
    instruction = SourceAccessInstruction.objects.create(source=source, version=1, status='approved', channel='api',
        allowed_scope='metadata', endpoint=collectors.API + '/sejm', terms_url='https://api.sejm.gov.pl/',
        evidence={'test': True}, reviewed_at=timezone.now(), reviewed_by='fixture',
        valid_until=timezone.now() + timedelta(days=3), minimum_interval_seconds=3, daily_request_cap=100)
    state.lease_token, state.lease_until = 'test', timezone.now() + timedelta(minutes=5)
    state.save()
    return instruction


def test_backfill_fetch_uses_own_cap_not_regular_daily_cap(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_DAILY_CAP', '1')
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_BACKFILL_CAP', '1')
    state, _ = PublicCollectionState.objects.get_or_create(source='votes')
    state.requests_today, state.budget_day = 1, timezone.localdate()  # zwykły limit na dziś wyczerpany
    state.save()
    job = collectors.enqueue(state, collectors.SEJM + '/votings/1/2', 'vote', {'sitting': 1, 'number': 2})[0]
    approve(state)
    with patch.object(collectors, 'fetch_feed', return_value=(vote(1, 2), None)) as transport:
        collectors.fetch(job, 'test', 'noc')
        assert transport.call_args.kwargs['budget_share'] == 1.0
        PublicCollectionState.objects.filter(pk=state.pk).update(next_request_at=None)
        with pytest.raises(HostRateLimited):
            collectors.fetch(job, 'test', 'noc')  # limit zasilania wyczerpany przed siecią
        assert transport.call_count == 1
    assert PublicCollectionState.objects.get(pk=state.pk).requests_today == 1
    assert zb.info('votes')['requests_today'] == 1


def test_run_source_starts_history_resumes_and_completes_idempotently(votes_on):
    responses = [(index((1, 1), (1, 2)), None), (vote(1, 1), None), (vote(1, 2), None), (b'[]', None)]
    with patch.object(collectors, 'fetch', fake(responses)) as fetch:
        first = zb.run_source('votes', max_requests=1)
        state = PublicCollectionState.objects.get(source='votes')
        assert first['status'] == 'partial' and state.since == collectors.START
        assert zb.info('votes')['cycle'] == state.cycle_started_at.isoformat()
        assert fetch.call_args.args[2] == 'noc'
        second = zb.run_source('votes', max_requests=20)
        assert second.get('complete') and second['added'] == 4
        assert fetch.call_count == 4
    assert zb.complete('votes') and zb.info('votes')['note'] == 'ok'
    with patch.object(collectors, 'fetch') as fetch:
        assert zb.run_source('votes')['status'] == 'complete'  # automatyczny koniec: bez sieci
        fetch.assert_not_called()
    assert PublicRecord.objects.filter(source='votes').count() == 4


def test_pending_regular_cycle_is_continued_not_restarted(votes_on):
    with patch.object(collectors, 'fetch', side_effect=HostRateLimited(100)):
        collectors.collect('votes', since='2024-06-01', max_requests=1)  # zwykły cykl z inną datą czeka
    state = PublicCollectionState.objects.get(source='votes')
    with patch.object(collectors, 'fetch', fake([(b'[]', None)])):
        result = zb.run_source('votes', max_requests=5)
    assert result['status'] == 'ok' and not result.get('error')
    state.refresh_from_db()
    assert state.since == date(2024, 6, 1)  # nie objął całej historii: zasilanie zacznie własny cykl
    assert not zb.complete('votes')


def test_finished_cycle_with_review_errors_is_not_restarted_forever(votes_on):
    with patch.object(collectors, 'fetch', side_effect=ValueError('Source response too large')):
        result = zb.run_source('votes', max_requests=1)
    assert result['status'] == 'needs_review'
    assert zb.complete('votes') and zb.info('votes')['note'] == 'z uwagami'


def test_ted_history_is_seeded_by_month_newest_first(monkeypatch):
    state, _ = PublicCollectionState.objects.get_or_create(source='ted')
    today = timezone.localdate()
    since = today - timedelta(days=95)
    assert zb.seed_history(state, since)
    assert zb.seed_history(state, since)  # idempotentne: te same zadania
    queries = [j.context['body']['query'] for j in state.jobs.order_by('id')]
    assert len(queries) == len({q for q in queries}) and 4 <= len(queries) <= 5
    assert f'publication-date<={today:%Y%m%d}' in queries[0]
    assert f'publication-date>={since:%Y%m%d}' in queries[-1]
    assert all(j.context['body']['limit'] == 100 for j in state.jobs.all())


def test_krs_history_enqueues_extract_for_every_tracked_organisation():
    for number, archived in (('0000000001', False), ('0000000002', False), ('0000000003', True)):
        RegisteredOrganisation.objects.create(name='Spółka ' + number, krs_number=number, kind='company',
                                              official_register_url='https://ekrs.ms.gov.pl/', archived=archived)
    state, _ = PublicCollectionState.objects.get_or_create(source='krs_changes')
    assert zb.seed_history(state, collectors.START)
    assert zb.seed_history(state, collectors.START)
    urls = sorted(state.jobs.values_list('url', flat=True))
    assert urls == [f'{collectors.KRS_API}/OdpisAktualny/000000000{i}?rejestr=P&format=json' for i in (1, 2)]
    assert set(state.jobs.values_list('kind', flat=True)) == {'krs_extract'}


def test_regular_krs_seed_stays_on_recent_bulletins(monkeypatch):
    RegisteredOrganisation.objects.create(name='Spółka', krs_number='0000000001', kind='company',
                                          official_register_url='https://ekrs.ms.gov.pl/')
    state, _ = PublicCollectionState.objects.get_or_create(source='krs_changes')
    collectors.seed(state, timezone.localdate() - timedelta(days=1))
    assert set(state.jobs.values_list('kind', flat=True)) == {'krs_bulletin'}


def test_run_respects_window_and_stops_when_everything_complete(votes_on, monkeypatch):
    noon = datetime(2026, 10, 6, 10, tzinfo=dt_timezone.utc)
    night = datetime(2026, 10, 7, 1, 30, tzinfo=dt_timezone.utc)  # 03:30 w Warszawie
    with patch.object(collectors, 'fetch') as fetch:
        assert zb.run('sejm', 'noc', now=noon)['status'] == 'skipped'
        fetch.assert_not_called()
    for source in zb.LANES['sejm']:
        monkeypatch.delenv(collectors.SOURCES[source].flag(source), raising=False)
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    zb._update('votes', complete_at=timezone.now().isoformat())
    with patch.object(collectors, 'fetch') as fetch:
        assert zb.run('sejm', 'noc', now=night) == {'status': 'complete', 'produced': 0, 'sources_left': 0}
        fetch.assert_not_called()
    monkeypatch.setenv('ZASIL_BAZE_ENABLED', 'false')
    assert zb.run('sejm', 'noc', now=night)['status'] == 'disabled'


def test_run_lane_collects_and_links_people(votes_on, monkeypatch):
    for source in zb.LANES['sejm']:
        monkeypatch.delenv(collectors.SOURCES[source].flag(source), raising=False)
    monkeypatch.setenv('PUBLIC_RECORDS_VOTES_ENABLED', 'true')
    responses = [(index((1, 1)), None), (vote(1, 1), None), (b'[]', None)]
    with patch.object(collectors, 'fetch', fake(responses)), \
            patch('news.public_record_people.link_people', return_value={'checked': 2, 'linked': 2, 'cleared': 0,
                                                                        'unlinked': 0}) as link:
        result = zb.run('sejm', 'noc', seconds=30, force=True)
    assert result['produced'] == 2 and result['sources_left'] == 0 and result['linked'] == 2
    link.assert_called_once()
    assert ImportState.objects.get(name=zb.LINKS).cursor['linked'] == 2


def test_plan_is_offline_and_command_prints_every_source(votes_on):
    with patch.object(collectors, 'fetch') as fetch, patch('scraper.utils.fetch_feed') as transport:
        rows = zb.plan()
        out = StringIO()
        call_command('zasil_baze', '--plan', stdout=out)
        fetch.assert_not_called()
        transport.assert_not_called()
    sources = [r['source'] for r in rows]
    assert set(sources) >= set(zb.LANES['sejm']) | set(zb.LANES['inne']) | {'bzp', 'youtube'}
    votes = next(r for r in rows if r['source'] == 'votes')
    assert votes['enabled'] and votes['card_cap'] == 0 and votes['days'] is None and votes['percent'] == 0
    text = out.getvalue()
    assert 'votes' in text and 'brak ważnej karty' in text and 'Powiązania z osobami' in text
    assert all(isinstance(line, str) for line in zb.report_lines())


def test_command_runs_bounded_portion(votes_on):
    out = StringIO()
    with patch.object(collectors, 'fetch', fake([(index((1, 1)), None), (vote(1, 1), None), (b'[]', None)])):
        call_command('zasil_baze', '--zrodlo', 'votes', '--limit', '2', stdout=out)
    result = json.loads(out.getvalue())
    assert result['sources']['votes']['added'] == 2 and not result['sources']['votes']['complete']


# --- BZP: okno historii i kolejne przejścia ------------------------------------------------------------

@pytest.fixture
def bzp_source(db):
    from scraper.management.commands.configure_bzp_metadata_source import configure
    return configure('fixture')[0]


@override_settings(BZP_API_ENABLED=True)
def test_bzp_stops_at_history_floor_then_starts_forward_pass(bzp_source, monkeypatch):
    from scraper.bzp_backfill import STATE_NAME, bzp_backfill_cycle
    monkeypatch.setenv('BZP_BACKFILL_DAYS', '2')
    ImportState.objects.create(name=STATE_NAME, cursor={'cutoff': '2026-09-13', 'day': '2026-09-10', 'page': 1,
                                                        'complete': False})
    now = datetime(2026, 9, 14, 8, tzinfo=dt_timezone.utc)
    with patch('scraper.bzp_backfill.timezone.now', return_value=now), \
            patch('scraper.bzp_backfill.fetch_page') as fetch:
        assert bzp_backfill_cycle()['status'] == 'complete'
        fetch.assert_not_called()
    cursor = ImportState.objects.get(name=STATE_NAME).cursor
    assert cursor['complete'] and cursor['floor'] == '2026-09-11' and cursor['history_complete_at']
    later = datetime(2026, 9, 17, 8, tzinfo=dt_timezone.utc)
    with patch('scraper.bzp_backfill.timezone.now', return_value=later), \
            patch('scraper.bzp_backfill.fetch_page', return_value=[]) as fetch:
        result = bzp_backfill_cycle()
    assert result['status'] == 'ok' and result['day'] == '2026-09-16'
    cursor = ImportState.objects.get(name=STATE_NAME).cursor
    assert cursor['floor'] == '2026-09-14' and cursor['cutoff'] == '2026-09-16' and not cursor['complete']
    row = zb.bzp_row()
    assert row['percent'] == 100 and row['complete_at']
