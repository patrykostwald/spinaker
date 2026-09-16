import csv

import pytest

from news.management.commands.apply_catalog_recon import apply_rows, reviewed_rows
from news.models import Source, SourceAccessInstruction


@pytest.mark.django_db
def test_apply_recon_creates_a_non_fetching_contact_decision(tmp_path):
    catalog_path = tmp_path / "sources.csv"
    with catalog_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "base_url"])
        writer.writeheader()
        writer.writerow({"name": "Publisher", "base_url": "https://publisher.example"})
    source = Source.objects.create(name="Publisher", url="https://publisher.example",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    report = tmp_path / "report.md"
    report.write_text("| 1 | Publisher | **B** | no proof |\n", encoding="utf-8")
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        result = apply_rows(list(csv.DictReader(handle)), reviewed_rows(report))
    card = SourceAccessInstruction.objects.get(source=source)
    source.refresh_from_db()
    assert result["contact_required"] == 1
    assert card.status == "contact_required"
    assert card.daily_request_cap == 0
    assert not source.is_active and not source.scrape_enabled


@pytest.mark.django_db
def test_apply_recon_keeps_positive_row_draft_and_inactive(tmp_path):
    source = Source.objects.create(name="Official", url="https://official.example",
        is_active=False, scrape_enabled=False, catalog_stage="candidate")
    result = apply_rows([{"name": "Official", "base_url": "https://official.example"}], {1: "A"})
    source.refresh_from_db()
    assert result["draft"] == 1
    assert SourceAccessInstruction.objects.get(source=source).status == "draft"
    assert not source.is_active


@pytest.mark.django_db
def test_reconcile_uses_linked_source_not_shifted_ordinal(tmp_path):
    catalog = [
        {"name": "Actual", "base_url": "https://actual.example"},
        {"name": "Wrong", "base_url": "https://wrong.example"},
    ]
    actual = Source.objects.create(name="Actual", url="https://actual.example", catalog_stage="candidate")
    wrong = Source.objects.create(name="Wrong", url="https://wrong.example", catalog_stage="candidate")
    SourceAccessInstruction.objects.create(source=wrong, version=1, status="suspended", channel="html",
        allowed_scope="metadata", endpoint=wrong.url, evidence={"catalog_position": 2},
        reviewed_by="spin.system", daily_request_cap=0)
    report = tmp_path / "report.md"
    report.write_text("| 2 | [Actual](https://actual.example) | **B** | proof |\n", encoding="utf-8")
    result = apply_rows(catalog, reviewed_rows(report), report_name=report.name, reconcile=True)
    assert result["contact_required"] == 1
    assert SourceAccessInstruction.objects.get(source=actual).status == "contact_required"
    assert SourceAccessInstruction.objects.filter(source=wrong).order_by("-version").first().status == "contact_required"
