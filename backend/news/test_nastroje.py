"""Raport nastrojów bez sieci: X (liczniki + wyszukiwanie), YouTube, Wykop, RSS i Mercury podmienione. Strażnik budżetu X liczy
odczyty, strażnik jednostek YouTube liczy jednostki, filtr odrzuca reklamy i powtórki, Wilson, wagi, cytaty bez autorów,
pliki HTML i CSV bez identyfikatorów, surowe dane tylko z --zachowaj, tryb --plan bez odczytu wpisów."""
import json
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from news import inception, nastroje, youtube_collect
from news.models import Article, ImportState, Source
from news.political_polling import PoliticalReadError

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=dt_timezone.utc)

ROWS = [
    {'id': '1900000000000000001', 'author_id': '7001', 'lang': 'pl', 'created_at': '2026-10-06T10:00:00.000Z',
     'text': '@ksiazulo Pizza z Żabki zaskakująco dobra, ciasto chrupiące https://t.co/x1', 'public_metrics': {'like_count': 40}},
    {'id': '1900000000000000002', 'author_id': '7002', 'lang': 'pl', 'created_at': '2026-10-06T11:00:00.000Z',
     'text': 'Pizza Książulo w Żabce to porażka, sucha i za droga', 'public_metrics': {'like_count': 90}},
    {'id': '1900000000000000003', 'author_id': '7003', 'lang': 'pl', 'created_at': '2026-10-05T09:00:00.000Z',
     'text': 'Czy pizza Książulo jest już w każdej Żabce?', 'public_metrics': {'like_count': 2}},
    {'id': '1900000000000000004', 'author_id': '7004', 'lang': 'en', 'created_at': '2026-10-05T09:00:00.000Z',
     'text': 'Pizza Książulo Żabka looks fine honestly', 'public_metrics': {'like_count': 1}},
    {'id': '1900000000000000005', 'author_id': '7005', 'lang': 'pl', 'created_at': '2026-10-05T09:00:00.000Z',
     'text': 'Kod rabatowy na pizza Żabka Książulo, link w bio #promo #pizza #zabka #ksiazulo #food', 'public_metrics': {'like_count': 0}},
    {'id': '1900000000000000006', 'author_id': '7002', 'lang': 'pl', 'created_at': '2026-10-05T12:00:00.000Z',
     'text': 'Pizza Książulo w Żabce to porażka, sucha i za droga!!!', 'public_metrics': {'like_count': 3}},
    {'id': '1900000000000000007', 'author_id': '7006', 'lang': 'pl', 'created_at': '2026-10-05T13:00:00.000Z',
     'text': 'RT pizza Książulo Żabka', 'referenced_tweets': [{'type': 'retweeted', 'id': '1'}], 'public_metrics': {'like_count': 0}},
    {'id': '1900000000000000008', 'author_id': '7007', 'lang': 'pl', 'created_at': '2026-10-05T14:00:00.000Z',
     'text': 'Książulo robi świetną robotę, pizza smakuje lepiej niż z sieciówek', 'public_metrics': {'like_count': 70}},
]
COUNTS = {'data': [{'start': '2026-10-04T00:00:00.000Z', 'end': '2026-10-05T00:00:00.000Z', 'tweet_count': 1},
                   {'start': '2026-10-05T00:00:00.000Z', 'end': '2026-10-06T00:00:00.000Z', 'tweet_count': 40},
                   {'start': '2026-10-06T00:00:00.000Z', 'end': '2026-10-07T00:00:00.000Z', 'tweet_count': 25},
                   {'start': '2026-10-07T00:00:00.000Z', 'end': '2026-10-07T12:00:00.000Z', 'tweet_count': 4}],
          'meta': {'total_tweet_count': 70}}
YT_SEARCH = {'items': [
    {'id': {'videoId': 'vidA'}, 'snippet': {'title': 'Testuję pizzę Książula z Żabki', 'channelTitle': 'Jakiś kanał', 'publishedAt': '2026-10-06T08:00:00Z'}},
    {'id': {'videoId': 'vidB'}, 'snippet': {'title': 'Moja pizza w Żabce', 'channelTitle': 'Książulo', 'publishedAt': '2026-10-05T08:00:00Z'}},
    {'id': {'videoId': 'vidC'}, 'snippet': {'title': 'Bez komentarzy', 'channelTitle': 'Inny', 'publishedAt': '2026-10-05T08:00:00Z'}}]}
