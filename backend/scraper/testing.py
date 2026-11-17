"""Test-only helpers: reviewed access cards for sources used in importer tests.

Production importers fail closed without a current, reviewed
``SourceAccessInstruction`` (scraper.access_gate).  Tests of importer logic
must create the same cards an editor would approve, instead of bypassing the
gate.
"""

from urllib.parse import urlsplit

from django.utils import timezone

from news.models import SourceAccessInstruction


def configure_source(source):
    """Mark a source operational, the state an approved catalogue entry has."""
    source.is_active = True
    source.scrape_enabled = True
    source.catalog_stage = 'configured'
    source.save(update_fields=['is_active', 'scrape_enabled', 'catalog_stage'])
    return source


def approve_access(source, channel, endpoint=None, scope='metadata', patterns=None, robots=True):
    version = (SourceAccessInstruction.objects.filter(source=source)
        .order_by('-version').values_list('version', flat=True).first() or 0) + 1
    card = SourceAccessInstruction.objects.create(
        source=source, version=version, status='approved', channel=channel,
        allowed_scope=scope, endpoint=endpoint or source.url,
        allowed_path_patterns=patterns or [],
        terms_url='https://example.org/terms', evidence={'basis': 'test'},
        reviewed_at=timezone.now(), reviewed_by='test', minimum_interval_seconds=3,
        daily_request_cap=24)
    if robots:
        # robots.txt is a separately authorised request in production.
        root = urlsplit(endpoint or source.url)
        robots_url = f'{root.scheme}://{root.netloc}/robots.txt'
        if not SourceAccessInstruction.objects.filter(source=source, status='approved',
                channel='sitemap', endpoint=robots_url).exists():
            SourceAccessInstruction.objects.create(
                source=source, version=version + 1, status='approved', channel='sitemap',
                allowed_scope='metadata', endpoint=robots_url,
                allowed_path_patterns=['/robots.txt'], terms_url='https://example.org/terms',
                evidence={'basis': 'test robots'}, reviewed_at=timezone.now(), reviewed_by='test',
                minimum_interval_seconds=3, daily_request_cap=24)
    return card
