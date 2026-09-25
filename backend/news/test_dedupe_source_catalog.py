import pytest
from django.core.management import call_command

from news.management.commands.dedupe_source_catalog import MARKER, publisher_key
from news.models import Source


def candidate(name, url, **extra):
    fields = {"is_active": False, "scrape_enabled": False, "catalog_stage": "candidate"}
    fields.update(extra)
    return Source.objects.create(name=name, url=url, **fields)


def test_publisher_key_groups_same_publisher_only():
    assert publisher_key("https://www.tvn24.pl") == publisher_key("https://tvn24.pl/najwazniejsze.xml")
    assert publisher_key("https://konkret24.tvn24.pl") != publisher_key("https://tvn24.pl")
    assert publisher_key("https://wiadomosci.onet.pl") == publisher_key("https://www.onet.pl/informacje/rss")
    assert publisher_key("https://www.gov.pl/web/finanse") == publisher_key("https://www.gov.pl/web/finanse/rss")
    assert publisher_key("https://www.gov.pl/web/finanse") != publisher_key("https://www.gov.pl/web/zdrowie")
    assert publisher_key("https://www.youtube.com/channel/A") != publisher_key("https://www.youtube.com/channel/B")
    assert publisher_key("https://bip.gov.pl/web/klimat") != publisher_key("https://bip.gov.pl/web/sport")


@pytest.mark.django_db
def test_keeps_feed_entry_and_excludes_host_card_then_restores():
    host_card = candidate("tvn24.pl", "https://www.tvn24.pl")
    feed = candidate("TVN24", "https://tvn24.pl/najwazniejsze.xml")
    other_outlet = candidate("konkret24.tvn24.pl", "https://konkret24.tvn24.pl")

    call_command("dedupe_source_catalog")
    host_card.refresh_from_db()
    assert host_card.catalog_stage == "candidate"  # plan only

    call_command("dedupe_source_catalog", "--apply")
    host_card.refresh_from_db()
    feed.refresh_from_db()
    other_outlet.refresh_from_db()
    assert host_card.catalog_stage == "excluded" and MARKER in host_card.catalog_notes
    assert feed.catalog_stage == "candidate"
    assert other_outlet.catalog_stage == "candidate"

    call_command("dedupe_source_catalog", "--restore", "--apply")
    host_card.refresh_from_db()
    assert host_card.catalog_stage == "candidate"


@pytest.mark.django_db
def test_configured_source_wins_and_is_never_excluded():
    configured = Source.objects.create(name="Najwyższa Izba Kontroli", url="https://www.nik.gov.pl/rss/", is_active=True, catalog_stage="configured")
    card = candidate("nik.gov.pl", "https://www.nik.gov.pl")

    call_command("dedupe_source_catalog", "--apply")

    configured.refresh_from_db()
    card.refresh_from_db()
    assert configured.catalog_stage == "configured"
    assert card.catalog_stage == "excluded"
