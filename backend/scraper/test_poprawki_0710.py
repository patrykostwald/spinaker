"""Poprawki po wdrożeniu 6.10 (zasil_baze --plan na serwerze): ściana botów Sejmu, karty z deploy, limity kart.

Bez sieci: transport jest podmieniony, karty powstają tą samą komendą i z tymi samymi argumentami co w deploy/*.sh.
"""
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import re
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicCollectionState, PublicRecord
from scraper import nowe_zrodla as nz
from scraper import public_records as collectors
from scraper import public_record_parsers as parsers
from scraper import zasil_baze as zb

pytestmark = pytest.mark.django_db
DEPLOY = Path(__file__).resolve().parents[2] / 'deploy'
FIXTURES = Path(__file__).parent / 'fixtures' / 'public_records'
NZ_DATA = json.loads((FIXTURES / 'nowe_zrodla.json').read_text(encoding='utf-8'))


def script(name):
    return (DEPLOY / name).read_text(encoding='utf-8')


def deploy_cards():
    """Wywołania cfg z wdrozenie-0610.sh (krok 3) i zasil-baze.sh w kolejności wdrożenia: (źródło, dowód, warunki, limit)."""
    calls = []
    for name in ('wdrozenie-0610.sh', 'zasil-baze.sh'):
        text = script(name)
        doc = re.search(r'^SEJM_DOC=(\S+)$', text, re.M)[1]
        value = lambda v: v.strip('"').replace('$SEJM_DOC', doc)  # noqa: E731
        loop = re.search(r'for s in ([^;]+); do\s+cfg "\$s" (\S+) (\S+)\s*\n\s*done', text)
        if loop:
            calls += [(s, value(loop[2]), value(loop[3]), 100) for s in loop[1].split()]
        for row in re.finditer(r'^cfg ([a-z_]+) (\S+) (\S+)(?: (\d+))?\s*$', text, re.M):
            calls.append((row[1], value(row[2]), value(row[3]), int(row[4] or 100)))
    return calls


def deploy_flags():
    text = script('wdrozenie-0610.sh')
    names = re.search(r'for f in (.+?); do', text, re.S)[1].replace('\\', ' ').split()
    return [n.lower() for n in names]


def apply_deploy_cards():
    for source, evidence, terms, cap in deploy_cards():
        call_command('configure_public_records', source=source, apply=True, reviewed_by='patrykostwald',
                     evidence_url=evidence, terms_url=terms, valid_days=365, daily_cap=cap, stdout=StringIO())


def job(source, kind, url, context=None):
    state, _ = PublicCollectionState.objects.get_or_create(source=source)
    return collectors.enqueue(state, url, kind, context)[0]


