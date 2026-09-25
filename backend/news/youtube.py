import re
from hashlib import sha256
from datetime import datetime, timezone as dt_timezone
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework.decorators import api_view
from news.schema import json_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from news.models import ImportState, Source
from news.serializers import ArticleSerializer
from scraper.utils import upsert_article

@json_view("Wyszukiwanie w YouTube (redakcja)", tags=["redakcja"])
@api_view(['GET', 'POST'])
def search_youtube(request):
    enabled = settings.YOUTUBE_ENABLED and bool(settings.YOUTUBE_API_KEY)
    if request.method == 'GET' or not enabled:
        return Response({'enabled': enabled, 'status': 'ready' if enabled else 'not_configured', 'articles': [], 'next_token': None})
    query = str(request.data.get('q', '')).strip()
    token = str(request.data.get('page_token', ''))
    if not 1 <= len(query) <= 200 or len(token) > 500:
        raise ValidationError('Nieprawidłowa fraza lub strona wyników.')
    key = 'youtube:' + sha256((query + '\0' + token).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None: return Response(cached)
    # Durable budget, shared by workers and API processes; reserve before request.
    day = datetime.now(dt_timezone.utc).date().isoformat()
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='youtube-budget:' + day)
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        if state.imported >= settings.YOUTUBE_DAILY_REQUEST_LIMIT:
            return Response({'enabled': True, 'status': 'daily_limit', 'articles': [], 'next_token': None}, status=429)
        state.imported += 1; state.save(update_fields=['imported'])
    try:
        response = requests.get('https://www.googleapis.com/youtube/v3/search', params={
            'key': settings.YOUTUBE_API_KEY, 'part': 'snippet', 'type': 'video', 'q': query,
            'maxResults': 25, 'order': 'date', 'relevanceLanguage': 'pl', 'pageToken': token}, timeout=(5, 20))
        response.raise_for_status(); data = response.json()
    except (requests.RequestException, ValueError):
        return Response({'detail': 'YouTube jest chwilowo niedostępny lub odrzucił zapytanie. Wyniki naszej bazy pozostają dostępne.'}, status=502)
    articles = []
    for item in data.get('items', []):
        video = item.get('id', {}).get('videoId', '')
        snippet = item.get('snippet', {})
        channel = snippet.get('channelId', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', channel): continue
        if not snippet.get('title') or not snippet.get('channelTitle'): continue
        source, _ = Source.objects.get_or_create(url='https://www.youtube.com/channel/' + channel, defaults={
            'name': snippet['channelTitle'][:255], 'source_type': 'portal', 'scrape_enabled': False})
        article, _ = upsert_article(source=source, title=snippet['title'], url='https://www.youtube.com/watch?v=' + video,
            published_date=snippet.get('publishedAt'), category='video', description=snippet.get('description', ''),
            author=snippet['channelTitle'], ingestion_method='youtube', image_url=snippet.get('thumbnails', {}).get('medium', {}).get('url', ''))
        if article: articles.append(ArticleSerializer(article).data)
    payload = {'enabled': True, 'status': 'ok', 'articles': articles, 'next_token': data.get('nextPageToken'),
        'notice': 'Wyniki indeksu YouTube. Zapisano metadane, bez treści filmu i transkrypcji.'}
    cache.set(key, payload, 3600)
    return Response(payload)
