from datetime import timedelta
import json
from pathlib import Path
from urllib.parse import urlparse
import feedparser
from django.utils import timezone
from news.models import Source
from news.models import SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.catalog import RSS_SOURCES, INSTITUTIONS
from scraper.utils import guarded, fetch_feed, get_or_create_source, upsert_article

def seed_sources():
    corrections = json.loads((Path(__file__).parent / 'data' / 'feed_corrections.json').read_text(encoding='utf-8'))
    feeds = {item['original']: item['feed'] for item in corrections}
    priority = json.loads((Path(__file__).parent / 'data' / 'priority_sources.json').read_text(encoding='utf-8'))
    for spec in RSS_SOURCES + INSTITUTIONS:
        institution = spec in INSTITUTIONS
        initial_frequency = priority['interval_minutes'] if spec['name'] in priority['names'] else 240 if institution else 60
        get_or_create_source(name=spec['name'], url=spec['url'], rss_url=feeds.get(spec['url'], spec['url']),
            source_type='institution' if institution else 'portal', scrape_frequency_minutes=initial_frequency)

    verified = json.loads((Path(__file__).parent / 'data' / 'verified_local_sources.json').read_text(encoding='utf-8'))
    for spec in verified:
        # Publisher homepage is the stable identity, including sources with sitemap only.
        # Existing editorial settings and disabled sources must remain untouched.
        get_or_create_source(name=spec['name'], url=spec['url'], rss_url=spec['rss_url'],
            source_type=spec['source_type'], scrape_frequency_minutes=spec['scrape_frequency_minutes'])

    # Static files supply initial defaults only. The editorial catalog owns all existing settings.

@guarded
def scrape_rss_sources():
    seed_sources()
    total = 0
    for source in Source.objects.filter(is_active=True, scrape_enabled=True).exclude(rss_url='').exclude(rss_url__startswith='https://news.google.com/rss/search?'):
        attempted = source.last_attempted or source.last_scraped
        if not attempted or timezone.now() >= attempted + timedelta(minutes=source.scrape_frequency_minutes):
            total += scrape_rss_source(source.pk)
    return total

@guarded
def scrape_rss_source(source_id):
    source = Source.objects.get(pk=source_id)
    if not source.is_active or not source.scrape_enabled or not source.rss_url:
        return 0
    if approved_instruction(source, SourceAccessInstruction.Channel.RSS, source.rss_url) is None:
        Source.objects.filter(pk=source.pk).update(last_error='no_approved_instruction')
        return 0
    Source.objects.filter(pk=source.pk).update(last_attempted=timezone.now())
    try:
        feed = feedparser.parse(fetch_feed(source.rss_url))
    except Exception as exc:
        response = getattr(exc, 'response', None)
        error = f'HTTP {response.status_code}' if response is not None else type(exc).__name__
        Source.objects.filter(pk=source.pk).update(last_error=error)
        raise
    if not feed.version or (feed.bozo and not feed.entries):
        Source.objects.filter(pk=source.pk).update(last_error='Nieprawidłowy lub niedostępny RSS')
        raise ValueError('Malformed RSS')
    total = 0
    for entry in feed.entries:
        _, created = upsert_article(source=source, title=entry.get('title'), url=entry.get('link'),
            published_date=entry.get('published'),
            category='statement' if source.source_type == 'institution' else 'article', ingestion_method='rss',
            description=entry.get('summary'), author=entry.get('author'), image_url=_entry_image(entry),
            tags=entry.get('tags') or entry.get('keywords') or [])
        total += created
    source.last_scraped = timezone.now()
    source.last_error = ''
    source.save(update_fields=['last_scraped', 'last_error'])
    return total

def _entry_image(entry):
    for image in entry.get('media_content', []) + entry.get('media_thumbnail', []) + entry.get('enclosures', []):
        url = image.get('url') or image.get('href')
        if url and (not image.get('type') or image['type'].startswith('image/')):
            return url
    return ''
