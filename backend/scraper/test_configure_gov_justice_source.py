import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_configure_gov_justice_source_is_read_only_without_apply():
    source = Source.objects.create(name="PR test", url="https://www.gov.pl/web/pr-test",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_gov_justice_source", source_id=source.pk,
        listing_url="https://www.gov.pl/web/pr-test/aktualnosci")
    source.refresh_from_db()
    assert not source.is_active
    assert not SourceAccessInstruction.objects.filter(source=source).exists()


@pytest.mark.django_db
def test_configure_gov_justice_source_records_two_narrow_cards():
    source = Source.objects.create(name="PR test", url="https://www.gov.pl/web/pr-test",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_gov_justice_source", "--apply", source_id=source.pk,
        listing_url="https://www.gov.pl/web/pr-test/aktualnosci")
    source.refresh_from_db()
    cards = list(SourceAccessInstruction.objects.filter(source=source).order_by("version"))
    assert source.is_active and source.scrape_enabled and source.catalog_stage == "configured"
    assert [(card.channel, card.endpoint, card.allowed_path_patterns) for card in cards] == [
        ("html", "https://www.gov.pl/web/pr-test/", []),
        ("sitemap", "https://www.gov.pl/robots.txt", ["/robots.txt"]),
    ]


@pytest.mark.django_db
def test_configure_gov_justice_source_rejects_url_outside_section():
    source = Source.objects.create(name="PR test", url="https://www.gov.pl/web/pr-test",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    with pytest.raises(Exception, match="własnej sekcji"):
        call_command("configure_gov_justice_source", "--apply", source_id=source.pk,
            listing_url="https://www.gov.pl/web/inny/aktualnosci")


@pytest.mark.django_db
def test_configure_gov_justice_source_can_set_reviewed_base_for_candidate():
    source = Source.objects.create(name="PO test", url=None,
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    call_command("configure_gov_justice_source", "--apply", source_id=source.pk,
        base_url="https://www.gov.pl/web/po-test",
        listing_url="https://www.gov.pl/web/po-test/aktualnosci-prokuratury-okregowej")
    source.refresh_from_db()
    assert source.url == "https://www.gov.pl/web/po-test"
    assert source.is_active
