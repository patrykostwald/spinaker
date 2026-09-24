"""Local-only scheduler; production uses Celery workers and Beat."""
from concurrent.futures import ThreadPoolExecutor
import time
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection
from django.utils import timezone
from news.models import ImportState, Source, Article, ArchiveJob
from scraper.rss_scraper import scrape_rss_sources
from scraper.tasks import import_official_task
from scraper.archive import archive_cycle, discovery_cycle
from scraper.news_sitemaps import news_sitemap_cycle
from scraper.quality import scan_quality
from scraper.html_archive import kprm_listing_cycle
from scraper.source_monitor import audit_due_sources
from scraper.official_backfill import backfill_votings_cycle
from news.research_metadata import research_metadata_cycle
from scraper.wordpress_backfill import wordpress_cycle
from news.political_polling import political_poll_cycle


def rss_cycle():
    started = timezone.now()
    imported = scrape_rss_sources.__wrapped__()
    attempted = list(Source.objects.filter(last_attempted__gte=started))
    failed = [source.pk for source in attempted if source.last_error or not source.last_scraped or source.last_scraped < source.last_attempted]
    return {'status': 'partial' if failed else 'ok' if attempted else 'idle',
        'attempted': len(attempted), 'failed_source_ids': failed, 'imported': imported}


def gdelt_cycle():
    from scraper.gdelt_scraper import scrape_gdelt
    from scraper.catalog import GDELT_TOPICS
    imported, failed = 0, []
    for topic in GDELT_TOPICS:
        try:
            imported += scrape_gdelt.__wrapped__(topic, 1) or 0
            state = ImportState.objects.get(name='gdelt:' + topic[:90])
            if state.last_error:
                failed.append({'topic': topic, 'reason': state.last_error})
        except Exception as exc:
            failed.append({'topic': topic, 'reason': type(exc).__name__})
    return {'status': 'partial' if failed else 'ok', 'imported': imported, 'failures': failed}


def run_monitored(name, fn):
    close_old_connections()
    state, _ = ImportState.objects.get_or_create(name='local:' + name)
    state.last_started = timezone.now()
    state.save(update_fields=['last_started'])
    try:
        result = fn()
        details = result if isinstance(result, dict) else {'status': 'ok'}
        status = details.get('status', 'ok')
        if status in ('partial', 'error'):
            state.last_error = 'Nie wszystkie źródła pobrano poprawnie. Szczegóły w raporcie przebiegu.'
        elif status == 'ok':
            state.last_success = timezone.now()
            state.last_error = ''
        # Idle polls never erase a preceding failure or fabricate a new success.
        state.cursor = {'completed_at': timezone.now().isoformat(), **details}
    except Exception as exc:
        state.last_error = type(exc).__name__
        state.cursor = {'completed_at': timezone.now().isoformat(), 'status': 'error', 'error': type(exc).__name__}
    finally:
        state.save(update_fields=['last_success', 'last_error', 'cursor'])
        close_old_connections()


def backup_delay(interval):
    """Keep the daily schedule across restarts without multiplying large copies."""
    state = ImportState.objects.filter(name='local:backup').first()
    if (not state or not state.last_started or not state.last_success
            or state.last_success < state.last_started):
        return 0
    elapsed = (timezone.now() - state.last_started).total_seconds()
    # A future timestamp cannot postpone protection after a clock correction.
    return max(0, interval - elapsed) if elapsed >= 0 else 0

class Command(BaseCommand):
    help = 'Run local background imports and daily verified SQLite backups. Keep this process alive.'
    def handle(self, *args, **options):
        if connection.vendor != 'sqlite': raise CommandError('Use Celery/Beat for production PostgreSQL.')
        # OS file lock prevents two local schedulers from importing concurrently.
        from django.conf import settings
        folder = settings.ROOT_DIR / '.local'; folder.mkdir(exist_ok=True)
        lock = open(folder / 'jobs.lock', 'a+b')
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        import os
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise CommandError('A local scheduler is already running.')
        jobs = {'rss': (60, rss_cycle), 'votes': (900, lambda: import_official_task.run('votings')),
            'prints': (3600, lambda: import_official_task.run('prints')), 'eli': (3600, lambda: import_official_task.run('eli')),
            'quality': (60, lambda: scan_quality(limit=1000, max_seconds=5)),
            'archive': (60, archive_cycle), 'discovery': (86400, discovery_cycle),
            'news-sitemaps': (60, news_sitemap_cycle),
            'gdelt': (7200, gdelt_cycle), 'html-kprm': (60, kprm_listing_cycle),
            'source-access': (300, audit_due_sources),
            'vote-history': (300, backfill_votings_cycle),
            'wordpress-history': (60, wordpress_cycle),
            'research-metadata': (10, research_metadata_cycle),
            'political-x': (60, political_poll_cycle),
            'backup': (86400, lambda: call_command('backup_database'))}
        running = {}; next_run = {'backup': time.monotonic() + backup_delay(jobs['backup'][0])}
        self.stdout.write('Local scheduler started. X import disabled. Stop with Ctrl+C.')
        # A separate slot per task prevents a slow archive/source from delaying votes.
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            try:
                while True:
                    now = time.monotonic()
                    for name, (interval, fn) in jobs.items():
                        future = running.get(name)
                        if (future is None or future.done()) and now >= next_run.get(name, 0):
                            running[name] = pool.submit(run_monitored, name, fn); next_run[name] = now + interval
                    ImportState.objects.update_or_create(name='local:heartbeat', defaults={'last_success': timezone.now()})
                    time.sleep(10)
            except KeyboardInterrupt:
                self.stdout.write('Finishing running jobs before shutdown.')
