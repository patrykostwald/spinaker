"""Raport nastrojów: udział opinii pozytywnych i negatywnych o jednym temacie z trzech legalnych źródeł.

Źródła (osobne sekcje + łączny wynik: wszystkie opinie ze znakiem razem, bez stałych wag; źródła z mniej niż 30 opiniami to „mała próba”):
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
Pamięć podręczna (24 h, katalog raportów/pamiec): teksty już po filtrze i anonimizacji, żeby ponowna ocena (--swiezo wymusza
pobranie) nie kupowała odczytów X drugi raz; --z-pliku <csv|jsonl|json> ocenia teksty z pliku (np. CSV poprzedniego raportu).
Ocena: Mercury (news/inception.py, trasa poboczna) w paczkach po 20 tekstów; gdy odmówi - darmowe modele Konsylium, potem
Groq/NIM z env; nigdy trasy płatne. Raport podaje, który model ocenił ile tekstów; bez łącznego procentu, gdy coś zostało nieocenione.
"""
from __future__ import annotations

import csv
import hashlib
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
SOURCE_SHORT = {'x': 'X', 'youtube': 'YouTube', 'wykop': 'Wykop', 'rss': 'Fora i blogi', 'media': 'Media'}
KIND = {'x': 'wpis z X', 'youtube': 'komentarz z YouTube', 'wykop': 'wpis z Wykopu', 'rss': 'wpis z forum lub bloga', 'media': 'tytuł artykułu'}
SMALL_SAMPLE = 30  # poniżej tylu opinii ze znakiem źródło dostaje etykietę „mała próba”
CACHE_HOURS = 24  # pamięć podręczna pobranych (zanonimizowanych) tekstów: ponowna ocena bez ponownego płacenia za X
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


# --- ocena: Mercury, potem darmowe modele Konsylium, potem Groq/NIM z env; nigdy trasy płatne ---
def _council_members() -> list[tuple[str, str]]:
    """Wolne darmowe modele Konsylium (ta sama reguła co ocena odpowiedzi w odbior_spinu: bez Gemini i Claude, limity, okno agentów)."""
    from news.odbior_spinu import _members
    return _members()


def _council_ask(member: tuple[str, str], system: str, user: str, schema: dict, max_tokens: int) -> dict:
    from news import agents_common as common
    from news import council_registry as registry
    from news.clinic_council import ask
    token = registry.reservation_guard.set(common._guard)
    try:
        return ask(member, system, user, schema, max_tokens)
    finally:
        registry.reservation_guard.reset(token)


def _free_chat(system: str, user: str, schema: dict, max_tokens: int) -> tuple[dict, str]:
    from news.clinic_ai import _free_chat
    return _free_chat(system, user, schema, max_tokens)


class _Router:
    """Jedna paczka tekstów: Mercury (własna darmowa pula), przy odmowie darmowi członkowie Konsylium, na końcu Groq/NIM z env.
    Trasa wypada z kolejki po odmowie budżetu albo po dwóch kolejnych błędach; `notes` tłumaczą każde wypadnięcie."""

    def __init__(self):
        self.mercury, self.mercury_fails, self.members, self.free_chat = True, 0, None, True
        self.notes: list[str] = []

    def mercury_reason(self, need: int) -> str:
        from news import inception
        if not inception.configured():
            return 'brak klucza INCEPTION_API_KEY'
        if not inception.no_training():
            return 'INCEPTION_NO_TRAINING nie jest true (dane osób prywatnych)'
        reason = inception.refusal(need)
        if reason:
            return {'inception_free_budget': 'wyczerpana darmowa pula tokenów', 'inception_daily_limit': 'pułap dzienny tokenów (INCEPTION_DAILY_TOKENS)',
                    'inception_monthly_limit': 'pułap miesięczny tokenów', 'inception_halted': 'zatrzymany po błędzie konta (402/401)'}.get(reason, reason)
        return ''

    def ask(self, user: str, max_tokens: int):
        from news import inception
        from news.clinic_ai import ClinicAIError
        if self.mercury:
            answer = inception.side_json(SYSTEM, user, SCHEMA, max_tokens=max_tokens, private_data=True)
            if answer is not None:
                self.mercury_fails = 0
                return answer
            reason = self.mercury_reason(inception.estimate(SYSTEM, user, max_tokens))
            last = str(inception.usage().get('last_error') or '')
            if reason:
                self.mercury = False
                self.notes.append(f'Mercury: {reason}')
            else:
                self.mercury_fails += 1
                if self.mercury_fails >= 2:
                    self.mercury = False
                    self.notes.append(f'Mercury: dwie kolejne paczki bez odpowiedzi ({last or "błąd API, np. 429 albo przekroczony czas"}), dalej bez niego')
                else:
                    self.notes.append(f'Mercury: paczka bez odpowiedzi ({last or "błąd API"}), następna paczka znów do niego')
        if self.members is None:
            try:
                self.members = _council_members()
            except Exception as error:  # noqa: BLE001 - brak bazy albo rejestru: dalej bez Konsylium
                self.members, _ = [], self.notes.append(f'Konsylium: {type(error).__name__}')
        while self.members:
            member = self.members[0]
            try:
                return _council_ask(member, SYSTEM, user, SCHEMA, max_tokens), member[1]
            except ClinicAIError as error:
                self.notes.append(f'{member[1]}: {error.code}')
            except Exception as error:  # noqa: BLE001 - zła odpowiedź jednego modelu: następny
                self.notes.append(f'{member[1]}: {type(error).__name__}')
            self.members.pop(0)
        if self.free_chat:
            try:
                return _free_chat(SYSTEM, user, SCHEMA, max_tokens)
            except ClinicAIError as error:
                self.free_chat = False
                self.notes.append(f'Groq/NIM z env: {error.code}')
        return None


