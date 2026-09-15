from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

import pytest
from django.utils import timezone

from news.models import Article, ArticleContent, ImportState, OfficialRecord, Source, SourceAccessInstruction
from scraper.uokik_sudop import API, STATE_NAME, sudop_pilot_cycle


NOW = datetime(2026, 9, 14, 8, tzinfo=dt_timezone.utc)


class Response:
    def __init__(self, status, *, location="", payload=None, retry_after=""):
        self.status_code = status
        self.headers = {"Location": location, "Retry-After": retry_after}
        self._payload = payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0), None


@pytest.fixture
def source(db, monkeypatch):
    monkeypatch.setenv("UOKIK_SUDOP_PILOT_ENABLED", "true")
    source = Source.objects.create(name="UOKiK — SUDOP", url=API,
        is_active=True, scrape_enabled=True, catalog_stage="configured")
    SourceAccessInstruction.objects.create(
        source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API,
        endpoint=API + "/api", allowed_scope=SourceAccessInstruction.Scope.METADATA,
        terms_url=API, evidence={"test": True}, reviewed_at=timezone.now(),
        reviewed_by="Test redakcyjny", valid_until=timezone.now() + timedelta(days=1),
        minimum_interval_seconds=3)
    return source


def run_due(session):
    state = ImportState.objects.get(name=STATE_NAME)
    state.cursor["available_at"] = (NOW - timedelta(seconds=1)).isoformat()
    state.save(update_fields=["cursor"])
    return sudop_pilot_cycle(transport=session, now=NOW)


def event(**overrides):
    row = {
        "nip-udzielajacego-pomocy": "5261009497", "nazwa-udzielajacego-pomocy": "Urząd",
        "srodek-pomocowy-numer": "SA.1", "srodek-pomocowy-nazwa": "Program",
        "dzien-udzielenia-pomocy": "2016-01-01", "nip-beneficjenta": "1234567890",
        "nazwa-beneficjenta": "Firma Test", "przeznaczenie-pomocy-kod": "b1",
        "przeznaczenie-pomocy-nazwa": "Inwestycja", "forma-pomocy-kod": "A1",
        "forma-pomocy-nazwa": "Dotacja", "wartosc-nominalna-pln": "1000",
        "wartosc-brutto-pln": "900", "wartosc-brutto-eur": "200",
    }
    row.update(overrides)
    return row


def test_disabled_does_not_create_state_or_call_network(db, monkeypatch):
    Source.objects.create(name="SUDOP", url=API, catalog_stage="configured")
    monkeypatch.delenv("UOKIK_SUDOP_PILOT_ENABLED", raising=False)
    session = Session()
    assert sudop_pilot_cycle(transport=session, now=NOW)["status"] == "disabled"
    assert not session.calls and not ImportState.objects.exists()


def test_enabled_flag_without_access_card_still_cannot_call_network(db, monkeypatch):
    monkeypatch.setenv("UOKIK_SUDOP_PILOT_ENABLED", "true")
    Source.objects.create(name="SUDOP", url=API, is_active=True, scrape_enabled=True)
    session = Session()

    assert sudop_pilot_cycle(transport=session, now=NOW)["status"] == "disabled"
    assert not session.calls and not ImportState.objects.exists()


def test_three_stage_protocol_frozen_cutoff_and_metadata_only(source):
    session = Session(
        Response(303, location=API + "/api/kolejka/q-1"),
        Response(303, location=API + "/api/wynik/r-1"),
        Response(200, payload={"liczba-wynikow": 2, "wyniki": [event(), {"name": "dictionary"}]}),
    )
    first = sudop_pilot_cycle(transport=session, now=NOW)
    state = ImportState.objects.get(name=STATE_NAME)
    assert first["phase"] == "queue" and state.cursor["cutoff"] == "2026-09-14"
    assert len(session.calls) == 1 and "audit_source" in session.calls[0][1]
    assert run_due(session)["phase"] == "result"
    result = run_due(session)
    assert result == {"status": "ok", "new_records": 1, "processed": 2, "cutoff": "2026-09-14"}
    article = Article.objects.get()
    assert article.category == "document" and article.ingestion_method == "sudop"
    assert "Dane mogą ulec zmianie" in article.description and "Pozyskano: 2026-09-14" in article.description
    assert not ArticleContent.objects.exists() and not OfficialRecord.objects.exists()


def test_replayed_result_is_idempotent(source):
    row = event()
    state = ImportState.objects.create(name=STATE_NAME, cursor={
        "next_date": "2016-01-01", "cutoff": "2026-09-14", "page": 1,
        "row_offset": 0, "phase": "result", "request_id": "one", "complete": False,
    })
    payload = {"liczba-wynikow": 1, "wyniki": [row]}
    assert sudop_pilot_cycle(transport=Session(Response(200, payload=payload)), now=NOW)["new_records"] == 1
    state.refresh_from_db()
    state.cursor.update(next_date="2016-01-01", phase="result", request_id="two",
        row_offset=0, page=1, complete=False, available_at=(NOW - timedelta(seconds=1)).isoformat())
    state.save(update_fields=["cursor"])
    assert sudop_pilot_cycle(transport=Session(Response(200, payload=payload)), now=NOW)["new_records"] == 0
    assert Article.objects.count() == 1


def test_batch_is_bounded_and_cursor_resumes_same_report(source, monkeypatch):
    monkeypatch.setattr("scraper.uokik_sudop.MAX_RECORDS_PER_CYCLE", 2)
    ImportState.objects.create(name=STATE_NAME, cursor={
        "next_date": "2016-01-01", "cutoff": "2026-09-14", "page": 1,
        "row_offset": 0, "phase": "result", "request_id": "one", "complete": False,
    })
    rows = [event(**{"nip-beneficjenta": str(index).zfill(10)}) for index in range(3)]
    result = sudop_pilot_cycle(transport=Session(Response(200,
        payload={"liczba-wynikow": 3, "wyniki": rows})), now=NOW)
    state = ImportState.objects.get(name=STATE_NAME)
    assert result["processed"] == 2 and Article.objects.count() == 2
    assert state.cursor["row_offset"] == 2 and state.cursor["phase"] == "submit"


def test_429_retry_after_preserves_phase_and_exact_delay(source):
    session = Session(Response(429, retry_after="120"))
    result = sudop_pilot_cycle(transport=session, now=NOW)
    state = ImportState.objects.get(name=STATE_NAME)
    assert result["retry_after"] == 120 and state.cursor["phase"] == "submit"
    assert datetime.fromisoformat(state.cursor["available_at"]) == NOW + timedelta(seconds=120)


def test_invalid_redirect_host_and_payload_do_not_advance_cursor(source):
    result = sudop_pilot_cycle(transport=Session(Response(303,
        location="https://evil.example/api/kolejka/q")), now=NOW)
    assert result["status"] == "error"
    assert ImportState.objects.get(name=STATE_NAME).cursor["phase"] == "submit"
