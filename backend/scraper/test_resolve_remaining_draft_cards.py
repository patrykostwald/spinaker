import pytest
from news.models import Source, SourceAccessInstruction, SourceContactCard
from scraper.management.commands.resolve_remaining_draft_cards import DECISIONS, resolve


@pytest.mark.django_db
def test_resolver_is_append_only_and_never_activates_or_sends():
    url = next(iter(DECISIONS))
    source = Source.objects.create(name="candidate", url=url, is_active=False, scrape_enabled=False, catalog_stage="candidate")
    SourceAccessInstruction.objects.create(source=source, version=1, status="draft", channel="rss",
        allowed_scope="metadata", endpoint=url, evidence={"reason": "test"}, daily_request_cap=0)
    resolve(source)
    source.refresh_from_db()
    cards = list(source.access_instructions.order_by("version"))
    contact = source.contact_cards.get()
    assert [card.status for card in cards] == ["draft", "contact_required"]
    assert not source.is_active and not source.scrape_enabled
    assert contact.status == SourceContactCard.Status.READY_FOR_REVIEW
    assert contact.sent_at is None


@pytest.mark.django_db
def test_resolver_is_idempotent_after_contact_card_exists():
    url = next(iter(DECISIONS))
    source = Source.objects.create(name="candidate", url=url, is_active=False, scrape_enabled=False, catalog_stage="candidate")
    SourceAccessInstruction.objects.create(source=source, version=1, status="draft", channel="rss",
        allowed_scope="metadata", endpoint=url, evidence={"reason": "test"}, daily_request_cap=0)
    resolve(source)
    source.refresh_from_db()
    # The command detects an already resolved source and performs no second write.
    assert source.access_instructions.order_by("-version").first().status == "contact_required"
    assert source.access_instructions.count() == 2
    assert source.contact_cards.count() == 1