YT_STATS = {'items': [{'id': 'vidA', 'statistics': {'viewCount': '500000', 'commentCount': '2'}},
                      {'id': 'vidB', 'statistics': {'viewCount': '100000', 'commentCount': '2'}},
                      {'id': 'vidC', 'statistics': {'viewCount': '900', 'commentCount': '0'}}]}


def yt_comment(cid, text, likes, author='UCauthor'):
    return {'id': cid, 'snippet': {'topLevelComment': {'snippet': {'textOriginal': text, 'likeCount': likes, 'publishedAt': '2026-10-06T09:00:00Z',
                                                                   'authorDisplayName': 'Jan Kowalski', 'authorChannelId': {'value': author}}}}}


YT_COMMENTS = {'vidA': {'items': [yt_comment('c1', 'Zaskakująco dobra ta pizza, polecam', 300, 'UC1'),
                                  yt_comment('c2', 'Porażka, zimna i bez smaku @ktoś', 120, 'UC2')]},
               'vidB': {'items': [yt_comment('c3', 'Świetną robotę robisz, pizza lepsza niż się spodziewałem', 50, 'UC3'),
                                  yt_comment('c4', 'ok', 1, 'UC4')]}}


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path, settings):
    cache.clear()
    for name, value in {'X_POLITICAL_POLLING_ENABLED': 'true', 'X_POLITICAL_BEARER_TOKEN': 'test-token',
                        'X_POLITICAL_MONTHLY_USD_LIMIT': '50', 'INCEPTION_API_KEY': 'k', 'INCEPTION_NO_TRAINING': 'true',
                        'RAPORTY_DIR': str(tmp_path / 'raporty')}.items():
        monkeypatch.setenv(name, value)
    for name in ('X_REPLIES_DAILY_CAP', 'X_REPLIES_BUDGET_FLOOR', 'WYKOP_API_KEY', 'WYKOP_API_SECRET', 'NASTROJE_RSS_FEEDS'):
        monkeypatch.delenv(name, raising=False)
    settings.YOUTUBE_ENABLED, settings.YOUTUBE_API_KEY = True, 'yt-key'
    monkeypatch.setattr(timezone, 'now', lambda: NOW)
    yield
    cache.clear()


class FakeX:
    def __init__(self, monkeypatch, pages=None, error=None, counts=COUNTS, counts_error=None):
        self.calls, self.count_calls = [], []
        self.pages, self.error, self.counts, self.counts_error = pages if pages is not None else [ROWS], error, counts, counts_error

        def request(url, params, config):
            if url == nastroje.X_COUNTS:
                self.count_calls.append(params)
                if self.counts_error:
                    raise self.counts_error
                return json.dumps(self.counts).encode()
            assert url == nastroje.X_SEARCH
            self.calls.append(params)
            if self.error:
                raise self.error
            index = len(self.calls) - 1
            rows = self.pages[index] if index < len(self.pages) else []
            meta = {'result_count': len(rows)}
            if index < len(self.pages) - 1:
                meta['next_token'] = f't{index + 1}'
            return json.dumps({'data': rows, 'meta': meta}).encode()
        monkeypatch.setattr('news.political_polling.request_x', request)


class FakeYT:
    def __init__(self, monkeypatch, search=YT_SEARCH, comments=YT_COMMENTS, fail=None):
        self.calls = []

        def get(url, params, timeout):
            path = url.rsplit('/', 1)[-1]
            self.calls.append((path, {k: v for k, v in params.items() if k != 'key'}))
            if fail:
                raise fail

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(inner):
                    if path == 'search':
                        return search
                    if path == 'videos':
                        return YT_STATS
                    return comments.get(params['videoId'], {'items': []})
            return R()
        monkeypatch.setattr(youtube_collect.requests, 'get', get)


LABELS = {'zaskakująco dobra': ('pozytyw', 'smak'), 'porażka': ('negatyw', 'cena'), 'każdej żabce': ('neutralny', 'marketing'),
          'świetną robotę': ('pozytyw', 'osoba'), 'pierwsze opinie': ('neutralny', 'marketing'), 'hit': ('pozytyw', 'marketing')}