def classify(posts: list[dict], topic: str, batch: int = BATCH) -> dict:
    """Dopisuje do każdego tekstu ocenę, temat i powód. Teksty pominięte przez model wracają w drugim przebiegu.
    Zwraca {'calls': n, 'models': {model: liczba ocenionych tekstów}, 'model': nazwy, 'unrated': n, 'stopped': powód, 'routes': uwagi}."""
    router, calls, models = _Router(), 0, Counter()
    exhausted = False
    for _pass in range(2):
        todo = [p for p in posts if not p.get('label')]
        if not todo or exhausted:
            break
        for start in range(0, len(todo), batch):
            chunk = todo[start:start + batch]
            payload = {'temat': topic, 'teksty': [{'i': i, 'rodzaj': KIND[p['src']], 'tekst': p['text'][:300]} for i, p in enumerate(chunk)]}
            answer = router.ask(json.dumps(payload, ensure_ascii=False), 120 * len(chunk) + 200)
            if answer is None:
                exhausted = True
                break
            data, model = answer
            calls += 1
            rated = {item['i']: item for item in (data.get('oceny') or []) if isinstance(data, dict)
                     if isinstance(item, dict) and isinstance(item.get('i'), int) and 0 <= item['i'] < len(chunk)}
            for i, post in enumerate(chunk):
                item = rated.get(i) or {}
                label, topic_key = item.get('ocena'), item.get('temat')
                if label not in LABELS:
                    continue
                post['label'], post['topic'] = label, topic_key if topic_key in TOPICS else 'inne'
                post['reason'] = ' '.join(str(item.get('powod') or '').split())[:200]
                models[model] += 1
    unrated = sum(1 for p in posts if not p.get('label'))
    for post in posts:
        post.setdefault('label', ''), post.setdefault('topic', 'inne'), post.setdefault('reason', '')
    stopped = ''
    if unrated and exhausted:
        stopped = f'Żadna darmowa trasa nie oceniła {unrated} z {len(posts)} tekstów: ' + '; '.join(router.notes[:6])
    elif unrated:
        stopped = f'Model pominął {unrated} z {len(posts)} tekstów także w drugim przebiegu.'
    return {'calls': calls, 'models': dict(models), 'model': ', '.join(models), 'unrated': unrated, 'stopped': stopped, 'routes': router.notes}


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
            'nie_na_temat': sum(1 for p in group if p.get('label') == 'nie_na_temat'), 'udzial': p, 'od': low, 'do': high,
            'small': 0 < pos + neg < SMALL_SAMPLE}


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


def pooled(by_source: dict, sources=SOCIAL) -> dict:
    """Łączny udział pozytywnych: wszystkie opinie ze znakiem z podanych źródeł razem (każdy głos liczy się raz, więc źródło
    waży tyle, ile ma opinii). `wagi` to udział źródła w tej puli - tylko do pokazania, nie do liczenia. Wilson 95%."""
    parts = {s: v for s, v in by_source.items() if s in sources and v['pozytyw'] + v['negatyw']}
    pos, n = sum(v['pozytyw'] for v in parts.values()), sum(v['pozytyw'] + v['negatyw'] for v in parts.values())
    p, low, high = wilson(pos, n)
    return {'udzial': p, 'od': low, 'do': high, 'n': n, 'pozytyw': pos, 'negatyw': n - pos,
            'wagi': {s: (v['pozytyw'] + v['negatyw']) / n for s, v in parts.items()} if n else {}, 'small': 0 < n < SMALL_SAMPLE}


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
            'total': share(on_topic), 'social': share(social), 'by_source': by_source, 'pooled': pooled(by_source),
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


# --- pamięć podręczna (24 h, zanonimizowane teksty po filtrze) i teksty z pliku ---
def cache_dir() -> Path:
    path = output_dir() / 'pamiec'
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(frazy: list[str], start: datetime, end: datetime) -> str:
    raw = '|'.join(sorted(_norm(f) for f in frazy)) + '|' + start.astimezone(PL).date().isoformat() + '|' + end.astimezone(PL).date().isoformat()
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def cache_sweep(now=None) -> int:
    """Usuwa wpisy starsze niż CACHE_HOURS (pole `expires` albo czas pliku). Zwraca liczbę usuniętych."""
    now, removed = now or timezone.now(), 0
    for path in cache_dir().glob('*.json'):
        try:
            expires = json.loads(path.read_text(encoding='utf-8')).get('expires', '')
            stale = datetime.fromisoformat(expires) <= now if expires else True
        except (ValueError, OSError, AttributeError):
            stale = True
        if stale or datetime.fromtimestamp(path.stat().st_mtime, dt_timezone.utc) <= now - timedelta(hours=CACHE_HOURS):
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def cache_save(frazy: list[str], start: datetime, end: datetime, bundle: dict, now=None) -> str:
    now = now or timezone.now()
    path = cache_dir() / f'{cache_key(frazy, start, end)}.json'
    payload = {'uwaga': 'zanonimizowane teksty po filtrze (bez autorów i identyfikatorów), kasowane po 24 h', 'frazy': frazy,
               'saved': now.isoformat(), 'expires': (now + timedelta(hours=CACHE_HOURS)).isoformat(), **bundle}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return str(path)


def cache_load(frazy: list[str], start: datetime, end: datetime, now=None) -> dict | None:
    now = now or timezone.now()
    path = cache_dir() / f'{cache_key(frazy, start, end)}.json'
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        if datetime.fromisoformat(payload['expires']) <= now:
            path.unlink(missing_ok=True)
            return None
        return payload
    except (ValueError, KeyError, OSError):
        path.unlink(missing_ok=True)
        return None


