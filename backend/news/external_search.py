"""External discovery is separate from publisher-verified archive records."""
import re
from hashlib import sha256
from urllib.parse import urlsplit, unquote
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.decorators import api_view
from news.schema import json_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from news.models import Source, ArchiveJob, ImportState, ArticleCategory
from scraper.utils import safe_url
from scraper.queue import enqueue_requested_url


class SourceRegistry(dict):
    """Domain filters stay unique; publisher identity never loses shared-host peers."""
    def __init__(self, sources):
        super().__init__()
        self.all_sources = tuple(sources)
        for source in self.all_sources:
            host = (urlsplit(source.url).hostname or '').lower()
            self.setdefault(host, source)


def allowed_sources():
    result = []
    for source in Source.objects.filter(is_active=True, scrape_enabled=True, catalog_stage='configured').exclude(source_type__in=['twitter', 'politician', 'editorial']).order_by('pk'):
        host = (urlsplit(source.url).hostname or '').lower()
        if host and re.fullmatch(r'[a-z0-9.-]+', host): result.append(source)
    return SourceRegistry(result)


def match_source(url, sources):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower().removeprefix('www.')
    except (ValueError, TypeError):
        return None
    path = unquote(parsed.path)
    if '\\' in path or any(part in {'.', '..'} for part in path.split('/')):
        return None
    peers = [source for source in getattr(sources, 'all_sources', sources.values())
             if (urlsplit(source.url).hostname or '').lower().removeprefix('www.') == host]
    peers = list({source.pk: source for source in peers}.values())
    if host == 'gov.pl':
        candidates = []
        for source in peers:
            parts = urlsplit(source.url).path.strip('/').split('/')
            if len(parts) < 2 or parts[0] != 'web' or not parts[1]:
                continue
            prefix = '/web/' + parts[1]
            if path.rstrip('/') == prefix or path.startswith(prefix + '/'):
                candidates.append(source)
        return candidates[0] if len(candidates) == 1 else None
    if len(peers) == 1:
        return peers[0]
    # Shared non-government hosts also require an unambiguous configured path.
    candidates = []
    for source in peers:
        prefix = urlsplit(source.url).path.rstrip('/')
        if prefix and (path.rstrip('/') == prefix or path.startswith(prefix + '/')):
            candidates.append((len(prefix), source))
    if candidates:
        longest = max(length for length, _ in candidates)
        matches = [source for length, source in candidates if length == longest]
        if len(matches) == 1:
            return matches[0]
    return None


@json_view("Wyszukiwanie zewnętrzne (redakcja)", tags=["redakcja"])
@api_view(['GET'])
def external_search(request):
    query = request.query_params.get('q', '').strip()
    if not 1 <= len(query) <= 200: raise ValidationError({'q': 'Podaj frazę od 1 do 200 znaków.'})
    categories = [c for c in request.query_params.get('categories', '').split(',') if c]
    if set(categories) - set(ArticleCategory.values): raise ValidationError({'categories': 'Nieznana kategoria.'})
    empty = {'results': [], 'complete': False}
    if not settings.EXTERNAL_SEARCH_ENABLED or not settings.BRAVE_SEARCH_API_KEY:
        return Response({**empty, 'status': 'disabled', 'detail': 'Wyszukiwanie internetowe nie jest jeszcze skonfigurowane. Wyniki naszej bazy są dostępne.'})
    # External dates can mean modification, and genres are unknown until read.
    if categories or request.query_params.get('from_date') or request.query_params.get('to_date'):
        return Response({**empty, 'status': 'filtered', 'detail': 'Filtry dat i kategorii dotyczą zweryfikowanych metadanych w bazie. Usuń filtry, aby odkrywać dodatkowe źródła.'})
    sources = allowed_sources()
    if not sources: return Response({**empty, 'status': 'disabled', 'detail': 'Brak aktywnych źródeł.'})
    key = 'external-search:v2:' + sha256(repr((query, [(source.pk, source.url) for source in sources.all_sources])).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None: return Response(cached)
    day = timezone.now().date().isoformat()
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='brave-budget:' + day)
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        if state.imported >= settings.EXTERNAL_SEARCH_DAILY_LIMIT:
            return Response({**empty, 'status': 'daily_limit', 'detail': 'Osiągnięto dzisiejszy limit wyszukiwania internetowego. Baza pozostaje dostępna.'})
        state.imported += 1
        state.save(update_fields=['imported'])
    goggles = '$discard\n' + '\n'.join('$boost=1,site=' + host for host in sorted(sources))
    try:
        response = requests.get('https://api.search.brave.com/res/v1/web/search', headers={'X-Subscription-Token': settings.BRAVE_SEARCH_API_KEY},
            params={'q': query, 'count': 20, 'country': 'PL', 'search_lang': 'pl', 'text_decorations': 'false', 'spellcheck': 'false', 'result_filter': 'web', 'goggles': goggles}, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        items = data.get('web', {}).get('results', [])
        if not isinstance(items, list): raise ValueError()
    except (requests.RequestException, ValueError, AttributeError):
        return Response({**empty, 'status': 'unavailable', 'detail': 'Nie udało się teraz wyszukać dodatkowych źródeł. Wyniki bazy pozostają dostępne.'})
    results, seen = [], set()
    for item in items[:20]:
        if not isinstance(item, dict): continue
        url = safe_url(item.get('url'))
        if not url or len(url) > 1024 or url in seen: continue
        source = match_source(url, sources)
        title = strip_tags(str(item.get('title') or ''))[:500]
        if not source or not title: continue
        seen.add(url)
        # Only the URL enters discovery; search snippets/dates never become source facts.
        if settings.EXTERNAL_SEARCH_ARCHIVE_URLS:
            enqueue_requested_url(url, source)
        results.append({'url': url, 'title': title, 'source_name': source.name, 'published_date': None,
            'image_url': '', 'category': 'other', 'status': 'discovered'})
    payload = {**empty, 'status': 'ok', 'results': results, 'detail': 'Znalezione w internecie. Tytuły pochodzą z indeksu wyszukiwarki; data i kategoria wymagają sprawdzenia u wydawcy.'}
    if settings.EXTERNAL_SEARCH_CACHE_SECONDS:
        cache.set(key, payload, settings.EXTERNAL_SEARCH_CACHE_SECONDS)
    return Response(payload)
