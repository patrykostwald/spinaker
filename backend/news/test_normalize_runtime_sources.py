import csv

import pytest

from news.management.commands.normalize_runtime_sources import build_ledger, create_contact_cards
from news.models import Source, SourceAccessInstruction, SourceContactCard


@pytest.mark.django_db
def test_no_card_with_missing_address_becomes_one_contact_draft_without_activation():
    source = Source.objects.create(name="Adres do ustalenia", url=None,
        catalog_stage="candidate", is_active=False, scrape_enabled=False)
    rows = build_ledger([], [source])
    assert rows[0]["classification"] == "contact_missing_address"
    assert create_contact_cards(rows) == 1
    assert create_contact_cards(rows) == 0
    source.refresh_from_db()
    card = SourceContactCard.objects.get(source=source)
    assert card.status == "draft"
    assert not source.is_active and not source.scrape_enabled


@pytest.mark.django_db
def test_related_catalog_path_is_only_a_possible_alias_never_an_automatic_merge():
    canonical = Source.objects.create(name="Katalog", url="https://example.test/web/organ",
        catalog_stage="candidate", is_active=False, scrape_enabled=False)
    legacy = Source.objects.create(name="Dawny RSS", url="https://example.test/web/organ/rss",
        catalog_stage="candidate", is_active=False, scrape_enabled=False)
    rows = build_ledger([canonical], [legacy])
    assert rows[0]["classification"] == "contact_possible_catalog_alias"
    assert rows[0]["catalog_match_ids"] == [canonical.pk]
    create_contact_cards(rows)
    assert Source.objects.filter(pk__in=[canonical.pk, legacy.pk]).count() == 2
    assert SourceAccessInstruction.objects.filter(source=legacy).count() == 0