def _post(row: dict) -> dict | None:
    src, text = str(row.get('src') or row.get('zrodlo') or ''), str(row.get('text') or row.get('tekst_skrocony') or row.get('tekst') or '')
    if src not in SOURCES or not text.strip():
        return None
    created = str(row.get('created_at') or row.get('dzien') or '')
    try:
        likes = int(row.get('likes') if row.get('likes') is not None else row.get('polubienia') or 0)
    except (TypeError, ValueError):
        likes = 0
    return {'src': src, 'text': scrub(text)[:300], 'likes': likes, 'created_at': created, 'video': str(row.get('video') or ''),
            'outlet': str(row.get('outlet') or '')}


def load_posts(path: str) -> list[dict]:
    """Teksty z pliku: CSV raportu (zrodlo;dzien;...;tekst_skrocony), JSONL (jeden tekst na linię) albo JSON pamięci podręcznej
    (`posts`) lub pliku --zachowaj (`wiersze`, wtedy przechodzą przez filtr). Bez pliku albo bez tekstów: NastrojeError."""
    file = Path(path)
    if not file.is_file():
        raise NastrojeError('brak_pliku', f'Nie ma pliku {path}.')
    text = file.read_text(encoding='utf-8-sig')
    rows: list[dict] = []
    if file.suffix.lower() == '.csv':
        rows = list(csv.DictReader(text.splitlines(), delimiter=';'))
    elif file.suffix.lower() == '.jsonl':
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        if isinstance(data, dict) and data.get('wiersze'):
            rows, _ = filter_posts([r for r in data['wiersze'] if isinstance(r, dict) and r.get('src') in SOURCES])
        else:
            rows = data.get('posts') if isinstance(data, dict) else data
    posts = [p for p in (_post(r) for r in rows or [] if isinstance(r, dict)) if p]
    if not posts:
        raise NastrojeError('pusty_plik', f'W pliku {path} nie ma tekstów do oceny.')
    return posts


def _pct(value: float) -> str:
    return f'{round(value * 100)}%'


def _dm(day: str) -> str:
    try:
        return datetime.fromisoformat(day).strftime('%d.%m')
    except ValueError:
        return day


LOGO_SERIF = "Georgia, 'Times New Roman', 'DejaVu Serif', serif"
LOGO_SANS = "Montserrat, 'Segoe UI', Inter, system-ui, sans-serif"


def logo_svg(variant: int = 1, height: int = 28, title: bool = True) -> str:
    """Znak przeszłość.today: czerń, czerwień i biel (właściciel 7.10). Dwa kroje: szeryfowy „przeszłość” i bezszeryfowe „today”;
    czerwień tylko jako jeden akcent (kropka albo linia). 1: biały na czerni (raport), 2: czarny na bieli, 3: układ dwuwierszowy
    na czerni z czerwoną linią (kwadrat, np. awatar). Tekst w SVG, bez osadzonych fontów."""
    ink, bg = ('#ffffff', '#000000') if variant != 2 else ('#111111', '#ffffff')
    red = '#e0313a'
    label = f'<title>przeszłość.today</title>' if title else ''
    if variant == 3:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320" width="{height}" height="{height}" role="img" aria-label="przeszłość.today">'
                f'{label}<rect width="320" height="320" fill="{bg}"/>'
                f'<text x="32" y="150" fill="{ink}" font-family="{LOGO_SERIF}" font-size="58" letter-spacing="-1.5">przeszłość</text>'
                f'<rect x="32" y="172" width="64" height="4" fill="{red}"/>'
                f'<text x="32" y="236" fill="{ink}" font-family="{LOGO_SANS}" font-size="30" font-weight="600" letter-spacing="7">TODAY</text></svg>')
    width = round(height * 600 / 120)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="{width}" height="{height}" role="img" aria-label="przeszłość.today">'
            f'{label}<rect width="600" height="120" fill="{bg}"/>'
            f'<text x="20" y="82" fill="{ink}" font-family="{LOGO_SERIF}" font-size="72" letter-spacing="-2">przeszłość'
            f'<tspan fill="{red}" dx="2">.</tspan><tspan fill="{ink}" font-family="{LOGO_SANS}" font-size="38" font-weight="600" letter-spacing="3" dx="6">today</tspan></text></svg>')


