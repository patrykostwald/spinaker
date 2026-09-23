from io import StringIO

import pytest
from django.core.management import call_command

from news.models import ImportState, Source, SourceType


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
