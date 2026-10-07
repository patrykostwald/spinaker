"""Raport nastrojów: udział opinii pozytywnych i negatywnych o jednym temacie z trzech legalnych źródeł.

Źródła (osobne sekcje + łączny wynik z jawnymi wagami):
- X: oficjalne API, wyszukiwanie pełnotekstowe ostatnich 7 dni po frazach (wszystkie publiczne wpisy zwykłych
  użytkowników), ten sam klient i ten sam strażnik budżetu co zbieranie wpisów; liczniki (tweets/counts) do planu
  i wykresu dzień po dniu;
- YouTube Data API v3: filmy z frazami w okresie (search.list) i publiczne komentarze pod najpopularniejszymi
  (commentThreads.list), wspólny strażnik jednostek (news/youtube_collect.py);
- Wykop API v3 (opcjonalnie, gdy w env są WYKOP_API_KEY i WYKOP_API_SECRET): wyszukiwanie wpisów i znalezisk po frazach;
- kanały RSS/Atom forów i blogów: źródła z katalogu z zatwierdzoną kartą dostępu (kanał rss) oraz lista NASTROJE_RSS_FEEDS
  z env (publiczne kanały sprawdzone przez Prawnika); tylko tytuły i krótkie fragmenty z kanału;
- media: tytuły artykułów, które już mamy w bazie (Article, tylko metadane) - „jak piszą media”.
Bez Facebooka, Instagrama i TikToka; bez Google Trends (brak oficjalnego API).

RODO: dane przetwarzamy zbiorczo i tylko w pamięci. Nic nie zapisujemy do tabel spin.clinic. Do raportu i CSV trafia
wyłącznie skrócony tekst bez @nazw i linków, data, klasa i temat - żadnych nazw ani identyfikatorów autorów (także osób
publicznych). Surowe dane znikają po wygenerowaniu raportu; --zachowaj (debugowanie) zapisuje je obok raportu.
Ocena: Mercury (news/inception.py, trasa poboczna, json_object) w paczkach po 20 tekstów.
"""
from __future__ import annotations

import csv
import html
import json
import logging
import math
import os
import re
import time as _time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

LABELS = ('pozytyw', 'negatyw', 'neutralny', 'nie_na_temat')
TOPICS = ('smak', 'cena', 'osoba', 'marketing', 'inne')
TOPIC_NAMES = {'smak': 'Smak i jakość', 'cena': 'Cena', 'osoba': 'Książulo jako osoba', 'marketing': 'Marketing i akcja',
               'inne': 'Inne'}
SOURCES = ('x', 'youtube', 'wykop', 'rss', 'media')
SOCIAL = ('x', 'youtube', 'wykop', 'rss')
SOURCE_NAMES = {'x': 'X (wpisy)', 'youtube': 'YouTube (komentarze)', 'wykop': 'Wykop (wpisy)', 'rss': 'Fora i blogi (RSS)',
                'media': 'Media (tytuły)'}
KIND = {'x': 'wpis z X', 'youtube': 'komentarz z YouTube', 'wykop': 'wpis z Wykopu', 'rss': 'wpis z forum lub bloga', 'media': 'tytuł artykułu'}
# Wagi łącznego wyniku: wybór redakcyjny, nie statystyka. Źródła bez danych wypadają, reszta jest przeskalowana do 1.
WEIGHTS = {'x': 0.35, 'youtube': 0.35, 'wykop': 0.15, 'rss': 0.05, 'media': 0.10}
WYKOP_PAGES = 3
RSS_FEEDS_MAX = 20
UA = {'User-Agent': 'spin.clinic raport nastrojow (+https://spin.clinic)'}
BATCH = 20
QUERY_LIMIT = 512
PAGE_MAX = 100
PER_AUTHOR = 3
YT_VIDEOS = 8
YT_PAGE = 100
PL = ZoneInfo('Europe/Warsaw')
DEFAULT_DIR = '/srv/backups/raporty'
X_SEARCH = 'https://api.x.com/2/tweets/search/recent'
X_COUNTS = 'https://api.x.com/2/tweets/counts/recent'

SYSTEM = ('Jesteś analitykiem opinii. Dostajesz temat i listę krótkich tekstów (wpisy z X, komentarze z YouTube albo tytuły '
          'artykułów, po polsku). Dla każdego tekstu podaj:\n'
          '- ocena: "pozytyw" (autor chwali temat), "negatyw" (krytykuje), "neutralny" (na temat, bez wyraźnego znaku: pytanie, '
          'informacja, tytuł bez oceny, żart bez oceny), "nie_na_temat" (nie dotyczy tematu albo to reklama).\n'
          '- temat: "smak" (smak, jakość, składniki), "cena" (cena, opłacalność), "osoba" (autor marki jako człowiek, jego '
          'wiarygodność), "marketing" (akcja, kampania, kolejki, dostępność, sieć sklepów), "inne".\n'
          '- powod: jedno krótkie zdanie po polsku, bez cytowania nazw użytkowników.\n'
          'Odpowiedz obiektem JSON {"oceny": [{"i": numer tekstu, "ocena": ..., "temat": ..., "powod": ...}, ...]} - po jednej '
          'pozycji na każdy tekst, w kolejności.')
SCHEMA = {'type': 'object', 'properties': {'oceny': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'i': {'type': 'integer'}, 'ocena': {'type': 'string', 'enum': list(LABELS)}, 'temat': {'type': 'string', 'enum': list(TOPICS)},
    'powod': {'type': 'string'}}, 'required': ['i', 'ocena', 'temat', 'powod']}}}, 'required': ['oceny']}

_URL = re.compile(r'https?://\S+|www\.\S+', re.I)
_HANDLE = re.compile(r'@\w+')
_HASHTAG = re.compile(r'#\w+')
_TAG = re.compile(r'<[^>]+>')
_AD = re.compile(r'#reklama\b|#ad\b|kod rabatow|link w bio|współpraca reklamowa|wspolpraca reklamowa|sponsorowan|#współpraca|#wspolpraca',
                 re.I)


class NastrojeError(Exception):
    def __init__(self, code: str, detail: str = ''):
        super().__init__(code)
        self.code, self.detail = code, detail


# --- frazy, zakres ---
def phrases(frazy: list[str]) -> list[str]:
    clean = []
    for fraza in frazy or []:
        text = ' '.join((fraza or '').replace('"', ' ').split())
        if text and text not in clean:
            clean.append(text)
    if not clean:
        raise NastrojeError('brak_fraz', 'Podaj co najmniej jedną frazę (--fraza).')
    return clean


def build_query(frazy: list[str]) -> str:
    """Zapytanie X: frazy w cudzysłowach (dokładne wyrażenia), po polsku, bez podań dalej. Liczy się cały niezakodowany tekst."""
    clean = phrases(frazy)
    terms = ' OR '.join(f'"{t}"' if ' ' in t else t for t in clean)
    query = f'({terms}) lang:pl -is:retweet'
    if len(query) > QUERY_LIMIT:
        raise NastrojeError('za_dlugie_zapytanie', f'Zapytanie ma {len(query)} znaków; limit X to {QUERY_LIMIT}.')
    return query


