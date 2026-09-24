from celery import shared_task
from django.core.cache import cache
from scraper.gdelt_scraper import scrape_gdelt as import_gdelt
from scraper.newsapi_scraper import scrape_newsapi_batch as import_newsapi
from scraper.rss_scraper import scrape_rss_sources as import_rss, scrape_rss_source as import_feed
from scraper.twitter_scraper import scrape_twitter_politicians as import_twitter
from scraper.catalog import GDELT_TOPICS

@shared_task(name='scraper.tasks.scrape_gdelt_task', soft_time_limit=90, time_limit=120)
def scrape_gdelt_task(keyword='Polska', days_back=1):
    return import_gdelt(keyword, days_back)

@shared_task
def gdelt_daily_topics():
    for index, keyword in enumerate(GDELT_TOPICS):
        scrape_gdelt_task.apply_async(args=[keyword], countdown=index * 10)
    return len(GDELT_TOPICS)

@shared_task(name='scraper.tasks.scrape_newsapi_batch_task', soft_time_limit=1200, time_limit=1300)
def scrape_newsapi_batch_task():
    return import_newsapi()

@shared_task(name='scraper.tasks.scrape_rss_sources_task', soft_time_limit=3000, time_limit=3300)
def scrape_rss_sources_task():
    if not cache.add('lock:rss', True, 3600):
        return 0
    try:
        return import_rss()
    finally:
        cache.delete('lock:rss')

@shared_task(name='scraper.tasks.scrape_twitter_politicians_task', soft_time_limit=3000, time_limit=3300)
def scrape_twitter_politicians_task():
    if not cache.add('lock:twitter', True, 3600):
        return 0
    try:
        return import_twitter()
    finally:
        cache.delete('lock:twitter')

@shared_task(soft_time_limit=60, time_limit=90)
def scrape_rss_source(source_id):
    return import_feed(source_id)


@shared_task(soft_time_limit=90, time_limit=120)
def preflight_structured_metadata_source(key):
    """Daily proof that a narrowly approved metadata API still has its contract.

    This deliberately stores no provider payload as an article and never
    expands beyond the one endpoint covered by the source card.
    """
    from scraper.structured_metadata import preflight
    return preflight(key)


@shared_task(soft_time_limit=120, time_limit=150)
def sync_source_mailbox():
    """Read response headers from the dedicated outreach mailbox only."""
    from news.mailbox import SourceMailboxDisabled, sync_inbound
    try:
        return sync_inbound()
    except SourceMailboxDisabled as exc:
        return {'status': 'disabled', 'reason': str(exc)}

@shared_task(soft_time_limit=60, time_limit=90)
def scrape_google_news(keyword):
    from urllib.parse import urlencode
    from scraper.utils import get_or_create_source
    query = urlencode({'q': keyword, 'hl': 'pl', 'gl': 'PL', 'ceid': 'PL:pl'})
    url = 'https://news.google.com/rss/search?' + query
    source = get_or_create_source(name='Google News: ' + keyword, url=url, rss_url=url)
    # On-demand feeds must never enter the periodic RSS schedule.
    source.scrape_frequency_minutes = 2147483647
    source.save(update_fields=['scrape_frequency_minutes'])
    return import_feed(source.pk)

@shared_task
def send_keyword_alerts():
    # Integration point: subscriptions and an email provider are not enabled in MVP.
    return {'status': 'not_configured'}

scrape_gdelt = scrape_gdelt_task
scrape_newsapi_batch = scrape_newsapi_batch_task
scrape_rss_sources = scrape_rss_sources_task
scrape_twitter_politicians = scrape_twitter_politicians_task


