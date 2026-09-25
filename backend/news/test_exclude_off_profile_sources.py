import pytest
from django.core.management import call_command

from news.management.commands.exclude_off_profile_sources import MARKER, address_key, category_for
from news.models import Source


def candidate(name, url, **extra):
    fields = {"is_active": False, "scrape_enabled": False, "catalog_stage": "candidate"}
    fields.update(extra)
    return Source.objects.create(name=name, url=url, **fields)


def test_address_matching_is_exact_per_host_and_path():
    assert address_key("https://www.Interia.pl/Sport/") == "interia.pl/sport"
    assert category_for("https://smaker.pl") == "kulinaria"
    assert category_for("https://www.spidersweb.pl/feed") == "technologie konsumenckie i gry"
    assert category_for("https://interia.pl/sport") == "sport"
    # Similar-looking news addresses stay untouched.
    assert category_for("https://fakty.interia.pl") is None
    assert category_for("https://www.rmf24.pl") is None
    assert category_for("https://radiogra.pl") is None
    assert category_for("https://sportowefakty.wp.pl") == "sport"
    assert category_for("https://wiadomosci.wp.pl") is None


@pytest.mark.django_db
def test_plan_does_not_change_the_database():
    source = candidate("smaker.pl", "https://smaker.pl")

    call_command("exclude_off_profile_sources")

    source.refresh_from_db()
    assert source.catalog_stage == "candidate"


@pytest.mark.django_db
def test_apply_excludes_off_profile_candidates_and_restore_reverts():
    off = candidate("pudelek.pl", "https://www.pudelek.pl")
    news = candidate("tvn24.pl", "https://tvn24.pl")

    call_command("exclude_off_profile_sources", "--apply")

    off.refresh_from_db()
    news.refresh_from_db()
    assert off.catalog_stage == "excluded"
    assert MARKER in off.catalog_notes and "lifestyle i plotki" in off.catalog_notes
    assert news.catalog_stage == "candidate"

    call_command("exclude_off_profile_sources", "--restore", "--apply")

    off.refresh_from_db()
    assert off.catalog_stage == "candidate"


@pytest.mark.django_db
def test_active_or_configured_sources_are_never_excluded():
    active = Source.objects.create(name="eska.pl", url="https://eska.pl", is_active=True, catalog_stage="configured")

    call_command("exclude_off_profile_sources", "--apply")

    active.refresh_from_db()
    assert active.catalog_stage == "configured"
