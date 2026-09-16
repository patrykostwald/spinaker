import pytest

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.suspend_source_for_review import suspend


@pytest.mark.django_db
def test_suspend_creates_new_history_and_disables_source():
    source = Source.objects.create(name="test", url="https://example.test", is_active=True,
        scrape_enabled=True, catalog_stage="configured")
    card = SourceAccessInstruction.objects.create(
        source=source, version=1, status="approved", channel="html", allowed_scope="content",
        endpoint="https://example.test/news", terms_url="https://example.test/terms", evidence={"ok": True},
        reviewed_at="2026-01-01T00:00:00Z", reviewed_by="tester", daily_request_cap=5,
        valid_until="2027-01-01T00:00:00Z")
    assert suspend(source.pk, "adapter_structure_changed") == 1
    source.refresh_from_db()
    stopped = SourceAccessInstruction.objects.get(source=source, version=2)
    assert not source.is_active and not source.scrape_enabled
    assert card.status == "approved"
    assert stopped.status == "suspended" and stopped.daily_request_cap == 0
    assert stopped.evidence["suspension_reason"] == "adapter_structure_changed"