def utc_text(value: datetime) -> str:
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def window(days: int, od=None, do=None, now=None) -> tuple[datetime, datetime]:
    """Zakres czasu (UTC). --od/--do to dni w czasie polskim (do włącznie); X sięga najwyżej 7 dni wstecz."""
    now = now or timezone.now()
    floor = now - timedelta(days=6, hours=23)
    latest = now - timedelta(seconds=10)
    end = min(latest, datetime.combine(do + timedelta(days=1), datetime.min.time(), PL)) if do else latest
    start = datetime.combine(od, datetime.min.time(), PL) if od else now - timedelta(days=max(1, min(7, days)))
    start = max(start, floor)
    if start >= end:
        raise NastrojeError('zly_zakres', 'Początek zakresu nie jest wcześniejszy niż koniec (X sięga 7 dni wstecz).')
    return start, end


def _day(created: str) -> str:
    try:
        return datetime.fromisoformat((created or '').replace('Z', '+00:00')).astimezone(PL).date().isoformat()
    except ValueError:
        return ''


def day_axis(start: datetime, end: datetime) -> list[str]:
    first, last = start.astimezone(PL).date(), end.astimezone(PL).date()
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


# --- X: liczniki (bez odczytu wpisów) i wyszukiwanie pełnotekstowe ---
def x_counts(query: str, config: dict, start: datetime, end: datetime) -> dict:
    """Liczba wpisów dzień po dniu z punktu końcowego liczników: {'days': {dzień: n}, 'total': n, 'error': ''}."""
    from news.political_polling import PoliticalReadError, request_x
    out = {'days': Counter(), 'total': 0, 'error': ''}
    try:
        raw = request_x(X_COUNTS, {'query': query, 'granularity': 'day', 'start_time': utc_text(start), 'end_time': utc_text(end)}, config)
        payload = json.loads(raw)
        for row in payload.get('data') or []:
            if isinstance(row, dict) and isinstance(row.get('tweet_count'), int):
                # Przedziały X biegną od północy UTC; przypisujemy je do polskiego dnia początku przedziału.
                out['days'][_day(str(row.get('start') or ''))] += row['tweet_count']
        meta = payload.get('meta') or {}
        out['total'] = meta.get('total_tweet_count') if isinstance(meta.get('total_tweet_count'), int) else sum(out['days'].values())
    except PoliticalReadError as error:
        out['error'] = f'liczniki X: {error.code}'
    except (ValueError, TypeError, AttributeError):
        out['error'] = 'liczniki X: niepoprawna odpowiedź'
    out['days'] = dict(out['days'])
    return out


def fetch_x(query: str, limit: int, config: dict, start: datetime, end: datetime, now=None) -> dict:
    """Pobiera do `limit` wpisów ze wspólnym limitem X (rezerwacja przed każdą stroną, rozliczenie po niej).
    Zwraca {'rows': [...], 'reads': n, 'pages': n, 'stopped': powód albo ''}."""
    from news.odbior_spinu import reserve, settle
    from news.political_polling import PoliticalReadError, request_x
    now = now or timezone.now()
    base = {'query': query, 'sort_order': 'recency', 'start_time': utc_text(start), 'end_time': utc_text(end),
            'tweet.fields': 'author_id,created_at,lang,public_metrics,referenced_tweets'}
    rows, token, reads, pages, stopped = [], '', 0, 0, ''
    while len(rows) < limit:
        size = max(10, min(PAGE_MAX, limit - len(rows)))
        ok, reason = reserve(size, config, now)
        if not ok:
            stopped = f'budżet X: {reason}'
            break
        params = dict(base, max_results=size)
        if token:
            params['next_token'] = token
        used = 0
        try:
            payload = json.loads(request_x(X_SEARCH, params, config))
            data = payload.get('data') or [] if isinstance(payload, dict) else []
            meta = payload.get('meta') or {} if isinstance(payload, dict) else {}
            used = len(data)
            reads += used
            pages += 1
            for r in data:
                if isinstance(r, dict) and isinstance(r.get('id'), str) and isinstance(r.get('text'), str):
                    metrics = r.get('public_metrics') if isinstance(r.get('public_metrics'), dict) else {}
                    rows.append({'src': 'x', 'id': r['id'], 'author': str(r.get('author_id') or ''), 'text': r['text'],
                                 'lang': r.get('lang') or '', 'created_at': r.get('created_at') or '',
                                 'likes': metrics.get('like_count') if isinstance(metrics.get('like_count'), int) else 0,
                                 'repost': any(isinstance(x, dict) and x.get('type') == 'retweeted' for x in r.get('referenced_tweets') or [])})
            token = str(meta.get('next_token') or '')
        except PoliticalReadError as error:
            stopped = f'X: {error.code}' + (f' ({error.detail})' if getattr(error, 'detail', '') else '')
            break
        except (ValueError, TypeError, AttributeError):
            stopped = 'X: niepoprawna odpowiedź'
            break
        finally:
            settle(size, used, now)
        if not token:
            break
    return {'rows': rows[:limit], 'reads': reads, 'pages': pages, 'stopped': stopped}


# --- YouTube: filmy z frazami i publiczne komentarze (wspólny strażnik jednostek) ---
def yt_videos(frazy: list[str], start: datetime, end: datetime) -> dict:
    """search.list (100 jednostek) + videos.list (1): filmy z okresu z liczbą wyświetleń i komentarzy, kanał Książula pierwszy."""
    from news import youtube_collect as yt
    out = {'videos': [], 'units': 0, 'error': ''}
    if not yt.enabled():
        out['error'] = 'YouTube wyłączony (YOUTUBE_ENABLED / YOUTUBE_API_KEY)'
        return out
    try:
        found = yt.api('search', part='snippet', type='video', q='|'.join(phrases(frazy)), maxResults=25, order='relevance',
                       relevanceLanguage='pl', regionCode='PL', publishedAfter=utc_text(start), publishedBefore=utc_text(end))
        out['units'] += yt.UNIT_COST.get('search', 100)
        items = [i for i in found.get('items') or [] if isinstance(i, dict) and isinstance((i.get('id') or {}).get('videoId'), str)]
        videos = {i['id']['videoId']: {'id': i['id']['videoId'], 'title': str((i.get('snippet') or {}).get('title') or '')[:120],
                                       'channel': str((i.get('snippet') or {}).get('channelTitle') or ''),
                                       'published': str((i.get('snippet') or {}).get('publishedAt') or ''), 'views': 0, 'comments': 0}
                  for i in items}
        if videos:
            stats = yt.api('videos', part='statistics', id=','.join(list(videos)[:50]))
            out['units'] += 1
            for row in stats.get('items') or []:
                v = videos.get(row.get('id')) if isinstance(row, dict) else None
                if v:
                    st = row.get('statistics') or {}
                    v['views'] = int(st.get('viewCount') or 0)
                    v['comments'] = int(st.get('commentCount') or 0)
        ranked = sorted(videos.values(), key=lambda v: (0 if 'książulo' in v['channel'].lower() or 'ksiazulo' in v['channel'].lower() else 1,
                                                        -v['views']))
        out['videos'] = ranked
    except yt.QuotaExhausted:
        out['error'] = 'YouTube: wyczerpany dzienny limit jednostek'
    except Exception as error:  # noqa: BLE001 - błąd HTTP albo odpowiedzi: raport bez tego źródła
        out['error'] = f'YouTube: {type(error).__name__}'
    return out


