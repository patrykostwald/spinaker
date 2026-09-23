from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_contact_register_contains_only_unapproved_publisher_candidates(tmp_path):
    publisher = Source.objects.create(
        name="Publisher", url="https://publisher.example", source_type=SourceType.PORTAL,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    official = Source.objects.create(
        name="Official", url="https://official.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    ImportState.objects.create(name=f"source-check:{official.pk}", cursor={
        "audit_status": "completed", "rss": {"status": "working", "url": "https://official.example/feed"},
    })
    output = tmp_path / "contact.md"
    stream = StringIO()
    call_command("source_contact_register", "--output", str(output), stdout=stream)
    report = output.read_text(encoding="utf-8")
    assert "Sources requiring later confirmation: **1**" in report
    assert "Publisher" in report
    assert "Official" not in report
    assert "SOURCE_CONTACT_REGISTER: 1 sources" in stream.getvalue()
    publisher.refresh_from_db()
    assert not publisher.is_active


@pytest.mark.django_db
def test_contact_register_includes_automatic_safety_demotion(tmp_path):
    source = Source.objects.create(
        name="Uncarded", url="https://uncarded.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    SourceReviewDecision.objects.create(
        source=source, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason="No current reviewed access card.", reviewed_by="catalog safety gate", is_automated=True,
        audit_snapshot={"reason": "no_current_approved_access_card"},
    )
    output = tmp_path / "contact.md"
    call_command("source_contact_register", "--output", str(output), stdout=StringIO())
    assert "Sources requiring later confirmation: **1**" in output.read_text(encoding="utf-8")
