import re
from hashlib import sha256
from datetime import datetime, timezone as dt_timezone
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from news.schema import json_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from news.models import ImportState

@json_view("Wyszukiwanie w YouTube (zespół)", tags=["redakcja"])
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def search_youtube(request):
    """Podgląd wyników YouTube dla zespołu. Niczego nie zapisuje: wynik wyszukiwania z dowolnego kanału
    nie może stać się źródłem ani materiałem w bazie (filmy trafiają tu tylko z potwierdzonych kanałów)."""
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
    from news.youtube_collect import QuotaExhausted, spend
    try:
        spend('search')
    except QuotaExhausted:
        return Response({'enabled': True, 'status': 'daily_limit', 'articles': [], 'next_token': None}, status=429)
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
        articles.append({'title': snippet['title'], 'url': 'https://www.youtube.com/watch?v=' + video,
            'published_date': snippet.get('publishedAt'), 'channel': snippet['channelTitle'],
            'channel_url': 'https://www.youtube.com/channel/' + channel,
            'image_url': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')})
    payload = {'enabled': True, 'status': 'ok', 'articles': articles, 'next_token': data.get('nextPageToken'),
        'notice': 'Podgląd wyników YouTube. Nic nie zapisano w bazie.'}
    cache.set(key, payload, 3600)
    return Response(payload)
