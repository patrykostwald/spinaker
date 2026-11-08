from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from news.models import FetchAttempt, ImportState, Source, SourceAccessInstruction
from scraper import public_institution_approval as approval
from scraper.utils import _fetch_fingerprint


pytestmark = pytest.mark.django_db
FEED = b'<rss version="2.0"><channel><title>News</title><item><title>Title</title><link>https://www.gov.pl/web/test/news</link><description>Summary</description></item></channel></rss>'


@pytest.fixture(autouse=True)
def network():
    # Mock only the socket-facing transport: real robots handling and feed
    # validation remain exercised; no external requests or paid calls.
    def raw(address):
        return {'status': 200, 'raw': b'User-agent: *\nAllow: /' if address.endswith('/robots.txt') else FEED, 'headers': {}}
    with patch('scraper.source_probe.ProbeNetwork.raw', side_effect=raw) as mocked:
        yield mocked


def source(**fields):
    return Source.objects.create(**{'name': 'Instytucja testowa', 'source_type': 'institution',
        'url': 'https://www.gov.pl/web/test', 'rss_url': 'https://www.gov.pl/web/test/rss',
        'catalog_stage': 'candidate', 'is_active': False, 'scrape_enabled': False, **fields})


def run(apply=True):
    out = StringIO()
    call_command('approve_public_institution_sources', apply=apply, stdout=out)
    return out.getvalue()


def test_working_rss_card_and_idempotence(network):
    row = source()
    assert 'Zatwierdzono: 1' in run()
    card = row.access_instructions.get()
    assert (card.status, card.channel, card.allowed_scope) == ('approved', 'rss', 'metadata')
    assert card.daily_request_cap == 24
    assert card.valid_until - card.reviewed_at == timedelta(days=90)
    assert card.reviewed_by == 'hurtowa decyzja właściciela 3.10.2026'
    assert card.evidence['channel_url'] == row.rss_url
    assert 'bez pełnej treści' in card.evidence['scope']
    assert card.allowed_path_patterns == ['/web/test/rss']
    card.full_clean()
    row.refresh_from_db()
    assert row.catalog_stage == 'configured' and row.is_active and row.scrape_enabled
    assert network.call_count == 2  # robots and one feed
    assert 'Aktualna zatwierdzona karta' in run()
    assert row.access_instructions.count() == 1
    assert network.call_count == 2


def test_preview_never_writes_even_probe_state():
    row = source()
    with CaptureQueriesContext(connection) as queries:
        assert 'Do zatwierdzenia w podglądzie: 1' in run(apply=False)
    assert not any(q['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE'} for q in queries)
    assert not SourceAccessInstruction.objects.exists()
    assert not ImportState.objects.exists()
    row.refresh_from_db()
    assert row.catalog_stage == 'candidate' and not row.is_active


@pytest.mark.parametrize('fields', [
    {'source_type': 'portal'}, {'source_type': 'newspaper'}, {'source_type': 'rss'},
    {'url': 'https://gov.pl.publisher.example/news'}, {'url': 'https://notgov.pl'},
    {'rss_url': 'https://publisher.example/feed'}, {'catalog_stage': 'excluded'},
])
def test_media_unknown_domains_and_excluded_are_not_approved(fields, network):
    source(**fields)
    assert 'Pominięto: 1' in run()
    assert not SourceAccessInstruction.objects.exists()
    network.assert_not_called()


@pytest.mark.parametrize('status', ['suspended', 'contact_required', 'rejected'])
def test_newer_blocking_card_is_preserved(status, network):
    row = source()
    SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status='approved', version=1)
    blocked = SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status=status, version=2)
    # An unrelated later card cannot cancel the channel's refusal.
    SourceAccessInstruction.objects.create(source=row, channel='api', endpoint=row.url + '/api', status='draft', version=3)
    assert f'Decyzja blokująca: {status}' in run()
    assert row.access_instructions.count() == 3
    blocked.refresh_from_db()
    assert blocked.status == status
    network.assert_not_called()


@pytest.mark.parametrize('status', [403, 404, 410, 500])
def test_last_http_failure_is_not_retried(status, network):
    row = source()
    card = SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status='draft')
    FetchAttempt.objects.create(source=row, instruction=card, instruction_version=1,
        channel='rss', requested_kind='feed', url_fingerprint=_fetch_fingerprint(row.rss_url),
        url_host='www.gov.pl', outcome='http_error', http_status=status, network_started=True)
    # A later local gate refusal must not hide the real HTTP failure.
    FetchAttempt.objects.create(source=row, channel='rss', requested_kind='feed',
        url_fingerprint=_fetch_fingerprint(row.rss_url), url_host='www.gov.pl',
        outcome='refused_no_instruction', error_code='no_approved_instruction')
    output = run()
    assert str(status) in output and row.name in output
    if status == 403:
        assert 'szukać innego oficjalnego kanału' in output
    assert not row.access_instructions.filter(status='approved').exists()
    network.assert_not_called()


