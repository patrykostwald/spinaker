from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pytest
from django.core.cache import cache
from news.models import Article, Source
from scraper.catalog import RSS_SOURCES, INSTITUTIONS, TWITTER_POLITICIANS, NEWSAPI_TOPICS
from scraper.gdelt_scraper import scrape_gdelt, _parse_gdelt_date
from scraper.newsapi_scraper import scrape_newsapi_batch
from scraper.rss_scraper import scrape_rss_source, scrape_rss_sources
from scraper.twitter_scraper import scrape_twitter_politicians
from scraper.utils import parse_published, safe_url, reserve_budget

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

def response(payload):
    return MagicMock(json=lambda: payload, raise_for_status=lambda: None)

def test_catalog():
    assert len(RSS_SOURCES) == 43  # The brief labels this as 42, but lists 43.
    assert len(INSTITUTIONS) == 16
    assert len(TWITTER_POLITICIANS) == 40
    assert len(NEWSAPI_TOPICS) == 20

def test_dates_and_urls():
    assert _parse_gdelt_date('20250120T143000Z') == datetime(2025, 1, 20, 14, 30, tzinfo=timezone.utc)
    assert parse_published('Mon, 20 Jan 2025 14:30:00 +0000').hour == 14
    assert safe_url('javascript:alert(1)') == ''
    assert safe_url('https://example.org/x') == 'https://example.org/x'


@patch('scraper.utils.socket.getaddrinfo')
def test_private_fetch_is_rejected_before_connection(resolve):
    from scraper.utils import fetch_feed
    resolve.return_value = [(2, 1, 6, '', ('127.0.0.1', 80))]
    with patch('urllib3.HTTPConnectionPool') as pool:
        with pytest.raises(ValueError, match='public'):
            fetch_feed('http://source.example/a')
        pool.assert_not_called()


@patch('scraper.utils.socket.getaddrinfo')
def test_public_fetch_pins_ip_and_rejects_private_redirect(resolve):
    from scraper.utils import fetch_feed
    resolve.side_effect = [[(2, 1, 6, '', ('8.8.8.8', 443))], [(2, 1, 6, '', ('10.0.0.1', 443))]]
    with patch('urllib3.HTTPSConnectionPool') as pool:
        pool.return_value.urlopen.return_value = MagicMock(status=302, headers={'Location': 'https://internal.example/a'})
        with pytest.raises(ValueError, match='public'):
            fetch_feed('https://source.example/a')
        assert pool.call_args.args[0] == '8.8.8.8'
        assert pool.call_args.kwargs['assert_hostname'] == 'source.example'
        assert pool.call_count == 1

@pytest.mark.django_db
@patch('scraper.gdelt_scraper.requests.get')
def test_scrape_gdelt(mock_get):
    mock_get.return_value = response({'articles': [{'url': 'https://example.org/a', 'title': 'Test', 'seendate': '20250120T143000Z'}]})
    assert scrape_gdelt('Sejm') == 1
    assert scrape_gdelt('Sejm') == 0
    a = Article.objects.get()
    assert a.published_date is None and a.discovered_at.year == 2025
    assert a.source.total_articles == 1
    mock_get.side_effect = TimeoutError()
    assert scrape_gdelt('Sejm') == 0

@pytest.mark.django_db
@patch('scraper.newsapi_scraper.requests.get')
def test_scrape_newsapi(mock_get, settings):
    settings.NEWSAPI_KEY = 'secret'
    settings.NEWSAPI_ENABLED = True
    mock_get.return_value = response({'status': 'ok', 'articles': [{'url': 'https://example.org/news', 'title': 'Budżet', 'publishedAt': '2025-01-20T12:00:00Z', 'author': None, 'description': '<p>Opis</p>'}]})
    assert scrape_newsapi_batch() == 1
    assert Article.objects.get().description == 'Opis'
    assert Article.objects.get().author == ''
    assert 'language' not in mock_get.call_args.kwargs['params']
    assert 'apiKey' not in mock_get.call_args.kwargs['params']