class FakeMercury:
    def __init__(self, monkeypatch, answer=True):
        self.payloads = []

        def side_json(system, user, schema, *, max_tokens=1500, private_data=False):
            assert private_data is True
            self.payloads.append(json.loads(user))
            if not answer:
                return None
            oceny = []
            for item in self.payloads[-1]['teksty']:
                label, topic = next((v for k, v in LABELS.items() if k in item['tekst'].lower()), ('nie_na_temat', 'inne'))
                oceny.append({'i': item['i'], 'ocena': label, 'temat': topic, 'powod': 'Test.'})
            return {'oceny': oceny}, 'mercury-2'
        monkeypatch.setattr(inception, 'side_json', side_json)


def budget():
    return ImportState.objects.get(name='political-x-budget').cursor


def yt_units():
    state = ImportState.objects.filter(name__startswith='youtube-units:').first()
    return state.imported if state else 0


def test_query_quotes_phrases_and_limits_length():
    query = nastroje.build_query(['pizza Książulo', 'Książulo Żabka', 'pizza Żabka', 'pizza Książulo'])
    assert query == '("pizza Książulo" OR "Książulo Żabka" OR "pizza Żabka") lang:pl -is:retweet'
    with pytest.raises(nastroje.NastrojeError):
        nastroje.build_query(['x' * 600])
    with pytest.raises(nastroje.NastrojeError):
        nastroje.build_query([''])


def test_window_from_dates_and_seven_day_floor():
    start, end = nastroje.window(7, date(2026, 10, 4), date(2026, 10, 7), NOW)
    assert start.isoformat() == '2026-10-04T00:00:00+02:00' and end == NOW - timedelta(seconds=10)
    start, _ = nastroje.window(7, date(2026, 9, 1), None, NOW)
    assert start == NOW - timedelta(days=6, hours=23)
    with pytest.raises(nastroje.NastrojeError):
        nastroje.window(7, date(2026, 10, 8), None, NOW)
    assert nastroje.day_axis(*nastroje.window(7, date(2026, 10, 4), date(2026, 10, 7), NOW)) == ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07']


def test_wilson_interval_and_premiere():
    p, low, high = nastroje.wilson(60, 100)
    assert p == 0.6 and round(low, 3) == 0.502 and round(high, 3) == 0.691
    assert nastroje.wilson(0, 0) == (0.0, 0.0, 0.0) and nastroje.wilson(5, 5)[2] == 1.0
    assert nastroje.premiere({'2026-10-04': 1, '2026-10-05': 40, '2026-10-06': 25}) == '2026-10-05'
    assert nastroje.premiere({'2026-10-04': 2, '2026-10-05': 3}) == ''


def test_filter_drops_retweets_ads_language_duplicates_and_strips_identifiers():
    raw = [{'src': 'x', 'id': r['id'], 'author': r['author_id'], 'text': r['text'], 'lang': r['lang'], 'created_at': r['created_at'],
            'likes': r['public_metrics']['like_count'], 'repost': bool(r.get('referenced_tweets'))} for r in ROWS]
    kept, dropped = nastroje.filter_posts(raw + [raw[0]])
    assert [p['text'][:12] for p in kept] == ['Pizza z Żabk', 'Pizza Książu', 'Czy pizza Ks', 'Książulo rob']
    assert dropped == {'inny język': 1, 'reklama': 1, 'ten sam tekst': 1, 'podanie dalej': 1, 'powtórka': 1}
    assert kept[0]['text'] == 'Pizza z Żabki zaskakująco dobra, ciasto chrupiące'
    dumped = json.dumps(kept)
    assert '@' not in dumped and 'http' not in dumped and '7001' not in dumped and 'id' not in kept[0] and 'author' not in kept[0]


