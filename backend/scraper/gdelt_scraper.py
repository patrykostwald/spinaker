from datetime import datetime, timedelta, timezone as dt_timezone
import requests
from django.utils import timezone
from scraper.utils import guarded, safe_url, parse_published, source_from_article_url, upsert_article

GDELT_DOC_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'

@guarded
def scrape_gdelt(keyword, days_back=1):
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name='gdelt:' + keyword[:90])
    end = timezone.now()
    state.last_started = end
    state.save(update_fields=['last_started'])
    start = end - timedelta(days=max(1, min(int(days_back), 90)))
    try:
        response = requests.get(GDELT_DOC_URL, params={
            'query': f'{keyword} sourcelang:pol', 'mode': 'ArtList', 'format': 'json', 'maxrecords': 250,
            'startdatetime': start.strftime('%Y%m%d%H%M%S'), 'enddatetime': end.strftime('%Y%m%d%H%M%S'),
            'sort': 'DateDesc'}, timeout=(5, 45))
        response.raise_for_status()
        items = response.json().get('articles') or []
    except Exception as exc:
        state.last_error = type(exc).__name__
        state.save(update_fields=['last_error'])
        raise
    total = 0
    for item in items:
        url = safe_url(item.get('url'))
        if not url or not item.get('title'):
            continue
        source = source_from_article_url(url, 'GDELT')
        _, created = upsert_article(source=source, title=item['title'], url=url,
            published_date=None, discovered_at=_parse_gdelt_date(item.get('seendate')), ingestion_method='gdelt', category='other', image_url=item.get('socialimage'))
        total += created
    state.imported = total
    state.last_error = 'Osiągnięto limit 250 wyników GDELT. Zakres może być niekompletny.' if len(items) >= 250 else ''
    if not state.last_error:
        state.last_success = end
    state.save(update_fields=['imported', 'last_error', 'last_success'])
    return total

def _parse_gdelt_date(value):
    for fmt in ('%Y%m%dT%H%M%SZ', '%Y%m%d%H%M%S'):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=dt_timezone.utc)
        except (ValueError, TypeError):
            pass
    return parse_published(value)