# Zadania potomne (adresy, które zbieracz buduje z odpowiedzi), po jednym na każdą ścieżkę w kodzie.
SEJM = collectors.SEJM
CHILDREN = {
    'votes': [('vote', SEJM + '/votings/12/34')],
    'statements': [('transcript_index', SEJM + '/proceedings/12/2024-01-10/transcripts'),
                   ('statement', SEJM + '/proceedings/12/2024-01-10/transcripts/5')],
    'interpellations': [('question_index', SEJM + '/interpellations?sort_by=num&since=2024-01-01&offset=20&limit=20')],
    'questions': [('question_index', SEJM + '/writtenQuestions?sort_by=num&since=2024-01-01&offset=20&limit=20')],
    'assets': [('asset_profile', 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id=001&type=A'),
               ('asset_index', 'https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id=001&type=F')],
    'consultations': [('osr_text', SEJM + '/prints/123/OSR%20projekt.pdf')],
    'lobby_mswia': [('register_pdf', 'https://www.gov.pl/attachment/0c1d2e3f-aaaa-bbbb-cccc-123456789abc')],
    'lobby_sejm': [('lobby_people', 'https://www.sejm.gov.pl/sejm10.nsf/lobbing_osoby_tab.xsp')],
    'pkw': [('pkw_csv', 'https://pkw.gov.pl/uploaded_files/1700000000_sprawozdanie.csv'),
            ('pkw_page', 'https://pkw.gov.pl/finansowanie-polityki/sprawozdania-finansowe?page=2')],
    'processes': [('process', SEJM + '/processes/123-z')],
    'committees': [('committee_sittings', SEJM + '/committees/ASW/sittings')],
    'krs_changes': [('krs_extract', collectors.KRS_API + '/OdpisAktualny/0000012345?rejestr=P&format=json')],
    'videos': [('committee_transcript', SEJM + '/committees/ASW/sittings/7/html')],
    'howtheyvote': [('htv_vote', nz.HTV + '/197352'), ('htv_index', nz.htv_url(2))],
    'kohesio': [('kohesio_page', nz.kohesio_url(nz.KOHESIO_PAGE))],
    'integrity_watch': [('iw_income', nz.IW_INCOME)],
    'mileage': [('office_pdf', NZ_DATA['offices']['records'][0]['pdf_url'])],
}


def test_every_deploy_enabled_source_is_covered_by_its_own_deploy_card(monkeypatch):
    """Każde źródło włączone flagą w deploy: wszystkie adresy z seed i zadań potomnych przechodzą bramkę jego karty."""
    flags = deploy_flags()
    carded = {source for source, *_ in deploy_cards()}
    assert set(flags) <= set(collectors.SOURCES)
    assert set(flags) <= carded, 'flaga bez karty w deploy: ' + ', '.join(sorted(set(flags) - carded))
    apply_deploy_cards()
    RegisteredOrganisation.objects.create(krs_number='0000012345', name='Spółka Testowa S.A.', register='P', kind='company',
                                          official_register_url='https://wyszukiwarka-krs.ms.gov.pl/')
    for source in flags:
        state, _ = PublicCollectionState.objects.get_or_create(source=source)
        collectors.seed(state, collectors.START)
        jobs = list(state.jobs.all())
        jobs += [job(source, kind, url) for kind, url in CHILDREN.get(source, [])]
        assert jobs, source
        for item in jobs:
            provider, card = collectors.source_access(item)  # AccessDenied = karta nie pasuje do adresu zbieracza
            assert card.evidence['collector'] == source, (source, item.url)
            assert card.daily_request_cap >= 1 and provider.is_active


def test_card_cap_from_deploy_is_never_below_backfill_cap():
    """zasil_baze --plan ostrzega „karta mniejsza niż limit zasilania” - deploy musi dać kartę co najmniej tak dużą."""
    caps = {}
    for source, _, _, cap in deploy_cards():
        caps[source] = cap  # późniejsza wersja karty wygrywa, jak w bramce
    low = {s: (caps.get(s), zb.cap(s)) for s in zb.BACKFILL_CAP if s in caps and caps[s] < zb.cap(s)}
    assert not low, low


def test_plan_explains_block_from_before_the_card_and_collector_resumes(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_FTS_ENABLED', 'true')
    calls = []

    def fetch(item, token, mode=None):
        collectors.source_access(item)  # jak prawdziwy fetch: najpierw karta
        calls.append(item.url)
        PublicCollectionState.objects.filter(pk=item.state_id).update(next_request_at=timezone.now())
        return json.dumps([]).encode(), None
    with patch.object(collectors, 'fetch', side_effect=fetch):
        first = collectors.collect('fts', max_requests=1)  # beat po restarcie, zanim deploy założył karty
        assert first['status'] == 'blocked_access_review' and first['error'] == 'no_approved_instruction'
        assert not calls
        apply_deploy_cards()
        row = next(r for r in zb.plan() if r['source'] == 'fts')
        assert row['card_cap'] >= 1 and row['note'] == zb.STALE_NOTE
        second = collectors.collect('fts', max_requests=1)
    assert second['status'] != 'blocked_access_review' and calls


# --- Ściana botów (Imperva/Incapsula) na www.sejm.gov.pl i orka.sejm.gov.pl -----------------------------------

@pytest.fixture
def assets_on(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_ASSETS_ENABLED', 'true')
    apply_deploy_cards()
    state, _ = PublicCollectionState.objects.get_or_create(source='assets')
    state.since, state.cycle_started_at = collectors.START, timezone.now() - timedelta(hours=1)
    state.save()
    for mp in (1, 2, 3):
        collectors.enqueue(state, f'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id={mp:03d}&type=A', 'asset_profile',
                           {'since': '2023-11-13', 'mp_id': mp, 'name': f'Poseł {mp}'})
    return state


def test_bot_wall_detects_incapsula_page_but_not_real_content():
    assert parsers.bot_wall((FIXTURES / 'incapsula.html').read_bytes())
    assert not parsers.bot_wall((FIXTURES / 'assets.html').read_bytes())
    assert not parsers.bot_wall(b'{"id": 1}')


@pytest.mark.parametrize('transport', ['redirect_loop', 'challenge_page'])
def test_assets_behind_bot_wall_stop_with_reason_and_pause(assets_on, transport):
    """Serwer 6.10: 'error (ValueError)', 0 rekordów, kolejka 499 - pętla 302 Imperva. Teraz: jasny powód i przerwa."""
    def wall(*args, **kwargs):
        if transport == 'redirect_loop':
            raise ValueError('Too many source redirects')
        return (FIXTURES / 'incapsula.html').read_bytes(), None
    transport_mock = Mock(side_effect=wall)
    with patch.object(collectors, 'fetch_feed', transport_mock):
        result = collectors.collect('assets', max_requests=4)
        assert result['status'] == 'blocked_access_review' and result['error'] == collectors.BOT_WALL
        assert transport_mock.call_count == 1  # pierwsza ściana zatrzymuje źródło, nie 499 prób z backoffem
        state = PublicCollectionState.objects.get(source='assets')
        assert state.last_error == collectors.BOT_WALL and state.jobs.filter(done=False).count() == 3
        assert not state.jobs.exclude(last_error='').exists() and not PublicRecord.objects.exists()
        again = collectors.collect('assets', max_requests=4)  # kolejny przebieg beat w ciągu doby: bez sieci
        assert again['status'] == 'blocked_access_review' and transport_mock.call_count == 1
    row = next(r for r in zb.plan() if r['source'] == 'assets')
    assert row['note'] == zb.BOT_WALL_NOTE and 'Imperva' in zb._line(row)


def test_bot_wall_pause_ends_after_a_day(assets_on):
    with patch.object(collectors, 'fetch_feed', side_effect=ValueError('Too many source redirects')):
        collectors.collect('assets', max_requests=1)
    PublicCollectionState.objects.filter(source='assets').update(last_started_at=timezone.now() - timedelta(hours=25),
                                                                 next_request_at=None)
    with patch.object(collectors, 'fetch_feed', side_effect=ValueError('Too many source redirects')) as transport:
        collectors.collect('assets', max_requests=1)
    assert transport.call_count == 1


def test_zasil_baze_skips_walled_source_without_looping(assets_on):
    with patch.object(collectors, 'fetch_feed', side_effect=ValueError('Too many source redirects')) as transport:
        result = zb.run_source('assets', 'noc', max_requests=10)
        zb.run_source('assets', 'noc', max_requests=10)
    assert result['status'] == 'blocked_access_review' and transport.call_count == 1


def test_office_pdf_behind_bot_wall_marks_check_and_keeps_mileage_running(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_MILEAGE_ENABLED', 'true')
    state, _ = PublicCollectionState.objects.get_or_create(source='mileage')
    state.since, state.cycle_started_at = collectors.START, timezone.now()
    state.save()
    office = collectors.enqueue(state, nz.OFFICES, 'office_export')[0]
    collectors.handle(office, json.dumps(NZ_DATA['offices']).encode(), None)
    office.done = True
    office.save(update_fields=['done'])
    assert state.jobs.filter(kind='office_pdf', done=False).exists()

    def fetch(item, token, mode=None):
        PublicCollectionState.objects.filter(pk=item.state_id).update(next_request_at=timezone.now())
        raise collectors.BotWall()
    with patch.object(collectors, 'fetch', side_effect=fetch) as transport:
        result = collectors.collect('mileage', max_requests=5)
    assert result['status'] == 'ok' and transport.call_count == 1
    assert not state.jobs.filter(done=False).exists()
    report = PublicRecord.objects.get(source='mileage', kind='office_report')
    assert report.data['pdf_check'] == collectors.OPTIONAL_WALL_KINDS['office_pdf']


def test_own_parser_error_code_is_visible_instead_of_bare_valueerror(monkeypatch):
    monkeypatch.setenv('PUBLIC_RECORDS_ASSETS_ENABLED', 'true')
    state, _ = PublicCollectionState.objects.get_or_create(source='assets')
    item = collectors.enqueue(state, 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id=001&type=A', 'asset_profile',
                              {'since': '2023-11-13', 'mp_id': 1, 'name': 'Poseł'})[0]

    def fetch(job_, token, mode=None):
        PublicCollectionState.objects.filter(pk=job_.state_id).update(next_request_at=timezone.now())
        return b'<html><a href="/inne">Inna strona</a></html>', None
    with patch.object(collectors, 'fetch', side_effect=fetch), patch.object(collectors, 'source_access', Mock()):
        result = collectors.collect('assets', max_requests=1)
    item.refresh_from_db()
    assert result['status'] == 'error' and result['error'] == 'ValueError: asset_navigation_missing'
    assert item.last_error == 'ValueError: asset_navigation_missing'