def test_full_run_all_sources_budget_files_and_anonymity(monkeypatch, tmp_path):
    x, yt, mercury = FakeX(monkeypatch), FakeYT(monkeypatch), FakeMercury(monkeypatch)
    source = Source.objects.create(name='Portal', url='https://portal.example', rss_url='https://portal.example/rss')
    Article.objects.create(source=source, title='Pizza Książulo w Żabce: pierwsze opinie', url='https://portal.example/a',
                           published_date=NOW - timedelta(days=1))
    Article.objects.create(source=source, title='Stara wiadomość o pizzy Książulo', url='https://portal.example/b', published_date=NOW - timedelta(days=30))
    result = nastroje.run(['pizza Książulo', 'Książulo Żabka'], limit=40, title='Test pizza', od=date(2026, 10, 4), do=date(2026, 10, 7))
    # X: jeden licznik (bez rezerwacji) + jedna strona; budżet rozliczony do 8 zwróconych wpisów
    assert len(x.count_calls) == 1 and x.count_calls[0]['granularity'] == 'day'
    assert len(x.calls) == 1 and x.calls[0]['max_results'] == 40 and 'lang:pl' in x.calls[0]['query'] and 'expansions' not in x.calls[0]
    assert x.calls[0]['start_time'] == '2026-10-03T22:00:00Z'
    assert budget()['replies_reads'] == 8 and Decimal(budget()['spent_upper_usd']) == Decimal('0.040')
    # YouTube: search (100) + videos (1) + 2 strony komentarzy (po 1); kanał Książula pierwszy, film bez komentarzy pominięty
    paths = [c[0] for c in yt.calls]
    assert paths == ['search', 'videos', 'commentThreads', 'commentThreads'] and yt_units() == 103
    assert yt.calls[2][1]['videoId'] == 'vidB' and yt.calls[0][1]['publishedAfter'] == '2026-10-03T22:00:00Z'
    assert 'Jan Kowalski' not in json.dumps(mercury.payloads)
    # ocena: 4 wpisy X + 3 komentarze (jeden za krótki) + 1 tytuł = 8 tekstów w jednej paczce
    assert len(mercury.payloads) == 1 and len(mercury.payloads[0]['teksty']) == 8
    s = result['summary']
    assert s['by_source']['x']['pozytyw'] == 2 and s['by_source']['x']['negatyw'] == 1 and s['by_source']['youtube']['pozytyw'] == 2
    assert s['by_source']['youtube']['negatyw'] == 1 and s['by_source']['media']['neutralny'] == 1 and s['by_source']['wykop']['n'] == 0
    assert s['weighted']['udzial'] == pytest.approx(2 / 3) and set(s['weighted']['wagi']) == {'x', 'youtube'}
    assert s['social'] == {'n': 7, 'pozytyw': 4, 'negatyw': 2, 'neutralny': 1, 'nie_na_temat': 0, 'udzial': pytest.approx(2 / 3),
                           'od': pytest.approx(0.300, abs=0.001), 'do': pytest.approx(0.903, abs=0.001)}
    assert s['volume'] == {'2026-10-04': 1, '2026-10-05': 40, '2026-10-06': 25, '2026-10-07': 4} and s['premiere'] == '2026-10-05'
    assert list(s['by_day']) == ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07'] and s['by_day']['2026-10-04']['n'] == 0
    assert set(s['by_topic']) == {'smak', 'cena', 'osoba', 'marketing'}
    assert [q['likes'] for q in s['quotes']['pozytyw']] == [300, 70, 50, 40] and s['quotes']['negatyw'][0]['src'] == 'youtube'
    assert s['media'][0]['label'] == 'neutralny' and s['media'][0]['outlet'] == 'Portal'
    assert any('Wykop pominięty' in m for m in result['meta']['stopped']) and any('RSS pominięte' in m for m in result['meta']['stopped'])
    html = Path(result['html']).read_text(encoding='utf-8')
    assert 'Test pizza' in html and '67%' in html and 'premiera?' in html and 'Facebook, Instagram i TikTok' in html
    assert '@ksiazulo' not in html and 't.co' not in html and 'Jan Kowalski' not in html and '7002' not in html and 'bez nazwy autora' in html
    assert html.count('<tr><td>') == 5 and 'Wykop (wpisy)' in html and 'Fora i blogi (RSS)' in html
    csv_text = Path(result['csv']).read_text(encoding='utf-8')
    assert csv_text.count('\n') == 9 and '@' not in csv_text and 'UC1' not in csv_text and '7002' not in csv_text
    assert csv_text.splitlines()[0] == 'zrodlo;dzien;ocena;temat;powod;polubienia;tekst_skrocony'
    assert result['raw'] == '' and not list(Path(result['html']).parent.glob('*surowe*'))
    assert 'nastroje-pizza-ksiazulo-20261007-1400' in result['html']


def test_keep_raw_writes_debug_file_only_on_request(monkeypatch):
    FakeX(monkeypatch), FakeYT(monkeypatch, search={'items': []}), FakeMercury(monkeypatch)
    result = nastroje.run(['pizza Książulo'], limit=40, keep_raw=True)
    assert result['raw'].endswith('-surowe.json') and '7001' in Path(result['raw']).read_text(encoding='utf-8')


