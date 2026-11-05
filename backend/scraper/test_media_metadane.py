"""Metadane mediów (właściciel 6.10): komenda zatwierdz_media_metadane, strażnik importu RSS i sprawdzenie robots/TDM.
Wszystko bez sieci: transport robots.txt i kanał są podmienione."""
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from news.agent_models import AgentNote
from news.models import Article, FetchAttempt, Source, SourceAccessInstruction
from scraper import media_metadata as media
from scraper.rss_scraper import scrape_rss_source

pytestmark = pytest.mark.django_db

FEED = (b'<rss xmlns:media="http://search.yahoo.com/mrss/" version="2.0"><channel><title>Dziennik</title>'
        b'<item><title>Rzad przyjal projekt</title><link>https://dziennik.example/a/1</link>'
        b'<description>Pelny lead artykulu, ktorego nie wolno przechowywac.</description><author>Jan Autor</author>'
        b'<category>Polityka</category><pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate>'
        b'<media:content url="https://dziennik.example/foto.jpg" type="image/jpeg" /></item></channel></rss>')
ALLOW = b'User-agent: *\nAllow: /\n'


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def source(**fields):
    return Source.objects.create(**{'name': 'Dziennik Przykładowy', 'source_type': 'portal', 'url': 'https://dziennik.example',
        'rss_url': 'https://dziennik.example/rss', 'catalog_stage': 'candidate', 'is_active': False, 'scrape_enabled': False,
        'last_error': 'no_approved_instruction', **fields})


def run(plan=False):
    out = StringIO()
    call_command('zatwierdz_media_metadane', plan=plan, stdout=out)
    return out.getvalue()


def robots(content=ALLOW, status=200):
    def raw(address):
        assert address.endswith('/robots.txt'), 'w trybie metadanych sieć idzie tylko po robots.txt'
        return {'status': status, 'raw': content, 'headers': {}}
    return raw


def test_plan_prints_card_and_writes_nothing():
    row = source()
    with CaptureQueriesContext(connection) as queries:
        output = run(plan=True)
    assert 'KARTA: Dziennik Przykładowy' in output and 'Do zapisu: karty: 1' in output
    assert not any(q['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE'} for q in queries)
    assert not SourceAccessInstruction.objects.exists()
    row.refresh_from_db()
    assert row.catalog_stage == 'candidate' and not row.is_active and row.last_error == 'no_approved_instruction'


def test_card_is_metadata_only_and_run_is_idempotent():
    row = source()
    assert 'Zapisano: karty: 1' in run()
    card = row.access_instructions.get()
    card.full_clean()
    assert (card.status, card.channel, card.allowed_scope, card.endpoint) == ('approved', 'rss', 'metadata', row.rss_url)
    assert card.evidence['mode'] == media.MODE and card.evidence['fields'] == ['title', 'published_date', 'source', 'url']
    assert 'bez treści' in card.evidence['scope'] and any('LEGAL 6' in line for line in card.evidence['legal'])
    assert card.daily_request_cap == 24 and card.valid_until - card.reviewed_at == timedelta(days=90)
    assert card.allowed_path_patterns == ['/rss'] and card.reviewed_by == media.REVIEWED_BY
    row.refresh_from_db()
    assert row.catalog_stage == 'configured' and row.is_active and row.scrape_enabled and row.last_error == ''
    assert 'Aktualna karta już przepuszcza kanał: 1' in run()
    assert row.access_instructions.count() == 1


def test_valid_card_on_disabled_source_only_enables_it():
    row = source()
    now = timezone.now()
    SourceAccessInstruction.objects.create(source=row, version=1, status='approved', channel='rss', allowed_scope='metadata',
        endpoint=row.rss_url, terms_url=row.rss_url, evidence={'basis': 'test'}, reviewed_at=now, reviewed_by='test',
        minimum_interval_seconds=3, daily_request_cap=24, valid_until=now + timedelta(days=10))
    assert 'WŁĄCZONO' in run() and row.access_instructions.count() == 1
    row.refresh_from_db()
    assert row.is_active and row.scrape_enabled and row.catalog_stage == 'configured'


@pytest.mark.parametrize('fields,reason', [
    ({'source_type': 'institution'}, 'karty: 0'),
    ({'rss_url': ''}, 'Brak publicznego kanału RSS'),
    ({'rss_url': 'https://news.google.com/rss/search?q=x'}, 'Google News'),
    ({'catalog_stage': 'excluded'}, 'wykluczone'),
    ({'last_error': 'HTTP 404'}, 'do naprawy adresu'),
])
def test_out_of_scope_and_broken_feeds_are_skipped(fields, reason):
    source(**fields)
    output = run()
    assert reason in output and 'LIST:' not in output
    assert not SourceAccessInstruction.objects.exists() and not AgentNote.objects.exists()