def render_html(title: str, frazy: list[str], query: str, summary: dict, meta: dict) -> str:
    """Raport w stylu przeszłość.today (kit .px-*): czerń, cienkie linie, równe boksy z góra/środek/dół, jeden akcent (czerwień)."""
    e = html.escape
    w, src, soc = summary['pooled'], summary['by_source'], summary['social']
    unrated, kept = meta['unrated'], sum(meta['kept'].values())
    now = meta['now'].astimezone(PL)
    zakres = f'{meta["start"].astimezone(PL).strftime("%d.%m.%Y")} do {meta["end"].astimezone(PL).strftime("%d.%m.%Y")}'
    headline_ok = bool(w['n']) and not unrated

    def small_tag(row):
        return '<em class="tag">mała próba</em>' if row.get('small') else ''

    def cell(label, value, note, tag=''):
        return (f'<div class="cell"><h3 class="h3"><span>{e(label)}</span>{tag}</h3><b class="num">{e(value)}</b>'
                f'<span class="note" title="{e(note)}">{e(note)}</span></div>')

    def bar_row(name, row, mark=False):
        n = row['pozytyw'] + row['negatyw']
        pos = round(row['udzial'] * 100) if n else 0
        label = f'{e(name)}<em class="mark">premiera?</em>' if mark else e(name)
        hint = f'{e(name)}: {row["pozytyw"]} pozytywnych, {row["negatyw"]} negatywnych, {row["neutralny"]} neutralnych'
        return (f'<div class="row{" is-mark" if mark else ""}" title="{hint}"><div class="row-name">{label}</div>'
                f'<div class="bar"><span class="pos" style="width:{pos}%"></span><span class="neg" style="width:{100 - pos if n else 0}%"></span></div>'
                f'<div class="row-num">{_pct(row["udzial"]) if n else "-"}</div>'
                f'<div class="row-ci">{(_pct(row["od"]) + " do " + _pct(row["do"])) if n else "brak opinii ze znakiem"}</div>'
                f'<div class="row-n">n={n} / {row["n"]}</div></div>')

    def quote_box(q):
        return (f'<div class="quote"><p class="quote-text">„{e(q["text"])}”</p>'
                f'<div class="quote-foot"><span>{e(KIND[q["src"]])}, bez nazwy autora</span><span>{q["likes"]} polubień</span></div></div>')

    def src_cell(s):
        row = src[s]
        n = row['pozytyw'] + row['negatyw']
        note = f'n={n}/{row["n"]} · {_pct(row["od"])} do {_pct(row["do"])}' if n else (f'{row["n"]} na temat, bez znaku' if row['n'] else 'brak tekstów')
        return cell(SOURCE_SHORT[s], _pct(row['udzial']) if n else '-', note, small_tag(row))
    days = ''.join(bar_row(_dm(d), r, mark=(d == summary['premiere'])) for d, r in summary['by_day'].items()) \
        or '<p class="muted">Brak tekstów z datą.</p>'
    topics = ''.join(bar_row(TOPIC_NAMES[t], r) for t, r in summary['by_topic'].items()) or '<p class="muted">Brak ocenionych tekstów.</p>'
    peak = max(summary['volume'].values() or [1]) or 1
    volume = ''.join(f'<div class="vol{" is-mark" if d == summary["premiere"] else ""}" title="{_dm(d)}: {v} wpisów"><span class="vol-bar" style="height:{max(2, round(100 * v / peak))}%"></span>'
                     f'<span class="vol-n">{v}</span><span class="vol-day">{_dm(d)}</span></div>' for d, v in summary['volume'].items())
    premiere_note = (f'Najpewniej premiera: {_dm(summary["premiere"])} (pierwszy wysyp wpisów).' if summary['premiere']
                     else 'W danych nie widać wyraźnego dnia premiery (brak nagłego wysypu wpisów).')
    source_rows = ''.join(
        f'<tr><td>{e(SOURCE_NAMES[s])}{small_tag(src[s])}</td><td>{meta["raw"].get(s, 0)}</td><td>{meta["kept"].get(s, 0)}</td><td>{src[s]["n"]}</td>'
        f'<td>{src[s]["pozytyw"]}</td><td class="neg-t">{src[s]["negatyw"]}</td><td>{src[s]["neutralny"]}</td>'
        f'<td>{_pct(src[s]["udzial"]) if src[s]["pozytyw"] + src[s]["negatyw"] else "-"}</td>'
        f'<td>{(_pct(src[s]["od"]) + " do " + _pct(src[s]["do"])) if src[s]["pozytyw"] + src[s]["negatyw"] else "-"}</td>'
        f'<td>{_pct(w["wagi"][s]) if s in w["wagi"] else "-"}</td></tr>' for s in SOURCES)
    media_rows = ''.join(f'<li><span>{e(m["text"])}</span><small>{e(m["outlet"])} · {_dm(m["day"])} · {e(m["label"] or "nieocenione")}</small></li>'
                         for m in summary['media']) or '<li class="muted">Brak tytułów z frazami w tym okresie w naszej bazie.</li>'
    dropped = ', '.join(f'{k}: {v}' for k, v in sorted(meta['dropped'].items())) or 'nic'
    yt_note = (f'{meta["yt_videos"]} filmów z komentarzami, {meta["yt_units"]} jednostek YouTube' if meta['yt_units'] else 'bez YouTube')
    limits = [
        'Badamy tylko X, YouTube, Wykop, publiczne kanały RSS forów i blogów oraz tytuły z naszej bazy mediów. Facebook, Instagram i TikTok nie są '
        'badane (brak legalnego dostępu) - tam może toczyć się większa część rozmowy. Google Trends pomijamy (brak oficjalnego API).',
        'Użytkownicy X i komentujący na YouTube nie są próbą reprezentatywną: częściej piszą osoby zaangażowane, z silną opinią.',
        'Wyszukiwanie po frazach: pomijamy teksty bez tych słów (np. tylko ze zdjęciem albo z literówką), łapiemy część tekstów nie na temat.',
        'Filtr prosty: odrzucamy podania dalej, reklamy, powtórzone teksty i więcej niż 3 teksty tego samego autora; nie wykrywa wyrafinowanych botów.',
        'Ocenę nadają modele językowe (lista w Metodzie) - ironia i żarty bywają źle odczytane; przedziały Wilsona 95% dotyczą tylko błędu próby.',
        'Udział liczymy wśród tekstów z wyraźnym znakiem (pozytyw + negatyw); neutralne i nie na temat podajemy osobno.',
        f'Łączny wynik to wszystkie opinie ze znakiem razem (każdy głos liczy się raz, źródło waży tyle, ile ma opinii). Źródła z mniej niż {SMALL_SAMPLE} '
        'opiniami to „mała próba” - ich procent jest orientacyjny.',
        'Dane osób prywatnych tylko w pamięci: żadnych nazw ani identyfikatorów autorów w raporcie i CSV; surowe dane usunięte po wygenerowaniu.',
    ]
    alerts = [s for s in meta.get('stopped', []) if s]
    alert_html = ''.join(f'<li>{e(s)}</li>' for s in alerts)
    big = (f'<div class="alert"><b>Bez łącznego wyniku: {unrated} z {kept} tekstów nie dostało oceny.</b>'
           f'<span>Procenty niżej dotyczą tylko tekstów ocenionych i nie opisują całej próby. Uruchom raport ponownie, gdy wrócą darmowe modele.</span></div>'
           if unrated else '')
    headline = _pct(w['udzial']) if headline_ok else '-'
    headline_note = (f'{_pct(w["od"])} do {_pct(w["do"])} (Wilson 95%) · n={w["n"]}' if headline_ok else
                     ('bez wyniku: są teksty nieocenione' if unrated else 'brak opinii ze znakiem'))
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>{e(title)}</title>
<style>
:root{{--bg:#000;--ink:#fff;--ink-2:#b6bbc1;--ink-3:#71767b;--line:rgba(255,255,255,.11);--line-2:rgba(255,255,255,.2);--card:rgba(255,255,255,.035);--card-2:rgba(255,255,255,.06);
--red:#e0313a;--pos:#dcdcdc;--neg:#e0313a;--track:rgba(255,255,255,.08);--gap:20px;--r:16px;--pad:24px;--serif:{LOGO_SERIF};--sans:{LOGO_SANS}}}
*{{box-sizing:border-box;min-width:0}}html{{background:var(--bg)}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);overflow-wrap:anywhere;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 24px 56px;overflow-x:clip}}
.bar{{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:68px;border-bottom:1px solid var(--line)}}.bar svg{{display:block}}
.bar span{{font-size:13px;color:var(--ink-3);white-space:nowrap}}
.head{{padding:36px 0 28px;display:grid;gap:10px}}h1{{margin:0;font-family:var(--serif);font-weight:400;font-size:clamp(30px,4vw,46px);line-height:1.1;letter-spacing:-.02em}}
.sub{{margin:0;font-size:15px;color:var(--ink-2)}}.sub b{{color:var(--ink);font-weight:600}}
.alert{{display:grid;gap:4px;padding:16px 20px;margin-bottom:var(--gap);border:1px solid var(--red);border-left-width:4px;border-radius:12px;background:rgba(224,49,58,.08)}}
.alert b{{font-size:16px}}.alert span{{font-size:14px;color:var(--ink-2)}}
.notes{{margin:0 0 var(--gap);padding:0;list-style:none;display:grid;gap:6px}}.notes li{{position:relative;padding-left:16px;font-size:13px;color:var(--ink-2)}}
.notes li::before{{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;background:var(--red)}}
.proof{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));grid-auto-rows:1fr;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:40px}}
.proof .cell{{border-left:1px solid var(--line);border-radius:0;background:none;padding:20px 20px 20px 22px}}.proof .cell:first-child{{border-left:0;padding-left:0}}
.cell{{display:grid;grid-template-rows:auto 1fr auto;gap:6px;min-width:0;height:148px;padding:20px 22px;border:1px solid var(--line);border-radius:var(--r);background:var(--card)}}
.h3{{margin:0;display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12.5px;line-height:1.5;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2)}}
.h3 span{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tag{{flex-shrink:0;font-style:normal;font-size:11px;font-weight:600;letter-spacing:.02em;text-transform:none;color:var(--ink-3);border:1px solid var(--line-2);border-radius:6px;padding:1px 6px;white-space:nowrap}}
td .tag{{margin-left:8px;vertical-align:1px}}
.num{{align-self:center;font-size:clamp(26px,2.6vw,36px);line-height:1.1;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap}}
.note{{font-size:12.5px;line-height:1.5;color:var(--ink-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sec{{margin-bottom:40px}}h2{{margin:0 0 20px;font-size:22px;line-height:1.25;font-weight:650;letter-spacing:-.02em}}h2 small{{margin-left:10px;font-size:13px;font-weight:500;letter-spacing:0;color:var(--ink-3)}}
.grid5{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--gap)}}
.card{{display:grid;grid-template-rows:auto 1fr auto;gap:14px;padding:22px var(--pad);border:1px solid var(--line);border-radius:var(--r);background:var(--card);min-width:0}}
.card .h3{{justify-content:flex-start}}.card-foot{{margin:0;font-size:12.5px;line-height:1.5;color:var(--ink-3)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap);align-items:stretch}}
.legend{{display:flex;gap:16px;font-size:12.5px;color:var(--ink-3)}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}}
.rows{{display:grid;align-content:start}}
.row{{display:grid;grid-template-columns:minmax(72px,112px) minmax(100px,1fr) 44px 96px 78px;gap:10px;align-items:center;min-height:44px;border-top:1px solid var(--line)}}
.rows .row:first-child{{border-top:0}}.row-name{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}}.row-num{{text-align:right;font-weight:650;font-variant-numeric:tabular-nums}}
.row-ci,.row-n{{color:var(--ink-3);font-size:12.5px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.bar{{display:flex;gap:2px;height:8px;border-radius:4px;overflow:hidden;background:var(--track);border:0;min-height:0}}.bar .pos{{background:var(--pos)}}.bar .neg{{background:var(--neg)}}
.mark{{font-style:normal;font-size:11px;font-weight:600;color:var(--red);margin-left:6px}}
.vols{{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:8px;height:170px}}
.vol{{display:grid;grid-template-rows:1fr auto auto;height:100%;text-align:center;font-size:12.5px;color:var(--ink-3)}}
.vol-bar{{align-self:end;justify-self:center;width:min(100%,28px);background:var(--ink-2);border-radius:4px 4px 0 0}}.vol.is-mark .vol-bar{{background:var(--red)}}.vol.is-mark .vol-day{{color:var(--red)}}
.vol-n{{color:var(--ink);font-weight:600;margin-top:6px;font-variant-numeric:tabular-nums}}
.scroll{{overflow-x:auto;scrollbar-width:none}}.scroll::-webkit-scrollbar{{display:none}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:right;padding:10px 8px;border-top:1px solid var(--line);white-space:nowrap;font-variant-numeric:tabular-nums}}
th{{color:var(--ink-2);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.08em;border-top:0;padding-top:0}}th:first-child,td:first-child{{text-align:left;padding-left:0}}
th:last-child,td:last-child{{padding-right:0}}td.neg-t{{color:var(--neg)}}
.quotes{{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap)}}.quotes h2{{margin-bottom:16px}}
.quote{{display:grid;grid-template-rows:1fr auto;gap:10px;height:148px;padding:16px 20px;margin-bottom:12px;border:1px solid var(--line);border-radius:12px;background:var(--card)}}
.quote-text{{margin:0;font-family:var(--serif);font-size:15.5px;line-height:1.45;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:4;overflow:hidden}}
.quote-foot{{display:flex;justify-content:space-between;gap:12px;color:var(--ink-3);font-size:12.5px;white-space:nowrap}}
ul.list{{margin:0;padding:0;list-style:none}}.list li{{display:grid;gap:2px;min-height:44px;padding:8px 0;border-top:1px solid var(--line)}}.list li:first-child{{border-top:0;padding-top:0}}
.list li span{{font-size:14px}}.list li small{{font-size:12.5px;color:var(--ink-3)}}
ul.plain{{margin:0;padding-left:18px;display:grid;gap:6px;font-size:14px;color:var(--ink-2)}}ul.plain li::marker{{color:var(--ink-3)}}
code{{font-size:12.5px;color:var(--ink-3);word-break:break-all}}.muted{{color:var(--ink-3);margin:0}}
.foot{{display:flex;justify-content:space-between;gap:8px 24px;flex-wrap:wrap;padding-top:20px;border-top:1px solid var(--line);font-size:13px;color:var(--ink-3)}}
@media(max-width:960px){{.grid5{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media(max-width:720px){{.wrap{{padding:0 16px 40px}}.bar{{min-height:56px}}.bar span{{display:none}}.head{{padding:24px 0 20px}}
.proof{{grid-template-columns:1fr 1fr}}.proof .cell{{height:118px;padding:14px 12px}}.proof .cell:nth-child(odd){{border-left:0;padding-left:0}}.proof .cell:nth-child(n+3){{border-top:1px solid var(--line)}}.proof .cell:last-child{{grid-column:1/-1}}
.grid5{{grid-template-columns:1fr 1fr}}.grid5 .cell:last-child{{grid-column:1/-1}}.cell{{height:124px;padding:14px 16px}}
.two,.quotes{{grid-template-columns:1fr}}.row{{grid-template-columns:84px 1fr 44px;row-gap:0;padding:6px 0}}.row-ci,.row-n{{grid-column:2/4;text-align:left}}.row-n{{grid-column:1/2;grid-row:2}}.row-ci{{grid-column:2/4;grid-row:2}}
table{{font-size:12.5px}}th,td{{padding:8px 6px}}.quote{{height:auto;min-height:120px}}.vols{{height:140px}}.vol-day{{font-size:11px}}.sec{{margin-bottom:28px}}h2{{font-size:19px}}.card{{padding:18px 16px}}}}
</style></head><body><div class="wrap">
<header class="bar">{logo_svg(1, 30)}<span>raport nastrojów · {now.strftime('%d.%m.%Y %H:%M')}</span></header>
<div class="head"><h1>{e(title)}</h1><p class="sub">przeszłość.today · raport nastrojów · zakres <b>{zakres}</b> · frazy: {e(', '.join(frazy))} · {kept} tekstów po filtrze</p></div>
{big}{f'<ul class="notes">{alert_html}</ul>' if alert_html else ''}
<section class="proof">
{cell('Pozytywne', headline, headline_note, small_tag(w) if headline_ok else '')}
{cell('Negatywne', _pct(1 - w['udzial']) if headline_ok else '-', f'{w["negatyw"]} z {w["n"]} opinii ze znakiem' if headline_ok else headline_note)}
{cell('Neutralne', str(soc['neutralny']), 'na temat, bez znaku')}
{cell('Nie na temat', str(summary['counts'].get('nie_na_temat', 0)), 'odrzucone z udziałów')}
{cell('Ocenione', f'{kept - unrated} / {kept}', (f'{len(meta["models"])} modele: ' if len(meta['models']) > 1 else '') + models_text(meta) if meta.get('models') else 'żaden model nie odpowiedział')}
</section>
<section class="sec"><h2>Źródła<small>udział pozytywnych wśród opinii ze znakiem</small></h2>
<div class="grid5">{''.join(src_cell(s) for s in SOURCES)}</div></section>
<section class="sec"><div class="card"><h3 class="h3">Źródła w liczbach</h3><div class="scroll"><table><thead><tr><th>Źródło</th><th>Pobrane</th><th>Po filtrze</th><th>Na temat</th><th>Pozytyw</th><th>Negatyw</th><th>Neutralne</th><th>Pozytywne</th><th>Wilson 95%</th><th>Udział w puli</th></tr></thead>
<tbody>{source_rows}</tbody></table></div><p class="card-foot">Udział w puli: ile opinii ze znakiem z danego źródła weszło do łącznego wyniku (bez mediów). Facebook, Instagram i TikTok nie są badane.</p></div></section>
<section class="sec"><div class="card"><h3 class="h3">Wpisy na X dzień po dniu</h3><div class="vols">{volume}</div><p class="card-foot">{e(premiere_note)} Źródło liczb: {e(summary['volume_source'])}.</p></div></section>
<section class="sec two">
<div class="card"><h3 class="h3">Pozytywne po dniach (bez mediów)</h3><div><div class="legend"><span><i style="background:var(--pos)"></i>pozytywne</span><span><i style="background:var(--neg)"></i>negatywne</span></div><div class="rows">{days}</div></div><p class="card-foot">Procent i 95% przedział Wilsona; n = opinie ze znakiem / wszystkie na temat.</p></div>
<div class="card"><h3 class="h3">Pozytywne po tematach (bez mediów)</h3><div><div class="legend"><span><i style="background:var(--pos)"></i>pozytywne</span><span><i style="background:var(--neg)"></i>negatywne</span></div><div class="rows">{topics}</div></div><p class="card-foot">Temat nadaje model: smak, cena, osoba, marketing, inne.</p></div>
</section>
<section class="sec quotes">
<div><h2>Głosy pozytywne<small>5 najczęściej polubionych</small></h2>{''.join(quote_box(q) for q in summary['quotes']['pozytyw']) or '<p class="muted">Brak.</p>'}</div>
<div><h2>Głosy negatywne<small>5 najczęściej polubionych</small></h2>{''.join(quote_box(q) for q in summary['quotes']['negatyw']) or '<p class="muted">Brak.</p>'}</div>
</section>
<section class="sec"><div class="card"><h3 class="h3">Jak piszą media (tytuły z naszej bazy)</h3><ul class="list">{media_rows}</ul><p class="card-foot">Tylko metadane artykułów, które już mamy w bazie.</p></div></section>
<section class="sec two">
<div class="card"><h3 class="h3">Metoda</h3><ul class="plain">
<li>X: oficjalne API, wyszukiwanie pełnotekstowe od {zakres}, zapytanie: <code>{e(query)}</code>; {meta['reads']} odczytów, {meta['pages']} stron.</li>
<li>YouTube: filmy z frazami w okresie (search.list), komentarze pod najpopularniejszymi (commentThreads.list); {yt_note}.</li>
<li>Wykop: oficjalne API v3 (wyszukiwanie wpisów i znalezisk po frazach), {meta['wykop_calls']} zapytań.</li>
<li>Fora i blogi: {meta['rss_feeds']} publicznych kanałów RSS/Atom (źródła z zatwierdzoną kartą dostępu i lista z env), tylko tytuł i fragment z kanału.</li>
<li>Media: tytuły artykułów z frazami w okresie z naszej bazy (tylko metadane).</li>
<li>Filtr: po nim {kept} z {sum(meta['raw'].values())} tekstów; odrzucone: {e(dropped)}.</li>
<li>Ocena w paczkach po {BATCH} tekstów, {meta['calls']} paczek; modele i liczba ocenionych tekstów: {e(models_text(meta))}; nieocenione: {unrated}.</li>
</ul><p class="card-foot">Plik CSV obok raportu: źródło, dzień, ocena, temat, powód, polubienia, skrócony tekst.</p></div>
<div class="card"><h3 class="h3">Ograniczenia</h3><ul class="plain">{''.join(f'<li>{e(l)}</li>' for l in limits)}</ul><p class="card-foot">Zasady: tylko legalne źródła, nic nie trafia do tabel serwisu.</p></div>
</section>
<footer class="foot"><span>przeszłość.today prowadzi iapply sp. z o.o. · dane wspólne ze spin.clinic</span><span>raport jednorazowy, nie jest sondażem</span></footer>
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
            'mercury_ready': inception.configured() and inception.no_training() and inception.ready(4000),
            'council_models': [m[1] for m in _council_members()], 'cached': cache_load(frazy, start, end, now) is not None}


def run(frazy: list[str], *, days: int = 7, limit: int = 500, yt_limit: int = 1500, title: str = '', topic: str = '', od=None, do=None,
        keep_raw: bool = False, source_file: str = '', refresh: bool = False, now=None) -> dict:
    """Pełny przebieg: źródła (albo pamięć podręczna z 24 h, albo plik), filtr, ocena, statystyka, HTML + CSV.
    Surowe dane zostają w pamięci (keep_raw: plik JSON obok); do pamięci podręcznej trafiają tylko teksty po filtrze i anonimizacji."""
    now = now or timezone.now()
    frazy = phrases(frazy)
    query = build_query(frazy)
    start, end = window(days, od, do, now)
    title = title or f'Nastroje: {frazy[0]}'
    topic = topic or ', '.join(frazy)
    cache_sweep(now)
    raw_rows, cache_path = [], ''
    if source_file:
        posts = load_posts(source_file)
        bundle = {'posts': posts, 'counts': None, 'fetch': {}, 'raw': dict(Counter(p['src'] for p in posts)), 'dropped': {},
                  'stopped': [], 'origin': f'Teksty z pliku {Path(source_file).name} (bez pobierania ze źródeł).'}
    else:
        bundle = None if refresh else cache_load(frazy, start, end, now)
        if bundle:
            saved = datetime.fromisoformat(bundle['saved']).astimezone(PL).strftime('%d.%m.%Y %H:%M')
            bundle['origin'] = f'Teksty z pamięci podręcznej (pobrane {saved}, bez ponownego pobierania i płacenia; --swiezo wymusza pobranie).'
        else:
            bundle = fetch(frazy, query, limit=limit, yt_limit=yt_limit, start=start, end=end, now=now)
            raw_rows = bundle.pop('raw_rows')
            if bundle['posts']:
                cache_path = cache_save(frazy, start, end, {k: v for k, v in bundle.items() if k != 'origin'}, now)
    posts = bundle['posts']
    for post in posts:
        for key in ('label', 'topic', 'reason'):
            post.pop(key, None)
    fetched, counts = bundle.get('fetch') or {}, bundle.get('counts')
    stopped = list(bundle.get('stopped') or [])
    if bundle.get('origin'):
        stopped.insert(0, bundle['origin'])
    rated = classify(posts, topic)
    if rated['stopped']:
        stopped.append(rated['stopped'])
    summary = summarise(posts, start, end, counts if counts else None)
    meta = {'now': now, 'start': start, 'end': end, 'raw': dict(bundle.get('raw') or {}), 'kept': dict(Counter(p['src'] for p in posts)),
            'reads': fetched.get('reads', 0), 'pages': fetched.get('pages', 0), 'yt_units': fetched.get('yt_units', 0),
            'yt_videos': fetched.get('yt_videos', 0), 'wykop_calls': fetched.get('wykop_calls', 0), 'rss_feeds': fetched.get('rss_feeds', 0),
            'dropped': dict(bundle.get('dropped') or {}), 'calls': rated['calls'], 'model': rated['model'], 'models': rated['models'],
            'routes': rated['routes'], 'unrated': rated['unrated'], 'stopped': stopped, 'origin': bundle.get('origin', ''), 'cache': cache_path}
    folder = output_dir()
    stem = f'nastroje-{slug(frazy[0])}-{now.astimezone(PL).strftime("%Y%m%d-%H%M")}'
    html_path, csv_path = folder / f'{stem}.html', folder / f'{stem}.csv'
    html_path.write_text(render_html(title, frazy, query, summary, meta), encoding='utf-8')
    write_csv(csv_path, posts)
    raw_path = ''
    if keep_raw and raw_rows:
        raw_path = str(folder / f'{stem}-surowe.json')
        Path(raw_path).write_text(json.dumps({'uwaga': 'dane surowe do debugowania, usuń po użyciu', 'wiersze': raw_rows}, ensure_ascii=False, indent=1),
                                  encoding='utf-8')
    raw_rows.clear()
    return {'query': query, 'summary': summary, 'meta': meta, 'html': str(html_path), 'csv': str(csv_path), 'raw': raw_path, 'title': title}


def fetch(frazy: list[str], query: str, *, limit: int, yt_limit: int, start: datetime, end: datetime, now=None) -> dict:
    """Pobranie ze wszystkich źródeł i filtr. Zwraca paczkę do pamięci podręcznej (`posts` bez identyfikatorów) oraz `raw_rows`
    (surowe wiersze tylko w pamięci, nie trafiają do pamięci podręcznej)."""
    from news.political_polling import configuration
    config = configuration()
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
    stopped = [s for s in (fetched['stopped'], counts['error'], videos['error'], comments['error'], wykop['error'], rss['error']) if s]
    posts, dropped = filter_posts(raw)
    for bucket in (fetched['rows'], comments['rows'], wykop['rows'], rss['rows']):
        bucket.clear()
    return {'posts': posts, 'counts': counts['days'] if not counts['error'] and counts['days'] else None,
            'fetch': {'reads': fetched['reads'], 'pages': fetched['pages'], 'yt_units': videos['units'] + comments['units'],
                      'yt_videos': comments['videos'], 'wykop_calls': wykop['calls'], 'rss_feeds': rss['feeds']},
            'raw': dict(Counter(r['src'] for r in raw)), 'dropped': dict(dropped), 'stopped': stopped, 'raw_rows': raw}


def models_text(meta: dict) -> str:
    return '; '.join(f'{name}: {n}' for name, n in sorted(meta.get('models', {}).items(), key=lambda kv: -kv[1])) or 'żaden model nie ocenił tekstów'


def summary_text(result: dict) -> str:
    s, m, w = result['summary'], result['meta'], result['summary']['pooled']
    per_source = '; '.join(f'{SOURCE_NAMES[k]}: {_pct(v["udzial"])} (n={v["pozytyw"] + v["negatyw"]}{", mała próba" if v["small"] else ""})'
                           if v['pozytyw'] + v['negatyw'] else f'{SOURCE_NAMES[k]}: brak opinii ze znakiem' for k, v in s['by_source'].items())
    if m['unrated']:
        headline = f'BEZ ŁĄCZNEGO WYNIKU: {m["unrated"]} z {sum(m["kept"].values())} tekstów nieocenionych (patrz uwagi niżej).'
    elif w['n']:
        headline = (f'Łącznie (wszystkie opinie ze znakiem bez mediów, n={w["n"]}{", mała próba" if w["small"] else ""}): pozytywne {_pct(w["udzial"])} '
                    f'({_pct(w["od"])} do {_pct(w["do"])}, Wilson 95%), negatywne {_pct(1 - w["udzial"])}')
    else:
        headline = 'Brak opinii z wyraźnym znakiem'
    lines = [result['title'], headline, per_source,
             f'Neutralne: {s["total"]["neutralny"]}, nie na temat: {s["counts"].get("nie_na_temat", 0)}, nieocenione: {m["unrated"]}',
             f'Próba: {sum(m["kept"].values())} tekstów po filtrze z {sum(m["raw"].values())} pobranych ({m["reads"]} odczytów X, '
             f'{m["yt_units"]} jednostek YouTube)',
             f'Ocena ({m["calls"]} paczek): {models_text(m)}',
             f'Zakres: {m["start"].astimezone(PL).strftime("%d.%m.%Y")} do {m["end"].astimezone(PL).strftime("%d.%m.%Y")}'
             + (f', najpewniej premiera: {s["premiere"]}' if s['premiere'] else ''),
             *(f'Uwaga: {x}' for x in m['stopped']),
             f'HTML: {result["html"]}', f'CSV: {result["csv"]}', f'Surowe (debugowanie): {result["raw"]}' if result.get('raw') else '',
             f'Pamięć podręczna (24 h, bez autorów): {m["cache"]}' if m.get('cache') else '',
             'Tylko X, YouTube, Wykop, publiczne RSS i tytuły mediów (bez FB, IG, TikToka); ocena modelem; bez nazw autorów.']
    return '\n'.join(l for l in lines if l)


def admin_email() -> str:
    return next((os.environ.get(n, '').strip() for n in ('LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL', 'X_POST_ALERT_EMAIL', 'SOCIAL_VIDEO_EMAIL')
                 if os.environ.get(n, '').strip()), '')


def send(result: dict) -> bool:
    from news.social_publish import _mail
    to = admin_email()
    return bool(to) and _mail(to, f'przeszłość.today · {result["title"]}', summary_text(result), important=True)