def test_pagination_stops_at_limit_and_budget_cap(monkeypatch):
    rows = [dict(r, id=str(1900000000000000100 + i), author_id=str(8000 + i), text=f'Pizza Książulo numer {i} smakuje dobrze')
            for i in range(30) for r in [ROWS[0]]]
    x = FakeX(monkeypatch, pages=[rows[:20], rows[20:], rows])
    FakeYT(monkeypatch, search={'items': []}), FakeMercury(monkeypatch)
    result = nastroje.run(['pizza Książulo'], limit=25)
    assert len(x.calls) == 2 and x.calls[1]['next_token'] == 't1' and x.calls[1]['max_results'] == 10
    assert result['meta']['raw']['x'] == 25 and result['meta']['reads'] == 30
    monkeypatch.setenv('X_REPLIES_DAILY_CAP', '35')
    FakeX(monkeypatch, pages=[rows, rows])
    result = nastroje.run(['pizza Książulo'], limit=200)
    assert 'budżet X: daily_cap' in result['meta']['stopped'] and result['meta']['raw'].get('x', 0) == 0


def test_errors_are_reported_not_raised(monkeypatch):
    FakeX(monkeypatch, error=PoliticalReadError('x_http_429', 429, 300), counts_error=PoliticalReadError('x_http_403', 403, 3600))
    FakeYT(monkeypatch, fail=RuntimeError('boom'))
    FakeMercury(monkeypatch)
    result = nastroje.run(['pizza Książulo'], limit=40)
    assert result['meta']['stopped'][:3] == ['X: x_http_429', 'liczniki X: x_http_403', 'YouTube: RuntimeError']
    assert budget()['replies_reads'] == 0 and result['summary']['volume_source'] == 'próba X'
    FakeX(monkeypatch), FakeYT(monkeypatch, search={'items': []})
    FakeMercury(monkeypatch, answer=False)
    result = nastroje.run(['pizza Książulo'], limit=40)
    assert result['meta']['unrated'] == 4 and result['meta']['calls'] == 0 and any('Mercury' in s for s in result['meta']['stopped'])
    assert 'Brak opinii z wyraźnym znakiem' in nastroje.summary_text(result)


def test_youtube_quota_guard_stops_before_request(monkeypatch, settings):
    settings.YOUTUBE_DAILY_UNITS = 50
    yt = FakeYT(monkeypatch)
    out = nastroje.yt_videos(['pizza Książulo'], NOW - timedelta(days=3), NOW)
    assert out['error'] == 'YouTube: wyczerpany dzienny limit jednostek' and yt.calls == [] and out['videos'] == []


def test_wykop_optional_and_anonymous(monkeypatch):
    out = nastroje.wykop_search(['pizza Książulo'], NOW - timedelta(days=3), NOW)
    assert out['rows'] == [] and 'brak WYKOP_API_KEY' in out['error']
    monkeypatch.setenv('WYKOP_API_KEY', 'k'), monkeypatch.setenv('WYKOP_API_SECRET', 's')
    calls = []

    class R:
        status_code = 200

        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return {'data': self._data}
    monkeypatch.setattr(nastroje.requests, 'post', lambda url, **kw: calls.append(('post', url)) or R({'token': 'tok'}))

    def get(url, params, headers, timeout):
        calls.append(('get', url, params['page'], headers['Authorization']))
        if url.endswith('/entries'):
            return R([{'id': 1, 'content': 'Pizza Książulo zaskakująco dobra <b>serio</b>', 'created_at': '2026-10-06 10:00:00',
                       'votes': {'up': 12}, 'author': {'username': 'janek77'}},
                      {'id': 2, 'content': 'Stary wpis o pizzy Książulo', 'created_at': '2026-09-01 10:00:00', 'votes': {'up': 1}, 'author': {'username': 'x'}}])
        return R([{'id': 9, 'title': 'Książulo pizza hit', 'description': 'Znalezisko', 'created_at': '2026-10-06 11:00:00', 'votes': {'up': 3},
                   'author': {'username': 'anna'}}])
    monkeypatch.setattr(nastroje.requests, 'get', get)
    out = nastroje.wykop_search(['pizza Książulo'], NOW - timedelta(days=3), NOW)
    assert out['error'] == '' and [r['text'] for r in out['rows']] == ['Pizza Książulo zaskakująco dobra  serio ', 'Książulo pizza hit - Znalezisko']
    assert out['calls'] == 3 and calls[1][3] == 'Bearer tok' and out['rows'][0]['author'] == 'janek77'
    kept, _ = nastroje.filter_posts(out['rows'])
    assert 'janek77' not in json.dumps(kept) and kept[0]['src'] == 'wykop'


