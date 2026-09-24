"""Refresh access evidence without changing the owner's source configuration."""
from datetime import timedelta

from django.utils import timezone
from news.models import ImportState, Source
from scraper.source_probe import audit_source, source_signature


def due_sources(now=None, max_age_hours=168):
    now = now or timezone.now()
    states = {int(s.name.split(':')[-1]): s for s in
              ImportState.objects.filter(name__startswith='source-check:')
              if s.name.split(':')[-1].isdigit()}
    due = []
    for source in Source.objects.exclude(catalog_stage='excluded').order_by('id'):
        if not (source.url or source.rss_url):
            continue
        state = states.get(source.pk)
        cursor = state.cursor if state else {}
        if state and state.last_started:
            # Manual bulk audit and background polling share their checkpoint.
            if cursor.get('audit_status') == 'running' and state.last_started > now - timedelta(minutes=30):
                continue
            if cursor.get('audit_status') == 'failed' and state.last_started > now - timedelta(hours=6):
                continue
        changed = cursor.get('signature') != source_signature(source)
        if changed or not state or not state.last_success or state.last_success <= now - timedelta(hours=max_age_hours):
            due.append(source)
    return due


def audit_due_sources(limit=1, max_age_hours=168):
    selected = due_sources(max_age_hours=max_age_hours)[:limit]
    results = [audit_source(source) for source in selected]
    failed = [r['source_id'] for r in results if r.get('audit_status') == 'failed']
    return {'status': 'partial' if failed else 'ok' if results else 'idle',
            'checked': len(results), 'failed_source_ids': failed}
