from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source
from scraper.management.commands.prepare_uokik_rss_candidate import LISTING_URL, RSS_URL


@pytest.mark.django_db
def test_prepare_uokik_candidate_sets_the_disclosed_feed_without_activation():
    source = Source.objects.create(
        name="UOKiK candidate", url="https://uokik.gov.pl", source_type="institution",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")

    call_command("prepare_uokik_rss_candidate", "--source-id", str(source.pk), "--apply", stdout=StringIO())

    source.refresh_from_db()
    assert (source.url, source.rss_url) == (LISTING_URL, RSS_URL)
    assert source.catalog_stage == "candidate"
    assert not source.is_active and not source.scrape_enabled
