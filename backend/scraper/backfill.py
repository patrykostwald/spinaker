from datetime import datetime

from django.db import transaction
from django.utils import timezone

from news.models import ArchiveJob, ImportState, Source
from scraper.archive import run_parallel_batch
from scraper.news_sitemaps import verified_maps

STATE_PREFIX = 'archive-backfill:'
PILOT_CUTOFF_AT = '2026-09-14T23:59:59+02:00'


def parse_cutoff(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('cutoff_at must include a timezone')
    return parsed


def state_name(source_id):
    return f'{STATE_PREFIX}{source_id}'


def prepare_source(source, cutoff_at):
    maps = verified_maps(source)
    if not maps:
        raise ValueError('no_verified_sitemap')
    name = state_name(source.pk)
    with transaction.atomic():
        state, created = ImportState.objects.select_for_update().get_or_create(name=name)
        existing = state.cursor.get('cutoff_at')
        cutoff_text = cutoff_at.isoformat()
        if existing and existing != cutoff_text:
            raise ValueError('backfill_cutoff_mismatch')
        if not existing:
            state.cursor = {'cutoff_at': cutoff_text, 'direction': 'newest_to_oldest',
                'source_id': source.pk, 'verified_maps': maps, 'pages_completed': 0,
                'skipped_cutoff': 0, 'new_articles': 0, 'last_job_id': 0, 'last_job_url': ''}
            state.save(update_fields=['cursor'])
        for url in maps:
            ArchiveJob.objects.get_or_create(url=url, defaults={
                'source': source, 'kind': 'sitemap', 'priority': 5})
    return state, maps, created


def run_backfill(source_ids, cutoff_at, workers=2, per_source_limit=20):
    sources = list(Source.objects.filter(pk__in=source_ids, is_active=True,
        scrape_enabled=True, catalog_stage='configured').order_by('pk'))
    if len(sources) != len(set(source_ids)):
        raise ValueError('source_not_active_or_configured')
    prepared = []
    for source in sources:
        state, maps, _ = prepare_source(source, cutoff_at)
        prepared.append((source, state, maps))
    metrics = {}
    started = timezone.now()
    for source, state, _ in prepared:
        state.last_started = timezone.now()
        state.save(update_fields=['last_started'])
    def checkpoint(job):
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(name=state_name(job.source_id))
            cursor = dict(state.cursor)
            cursor['last_job_id'] = job.pk
            cursor['last_job_url'] = job.url
            if job.kind == 'page':
                cursor['pages_completed'] = cursor.get('pages_completed', 0) + 1
            if job.last_error == 'after_cutoff':
                cursor['skipped_cutoff'] = cursor.get('skipped_cutoff', 0) + 1
            state.cursor = cursor
            state.save(update_fields=['cursor'])
    completed = run_parallel_batch(workers=workers, per_worker=per_source_limit,
        metrics=metrics, source_ids=[source.pk for source, _, _ in prepared], cutoff_at=cutoff_at,
        state_callback=checkpoint, per_source_limit=per_source_limit)
    for source, state, _ in prepared:
        state.refresh_from_db()
        state.cursor = {**state.cursor,
            'last_run_started': started.isoformat(),
            'last_run_completed': timezone.now().isoformat()}
        state.last_success = timezone.now()
        state.last_error = ''
        state.save(update_fields=['cursor', 'last_success', 'last_error'])
    return {'status': 'ok', 'cutoff_at': cutoff_at.isoformat(), 'sources': [s.pk for s, _, _ in prepared],
        'completed': completed, 'metrics': metrics}