from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction
from scraper.bzp_backfill import SEARCH_URL, SOURCE_URL


pytestmark = pytest.mark.django_db


def test_bzp_configuration_is_explicit_and_idempotent():
    call_command('configure_bzp_metadata_source', stdout=StringIO())
    assert not Source.objects.filter(url=SOURCE_URL).exists()

    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    source = Source.objects.get(url=SOURCE_URL)
    cards = SourceAccessInstruction.objects.filter(source=source, channel='api')
    assert source.is_active and source.scrape_enabled and source.catalog_stage == 'configured'
    assert cards.count() == 1 and cards.get().endpoint == SEARCH_URL


def test_old_slow_card_is_replaced_by_new_version_with_20_requests_per_minute():
    from datetime import timedelta
    from django.utils import timezone
    from scraper.management.commands.configure_bzp_metadata_source import DAILY_CAP, INTERVAL_SECONDS, TERMS_URL
    source = Source.objects.create(name='BZP', url=SOURCE_URL, source_type='institution', is_active=False,
                                   scrape_enabled=False, catalog_stage='candidate')
    SourceAccessInstruction.objects.create(
        source=source, version=1, status='approved', channel='api', allowed_scope='metadata', endpoint=SEARCH_URL,
        terms_url=TERMS_URL, evidence={'basis': 'stara karta'}, reviewed_at=timezone.now(), reviewed_by='test',
        valid_until=timezone.now() + timedelta(days=100), minimum_interval_seconds=180, daily_request_cap=480)
    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    call_command('configure_bzp_metadata_source', '--apply', '--reviewed-by=test', stdout=StringIO())
    cards = SourceAccessInstruction.objects.filter(source=source, channel='api').order_by('version')
    assert [c.version for c in cards] == [1, 2]
    newest = cards.last()
    assert newest.minimum_interval_seconds == INTERVAL_SECONDS == 3 and newest.daily_request_cap == DAILY_CAP == 5000
    assert 60 / newest.minimum_interval_seconds <= 20
