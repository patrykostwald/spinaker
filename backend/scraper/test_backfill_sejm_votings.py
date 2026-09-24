from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction


def approved_source():
    source = Source.objects.create(
        name="Sejm Rzeczypospolitej Polskiej", url="https://api.sejm.gov.pl/sejm",
        is_active=True, scrape_enabled=True, catalog_stage="configured",
    )
    SourceAccessInstruction.objects.create(
        source=source, version=1, status="approved", channel="api", allowed_scope="content",
        endpoint="https://api.sejm.gov.pl/sejm/term10/votings",
        allowed_path_patterns=["/sejm/term10/votings/{int}", "/sejm/term10/votings/{int}/{int}"],
        terms_url="https://www.sejm.gov.pl/sejm10.nsf/page.xsp/copyright",
        evidence={"basis": "test"}, reviewed_at=timezone.now(), reviewed_by="test",
        valid_until=timezone.now() + timedelta(days=1), minimum_interval_seconds=3,
        daily_request_cap=24,
    )
    return source


@pytest.mark.django_db
def test_backfill_is_read_only_without_apply(monkeypatch):
    approved_source()
    module = "scraper.management.commands.backfill_sejm_votings"
    monkeypatch.setattr(f"{module}.connection.vendor", "postgresql")
    fetch = pytest.importorskip("unittest.mock").Mock()
    monkeypatch.setattr(f"{module}.fetch_json", fetch)

    output = StringIO()
    call_command("backfill_sejm_votings", "--from-sitting=1", "--to-sitting=2", stdout=output)

    assert "GOTOWY" in output.getvalue()
    fetch.assert_not_called()
    assert not ImportState.objects.exists()


@pytest.mark.django_db
def test_backfill_saves_cursor_at_request_limit(monkeypatch):
    approved_source()
    module = "scraper.management.commands.backfill_sejm_votings"
    monkeypatch.setattr(f"{module}.connection.vendor", "postgresql")
    monkeypatch.setattr(f"{module}.sleep", lambda _: None)
    monkeypatch.setattr(f"{module}.fetch_json", lambda _: [
        {"term": 10, "sitting": 1, "votingNumber": 1},
        {"term": 10, "sitting": 1, "votingNumber": 2},
    ])
    imported = pytest.importorskip("unittest.mock").Mock(return_value=True)
    monkeypatch.setattr(f"{module}.import_voting", imported)

    call_command("backfill_sejm_votings", "--from-sitting=1", "--to-sitting=1",
                 "--max-requests=2", "--apply", stdout=StringIO())

    imported.assert_called_once_with(10, 1, 1)
    assert ImportState.objects.get(name="sejm-term10-voting-backfill").cursor == {
        "sitting": 1, "next_vote": 2
    }


@pytest.mark.django_db
def test_backfill_defers_after_transport_error(monkeypatch):
    approved_source()
    module = "scraper.management.commands.backfill_sejm_votings"
    monkeypatch.setattr(f"{module}.connection.vendor", "postgresql")
    monkeypatch.setattr(f"{module}.fetch_json", lambda _: (_ for _ in ()).throw(OSError("offline")))

    output = StringIO()
    call_command("backfill_sejm_votings", "--from-sitting=1", "--to-sitting=1",
                 "--apply", stdout=output)

    state = ImportState.objects.get(name="sejm-term10-voting-backfill")
    assert state.cursor == {"sitting": 1, "next_vote": 1}
    assert "OSError" in state.last_error
    assert "ODROCZONO" in output.getvalue()
