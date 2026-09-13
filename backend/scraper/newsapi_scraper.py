from datetime import timedelta
from urllib.parse import urlparse
import requests
from django.conf import settings
from django.utils import timezone
from scraper.catalog import NEWSAPI_TOPICS, RSS_SOURCES
from scraper.utils import guarded, safe_url, source_from_article_url, upsert_article, reserve_budget

NEWSAPI_URL = 'https://newsapi.org/v2/everything'

@guarded
def scrape_newsapi_batch():
    if not settings.NEWSAPI_ENABLED or not settings.NEWSAPI_KEY:
        return 0
    return sum(_scrape_topic(topic, settings.NEWSAPI_KEY) for topic in NEWSAPI_TOPICS)

@guarded
def _scrape_topic(topic, api_key):
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name='newsapi:' + topic[:90])
    started = timezone.now()
    state.last_started = started
    state.save(update_fields=['last_started'])
    domains = ','.join(sorted({urlparse(s['url']).hostname.removeprefix('www.') for s in RSS_SOURCES}))
    since = (state.last_success - timedelta(hours=1)) if state.last_success else started - timedelta(days=7)
    total, page, received = 0, 1, 0
    try:
        while True:
            if not reserve_budget('newsapi:' + started.strftime('%Y-%m-%d'), 1, settings.NEWSAPI_DAILY_REQUEST_LIMIT, 172800):
                raise ValueError('Daily budget exhausted; incomplete import')
            response = requests.get(NEWSAPI_URL, headers={'X-Api-Key': api_key}, params={
                'q': topic, 'domains': domains, 'sortBy': 'publishedAt', 'pageSize': 100, 'page': page,
                'from': since.isoformat(), 'to': started.isoformat()}, timeout=(5, 45))
            response.raise_for_status()
            payload = response.json()
            if payload.get('status') == 'error':
                raise ValueError('NewsAPI provider error')
            items = payload.get('articles') or []
            for item in items:
                url = safe_url(item.get('url'))
                if not url or not item.get('title') or item.get('title') == '[Removed]':
                    continue
                source = source_from_article_url(url, (item.get('source') or {}).get('name') or 'NewsAPI')
                _, created = upsert_article(source=source, title=item['title'], url=url,
                    published_date=item.get('publishedAt'), ingestion_method='newsapi', category='other', image_url=item.get('urlToImage'),
                    author=item.get('author'), description=item.get('description'))
                total += created
            received += len(items)
            if received >= payload.get('totalResults', received):
                break
            if not items:
                raise ValueError('Incomplete NewsAPI pagination')
            page += 1
        state.last_success, state.last_error, state.imported = started, '', total
        state.save(update_fields=['last_success', 'last_error', 'imported'])
        return total
    except Exception as exc:
        state.last_error = type(exc).__name__ + ': incomplete import; cursor retained'
        state.save(update_fields=['last_error'])
        raise
