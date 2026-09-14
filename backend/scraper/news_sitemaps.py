"""Refresh only editorially verified small news maps; archive maps stay daily."""
import json
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlsplit
from django.db import transaction
from django.utils import timezone
from news.models import Source, ArchiveJob, ImportState
from scraper.utils import safe_url

CATALOG_PATH = Path(__file__).parent / 'data' / 'verified_local_sources.json'
NEWS_PRIORITY = 10


def _publisher_host(url):
    return (urlsplit(url or '').hostname or '').casefold().removeprefix('www.')


def verified_maps(source, field='sitemap_urls', require_archive_approval=False):
    rows = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    result = []
    for row in rows:
        same_url = str(row.get('url', '')).rstrip('/') == source.url.rstrip('/')
        same_host = _publisher_host(row.get('url')) == _publisher_host(source.url)
        same_name = str(row.get('name', '')).casefold() == source.name.casefold()
        if not (same_url or same_host or same_name):
            continue
        if require_archive_approval and not (
            row.get('archive_verification', {}).get('status') == 'verified'
            and row.get('archive_verification', {}).get('can_backfill') is True
        ):
            continue
        for url in row.get(field, []):
            if (isinstance(url, str) and safe_url(url) and len(url) <= 1024
                    and _publisher_host(url) == _publisher_host(row.get('url'))):
                result.append(url)
    return list(dict.fromkeys(result))


def news_sitemap_cycle():
    """No HTTP here: durable queue is fetched by the existing host-governed worker."""
    queued, dispatched = 0, 0
    for source in Source.objects.filter(is_active=True, scrape_enabled=True,
                                        catalog_stage='configured').iterator():
        urls = verified_maps(source, 'news_sitemap_urls')
        if not urls:
            continue
        now = timezone.now()
        with transaction.atomic():
            current = Source.objects.select_for_update().filter(pk=source.pk,
                is_active=True, scrape_enabled=True, catalog_stage='configured').first()
            if current is None or current.url != source.url:
                continue
            state, _ = ImportState.objects.select_for_update().get_or_create(
                name=f'news-sitemap-dispatch:{source.pk}')
            interval = timedelta(minutes=max(1, current.scrape_frequency_minutes))
            if state.last_success and state.last_success > now - interval:
                continue
            count = 0
            for url in urls:
                job, created = ArchiveJob.objects.get_or_create(url=url,
                    defaults={'source': current, 'kind': 'sitemap', 'priority': NEWS_PRIORITY})
                if job.source_id != current.pk or job.kind != 'sitemap':
                    continue
                if created:
                    count += 1
                elif job.status == 'done':
                    count += ArchiveJob.objects.filter(pk=job.pk, source=current,
                        kind='sitemap', status='done').update(status='pending',
                            available_at=now, priority=max(NEWS_PRIORITY, job.priority))
                # Pending/running/error keep their lease, attempts and retry backoff.
            state.last_started = now
            state.last_success = now  # dispatch checkpoint, not publisher fetch success
            state.last_error = ''
            state.imported += count
            state.cursor = {'urls': urls, 'meaning': 'queue_dispatch_only', 'queued': count}
            state.save()
            queued += count
            dispatched += 1
    return {'status': 'ok', 'dispatched_sources': dispatched, 'queued_maps': queued}