def test_successful_previous_fetch_needs_no_probe(network):
    row = source()
    card = SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status='draft')
    FetchAttempt.objects.create(source=row, instruction=card, instruction_version=1,
        channel='rss', requested_kind='feed', url_fingerprint=_fetch_fingerprint(row.rss_url),
        url_host='www.gov.pl', outcome='ok', http_status=200, network_started=True)
    assert 'Zatwierdzono: 1' in run()
    assert row.access_instructions.get(version=2).allowed_scope == 'metadata'
    network.assert_not_called()


@pytest.mark.parametrize('kind', ['feed_403', 'robots_403', 'robots_deny', 'html', 'redirect'])
def test_probe_respects_blocks_and_validates_channel(kind, network):
    row = source()
    def response(address):
        robots = address.endswith('/robots.txt')
        if kind == 'robots_403' or (kind == 'feed_403' and not robots):
            return {'status': 403, 'raw': b'', 'headers': {}}
        if robots:
            return {'status': 200, 'raw': b'User-agent: *\nDisallow: /' if kind == 'robots_deny' else b'', 'headers': {}}
        if kind == 'redirect':
            return {'status': 302, 'location': 'https://publisher.example/feed', 'raw': b'', 'headers': {}}
        return {'status': 200, 'raw': b'<html>Home</html>', 'headers': {}}
    network.side_effect = response
    output = run()
    assert 'Pominięto: 1' in output
    assert not row.access_instructions.exists()
    if '403' in kind:
        assert '403: szukać innego oficjalnego kanału: 1' in output and row.name in output
    assert all('publisher.example' not in call.args[0] for call in network.call_args_list)
    count = network.call_count
    run()  # Persisted failed probe prevents another request.
    assert network.call_count == count


def test_api_card_is_metadata_only(network):
    row = source(url='https://stat.gov.pl', rss_url='')
    network.side_effect = lambda address: {'status': 200, 'raw': b'' if address.endswith('/robots.txt') else b'{"results":[{"id":"1","name":"A"}]}', 'headers': {}}
    run()
    card = row.access_instructions.get()
    assert card.channel == 'api' and card.allowed_scope == 'metadata'
    assert card.endpoint == 'https://bdl.stat.gov.pl/api/v1/subjects?lang=pl&format=json'


def test_concurrent_suspension_is_rechecked_before_save(network):
    row = source()
    original = network.side_effect
    def response(address):
        if not address.endswith('/robots.txt'):
            SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url, status='suspended')
        return original(address)
    network.side_effect = response
    assert 'Decyzja blokująca: suspended' in run()
    assert not row.access_instructions.filter(status='approved').exists()


def test_known_legacy_403_without_fetch_attempt_is_not_retried(network):
    source(last_error='HTTP 403', last_attempted=timezone.now())
    assert 'szukać innego oficjalnego kanału' in run()
    network.assert_not_called()


def test_audited_channel_without_rss_field(network):
    row = source(rss_url='')
    ImportState.objects.create(name=f'source-check:{row.pk}', cursor={
        'signature': approval.source_signature(row), 'checked_at': timezone.now().isoformat(),
        'rss': {'status': 'working', 'url': row.url + '/rss'},
    })
    run()
    row.refresh_from_db()
    assert row.rss_url == row.url + '/rss'
    assert row.access_instructions.get().allowed_scope == 'metadata'
    network.assert_not_called()


def test_stale_audit_does_not_authorise_changed_channel(network):
    row = source()
    ImportState.objects.create(name=f'source-check:{row.pk}', cursor={
        'signature': 'stale', 'checked_at': timezone.now().isoformat(),
        'rss': {'status': 'working', 'url': row.rss_url},
    })
    run()
    assert network.call_count == 2


def test_new_channel_does_not_reuse_old_endpoint_success(network):
    row = source()
    card = SourceAccessInstruction.objects.create(source=row, channel='rss', endpoint=row.rss_url + '-old', status='draft')
    FetchAttempt.objects.create(source=row, instruction=card, instruction_version=1,
        channel='rss', requested_kind='feed', url_fingerprint=_fetch_fingerprint(card.endpoint),
        url_host='www.gov.pl', outcome='ok', http_status=200, network_started=True)
    run()
    assert network.call_count == 2


def test_probe_http_limit():
    network = approval.ApprovalProbeNetwork()
    for _ in range(8):
        network.raw('https://www.gov.pl/rss')
    with pytest.raises(approval.ProbeError, match='probe_request_limit'):
        network.raw('https://www.gov.pl/rss')


def test_approved_rss_import_ignores_full_content_and_images():
    from news.models import Article
    from scraper.rss_scraper import scrape_rss_source
    row = source()
    run()
    raw = b'''<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
        <channel><title>News</title><item><title>Title</title>
        <link>https://www.gov.pl/web/test/news</link><description>Summary</description>
        <content:encoded>Full content must not be stored</content:encoded>
        <enclosure url="https://www.gov.pl/photo.jpg" type="image/jpeg" />
        </item></channel></rss>'''
    with patch('scraper.rss_scraper.fetch_feed', return_value=raw):
        scrape_rss_source(row.pk)
    article = Article.objects.get(source=row)
    assert article.description == 'Summary' and not article.image_url
    assert not hasattr(article, 'content')
