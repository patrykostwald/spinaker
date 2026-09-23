"""Celery tasks owned by the editorial-news domain."""
from io import StringIO

from celery import shared_task
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState


@shared_task(name="news.tasks.political_poll_task", soft_time_limit=45, time_limit=60)
def political_poll_task():
    """Run at most one due, confirmed political X account.

    ``political_poll_cycle`` is independently opt-in, budgeted and leased.  A
    frequent scheduler tick therefore does not itself make a paid request when
    polling is disabled or no account is due.
    """
    from news.political_polling import political_poll_cycle
    return political_poll_cycle()


@shared_task(name='news.tasks.sync_live_public_rosters_task', soft_time_limit=600, time_limit=660)
def sync_live_public_rosters_task():
    """Refresh only rosters backed by a live, exact official source.

    This intentionally excludes static editorial lists such as KPRP leadership
    until each has its own live source adapter.  A failed source
    cannot block the other rosters or silently overwrite its last good state.
    No social account is discovered, confirmed or read here.
    """
    if not cache.add('lock:live-public-rosters', True, 900):
        return {'status': 'already_running', 'completed': [], 'failed': []}
    state, _ = ImportState.objects.get_or_create(name='public-figure:live-rosters')
    state.last_started = timezone.now()
    state.save(update_fields=['last_started'])
    completed, failed = [], []
    commands = [
        ('sejm-roster', 'sync_parliamentary_roster', {'source': 'sejm'}),
        ('sejm-profiles', 'sync_parliamentary_public_figures', {'source': 'sejm'}),
        ('senat-roster', 'sync_parliamentary_roster', {'source': 'senat'}),
        ('senat-profiles', 'sync_parliamentary_public_figures', {'source': 'senat'}),
        ('ep-roster', 'sync_parliamentary_roster', {'source': 'ep'}),
        ('ep-profiles', 'sync_parliamentary_public_figures', {'source': 'ep'}),
        ('voivodes', 'sync_voivodes', {}),
        ('cabinet', 'sync_public_figures', {'source': 'cabinet'}),
    ]
    try:
        for label, command, options in commands:
            try:
                call_command(command, stdout=StringIO(), **options)
                completed.append(label)
            except Exception as exc:  # Preserve other independently official rosters.
                failed.append({'roster': label, 'error': type(exc).__name__})
        status = 'partial' if failed else 'ok'
        state.last_error = '' if not failed else 'Nie wszystkie oficjalne rostery odświeżono; szczegóły w stanie zadania.'
        if not failed:
            state.last_success = timezone.now()
        state.cursor = {'completed_at': timezone.now().isoformat(), 'status': status,
                        'completed': completed, 'failed': failed}
        state.save(update_fields=['last_success', 'last_error', 'cursor'])
        return {'status': status, 'completed': completed, 'failed': failed}
    finally:
        cache.delete('lock:live-public-rosters')
