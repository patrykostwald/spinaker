import pytest
from django.core.management import call_command

from news.models import Source, SourceAccessInstruction, SourceContactCard, SourceRecoveryCase


def card(source, *, status, endpoint="https://example.test/feed", evidence=None):
    return SourceAccessInstruction.objects.create(
        source=source, version=1, status=status, channel="rss", allowed_scope="metadata",
        endpoint=endpoint, terms_url="https://example.test/terms", evidence=evidence or {},
    )


@pytest.mark.django_db
def test_register_creates_review_contact_card_without_sending(tmp_path):
    source = Source.objects.create(name="Publisher", url="https://example.test")
    card(source, status="contact_required", evidence={"evidence_url": "https://example.test/terms"})
    report = tmp_path / "register.md"

    call_command("build_source_outreach_register", "--report", report)

    contact = SourceContactCard.objects.get(source=source)
    assert contact.status == "ready_for_review"
    assert contact.sent_at is None
    assert contact.next_review_at is None
    assert contact.technical_findings["follow_up_rule"].startswith("Telefon")
    assert "Publisher" in report.read_text(encoding="utf-8")


@pytest.mark.django_db
def test_register_routes_confirmed_404_to_contact_after_bounded_retry():
    source = Source.objects.create(name="Old RSS", url="https://old.example", last_error="adapter_feed_returns_404")
    instruction = card(source, status="suspended")
    SourceRecoveryCase.objects.create(
        source=source, status="triage", trigger="terminal_error",
        failure_fingerprint="adapter_feed_returns_404", failed_instruction=instruction,
    )

    call_command("build_source_outreach_register")

    assert SourceContactCard.objects.get(source=source).status == "ready_for_review"
    assert SourceRecoveryCase.objects.get(source=source).status == "contact_required"


@pytest.mark.django_db
def test_register_is_idempotent_for_contact_source():
    source = Source.objects.create(name="Publisher", url="https://publisher.example")
    card(source, status="contact_required")

    call_command("build_source_outreach_register")
    call_command("build_source_outreach_register")

    assert SourceContactCard.objects.filter(source=source).count() == 1
