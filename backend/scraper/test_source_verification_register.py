from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceReviewDecision, SourceType


@pytest.mark.django_db
def test_verification_register_classifies_every_candidate_without_writing_sources(tmp_path):
    official = Source.objects.create(
        name="Official", url="https://official.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    publisher = Source.objects.create(
        name="Publisher", url="https://publisher.example", source_type=SourceType.PORTAL,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    ImportState.objects.create(name=f"source-check:{official.pk}", cursor={
        "audit_status": "completed", "rss": {"status": "working", "url": "https://official.example/feed"},
    })
    output = tmp_path / "register.md"
    stream = StringIO()
    call_command("source_verification_register", "--output", str(output), stdout=stream)
    report = output.read_text(encoding="utf-8")
    assert "Candidates: **2**" in report
    assert "terms review" in report
    assert "later contact list" in report
    assert "terms_review=1" in stream.getvalue()
    official.refresh_from_db()
    publisher.refresh_from_db()
    assert not official.is_active and not publisher.is_active


@pytest.mark.django_db
def test_verification_register_uses_manual_source_decision(tmp_path):
    source = Source.objects.create(
        name="Official", url="https://official.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    ImportState.objects.create(name=f"source-check:{source.pk}", cursor={
        "audit_status": "completed", "rss": {"status": "working", "url": "https://official.example/feed"},
    })
    SourceReviewDecision.objects.create(
        source=source, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason="Exact RSS terms were not found.", reviewed_by="editor", is_automated=False,
    )
    output = tmp_path / "register.md"
    call_command("source_verification_register", "--output", str(output), stdout=StringIO())
    report = output.read_text(encoding="utf-8")
    assert "later contact list" in report
    assert "Exact RSS terms were not found." in report


@pytest.mark.django_db
def test_verification_register_explains_automatic_safety_demotion(tmp_path):
    source = Source.objects.create(
        name="Uncarded", url="https://uncarded.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    SourceReviewDecision.objects.create(
        source=source, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason="No current reviewed access card.", reviewed_by="catalog safety gate", is_automated=True,
        audit_snapshot={"reason": "no_current_approved_access_card"},
    )
    output = tmp_path / "register.md"
    call_command("source_verification_register", "--output", str(output), stdout=StringIO())
    report = output.read_text(encoding="utf-8")
    assert "later contact list" in report
    assert "No current reviewed access card." in report


@pytest.mark.django_db
def test_verification_register_uses_automatic_final_contact_decision(tmp_path):
    source = Source.objects.create(
        name="No channel", url="https://no-channel.example", source_type=SourceType.INSTITUTION,
        catalog_stage="candidate", is_active=False, scrape_enabled=False,
    )
    SourceReviewDecision.objects.create(
        source=source, decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        reason="No confirmed public RSS/API channel with a metadata reuse basis.",
        reviewed_by="institution channel discovery", is_automated=True,
    )
    output = tmp_path / "register.md"
    call_command("source_verification_register", "--output", str(output), stdout=StringIO())
    report = output.read_text(encoding="utf-8")
    assert "later contact list" in report
    assert "No confirmed public RSS/API channel" in report