@pytest.mark.django_db
@patch('scraper.rss_scraper.fetch_feed')
def test_rss_dedup_counters_and_dates(fetch):
    fetch.return_value = b'''<rss version="2.0"><channel><title>Test</title><item><title>News</title><link>https://example.org/1</link><pubDate>Mon, 20 Jan 2025 14:30:00 +0000</pubDate><description>Summary</description></item></channel></rss>'''
    source = Source.objects.create(name='Institution', url='https://example.org', rss_url='https://example.org/rss', source_type='institution')
    assert scrape_rss_source(source.pk) == 1
    assert scrape_rss_source(source.pk) == 0
    source.refresh_from_db()
    assert source.total_articles == 1 and source.last_scraped is not None
    assert Article.objects.get().category == 'statement'
    source.scrape_enabled = False
    source.save()
    fetch.reset_mock()
    assert scrape_rss_source(source.pk) == 0
    fetch.assert_not_called()

@pytest.mark.django_db
@patch('scraper.rss_scraper.fetch_feed')
def test_rss_failures_do_not_stop_other_sources(fetch):
    fetch.side_effect = TimeoutError()
    assert scrape_rss_sources() == 0
    expected_feeds = set(Source.objects.exclude(rss_url='').values_list('rss_url', flat=True))
    assert {call.args[0] for call in fetch.call_args_list} == expected_feeds
    assert fetch.call_count == len(expected_feeds)

@pytest.mark.django_db
@patch('scraper.twitter_scraper.requests.get')
def test_twitter_disabled(mock_get, settings):
    settings.TWITTER_ENABLED = False
    settings.TWITTER_BEARER_TOKEN = 'secret'
    assert scrape_twitter_politicians() == 0
    mock_get.assert_not_called()

@pytest.mark.django_db
@patch('scraper.twitter_scraper.TWITTER_POLITICIANS', {'test': {'user_id': 'wrong'}})
@patch('scraper.twitter_scraper.requests.get')
def test_twitter_identity_and_cursor(mock_get, settings):
    settings.TWITTER_ENABLED = True
    settings.TWITTER_BEARER_TOKEN = 'secret'
    mock_get.side_effect = [response({'data': {'id': '42', 'name': 'Verified'}}), response({'data': [{'id': '123', 'text': 'Test post', 'created_at': '2025-01-20T12:00:00Z', 'public_metrics': {'like_count': 8}}]})]
    assert scrape_twitter_politicians() == 1
    assert '/42/tweets' in mock_get.call_args.args[0]
    assert Source.objects.get().last_tweet_id == '123'
    assert Article.objects.get().category == "tweet" and Article.objects.get().likes_count == 8
    mock_get.side_effect = None
    mock_get.return_value = response({'data': []})
    assert scrape_twitter_politicians() == 0
    assert mock_get.call_args.kwargs['params']['since_id'] == '123'

def test_budget_reservations():
    assert reserve_budget('test', 10, 20, 60)
    assert reserve_budget('test', 10, 20, 60)
    assert not reserve_budget('test', 10, 20, 60)


def test_missing_dates_are_not_invented():
    assert parse_published(None) is None
    assert parse_published('invalid') is None
    assert parse_published('January 20') is None


@pytest.mark.django_db
def test_seeding_preserves_increased_frequency():
    from scraper.rss_scraper import seed_sources
    seed_sources()
    source = Source.objects.filter(source_type='institution').first()
    source.scrape_frequency_minutes = 30
    source.save()
    seed_sources()
    source.refresh_from_db()
    assert source.scrape_frequency_minutes == 30


@pytest.mark.django_db
@patch('scraper.rss_scraper.fetch_feed')
def test_rss_updated_date_is_not_publication(fetch):
    fetch.return_value = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Test</title><entry><title>Test</title><link href="https://example.org/a"/><updated>2026-09-01T12:00:00Z</updated></entry></feed>'
    source = Source.objects.create(name='Test', url='https://example.org', rss_url='https://example.org/feed')
    assert scrape_rss_source(source.pk) == 1
    assert Article.objects.get().published_date is None


@pytest.mark.django_db
@patch('scraper.newsapi_scraper.requests.get')
def test_newsapi_reads_next_page(mock_get, settings):
    from scraper.newsapi_scraper import _scrape_topic
    from news.models import ImportState
    settings.NEWSAPI_DAILY_REQUEST_LIMIT = 100
    mock_get.side_effect = [response({'totalResults': 2, 'articles': [{'url': 'https://example.org/a', 'title': 'A'}]}), response({'totalResults': 2, 'articles': [{'url': 'https://example.org/b', 'title': 'B'}]})]
    assert _scrape_topic('test', 'test-only-key') == 2
    assert mock_get.call_args.kwargs['params']['page'] == 2
    assert ImportState.objects.get().last_success is not None


