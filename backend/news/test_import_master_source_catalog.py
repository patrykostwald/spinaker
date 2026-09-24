import csv

import pytest
from django.core.management import call_command

from news.models import Source


@pytest.mark.django_db
def test_master_catalog_import_is_fail_closed(tmp_path):
    path = tmp_path / "sources.md"
    fields = ["name", "base_url", "source_type", "tier", "crawl_mode", "rate_limit_per_min", "content_policy", "evidence_mode", "enabled"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(dict(zip(fields, ["Example", "https://example.org", "media", "1", "rss", "20", "full_text", "snapshot_full", "TRUE"])))
    call_command("import_master_source_catalog", "--catalog", str(path), "--apply")
    source = Source.objects.get(url="https://example.org")
    assert source.catalog_stage == "candidate"
    assert not source.is_active and not source.scrape_enabled
    assert "nie zgoda" in source.catalog_notes