@shared_task(soft_time_limit=3300, time_limit=3500)
def import_official_task(kind):
    from datetime import timedelta
    from django.conf import settings
    from django.utils import timezone
    from news.models import ImportState
    from scraper.official import import_voting_period, import_prints, import_eli_changes, official_access_allowed
    from scraper.utils import HostRateLimited
    if kind not in {'votings', 'prints', 'eli'}:
        raise ValueError('Unknown official import')
    lock = 'lock:official:' + kind
    if not cache.add(lock, True, 3600):
        return {'status': 'already_running'}
    state, _ = ImportState.objects.get_or_create(name='official:' + kind)
    started = timezone.now()
    state.last_started = started
    state.save(update_fields=['last_started'])
    try:
        paths = {
            'votings': f'/sejm/term{settings.SEJM_TERM}/votings/search',
            'prints': f'/sejm/term{settings.SEJM_TERM}/prints',
            'eli': '/eli/changes/acts',
        }
        provider = 'eli' if kind == 'eli' else 'sejm'
        if not official_access_allowed(provider, paths[kind]):
            state.last_error = 'no_approved_instruction'
            state.save(update_fields=['last_error'])
            return {'status': 'blocked_access_review', 'new_records': 0}
        # Revisit seven days for corrections; resume from last success after downtime.
        since = (state.last_success or started) - timedelta(days=7)
        if kind == 'votings':
            count = import_voting_period(settings.SEJM_TERM, timezone.localtime(since).date().isoformat(), timezone.localtime(started).date().isoformat())
        elif kind == 'prints':
            count = import_prints(settings.SEJM_TERM)
        else:
            count = import_eli_changes(timezone.localtime(since).strftime('%Y-%m-%dT%H:%M:%S'))
        state.last_success, state.last_error, state.imported = started, '', count
        state.save(update_fields=['last_success', 'last_error', 'imported'])
        return {'status': 'ok', 'new_records': count}
    except HostRateLimited as exc:
        # The provider's gateway has supplied a retry window.  Never sleep
        # inside a Celery worker: long windows otherwise consume the worker
        # until its soft limit and turn a controlled deferral into an error.
        state.last_error = f'host_rate_limited:{exc.retry_after_seconds:.3f}'
        state.save(update_fields=['last_error'])
        return {
            'status': 'deferred',
            'new_records': 0,
            'retry_after_seconds': exc.retry_after_seconds,
        }
    except Exception as exc:
        state.last_error = type(exc).__name__
        state.save(update_fields=['last_error'])
        raise
    finally:
        cache.delete(lock)


@shared_task(soft_time_limit=120, time_limit=150)
def import_bzp_metadata():
    """One bounded BZP API page; the environment flag remains the final on/off switch."""
    from scraper.bzp_backfill import bzp_backfill_cycle
    return bzp_backfill_cycle()


@shared_task(soft_time_limit=300, time_limit=360)
def archive_batch():
    from scraper.archive import archive_cycle
    if not cache.add('lock:archives', True, 400):
        return {'status': 'already_running'}
    try:
        return archive_cycle()
    finally:
        cache.delete('lock:archives')


@shared_task(soft_time_limit=90, time_limit=120)
def discover_kprm_html():
    from scraper.html_archive import kprm_listing_cycle
    return kprm_listing_cycle()


@shared_task(soft_time_limit=120, time_limit=150)
def discover_mswia_metadata():
    from scraper.mswia_listing import mswia_listing_cycle
    return mswia_listing_cycle()


@shared_task(soft_time_limit=120, time_limit=150)
def discover_ministry_finance_metadata():
    from scraper.ministry_finance_listing import ministry_finance_listing_cycle
    return ministry_finance_listing_cycle()


@shared_task(soft_time_limit=120, time_limit=150)
def discover_named_gov_metadata(source_key):
    from scraper.gov_metadata_listing import named_listing_cycle
    return named_listing_cycle(source_key)


@shared_task(soft_time_limit=120, time_limit=150)
def discover_senat_metadata():
    from scraper.senat_archive import discover_senat
    return discover_senat()


@shared_task(soft_time_limit=3000, time_limit=3300)
def discover_archives():
    from scraper.archive import discovery_cycle
    if not cache.add('lock:archive-discovery', True, 3600):
        return {'status': 'already_running'}
    try:
        return discovery_cycle()
    finally:
        cache.delete('lock:archive-discovery')


@shared_task(soft_time_limit=480, time_limit=540)
def audit_source_access():
    from django.conf import settings
    if not settings.SOURCE_ACCESS_AUTOPROBE_ENABLED:
        return {'status': 'disabled'}
    from scraper.source_monitor import audit_due_sources
    if not cache.add('lock:source-access', True, 600):
        return {'status': 'already_running'}
    try:
        return audit_due_sources()
    finally:
        cache.delete('lock:source-access')


@shared_task(soft_time_limit=1230, time_limit=1300)
def backfill_voting_history():
    from scraper.official_backfill import backfill_votings_cycle
    return backfill_votings_cycle()


@shared_task(soft_time_limit=60, time_limit=90)
def import_uokik_sudop_pilot():
    """Manual pilot hook; the adapter itself remains disabled unless opted in."""
    from scraper.uokik_sudop import sudop_pilot_cycle
    return sudop_pilot_cycle()


@shared_task(soft_time_limit=120, time_limit=150)
def check_data_quality():
    from scraper.quality import scan_quality
    return scan_quality(200)


@shared_task(soft_time_limit=240, time_limit=300)
def enrich_data_quality():
    """Build bounded derived quality profiles for the archive in the background."""
    from scraper.quality_enrichment import enrich_quality_cycle
    if not cache.add('lock:quality-enrichment', True, 600):
        return {'status': 'already_running'}
    try:
        return enrich_quality_cycle(limit=200)
    finally:
        cache.delete('lock:quality-enrichment')