@pytest.mark.django_db
@patch('scraper.newsapi_scraper.requests.get')
def test_newsapi_partial_import_keeps_cursor(mock_get, settings):
    from scraper.newsapi_scraper import _scrape_topic
    from news.models import ImportState
    settings.NEWSAPI_DAILY_REQUEST_LIMIT = 1
    mock_get.return_value = response({'totalResults': 2, 'articles': [{'url': 'https://example.org/a', 'title': 'A'}]})
    _scrape_topic('test', 'test-only-key')
    state = ImportState.objects.get()
    assert state.last_success is None and state.last_error
    assert Article.objects.count() == 1

@pytest.mark.django_db
@patch('scraper.twitter_scraper.TWITTER_POLITICIANS', {'test': {'user_id': '42'}})
@patch('scraper.twitter_scraper.requests.get')
def test_x_reads_all_pages_before_advancing_cursor(mock_get, settings):
    settings.TWITTER_ENABLED = True
    settings.TWITTER_BEARER_TOKEN = 'secret'
    source = Source.objects.create(name='Test', url='https://x.com/test', twitter_user_id='42', last_tweet_id='100')
    mock_get.side_effect = [response({'data': [{'id': '120', 'text': 'Newer'}], 'meta': {'next_token': 'page2'}}), response({'data': [{'id': '110', 'text': 'Older'}]})]
    assert scrape_twitter_politicians() == 2
    source.refresh_from_db()
    assert source.last_tweet_id == '120'
    assert mock_get.call_args.kwargs['params']['pagination_token'] == 'page2'
    assert cache.get('budget:twitter:' + __import__('django.utils.timezone', fromlist=['now']).now().strftime('%Y-%m')) == 2

@pytest.mark.django_db
@patch('scraper.twitter_scraper.TWITTER_POLITICIANS', {'test': {'user_id': '42'}})
@patch('scraper.twitter_scraper.requests.get')
def test_x_partial_failure_preserves_cursor(mock_get, settings):
    settings.TWITTER_ENABLED = True
    settings.TWITTER_BEARER_TOKEN = 'secret'
    source = Source.objects.create(name='Test', url='https://x.com/test', twitter_user_id='42', last_tweet_id='100')
    mock_get.side_effect = [response({'data': [{'id': '120', 'text': 'Newer'}], 'meta': {'next_token': 'page2'}}), TimeoutError()]
    scrape_twitter_politicians()
    source.refresh_from_db()
    assert source.last_tweet_id == '100' and source.last_error == 'TimeoutError'


@pytest.mark.django_db
def test_html_response_never_counts_as_successful_feed(monkeypatch):
    from django.utils import timezone as dj_timezone
    source = Source.objects.create(name='Publisher', url='https://example.org', rss_url='https://example.org/feed', last_scraped=dj_timezone.now())
    previous = source.last_scraped
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', lambda url: b'<html><head><title>Welcome</title></head><body>Not an RSS feed</body></html>')
    assert scrape_rss_source(source.pk) == 0
    source.refresh_from_db()
    assert source.last_scraped == previous
    assert source.last_attempted is not None and source.last_error
    assert not Article.objects.exists()


@pytest.mark.django_db
def test_valid_empty_feed_is_successful(monkeypatch):
    source = Source.objects.create(name='Publisher', url='https://example.org', rss_url='https://example.org/feed')
    monkeypatch.setattr('scraper.rss_scraper.fetch_feed', lambda url: b'<?xml version="1.0"?><rss version="2.0"><channel><title>Publisher</title><link>https://example.org</link><description>Updates</description></channel></rss>')
    assert scrape_rss_source(source.pk) == 0
    source.refresh_from_db()
    assert source.last_scraped is not None and not source.last_error


@pytest.mark.django_db
def test_priority_sources_poll_faster_without_slowing_other_sources():
    from scraper.rss_scraper import seed_sources
    seed_sources()
    a = Source.objects.get(name='Onet Wiadomości')
    assert a.scrape_frequency_minutes == 5
    a.scrape_frequency_minutes = 2
    a.save()
    ordinary = Source.objects.get(name='Kultura Liberalna')
    old_interval = ordinary.scrape_frequency_minutes
    seed_sources()
    a.refresh_from_db(); ordinary.refresh_from_db()
    assert a.scrape_frequency_minutes == 2
    assert ordinary.scrape_frequency_minutes == old_interval
    assert Source.objects.get(name='NIK').scrape_frequency_minutes == 240
