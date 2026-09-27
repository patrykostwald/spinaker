"""Filmy z potwierdzonych oficjalnych kanałów YouTube (tylko metadane: tytuł, data, miniatura, link).

Zasady:
- zbieramy wyłącznie kanały ``OfficialVideoChannel`` ze statusem ``confirmed`` i ``collection_enabled``;
  wynik wyszukiwania z dowolnego kanału nigdy nie trafia do bazy;
- darmowy dzienny limit YouTube Data API (domyślnie 10 000 jednostek, reset o północy czasu pacyficznego,
  czyli ok. 9:00 w Polsce) liczymy sami — wspólnie z automatycznym wyborem wywiadu dnia;
- przed resetem limitu zużywamy resztę jednostek na głębsze archiwum oficjalnych kanałów
  (każda strona 50 filmów kosztuje 1 jednostkę), zostawiając zapas.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.db import transaction

from news.models import ImportState, Source

QUOTA_ZONE = ZoneInfo('America/Los_Angeles')
UNIT_COST = {'search': 100}
LEFTOVER_RESERVE = 300  # jednostki zostawione na nieprzewidziane wywołania przed resetem


class QuotaExhausted(Exception):
    pass


def enabled() -> bool:
    return bool(settings.YOUTUBE_ENABLED and settings.YOUTUBE_API_KEY)


def daily_units() -> int:
    return int(getattr(settings, 'YOUTUBE_DAILY_UNITS', 10000))


def _state():
    return f'youtube-units:{datetime.now(QUOTA_ZONE).date().isoformat()}'


def units_used() -> int:
    state = ImportState.objects.filter(name=_state()).first()
    return state.imported if state else 0


def units_left() -> int:
    return max(0, daily_units() - units_used())


def spend(path: str) -> None:
    """Rezerwuje jednostki przed zapytaniem; przy braku — QuotaExhausted (bez zapytania)."""
    cost = UNIT_COST.get(path, 1)
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=_state())
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        if state.imported + cost > daily_units():
            raise QuotaExhausted(path)
        state.imported += cost
        state.save(update_fields=['imported'])


def api(path: str, **params) -> dict:
    spend(path)
    response = requests.get(f'https://www.googleapis.com/youtube/v3/{path}',
                            params={**params, 'key': settings.YOUTUBE_API_KEY}, timeout=(5, 20))
    response.raise_for_status()
    return response.json()


def official_channels():
    from news.political_models import OfficialVideoChannel
    return (OfficialVideoChannel.objects.filter(status='confirmed', collection_enabled=True)
            .exclude(channel_id='').order_by('pk'))


def channel_source(channel) -> Source:
    """Źródło dla potwierdzonego kanału — aktywne, także gdy wcześniej ukryto je jako nieoficjalne."""
    source, created = Source.objects.get_or_create(url=f'https://www.youtube.com/channel/{channel.channel_id}', defaults={
        'name': (channel.display_name or channel.channel_id)[:255], 'source_type': 'portal', 'scrape_enabled': False,
        'is_active': True, 'catalog_stage': 'configured'})
    if not created and (not source.is_active or source.catalog_stage == 'excluded'):
        source.is_active, source.catalog_stage = True, 'configured'
        source.save(update_fields=['is_active', 'catalog_stage'])
    return source


def collect_page(channel, token: str = '') -> tuple[int, str]:
    """Jedna strona (do 50) najnowszych filmów kanału z listy „uploads”. Zwraca (zapisane, następna strona)."""
    from scraper.utils import upsert_article
    playlist = 'UU' + channel.channel_id[2:]
    params = {'part': 'snippet,contentDetails', 'playlistId': playlist, 'maxResults': 50}
    if token:
        params['pageToken'] = token
    data = api('playlistItems', **params)
    source = channel_source(channel)
    saved = 0
    for item in data.get('items', []):
        snippet, details = item.get('snippet', {}), item.get('contentDetails', {})
        video = details.get('videoId') or snippet.get('resourceId', {}).get('videoId', '')
        title = snippet.get('title', '')
        if not video or title in ('Private video', 'Deleted video'):
            continue
        article, _ = upsert_article(source=source, title=title, url=f'https://www.youtube.com/watch?v={video}',
            published_date=details.get('videoPublishedAt') or snippet.get('publishedAt'), category='video',
            description=snippet.get('description', '')[:2000], author=snippet.get('channelTitle', ''),
            ingestion_method='youtube', image_url=snippet.get('thumbnails', {}).get('medium', {}).get('url', ''))
        saved += bool(article)
    return saved, data.get('nextPageToken', '')


def collect_latest() -> dict:
    """Co kilka godzin: pierwsza strona każdego oficjalnego kanału (1 jednostka na kanał)."""
    if not enabled():
        return {'status': 'disabled'}
    saved = 0
    for channel in official_channels():
        try:
            saved += collect_page(channel)[0]
        except QuotaExhausted:
            return {'status': 'quota', 'saved': saved}
        except requests.RequestException:
            continue
    return {'status': 'ok', 'saved': saved, 'units_left': units_left()}


REFRESH_AFTER_DAYS = 25  # zasady YouTube API: dane odświeżone albo usunięte najpóźniej po 30 dniach


def refresh_stale(reserve: int = LEFTOVER_RESERVE) -> dict:
    """Odświeża tytuły i miniatury filmów starszych niż 25 dni (50 filmów = 1 jednostka).
    Film usunięty albo ukryty przez autora znika z bazy — nie trzymamy danych, których YouTube już nie podaje."""
    from datetime import timedelta
    from django.utils import timezone
    from news.models import Article
    refreshed = removed = 0
    stale = Article.objects.filter(ingestion_method='youtube', updated_at__lt=timezone.now() - timedelta(days=REFRESH_AFTER_DAYS))
    while units_left() > reserve:
        batch = list(stale.order_by('updated_at')[:50])
        if not batch:
            break
        ids = {row.url.rsplit('v=', 1)[-1][:11]: row for row in batch}
        try:
            data = api('videos', part='snippet', id=','.join(ids), maxResults=50)
        except QuotaExhausted:
            break
        except requests.RequestException:
            break
        found = {item['id']: item.get('snippet', {}) for item in data.get('items', [])}
        for video, row in ids.items():
            snippet = found.get(video)
            if snippet is None:
                row.delete()
                removed += 1
                continue
            row.title = (snippet.get('title') or row.title)[:500]
            row.image_url = snippet.get('thumbnails', {}).get('medium', {}).get('url', row.image_url)
            row.save(update_fields=['title', 'image_url', 'updated_at'])
            refreshed += 1
    return {'refreshed': refreshed, 'removed': removed}


def backfill_leftover(reserve: int = LEFTOVER_RESERVE) -> dict:
    """Przed resetem limitu: najpierw odświeżenie starszych filmów, potem reszta jednostek na archiwa kanałów."""
    if not enabled():
        return {'status': 'disabled'}
    refresh = refresh_stale(reserve)
    channels = list(official_channels())
    saved = pages = 0
    active = True
    while active and units_left() > reserve:
        active = False
        for channel in channels:
            if units_left() <= reserve:
                break
            state, _ = ImportState.objects.get_or_create(name=f'youtube-backfill:{channel.channel_id}')
            cursor = dict(state.cursor or {})
            if cursor.get('done'):
                continue
            try:
                count, token = collect_page(channel, cursor.get('token', ''))
            except QuotaExhausted:
                return {'status': 'quota', 'saved': saved, 'pages': pages}
            except requests.RequestException:
                continue
            saved, pages, active = saved + count, pages + 1, True
            state.cursor = {'token': token, 'done': not token}
            state.save(update_fields=['cursor'])
    return {'status': 'ok', 'saved': saved, 'pages': pages, 'units_left': units_left(), **refresh}
