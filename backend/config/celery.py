from celery.schedules import crontab
from celery import Celery
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('spin_clinic')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.beat_schedule = {
    'sejm-votes-15m': {'task': 'scraper.tasks.import_official_task', 'args': ['votings'], 'schedule': crontab(minute='*/15')},
    'sejm-prints-hourly': {'task': 'scraper.tasks.import_official_task', 'args': ['prints'], 'schedule': crontab(minute=10)},
    'eli-hourly': {'task': 'scraper.tasks.import_official_task', 'args': ['eli'], 'schedule': crontab(minute=20)},
    'gdelt-2h': {'task': 'scraper.tasks.gdelt_daily_topics', 'schedule': crontab(minute=0, hour='*/2')},
    'archive-discovery-daily': {'task': 'scraper.tasks.discover_archives', 'schedule': crontab(hour=3, minute=30)},
    'quality-5m': {'task': 'scraper.tasks.check_data_quality', 'schedule': crontab(minute='*/5')},
    'archives-minute': {'task': 'scraper.tasks.archive_batch', 'schedule': crontab(minute='*')},
    'kprm-listing-minute': {'task': 'scraper.tasks.discover_kprm_html', 'schedule': crontab(minute='*')},
    # Four listing checks daily, capped again by the reviewed MSWiA source card.
    'mswia-metadata-6h': {'task': 'scraper.tasks.discover_mswia_metadata', 'schedule': crontab(minute=35, hour='*/6')},
    'ministry-finance-metadata-6h': {'task': 'scraper.tasks.discover_ministry_finance_metadata', 'schedule': crontab(minute=45, hour='*/6')},
    'map-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['map'], 'schedule': crontab(minute=5, hour='*/6')},
    'msz-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['msz'], 'schedule': crontab(minute=15, hour='*/6')},
    'klimat-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['klimat'], 'schedule': crontab(minute=25, hour='*/6')},
    'zdrowie-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['zdrowie'], 'schedule': crontab(minute=55, hour='*/6')},
    'edukacja-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['edukacja'], 'schedule': crontab(minute=10, hour='*/6')},
    'rolnictwo-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['rolnictwo'], 'schedule': crontab(minute=20, hour='*/6')},
    'senat-metadata-6h': {'task': 'scraper.tasks.discover_senat_metadata', 'schedule': crontab(minute=40, hour='*/6')},
    'mon-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['mon'], 'schedule': crontab(minute=2, hour='*/6')},
    'justice-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['sprawiedliwosc'], 'schedule': crontab(minute=32, hour='*/6')},
    'infrastructure-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['infrastruktura'], 'schedule': crontab(minute=50, hour='*/6')},
    'digital-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['cyfryzacja'], 'schedule': crontab(minute=4, hour='*/6')},
    'culture-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['kultura'], 'schedule': crontab(minute=12, hour='*/6')},
    'development-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['rozwoj'], 'schedule': crontab(minute=18, hour='*/6')},
    'science-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['nauka'], 'schedule': crontab(minute=28, hour='*/6')},
    'sanitary-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['gis'], 'schedule': crontab(minute=38, hour='*/6')},
    'environment-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['gios'], 'schedule': crontab(minute=42, hour='*/6')},
    'strategic-reserves-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['rars'], 'schedule': crontab(minute=48, hour='*/6')},
    'family-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['rodzina'], 'schedule': crontab(minute=8, hour='*/6')},
    'sport-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['sport'], 'schedule': crontab(minute=22, hour='*/6')},
    'kowr-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['kowr'], 'schedule': crontab(minute=52, hour='*/6')},
    'gdos-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['gdos'], 'schedule': crontab(minute=14, hour='*/6')},
    'kis-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['kis'], 'schedule': crontab(minute=30, hour='*/6')},
    'ncbr-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['ncbr'], 'schedule': crontab(minute=46, hour='*/6')},
    'paa-metadata-6h': {'task': 'scraper.tasks.discover_named_gov_metadata', 'args': ['paa'], 'schedule': crontab(minute=58, hour='*/6')},
    'source-access-5m': {'task': 'scraper.tasks.audit_source_access', 'schedule': crontab(minute='*/5')},
    'voting-history-5m': {'task': 'scraper.tasks.backfill_voting_history', 'schedule': crontab(minute='2-59/5')},
    'rss-hourly': {'task': 'scraper.tasks.scrape_rss_sources_task', 'schedule': crontab(minute=0)},
    'dane-gov-metadata-daily': {'task': 'scraper.tasks.preflight_structured_metadata_source', 'args': ['dane_gov'], 'schedule': crontab(hour=2, minute=10)},
    'gus-bdl-metadata-daily': {'task': 'scraper.tasks.preflight_structured_metadata_source', 'args': ['gus_bdl'], 'schedule': crontab(hour=2, minute=15)},
    # This tick is cheap: the task makes no X request unless a confirmed,
    # enabled account is due and the explicit X polling flag is on.
    'political-x-minute': {'task': 'news.tasks.political_poll_task', 'schedule': crontab(minute='*')},
    # BZP remains inactive until BZP_API_ENABLED=true is set in the deployment environment.
    'bzp-metadata-3m': {'task': 'scraper.tasks.import_bzp_metadata', 'schedule': crontab(minute='*/3')},
}
if os.environ.get('NEWSAPI_TIER', 'free') in ('business', 'advanced'):
    app.conf.beat_schedule['newsapi-frequent'] = {'task': 'scraper.tasks.scrape_newsapi_batch_task', 'schedule': crontab(minute='*/15')}
else:
    for hour, minute in [(6, 30), (12, 30), (18, 0)]:
        app.conf.beat_schedule[f'newsapi-{hour}'] = {'task': 'scraper.tasks.scrape_newsapi_batch_task', 'schedule': crontab(hour=hour, minute=minute)}

if os.environ.get('SOURCE_MAIL_IMAP_ENABLED', '').lower() in ('1', 'true', 'yes'):
    app.conf.beat_schedule['source-mail-inbox-5m'] = {
        'task': 'scraper.tasks.sync_source_mailbox', 'schedule': crontab(minute='*/5')}