def test_rss_only_approved_or_env_feeds(monkeypatch):
    assert nastroje.rss_feed_urls() == []
    Source.objects.create(name='Blog', url='https://blog.example', rss_url='https://blog.example/feed')  # bez zatwierdzonej karty
    monkeypatch.setenv('NASTROJE_RSS_FEEDS', 'https://forum.example/rss.xml, http://zly.example/rss')
    assert nastroje.rss_feed_urls() == ['https://forum.example/rss.xml']
    feed = ('<?xml version="1.0"?><rss><channel><item><title>Pizza Książulo w Żabce - test</title><link>https://forum.example/1</link>'
            '<description>Zaskakująco dobra &lt;b&gt;pizza&lt;/b&gt;</description><pubDate>Tue, 06 Oct 2026 09:00:00 GMT</pubDate></item>'
            '<item><title>Przepis na chleb</title><link>https://forum.example/2</link><pubDate>Tue, 06 Oct 2026 09:00:00 GMT</pubDate></item>'
            '<item><title>Stara pizza Książulo</title><link>https://forum.example/3</link><pubDate>Tue, 01 Sep 2026 09:00:00 GMT</pubDate></item>'
            '</channel></rss>')

    class R:
        content = feed.encode()
    monkeypatch.setattr(nastroje.requests, 'get', lambda url, **kw: R())
    out = nastroje.rss_entries(['pizza Książulo'], NOW - timedelta(days=3), NOW)
    assert out['feeds'] == 1 and len(out['rows']) == 1 and out['rows'][0]['text'].startswith('Pizza Książulo w Żabce - test - Zaskakująco dobra')
    assert out['rows'][0]['src'] == 'rss' and out['rows'][0]['author'] == ''


def test_plan_counts_without_reading_posts(monkeypatch):
    x, yt = FakeX(monkeypatch), FakeYT(monkeypatch)
    calls = []
    monkeypatch.setattr(inception, 'side_json', lambda *a, **k: calls.append(1))
    out = StringIO()
    call_command('raport_nastrojow', '--fraza', 'pizza Książulo', '--fraza', 'pizza Żabka', '--limit', '500', '--od', '2026-10-04', '--plan', stdout=out)
    text = out.getvalue()
    assert 'Wpisów na X w zakresie: 70 (10-04: 1, 10-05: 40, 10-06: 25, 10-07: 4)' in text
    assert 'do 70 odczytów X (~0.350 USD), do 4 komentarzy YouTube' in text and 'Mercury' in text and 'Książulo: Moja pizza' in text
    assert 'Wykop: nie; kanałów RSS: 0' in text
    assert len(x.count_calls) == 1 and not x.calls and not calls and [c[0] for c in yt.calls] == ['search', 'videos']
    assert not ImportState.objects.filter(name='political-x-budget').exists()


def test_command_prints_summary_and_mails_admin(monkeypatch):
    FakeX(monkeypatch), FakeYT(monkeypatch, search={'items': []}), FakeMercury(monkeypatch)
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'admin@example.com')
    sent = []
    monkeypatch.setattr('news.social_publish._mail', lambda to, subject, body, **kw: sent.append((to, subject, kw)) or True)
    out = StringIO()
    call_command('raport_nastrojow', '--fraza', 'pizza Książulo', '--limit', '40', '--tytul', 'Pizza test', '--od', '2026-10-04', '--do', '2026-10-07',
                 '--wyslij', stdout=out)
    text = out.getvalue()
    assert 'pozytywne 67%' in text and 'X (wpisy): 67% (n=3)' in text and 'HTML: ' in text and 'Mail: wysłany' in text
    assert 'Zakres: 04.10.2026 do 07.10.2026, najpewniej premiera: 2026-10-05' in text
    assert sent == [('admin@example.com', 'spin.clinic · Pizza test', {'important': True})]


def test_command_without_phrase_or_bad_date_fails_clearly():
    from django.core.management.base import CommandError
    with pytest.raises(CommandError, match='brak_fraz'):
        call_command('raport_nastrojow')
    with pytest.raises(CommandError, match='Zła data'):
        call_command('raport_nastrojow', '--fraza', 'x', '--od', '2026-13-01')