def yt_comments(videos: list[dict], limit: int) -> dict:
    """commentThreads.list (1 jednostka na stronę 100): komentarze najwyższego poziomu bez nazw autorów."""
    from news import youtube_collect as yt
    out = {'rows': [], 'units': 0, 'error': '', 'videos': 0}
    per_video = max(YT_PAGE, limit // max(1, min(YT_VIDEOS, len(videos)))) if videos else 0
    for video in videos[:YT_VIDEOS]:
        if len(out['rows']) >= limit:
            break
        if not video.get('comments'):
            continue
        token, taken = '', 0
        out['videos'] += 1
        while len(out['rows']) < limit and taken < per_video:
            params = {'part': 'snippet', 'videoId': video['id'], 'maxResults': YT_PAGE, 'order': 'relevance', 'textFormat': 'plainText'}
            if token:
                params['pageToken'] = token
            try:
                page = yt.api('commentThreads', **params)
            except yt.QuotaExhausted:
                out['error'] = 'YouTube: wyczerpany dzienny limit jednostek'
                return out
            except Exception as error:  # noqa: BLE001 - np. komentarze wyłączone (403): następny film
                logger.info('youtube comments %s: %s', video['id'], type(error).__name__)
                break
            out['units'] += 1
            for item in page.get('items') or []:
                sn = (((item or {}).get('snippet') or {}).get('topLevelComment') or {}).get('snippet') or {}
                text = sn.get('textOriginal') or sn.get('textDisplay') or ''
                if not isinstance(text, str) or not text.strip():
                    continue
                author = (sn.get('authorChannelId') or {}).get('value') if isinstance(sn.get('authorChannelId'), dict) else ''
                out['rows'].append({'src': 'youtube', 'id': str(item.get('id') or ''), 'author': str(author or ''), 'text': _TAG.sub(' ', text),
                                    'lang': '', 'created_at': str(sn.get('publishedAt') or ''), 'likes': int(sn.get('likeCount') or 0),
                                    'repost': False, 'video': video['title']})
                taken += 1
            token = str(page.get('nextPageToken') or '')
            if not token:
                break
    return out


# --- Wykop API v3 (opcjonalnie, oficjalny klucz) ---
def wykop_enabled() -> bool:
    return bool(os.environ.get('WYKOP_API_KEY', '').strip() and os.environ.get('WYKOP_API_SECRET', '').strip())


def _wykop_time(value: str) -> str:
    try:
        return datetime.strptime(str(value or '')[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=PL).isoformat()
    except ValueError:
        return ''


def wykop_search(frazy: list[str], start: datetime, end: datetime, limit: int = 300) -> dict:
    """Wpisy (mikroblog) i znaleziska z frazami, do WYKOP_PAGES stron na frazę i rodzaj. Autor zostaje tylko w pamięci."""
    out = {'rows': [], 'calls': 0, 'error': ''}
    if not wykop_enabled():
        out['error'] = 'Wykop pominięty (brak WYKOP_API_KEY / WYKOP_API_SECRET)'
        return out
    try:
        auth = requests.post('https://wykop.pl/api/v3/auth', json={'data': {'key': os.environ['WYKOP_API_KEY'].strip(),
                             'secret': os.environ['WYKOP_API_SECRET'].strip()}}, headers=UA, timeout=(5, 15))
        out['calls'] += 1
        auth.raise_for_status()
        token = str(((auth.json() or {}).get('data') or {}).get('token') or '')
        if not token:
            raise ValueError('brak tokenu')
        headers = {**UA, 'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
        for fraza in phrases(frazy)[:3]:
            for kind in ('entries', 'links'):
                for page in range(1, WYKOP_PAGES + 1):
                    if len(out['rows']) >= limit:
                        break
                    response = requests.get(f'https://wykop.pl/api/v3/search/{kind}', params={'query': fraza, 'page': page, 'limit': 25},
                                            headers=headers, timeout=(5, 15))
                    out['calls'] += 1
                    if response.status_code == 429:
                        _time.sleep(1)
                        continue
                    response.raise_for_status()
                    data = (response.json() or {}).get('data') or []
                    if not data:
                        break
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        created = _wykop_time(item.get('created_at'))
                        if not created or not (start <= datetime.fromisoformat(created) <= end):
                            continue
                        text = item.get('content') if kind == 'entries' else ' - '.join(x for x in (item.get('title'), item.get('description')) if x)
                        votes = item.get('votes') if isinstance(item.get('votes'), dict) else {}
                        author = item.get('author') if isinstance(item.get('author'), dict) else {}
                        out['rows'].append({'src': 'wykop', 'id': f'{kind}:{item.get("id")}', 'author': str(author.get('username') or ''),
                                            'text': _TAG.sub(' ', str(text or '')), 'lang': '', 'created_at': created,
                                            'likes': int(votes.get('up') or 0), 'repost': False})
                    if len(data) < 25:
                        break
    except Exception as error:  # noqa: BLE001 - błąd klucza, sieci albo odpowiedzi: raport bez tego źródła
        out['error'] = f'Wykop: {type(error).__name__}'
    return out


# --- kanały RSS/Atom forów i blogów (publiczne kanały; tylko tytuł i krótki fragment) ---
def rss_feed_urls() -> list[str]:
    """Źródła z katalogu z zatwierdzoną kartą dostępu dla kanału rss oraz lista NASTROJE_RSS_FEEDS z env (po sprawdzeniu Prawnika)."""
    from news.models import Source
    from scraper.access_gate import approved_instruction
    urls = [u.strip() for u in os.environ.get('NASTROJE_RSS_FEEDS', '').split(',') if u.strip().startswith('https://')]
    for source in Source.objects.exclude(rss_url='').filter(is_active=True, scrape_enabled=True).order_by('pk'):
        if source.rss_url.startswith('https://') and source.rss_url not in urls and approved_instruction(source, 'rss', source.rss_url):
            urls.append(source.rss_url)
    return urls[:RSS_FEEDS_MAX]


def rss_entries(frazy: list[str], start: datetime, end: datetime, urls: list[str] | None = None) -> dict:
    import feedparser
    out = {'rows': [], 'feeds': 0, 'error': ''}
    urls = rss_feed_urls() if urls is None else urls
    if not urls:
        out['error'] = 'RSS pominięte (brak kanałów z zatwierdzoną kartą ani NASTROJE_RSS_FEEDS)'
        return out
    words = [w.lower() for f in phrases(frazy) for w in f.split() if len(w) >= 4]
    for url in urls:
        try:
            parsed = feedparser.parse(requests.get(url, timeout=(5, 15), headers=UA).content)
        except Exception as error:  # noqa: BLE001 - jeden kanał nie psuje raportu
            logger.info('rss %s: %s', url, type(error).__name__)
            continue
        out['feeds'] += 1
        for entry in parsed.entries[:100]:
            stamp = entry.get('published_parsed') or entry.get('updated_parsed')
            if not stamp:
                continue
            created = datetime(*stamp[:6], tzinfo=dt_timezone.utc)
            if not (start <= created <= end):
                continue
            title = str(entry.get('title') or '')
            summary = _TAG.sub(' ', str(entry.get('summary') or ''))[:300]
            text = ' - '.join(x for x in (title, summary) if x)
            if not any(w in text.lower() for w in words):
                continue
            out['rows'].append({'src': 'rss', 'id': str(entry.get('id') or entry.get('link') or title), 'author': '', 'text': text, 'lang': '',
                                'created_at': created.isoformat(), 'likes': 0, 'repost': False})
    return out


# --- media: tytuły, które już mamy ---
def media_titles(frazy: list[str], start: datetime, end: datetime, limit: int = 60) -> list[dict]:
    from django.db.models import Q
    from news.models import Article
    words = sorted({w for f in phrases(frazy) for w in f.split() if len(w) >= 4}, key=len, reverse=True)
    cond = Q()
    for word in words:
        cond |= Q(title__icontains=word)
    rows = (Article.objects.filter(cond, published_date__gte=start, published_date__lte=end).select_related('source')
            .order_by('-published_date')[:limit])
    return [{'src': 'media', 'id': str(a.pk), 'author': '', 'text': a.title, 'lang': '', 'created_at': a.published_date.isoformat() if a.published_date else '',
             'likes': 0, 'repost': False, 'outlet': (getattr(a.source, 'name', '') or '')[:60]} for a in rows]


# --- filtr w pamięci: podania dalej, reklamy, boty, powtórki ---
def scrub(text: str) -> str:
    return ' '.join(_HANDLE.sub(' ', _URL.sub(' ', text or '')).split())


def _norm(text: str) -> str:
    base = unicodedata.normalize('NFKD', scrub(text).lower())
    return ' '.join(re.sub(r'[^a-z0-9ąćęłńóśźż ]+', ' ', ''.join(c for c in base if not unicodedata.combining(c))).split())


def filter_posts(rows: list[dict], min_words: int = 3) -> tuple[list[dict], Counter]:
    """Zwraca kopie bez surowych identyfikatorów: tylko źródło, oczyszczony tekst, polubienia, data (+ tytuł filmu / tytuł medium)."""
    kept, dropped, seen_ids, seen_text, per_author = [], Counter(), set(), set(), Counter()
    for row in rows:
        key_id = (row['src'], row.get('id'))
        if row.get('id') and key_id in seen_ids:
            dropped['powtórka'] += 1
            continue
        seen_ids.add(key_id)
        text = row.get('text') or ''
        if row.get('repost'):
            dropped['podanie dalej'] += 1
            continue
        if row.get('lang') and row['lang'] != 'pl':
            dropped['inny język'] += 1
            continue
        if row['src'] != 'media' and (_AD.search(text) or len(_HASHTAG.findall(text)) >= 5
                                      or (len(_URL.findall(text)) >= 2 and len(scrub(text).split()) < 8)):
            dropped['reklama'] += 1
            continue
        clean = scrub(text)
        if len(clean.split()) < (1 if row['src'] == 'media' else min_words):
            dropped['za krótkie'] += 1
            continue
        key = (row['src'], _norm(clean))
        if key in seen_text:
            dropped['ten sam tekst'] += 1
            continue
        author = (row['src'], row.get('author') or '')
        if author[1] and per_author[author] >= PER_AUTHOR:
            dropped['zbyt aktywny autor'] += 1
            continue
        per_author[author] += 1
        seen_text.add(key)
        kept.append({'src': row['src'], 'text': clean[:300], 'likes': row.get('likes') or 0, 'created_at': row.get('created_at') or '',
                     'video': row.get('video', ''), 'outlet': row.get('outlet', '')})
    return kept, dropped


# --- ocena (Mercury, paczki) ---
def classify(posts: list[dict], topic: str, batch: int = BATCH) -> dict:
    """Dopisuje do każdego tekstu ocenę, temat i powód. Zwraca {'calls': n, 'model': nazwa, 'unrated': n, 'stopped': powód}."""
    from news import inception
    calls, model, unrated, stopped = 0, '', 0, ''
    for start in range(0, len(posts), batch):
        chunk = posts[start:start + batch]
        if stopped:
            unrated += len(chunk)
            continue
        payload = {'temat': topic, 'teksty': [{'i': i, 'rodzaj': KIND[p['src']], 'tekst': p['text'][:300]} for i, p in enumerate(chunk)]}
        answer = inception.side_json(SYSTEM, json.dumps(payload, ensure_ascii=False), SCHEMA, max_tokens=120 * len(chunk) + 200,
                                     private_data=True)
        if answer is None:
            stopped = 'Mercury niedostępny (limit, brak klucza albo INCEPTION_NO_TRAINING nie jest true)'
            unrated += len(chunk)
            continue
        data, model = answer
        calls += 1
        rated = {item['i']: item for item in data.get('oceny') or []
                 if isinstance(item, dict) and isinstance(item.get('i'), int) and 0 <= item['i'] < len(chunk)}
        for i, post in enumerate(chunk):
            item = rated.get(i) or {}
            label, topic_key = item.get('ocena'), item.get('temat')
            post['label'] = label if label in LABELS else ''
            post['topic'] = topic_key if topic_key in TOPICS else 'inne'
            post['reason'] = ' '.join(str(item.get('powod') or '').split())[:200]
            if not post['label']:
                unrated += 1
    return {'calls': calls, 'model': model, 'unrated': unrated, 'stopped': stopped}


# --- statystyka ---
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Udział i 95% przedział Wilsona (w ułamkach). Dla n=0: (0, 0, 0)."""
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def share(group: list[dict]) -> dict:
    pos = sum(1 for p in group if p.get('label') == 'pozytyw')
    neg = sum(1 for p in group if p.get('label') == 'negatyw')
    p, low, high = wilson(pos, pos + neg)
    return {'n': len(group), 'pozytyw': pos, 'negatyw': neg, 'neutralny': sum(1 for p in group if p.get('label') == 'neutralny'),
            'nie_na_temat': sum(1 for p in group if p.get('label') == 'nie_na_temat'), 'udzial': p, 'od': low, 'do': high}


def premiere(counts: dict) -> str:
    """„Najpewniej premiera”: pierwszy dzień z wysypem (co najmniej 3 teksty i co najmniej dwa razy więcej niż dzień wcześniej).
    Pierwszy dzień zakresu jest tylko bazą odniesienia - bez dnia wcześniej nie da się mówić o wysypie."""
    previous = None
    for day in sorted(counts):
        n = counts[day]
        if previous is not None and n >= 3 and n >= 2 * max(previous, 1):
            return day
        previous = n
    return ''


def weighted(by_source: dict) -> dict:
    """Łączny udział pozytywnych: średnia udziałów źródeł z wagami WEIGHTS (tylko źródła z opiniami ze znakiem)."""
    parts = {s: v for s, v in by_source.items() if v['pozytyw'] + v['negatyw']}
    total = sum(WEIGHTS[s] for s in parts)
    if not total:
        return {'udzial': 0.0, 'wagi': {}, 'n': 0}
    return {'udzial': sum(WEIGHTS[s] / total * parts[s]['udzial'] for s in parts), 'wagi': {s: WEIGHTS[s] / total for s in parts},
            'n': sum(parts[s]['pozytyw'] + parts[s]['negatyw'] for s in parts)}


def summarise(posts: list[dict], start: datetime | None = None, end: datetime | None = None, counts: dict | None = None) -> dict:
    rated = [p for p in posts if p.get('label')]
    on_topic = [p for p in rated if p['label'] != 'nie_na_temat']
    social = [p for p in on_topic if p['src'] in SOCIAL]
    days = day_axis(start, end) if start and end else sorted({_day(p['created_at']) for p in on_topic} - {''})
    by_source = {s: share([p for p in on_topic if p['src'] == s]) for s in SOURCES}
    by_day = {day: share([p for p in social if _day(p['created_at']) == day]) for day in days}
    sample_volume = {day: sum(1 for p in posts if p['src'] == 'x' and _day(p['created_at']) == day) for day in days}
    volume = {day: (counts or {}).get(day, 0) for day in days} if counts else sample_volume
    by_topic = {t: v for t, v in ((t, share([p for p in social if p.get('topic') == t])) for t in TOPICS) if v['n']}

    def quotes(label):
        rows = sorted((p for p in social if p['label'] == label), key=lambda p: (-p['likes'], p['text']))
        return [{'text': p['text'][:220], 'likes': p['likes'], 'src': p['src'], 'reason': p.get('reason', '')} for p in rows[:5]]
    return {'rated': len(rated), 'on_topic': len(on_topic), 'counts': dict(Counter(p['label'] for p in rated)),
            'total': share(on_topic), 'social': share(social), 'by_source': by_source, 'weighted': weighted(by_source),
            'by_day': by_day, 'by_topic': by_topic, 'volume': volume, 'volume_source': 'liczniki X' if counts else 'próba X',
            'premiere': premiere(volume),
            'media': [{'text': p['text'][:160], 'outlet': p.get('outlet', ''), 'day': _day(p['created_at']), 'label': p.get('label', '')}
                      for p in sorted((p for p in rated if p['src'] == 'media'), key=lambda p: p['created_at'], reverse=True)[:12]],
            'quotes': {'pozytyw': quotes('pozytyw'), 'negatyw': quotes('negatyw')}}


# --- zapis ---
def output_dir() -> Path:
    for candidate in (os.environ.get('RAPORTY_DIR', '').strip(), DEFAULT_DIR):
        if not candidate:
            continue
        path = Path(candidate)
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    from django.conf import settings
    path = Path(settings.BASE_DIR) / 'raporty'
    path.mkdir(parents=True, exist_ok=True)
    return path


def slug(text: str) -> str:
    base = unicodedata.normalize('NFKD', text.lower())
    base = ''.join(c for c in base if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:40] or 'raport'


def write_csv(path: Path, posts: list[dict]) -> None:
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter=';')
        writer.writerow(['zrodlo', 'dzien', 'ocena', 'temat', 'powod', 'polubienia', 'tekst_skrocony'])
        for p in posts:
            writer.writerow([p['src'], _day(p['created_at']), p.get('label', ''), p.get('topic', ''), p.get('reason', ''), p['likes'], p['text'][:160]])


def _pct(value: float) -> str:
    return f'{round(value * 100)}%'


def _dm(day: str) -> str:
    try:
        return datetime.fromisoformat(day).strftime('%d.%m')
    except ValueError:
        return day


def render_html(title: str, frazy: list[str], query: str, summary: dict, meta: dict) -> str:
    e = html.escape
    w, src = summary['weighted'], summary['by_source']
    soc = summary['social']
    n_soc = soc['pozytyw'] + soc['negatyw']
    now = meta['now'].astimezone(PL)
    zakres = f'{meta["start"].astimezone(PL).strftime("%d.%m.%Y")} do {meta["end"].astimezone(PL).strftime("%d.%m.%Y")}'

    def tile(label, value, note, tone=''):
        return (f'<div class="tile {tone}"><div class="tile-label">{e(label)}</div><div class="tile-value">{e(value)}</div>'
                f'<div class="tile-note">{e(note)}</div></div>')

    def bar_row(name, row, mark=False):
        n = row['pozytyw'] + row['negatyw']
        pos = round(row['udzial'] * 100) if n else 0
        label = f'{e(name)} <b class="mark">premiera?</b>' if mark else e(name)
        return (f'<div class="row{" is-premiere" if mark else ""}"><div class="row-name">{label}</div>'
                f'<div class="bar"><span class="pos" style="width:{pos}%"></span><span class="neg" style="width:{100 - pos if n else 0}%"></span></div>'
                f'<div class="row-num">{_pct(row["udzial"]) if n else "-"}</div>'
                f'<div class="row-ci">{(_pct(row["od"]) + " do " + _pct(row["do"])) if n else "brak opinii ze znakiem"}</div>'
                f'<div class="row-n">n={n} / {row["n"]}</div></div>')

    def quote_box(q):
        return (f'<div class="quote"><p class="quote-text">„{e(q["text"])}”</p>'
                f'<div class="quote-foot"><span>{e(KIND[q["src"]])}, bez nazwy autora</span><span>{q["likes"]} polubień</span></div></div>')

    def src_tile(s):
        row = src[s]
        n = row['pozytyw'] + row['negatyw']
        return tile(SOURCE_NAMES[s], _pct(row['udzial']) if n else '-',
                    f'{_pct(row["od"])} do {_pct(row["do"])}, n={n} / {row["n"]}' if n else f'{row["n"]} na temat, brak opinii ze znakiem', 'src')
    days = ''.join(bar_row(_dm(d), r, mark=(d == summary['premiere'])) for d, r in summary['by_day'].items()) \
        or '<p class="muted">Brak tekstów z datą.</p>'
    topics = ''.join(bar_row(TOPIC_NAMES[t], r) for t, r in summary['by_topic'].items()) or '<p class="muted">Brak ocenionych tekstów.</p>'
    peak = max(summary['volume'].values() or [1]) or 1
    volume = ''.join(f'<div class="vol"><span class="vol-bar" style="height:{round(100 * v / peak)}%"></span>'
                     f'<span class="vol-n">{v}</span><span class="vol-day">{_dm(d)}</span></div>' for d, v in summary['volume'].items())
    premiere_note = (f'Najpewniej premiera: {_dm(summary["premiere"])} (pierwszy wysyp wpisów).' if summary['premiere']
                     else 'W danych nie widać wyraźnego dnia premiery (brak nagłego wysypu wpisów).')
    source_rows = ''.join(
        f'<tr><td>{e(SOURCE_NAMES[s])}</td><td>{meta["raw"].get(s, 0)}</td><td>{meta["kept"].get(s, 0)}</td><td>{src[s]["n"]}</td>'
        f'<td class="pos-t">{src[s]["pozytyw"]}</td><td class="neg-t">{src[s]["negatyw"]}</td><td>{src[s]["neutralny"]}</td>'
        f'<td>{_pct(src[s]["udzial"]) if src[s]["pozytyw"] + src[s]["negatyw"] else "-"}</td>'
        f'<td>{_pct(w["wagi"][s]) if s in w["wagi"] else "-"}</td></tr>' for s in SOURCES)
    media_rows = ''.join(f'<li><span>{e(m["text"])}</span><span class="muted">{e(m["outlet"])} · {_dm(m["day"])} · '
                         f'{e(m["label"] or "nieocenione")}</span></li>' for m in summary['media']) \
        or '<li class="muted">Brak tytułów z frazami w tym okresie w naszej bazie.</li>'
    dropped = ', '.join(f'{k}: {v}' for k, v in sorted(meta['dropped'].items())) or 'nic'
    yt_note = (f'{meta["yt_videos"]} filmów z komentarzami, {meta["yt_units"]} jednostek YouTube' if meta['yt_units'] else 'bez YouTube')
    limits = [
        'Badamy tylko X, YouTube, Wykop, publiczne kanały RSS forów i blogów oraz tytuły z naszej bazy mediów. Facebook, Instagram i TikTok nie są '
        'badane (brak legalnego dostępu) - tam może toczyć się większa część rozmowy. Google Trends pomijamy (brak oficjalnego API).',
        'Użytkownicy X i komentujący na YouTube nie są próbą reprezentatywną klientów sieci: częściej piszą osoby zaangażowane, z silną opinią.',
        'Wyszukiwanie po frazach: pomijamy teksty bez tych słów (np. tylko ze zdjęciem albo z literówką), łapiemy część tekstów nie na temat.',
        'Filtr prosty: odrzucamy podania dalej, reklamy, powtórzone teksty i więcej niż 3 teksty tego samego autora; nie wykrywa wyrafinowanych botów.',
        'Ocenę nadaje model językowy (Mercury) - ironia i żarty bywają źle odczytane; przedziały ufności (Wilson 95%) dotyczą tylko błędu próby.',
        'Udział liczymy wśród tekstów z wyraźnym znakiem (pozytyw + negatyw); neutralne i nie na temat podajemy osobno.',
        'Łączny wynik to średnia udziałów źródeł z wagami ' + ', '.join(f'{SOURCE_NAMES[s].split(" ")[0]} {WEIGHTS[s]:.2f}' for s in SOURCES) + ' '
        '(wybór redakcyjny, przeskalowany do źródeł z danymi), nie wynik statystyczny.',
        'Dane osób prywatnych tylko w pamięci: żadnych nazw ani identyfikatorów autorów w raporcie i CSV; surowe dane usunięte po wygenerowaniu.',
    ]
    mercury = f'{meta["calls"]} wywołań Mercury' + (f' ({e(meta["model"])})' if meta.get('model') else '')
    stopped = ''.join(f'<p class="warn">{e(s)}</p>' for s in meta.get('stopped', []) if s)
    weights_note = ' · '.join(f'{SOURCE_NAMES[s].split(" ")[0]} {_pct(v)}' for s, v in w['wagi'].items()) or 'brak źródeł z opiniami'
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>
:root{{--bg:#0b1020;--card:#121a2d;--line:#223052;--ink:#e8edf7;--muted:#9aa7bf;--pos:#2fbf71;--neg:#e5484d;--blue:#4f8cff;--gap:16px}}
*{{box-sizing:border-box;min-width:0}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:anywhere}}
.wrap{{max-width:1080px;margin:0 auto;padding:32px 16px 48px;overflow-x:clip}}h1{{font-size:28px;margin:0 0 4px;line-height:1.2}}h2{{font-size:18px;margin:0 0 12px;line-height:1.3}}
.sub{{color:var(--muted);margin:0 0 24px}}.muted{{color:var(--muted)}}.warn{{color:#f5b84f;margin:0 0 8px}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap);margin-bottom:var(--gap)}}.tiles.five{{grid-template-columns:repeat(5,1fr)}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;height:124px;display:grid;grid-template-rows:auto 1fr auto}}
.tile-label{{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tile-value{{font-size:30px;font-weight:600;line-height:1;align-self:center}}.tile-note{{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tile.pos .tile-value{{color:var(--pos)}}.tile.neg .tile-value{{color:var(--neg)}}.tile.src .tile-value{{color:var(--blue)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:var(--gap)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap);margin-bottom:var(--gap)}}.two .card{{margin-bottom:0;display:grid;grid-template-rows:auto 1fr auto}}
.row{{display:grid;grid-template-columns:minmax(72px,110px) minmax(120px,1fr) 44px 96px 78px;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}}
.row:first-of-type{{border-top:0}}.row-name{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.row-num{{text-align:right;font-weight:600}}
.row-ci,.row-n{{color:var(--muted);font-size:12px;text-align:right;white-space:nowrap}}
.bar{{display:flex;height:10px;border-radius:5px;overflow:hidden;background:#1a2440}}.bar .pos{{background:var(--pos)}}.bar .neg{{background:var(--neg)}}
.mark{{font-size:11px;font-weight:600;color:var(--blue);margin-left:6px}}.row.is-premiere .row-name{{color:var(--blue)}}
.vols{{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;height:150px;margin:12px 0 0}}
.vol{{display:grid;grid-template-rows:1fr auto auto;height:100%;text-align:center;font-size:12px;color:var(--muted)}}
.vol-bar{{align-self:end;background:var(--blue);border-radius:4px 4px 0 0;min-height:2px;width:100%}}.vol-n{{color:var(--ink);font-weight:600;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:right;padding:8px 6px;border-top:1px solid var(--line);white-space:nowrap}}
th{{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.04em;border-top:0}}th:first-child,td:first-child{{text-align:left}}
td.pos-t{{color:var(--pos)}}td.neg-t{{color:var(--neg)}}
.quotes{{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap);margin-bottom:var(--gap)}}
.quote{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-height:132px;display:grid;grid-template-rows:1fr auto;margin-bottom:12px}}
.quote-text{{margin:0 0 10px;font-size:14px}}.quote-foot{{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}}
.side h2 span{{font-size:12px;font-weight:400;color:var(--muted);margin-left:8px}}
ul{{margin:0;padding-left:18px}}li{{margin:4px 0}}li span{{display:block}}li span.muted{{font-size:12px}}
.legend{{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-bottom:8px}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}}
code{{font-size:12px;color:var(--muted);word-break:break-all}}.scroll{{overflow-x:auto}}.foot{{color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}}
@media(max-width:720px){{.wrap{{padding-top:20px}}.tiles,.tiles.five{{grid-template-columns:1fr 1fr}}.two,.quotes{{grid-template-columns:1fr}}.row{{grid-template-columns:90px 1fr 44px;row-gap:2px}}.row-ci,.row-n{{grid-column:2/4;text-align:left}}.tile-value{{font-size:24px}}table{{font-size:12px}}th,td{{padding:6px 4px}}.quote{{min-height:0}}.vol-day{{font-size:10px}}}}
</style></head><body><div class="wrap">
<h1>{e(title)}</h1>
<p class="sub">spin.clinic · raport nastrojów · {now.strftime('%d.%m.%Y %H:%M')} · zakres: {zakres} · frazy: {e(', '.join(frazy))}</p>
{stopped}
<div class="tiles">
{tile('Łącznie pozytywne', _pct(w['udzial']) if w['n'] else '-', f'wagi: {weights_note}' if w['n'] else 'brak opinii ze znakiem', 'pos')}
{tile('Łącznie negatywne', _pct(1 - w['udzial']) if w['n'] else '-', f'{w["n"]} opinii ze znakiem we wszystkich źródłach' if w['n'] else 'brak opinii ze znakiem', 'neg')}
{tile('Wszystkie głosy bez mediów', _pct(soc['udzial']) if n_soc else '-', f'{_pct(soc["od"])} do {_pct(soc["do"])} (95%), n={n_soc}' if n_soc else 'brak opinii ze znakiem')}
{tile('Próba', str(sum(meta['kept'].values())), f'{meta["reads"]} odczytów X, {yt_note}; {summary["total"]["neutralny"]} neutralnych, {meta["unrated"]} nieocenionych')}
</div>
<div class="tiles five">
{''.join(src_tile(s) for s in SOURCES)}
</div>
<div class="card"><h2>Źródła</h2><div class="scroll"><table><thead><tr><th>Źródło</th><th>Pobrane</th><th>Po filtrze</th><th>Na temat</th><th>Pozytyw</th><th>Negatyw</th><th>Neutralne</th><th>Udział pozytyw</th><th>Waga</th></tr></thead>
<tbody>{source_rows}</tbody></table></div><p class="muted" style="margin:12px 0 0">Udział pozytywnych wśród opinii ze znakiem. Facebook, Instagram i TikTok nie są badane.</p></div>
<div class="card"><h2>Wpisy na X dzień po dniu</h2><p class="muted" style="margin:0">{e(premiere_note)} Źródło liczb: {e(summary['volume_source'])}.</p><div class="vols">{volume}</div></div>
<div class="two">
<div class="card"><h2>Udział pozytywnych po dniach (bez mediów)</h2><div><div class="legend"><span><i style="background:var(--pos)"></i>pozytywne</span><span><i style="background:var(--neg)"></i>negatywne</span></div>{days}</div><p class="muted" style="margin:12px 0 0">Procent i 95% przedział Wilsona; n = opinie ze znakiem / wszystkie na temat.</p></div>
<div class="card"><h2>Udział pozytywnych po tematach (bez mediów)</h2><div><div class="legend"><span><i style="background:var(--pos)"></i>pozytywne</span><span><i style="background:var(--neg)"></i>negatywne</span></div>{topics}</div><p class="muted" style="margin:12px 0 0">Temat nadaje model: smak, cena, osoba, marketing, inne.</p></div>
</div>
<div class="quotes">
<div class="side"><h2>Głosy pozytywne<span>5 najczęściej polubionych</span></h2>{''.join(quote_box(q) for q in summary['quotes']['pozytyw']) or '<p class="muted">Brak.</p>'}</div>
<div class="side"><h2>Głosy negatywne<span>5 najczęściej polubionych</span></h2>{''.join(quote_box(q) for q in summary['quotes']['negatyw']) or '<p class="muted">Brak.</p>'}</div>
</div>
<div class="card"><h2>Jak piszą media (tytuły z naszej bazy)</h2><ul>{media_rows}</ul></div>
<div class="two">
<div class="card"><h2>Metoda</h2><ul>
<li>X: oficjalne API, wyszukiwanie pełnotekstowe od {zakres}, zapytanie: <code>{e(query)}</code>; {meta['reads']} odczytów, {meta['pages']} stron.</li>
<li>YouTube: filmy z frazami w okresie (search.list), komentarze pod najpopularniejszymi (commentThreads.list); {yt_note}.</li>
<li>Wykop: oficjalne API v3 (wyszukiwanie wpisów i znalezisk po frazach), {meta['wykop_calls']} zapytań.</li>
<li>Fora i blogi: {meta['rss_feeds']} publicznych kanałów RSS/Atom (źródła z zatwierdzoną kartą dostępu i lista z env), tylko tytuł i fragment z kanału.</li>
<li>Media: tytuły artykułów z frazami w okresie z naszej bazy (tylko metadane).</li>
<li>Filtr: po nim {sum(meta['kept'].values())} z {sum(meta['raw'].values())} tekstów; odrzucone: {e(dropped)}.</li>
<li>Ocena: {mercury}, paczki po {BATCH} tekstów; nieocenione: {meta['unrated']}.</li>
</ul><p class="muted" style="margin:12px 0 0">Plik CSV obok raportu: źródło, dzień, ocena, temat, powód, polubienia, skrócony tekst.</p></div>
<div class="card"><h2>Ograniczenia</h2><ul>{''.join(f'<li>{e(l)}</li>' for l in limits)}</ul><p class="muted" style="margin:12px 0 0">Zasady: tylko legalne źródła, nic nie trafia do tabel spin.clinic.</p></div>
</div>
<p class="foot">spin.clinic · operator iapply sp. z o.o. · raport jednorazowy, nie jest sondażem</p>
</div></body></html>'''


# --- całość ---
def plan(frazy: list[str], *, days: int = 7, limit: int = 500, yt_limit: int = 1500, od=None, do=None, now=None) -> dict:
    """Szacunek przed pobraniem: liczniki X (bez odczytu wpisów), filmy YouTube (search 100 jednostek + videos 1), tytuły z bazy."""
    from news import inception, youtube_collect as yt
    from news.odbior_spinu import options
    from news.political_polling import POST_PRICE, configuration
    now = now or timezone.now()
    frazy = phrases(frazy)
    query = build_query(frazy)
    start, end = window(days, od, do, now)
    config = configuration()
    counts = x_counts(query, config, start, end) if config else {'days': {}, 'total': 0, 'error': 'X wyłączony'}
    videos = yt_videos(frazy, start, end)
    yt_comments_total = sum(v['comments'] for v in videos['videos'][:YT_VIDEOS])
    x_reads = min(limit, counts['total']) if not counts['error'] else limit
    yt_reads = min(yt_limit, yt_comments_total)
    media = len(media_titles(frazy, start, end))
    texts = x_reads + yt_reads + media
    calls = math.ceil(texts / BATCH)
    return {'query': query, 'start': start, 'end': end, 'counts': counts, 'videos': videos, 'media': media,
            'estimate': {'x_reads': x_reads, 'x_usd': str(POST_PRICE * x_reads), 'yt_comments': yt_reads,
                         'yt_units': yt.UNIT_COST.get('search', 100) + 1 + math.ceil(yt_reads / YT_PAGE) + min(YT_VIDEOS, len(videos['videos'])),
                         'mercury_calls': calls, 'mercury_tokens': calls * (len(SYSTEM) // 3 + BATCH * 130 + 120 * BATCH + 200)},
            'x_configured': bool(config), 'daily_cap': options()['daily_cap'], 'yt_units_left': yt.units_left() if yt.enabled() else 0,
            'wykop': wykop_enabled(), 'rss_feeds': len(rss_feed_urls()),
            'mercury_ready': inception.configured() and inception.no_training() and inception.ready(4000)}


def run(frazy: list[str], *, days: int = 7, limit: int = 500, yt_limit: int = 1500, title: str = '', topic: str = '', od=None, do=None,
        keep_raw: bool = False, now=None) -> dict:
    """Pełny przebieg: trzy źródła, filtr, ocena, statystyka, HTML + CSV. Surowe dane zostają w pamięci (keep_raw: plik JSON obok)."""
    from news.political_polling import configuration
    now = now or timezone.now()
    frazy = phrases(frazy)
    query = build_query(frazy)
    start, end = window(days, od, do, now)
    title = title or f'Nastroje: {frazy[0]}'
    topic = topic or ', '.join(frazy)
    config = configuration()
    stopped = []
    if config:
        counts = x_counts(query, config, start, end)
        fetched = fetch_x(query, limit, config, start, end, now)
    else:
        counts = {'days': {}, 'total': 0, 'error': 'X wyłączony (X_POLITICAL_POLLING_ENABLED / X_POLITICAL_BEARER_TOKEN)'}
        fetched = {'rows': [], 'reads': 0, 'pages': 0, 'stopped': counts['error']}
    videos = yt_videos(frazy, start, end)
    comments = yt_comments(videos['videos'], yt_limit) if videos['videos'] else {'rows': [], 'units': 0, 'error': '', 'videos': 0}
    wykop = wykop_search(frazy, start, end)
    rss = rss_entries(frazy, start, end)
    media = media_titles(frazy, start, end)
    raw = fetched['rows'] + comments['rows'] + wykop['rows'] + rss['rows'] + media
    stopped += [s for s in (fetched['stopped'], counts['error'], videos['error'], comments['error'], wykop['error'], rss['error']) if s]
    posts, dropped = filter_posts(raw)
    rated = classify(posts, topic)
    if rated['stopped']:
        stopped.append(rated['stopped'])
    summary = summarise(posts, start, end, counts['days'] if not counts['error'] and counts['days'] else None)
    meta = {'now': now, 'start': start, 'end': end, 'raw': dict(Counter(r['src'] for r in raw)), 'kept': dict(Counter(p['src'] for p in posts)),
            'reads': fetched['reads'], 'pages': fetched['pages'], 'yt_units': videos['units'] + comments['units'], 'yt_videos': comments['videos'],
            'wykop_calls': wykop['calls'], 'rss_feeds': rss['feeds'],
            'dropped': dict(dropped), 'calls': rated['calls'], 'model': rated['model'], 'unrated': rated['unrated'], 'stopped': stopped}
    folder = output_dir()
    stem = f'nastroje-{slug(frazy[0])}-{now.astimezone(PL).strftime("%Y%m%d-%H%M")}'
    html_path, csv_path = folder / f'{stem}.html', folder / f'{stem}.csv'
    html_path.write_text(render_html(title, frazy, query, summary, meta), encoding='utf-8')
    write_csv(csv_path, posts)
    raw_path = ''
    if keep_raw:
        raw_path = str(folder / f'{stem}-surowe.json')
        Path(raw_path).write_text(json.dumps({'uwaga': 'dane surowe do debugowania, usuń po użyciu', 'wiersze': raw}, ensure_ascii=False, indent=1),
                                  encoding='utf-8')
    for bucket in (raw, fetched['rows'], comments['rows'], wykop['rows'], rss['rows']):
        bucket.clear()
    return {'query': query, 'summary': summary, 'meta': meta, 'html': str(html_path), 'csv': str(csv_path), 'raw': raw_path, 'title': title}


def summary_text(result: dict) -> str:
    s, m, w = result['summary'], result['meta'], result['summary']['weighted']
    soc = s['social']
    n = soc['pozytyw'] + soc['negatyw']
    per_source = '; '.join(f'{SOURCE_NAMES[k]}: {_pct(v["udzial"])} (n={v["pozytyw"] + v["negatyw"]})' if v['pozytyw'] + v['negatyw']
                           else f'{SOURCE_NAMES[k]}: brak opinii ze znakiem' for k, v in s['by_source'].items())
    lines = [result['title'],
             'Łącznie (wagi ' + ', '.join(f'{SOURCE_NAMES[s].split(" ")[0]} {WEIGHTS[s]}' for s in SOURCES) + f'): pozytywne {_pct(w["udzial"])}, '
             f'negatywne {_pct(1 - w["udzial"])}, {w["n"]} opinii ze znakiem' if w['n'] else 'Brak opinii z wyraźnym znakiem',
             f'Wszystkie głosy bez mediów: {_pct(soc["udzial"])} pozytywnych ({_pct(soc["od"])} do {_pct(soc["do"])}, 95%), n={n}' if n else '',
             per_source,
             f'Neutralne: {s["total"]["neutralny"]}, nie na temat: {s["counts"].get("nie_na_temat", 0)}, nieocenione: {m["unrated"]}',
             f'Próba: {sum(m["kept"].values())} tekstów po filtrze z {sum(m["raw"].values())} pobranych ({m["reads"]} odczytów X, '
             f'{m["yt_units"]} jednostek YouTube, {m["calls"]} wywołań Mercury)',
             f'Zakres: {m["start"].astimezone(PL).strftime("%d.%m.%Y")} do {m["end"].astimezone(PL).strftime("%d.%m.%Y")}'
             + (f', najpewniej premiera: {s["premiere"]}' if s['premiere'] else ''),
             *(f'Uwaga: {x}' for x in m['stopped']),
             f'HTML: {result["html"]}', f'CSV: {result["csv"]}', f'Surowe (debugowanie): {result["raw"]}' if result.get('raw') else '',
             'Tylko X, YouTube, Wykop, publiczne RSS i tytuły mediów (bez FB, IG, TikToka); ocena modelem; bez nazw autorów.']
    return '\n'.join(l for l in lines if l)


def admin_email() -> str:
    return next((os.environ.get(n, '').strip() for n in ('LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL', 'X_POST_ALERT_EMAIL', 'SOCIAL_VIDEO_EMAIL')
                 if os.environ.get(n, '').strip()), '')


def send(result: dict) -> bool:
    from news.social_publish import _mail
    to = admin_email()
    return bool(to) and _mail(to, f'spin.clinic · {result["title"]}', summary_text(result), important=True)
