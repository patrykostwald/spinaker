"""Read-only mapping from an active source to its scheduled MVP harvester.

This module never authorises a request.  It only makes the existing Celery
schedule auditable, so an active access card cannot be mistaken for a running
periodic importer.
"""

from scraper.gov_metadata_listing import OFFICIAL_GOV_LISTINGS


DIRECT_SCHEDULES = {
    'https://api.sejm.gov.pl/sejm': 'sejm-votes-15m / sejm-prints-hourly',
    'https://api.sejm.gov.pl/eli': 'eli-hourly',
    'https://www.senat.gov.pl': 'senat-metadata-6h',
    'https://www.gov.pl/web/premier': 'kprm-listing-minute',
    'https://www.gov.pl/web/mswia': 'mswia-metadata-6h',
    'https://www.gov.pl/web/finanse': 'ministry-finance-metadata-6h',
    'https://dane.gov.pl': 'dane-gov-metadata-daily',
    'https://stat.gov.pl': 'gus-bdl-metadata-daily',
}


def schedule_label(source, cards):
    """Return the periodic task label or a precise reason it is not scheduled.

    ``cards`` should contain current approved instructions only.  RSS has a
    generic hourly worker; reviewed HTML/API/importers are deliberately listed
    explicitly, because their endpoints and environment flags differ.
    """
    if source.rss_url and any(card.channel == 'rss' and card.endpoint == source.rss_url for card in cards):
        return 'rss-hourly', 'scheduled'
    if source.url in DIRECT_SCHEDULES:
        return DIRECT_SCHEDULES[source.url], 'scheduled'
    for key, spec in OFFICIAL_GOV_LISTINGS.items():
        if source.url == spec['source_url']:
            return f'{key}-metadata-6h', 'scheduled'
    return 'brak mapowania w Celery', 'needs_schedule_mapping'
