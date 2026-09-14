"""One persisted weekly window; the scheduler decides when to run the next one."""
from datetime import date, timedelta
from time import monotonic
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from news.models import ImportState, Source
from scraper.official import API, fetch_json, import_voting_period, official_access_allowed

# Confirmed by https://api.sejm.gov.pl/sejm/term10 and the Sejm API docs.
TERM_STARTS = {10: date(2023, 11, 13)}
LOCK = 'lock:official:votings'  # Shared with import_official_task('votings').


class BackfillPaused(Exception):
    pass


def _source_enabled(source_id):
    return Source.objects.filter(pk=source_id, url=API + '/sejm', is_active=True,
        scrape_enabled=True, catalog_stage='configured').exists()


def backfill_votings_cycle():
    """No whole-archive loop: replay one inclusive 7-day period, advance on success."""
    source = Source.objects.filter(url=API + '/sejm').first()
    if not source or not _source_enabled(source.pk):
        return {'status': 'disabled', 'new_records': 0}
    if not official_access_allowed('sejm'):
        return {'status': 'blocked_access_review', 'new_records': 0}
    token = uuid4().hex
    if not cache.add(LOCK, token, 3600):
        return {'status': 'already_running', 'new_records': 0}
    state = None
    deadline = monotonic() + 1200

    def guard():
        if not _source_enabled(source.pk):
            raise BackfillPaused('source_disabled')
        if monotonic() >= deadline:
            raise BackfillPaused('cycle_budget_reached')
        if cache.get(LOCK) != token:
            raise BackfillPaused('lock_lost')
        cache.touch(LOCK, 3600)

    try:
        term, started = settings.SEJM_TERM, timezone.now()
        state, _ = ImportState.objects.get_or_create(name=f'official-backfill:votings:{term}')
        state.last_started = started
        state.save(update_fields=['last_started'])
        cursor = dict(state.cursor)
        if not cursor:
            guard()
            start = TERM_STARTS.get(term)
            if start is None:
                meta = fetch_json(f'/sejm/term{term}')
                if meta.get('num') != term:
                    raise ValueError('Term identity mismatch')
                start = date.fromisoformat(meta['from'])
            # Freeze the target at the start of this historical pass. Current
            # collection remains responsible for days after this cutoff.
            cursor = {'term': term, 'next_from': start.isoformat(),
                'cutoff': timezone.localdate(started).isoformat(), 'complete': False,
                'periods_completed': 0}
            state.cursor = cursor
            state.save(update_fields=['cursor'])
        if cursor.get('term') != term:
            raise ValueError('Backfill cursor term mismatch')
        if cursor.get('complete'):
            return {'status': 'complete', 'new_records': 0, 'cutoff': cursor['cutoff']}
        start, cutoff = date.fromisoformat(cursor['next_from']), date.fromisoformat(cursor['cutoff'])
        if start > cutoff:
            raise ValueError('Invalid backfill date range')
        # API dateTo is inclusive (verified using 2023-11-13 through 2023-11-14).
        end = min(start + timedelta(days=6), cutoff)
        guard()
        count = import_voting_period(term, start.isoformat(), end.isoformat(), guard=guard)
        guard()
        next_from = end + timedelta(days=1)
        with transaction.atomic():
            current = ImportState.objects.select_for_update().get(pk=state.pk)
            if current.cursor != cursor:
                raise ValueError('Backfill cursor changed during import')
            current.cursor = {**cursor, 'next_from': next_from.isoformat(),
                'complete': next_from > cutoff, 'periods_completed': cursor.get('periods_completed', 0) + 1}
            current.last_success, current.last_error = timezone.now(), ''
            current.imported += count
            current.save(update_fields=['cursor', 'last_success', 'last_error', 'imported'])
        return {'status': 'complete' if next_from > cutoff else 'ok', 'new_records': count,
            'from_date': start.isoformat(), 'to_date': end.isoformat(), 'next_from': next_from.isoformat(),
            'cutoff': cutoff.isoformat()}
    except Exception as exc:
        if state:
            # Keep the start and frozen cutoff intact. Per-vote transactions may
            # have committed; replay uses their identities and never duplicates them.
            ImportState.objects.filter(pk=state.pk).update(last_error=str(exc)[:200])
        return {'status': 'deferred' if isinstance(exc, BackfillPaused) else 'error',
            'new_records': 0, 'error': str(exc)[:200], 'partial_writes_possible': True}
    finally:
        if cache.get(LOCK) == token:
            cache.delete(LOCK)