@pytest.mark.parametrize('fields,reason', [
    ({'url': 'https://wiadomosci.wp.pl', 'rss_url': 'https://wiadomosci.wp.pl/rss.xml'}, 'rejestr zgód'),
    ({'catalog_notes': 'Redakcja ma paywall na większości tekstów.'}, 'paywall'),
    ({'last_error': 'HTTP 403'}, '403'),
    ({'last_error': 'robots_disallowed'}, 'robots'),
])
def test_recorded_refusal_goes_to_consent_letters_not_card(fields, reason):
    row = source(**fields)
    output = run()
    assert f'LIST: {row.name}' in output and reason in output and 'do listu o zgodę: 1' in output
    assert not SourceAccessInstruction.objects.exists()
    note = AgentNote.objects.get()
    assert (note.agent, note.kind, note.status) == ('prawnik', 'request', 'pending')
    assert note.sources[0]['rss_url'] == row.rss_url and reason in note.body
    row.refresh_from_db()
    assert not row.is_active
    run()
    assert AgentNote.objects.count() == 1, 'kolejny przebieg odświeża tę samą notatkę'


def test_blocking_card_is_preserved_and_listed():
    row = source()
    SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status='contact_required', version=1)
    output = run()
    assert 'LIST:' in output and 'contact_required' in output
    assert row.access_instructions.count() == 1


def test_plan_lists_letters_without_saving_note():
    source(catalog_notes='opt-out w regulaminie')
    output = run(plan=True)
    assert 'LIST:' in output and 'w planie bez zapisu' in output
    assert not AgentNote.objects.exists()


def approved(row, mode=True):
    run()
    row.refresh_from_db()
    card = row.access_instructions.get()
    if not mode:
        card.evidence = {'basis': 'instytucja'}
        card.save(update_fields=['evidence'])
    return card


def test_import_in_metadata_mode_keeps_only_title_date_outlet_url(monkeypatch):
    row = source()
    approved(row)
    fetch = Mock(return_value=FEED)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)
    with patch('scraper.source_probe.ProbeNetwork.raw', side_effect=robots()) as net:
        assert scrape_rss_source(row.pk) == 1
        assert scrape_rss_source(row.pk) == 0
    assert net.call_count == 1, 'robots.txt raz na dobę (pamięć podręczna)'
    assert fetch.call_count == 2
    article = Article.objects.get()
    assert article.title == 'Rzad przyjal projekt' and article.url == 'https://dziennik.example/a/1'
    assert article.source_id == row.pk and article.published_date is not None
    assert article.description == '' and article.author == '' and article.image_url == '' and article.tags == []
    row.refresh_from_db()
    assert row.last_error == '' and row.last_scraped is not None


def test_import_without_media_mode_keeps_feed_summary(monkeypatch):
    row = source()
    approved(row, mode=False)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', lambda url, **_: FEED)
    with patch('scraper.source_probe.ProbeNetwork.raw') as net:
        assert scrape_rss_source(row.pk) == 1
    net.assert_not_called()
    assert Article.objects.get().description.startswith('Pelny lead')


@pytest.mark.parametrize('content,status,reason', [
    (b'User-agent: *\nDisallow: /\n', 200, 'robots_disallowed'),
    (b'User-agent: ContextBeforeContent\nDisallow: /rss\n', 200, 'robots_disallowed'),
    (b'User-agent: *\nAllow: /\nContent-Signal: search=no, ai-train=no\n', 200, 'tdm_opt_out:search=no'),
    (b'User-agent: *\nAllow: /\ntdm-reservation: 1\n', 200, 'tdm_opt_out:tdm-reservation'),
    (b'', 403, 'robots_http_403'),
])
def test_import_skips_source_on_robots_or_tdm_opt_out(monkeypatch, content, status, reason):
    row = source()
    card = approved(row)
    fetch = Mock(return_value=FEED)
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', fetch)
    with patch('scraper.source_probe.ProbeNetwork.raw', side_effect=robots(content, status)):
        assert scrape_rss_source(row.pk) == 0
    fetch.assert_not_called()
    assert not Article.objects.exists()
    attempt = FetchAttempt.objects.get()
    attempt.full_clean()
    assert (attempt.outcome, attempt.error_code, attempt.instruction_id, attempt.network_started) == ('blocked_robots', reason, card.pk, False)
    row.refresh_from_db()
    assert row.last_error == reason


@pytest.mark.parametrize('content,status', [(b'', 404), (b'<html>blokada</html>', 200), (b'User-agent: *\nAllow: /\nContent-Signal: ai-train=no\n', 200)])
def test_absent_html_or_training_only_signal_is_not_an_opt_out(content, status):
    network = Mock()
    network.raw.return_value = {'status': status, 'raw': content, 'headers': {}}
    assert media.robots_verdict('https://dziennik.example/rss', network)['ok']


def test_network_error_on_robots_is_not_a_publisher_decision():
    network = Mock()
    network.raw.side_effect = OSError('dns')
    verdict = media.robots_verdict('https://dziennik.example/rss', network)
    assert verdict['ok'] and verdict['note'].startswith('robots_error')


def test_registry_lists_backlog_hosts_without_network():
    assert any('wp.pl' in host for host in media.registry())
    assert media.refusal(Source(name='PAP', source_type='portal', url='https://www.pap.pl/', rss_url='https://www.pap.pl/rss'), []).startswith('rejestr zgód')
