"""Disabled-by-default, metadata-only pilot for official SUDOP aid events.

BDL is deliberately not implemented here: a BDL API row is a statistical cell
(variable, territory, year, value), not a publication-like record suitable for
an Article box.  A SUDOP row is a dated, separately reported aid event.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import os
from urllib.parse import urlparse
from uuid import uuid4

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from news.models import Article, ArticleCategory, ImportState, Source
from scraper.utils import upsert_article


API = "https://api-sudop.uokik.gov.pl/sudop-api"
SOURCE_URL = API
STATE_NAME = "official-pilot:uokik-sudop"
LOCK = "lock:official-pilot:uokik-sudop"
INTERVAL_SECONDS = 4  # Catalogue: 15 requests/minute.
MAX_RECORDS_PER_CYCLE = 250
REMOTE_PAGE_SIZE = 10_000
ATTRIBUTION = (
    "Źródło: System Udostępniania Danych o Pomocy Publicznej UOKiK. "
    "Pozyskano: {retrieved}. Dane mogą ulec zmianie. Za kompletność, prawidłowość "
    "i aktualność odpowiadają podmioty udzielające pomocy. Dane mają charakter "
    "pomocniczy i nie powinny być wyłączną podstawą weryfikacji pomocy."
)


def _enabled(source: Source | None) -> bool:
    flag = os.getenv("UOKIK_SUDOP_PILOT_ENABLED", "").strip().lower()
    return bool(source and flag in {"1", "true", "yes"} and source.is_active
                and source.scrape_enabled and source.catalog_stage == "configured")


def _retry_seconds(response, now):
    value = response.headers.get("Retry-After", "").strip()
    if value.isdigit():
        return max(INTERVAL_SECONDS, int(value))
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=dt_timezone.utc)
        return max(INTERVAL_SECONDS, int((retry_at - now.astimezone(dt_timezone.utc)).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return 60


def _path_id(location: str, expected_segment: str) -> str:
    parsed = urlparse(location)
    if parsed.netloc and parsed.netloc != "api-sudop.uokik.gov.pl":
        raise ValueError("SUDOP redirect changed host")
    parts = [part for part in parsed.path.split("/") if part]
    try:
        index = parts.index(expected_segment)
        value = parts[index + 1]
    except (ValueError, IndexError):
        raise ValueError("Invalid SUDOP redirect")
    if not value or len(value) > 200 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in value):
        raise ValueError("Invalid SUDOP redirect identifier")
    return value


def _canonical_event(row):
    if not isinstance(row, dict):
        return None
    fields = {
        key: str(row.get(key) or "").strip()
        for key in (
            "nip-udzielajacego-pomocy", "nazwa-udzielajacego-pomocy",
            "srodek-pomocowy-numer", "srodek-pomocowy-nazwa",
            "dzien-udzielenia-pomocy", "nip-beneficjenta", "nazwa-beneficjenta",
            "przeznaczenie-pomocy-kod", "przeznaczenie-pomocy-nazwa",
            "forma-pomocy-kod", "forma-pomocy-nazwa", "wartosc-nominalna-pln",
            "wartosc-brutto-pln", "wartosc-brutto-eur",
        )
    }
    # A box must identify an actual dated transfer, its beneficiary, provider,
    # programme and at least one official amount. Dictionary-like rows are skipped.
    required = ("dzien-udzielenia-pomocy", "nip-beneficjenta", "nazwa-beneficjenta",
                "nip-udzielajacego-pomocy", "srodek-pomocowy-numer")
    if any(not fields[key] for key in required) or not any(fields[key] for key in
            ("wartosc-nominalna-pln", "wartosc-brutto-pln", "wartosc-brutto-eur")):
        return None
    try:
        event_date = date.fromisoformat(fields["dzien-udzielenia-pomocy"])
    except ValueError:
        return None
    digest = sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    return fields, event_date, digest


def _save_event(source, row, query_url, retrieved_at):
    parsed = _canonical_event(row)
    if not parsed:
        return False
    fields, event_date, digest = parsed
    title = f"Pomoc dla {fields['nazwa-beneficjenta']} — {fields['srodek-pomocowy-numer']}"
    amount = fields["wartosc-brutto-pln"] or fields["wartosc-nominalna-pln"]
    detail = fields["przeznaczenie-pomocy-nazwa"] or fields["forma-pomocy-nazwa"]
    description = "; ".join(part for part in (
        f"Udzielający: {fields['nazwa-udzielajacego-pomocy']}",
        f"Kwota PLN: {amount}" if amount else "",
        detail,
        ATTRIBUTION.format(retrieved=timezone.localtime(retrieved_at).date().isoformat()),
    ) if part)
    article, created = upsert_article(source=source, title=title,
        url=f"{query_url}#event-{digest}", published_date=event_date,
        category=ArticleCategory.DOCUMENT, description=description,
        ingestion_method="sudop", category_reviewed=True,
        category_evidence="Oficjalny, datowany przypadek pomocy z API SUDOP.")
    # No OfficialRecord/ArticleContent: the pilot stores metadata, not API payloads
    # or text/snapshots. Refresh the mandatory retrieval attribution on replay.
    if article and not created and article.source_id == source.pk:
        Article.objects.filter(pk=article.pk).update(description=description)
    return created


def _initial_cursor(today):
    start = date(today.year - 10, 1, 1)
    return {"next_date": start.isoformat(), "cutoff": today.isoformat(), "page": 1,
            "row_offset": 0, "phase": "submit", "complete": False, "requests": 0}


def _sudop_pilot_cycle(*, session=requests, now=None):
    source = Source.objects.filter(url=SOURCE_URL).first()
    if not _enabled(source):
        return {"status": "disabled", "new_records": 0}
    now = now or timezone.now()
    state, _ = ImportState.objects.get_or_create(name=STATE_NAME)
    cursor = dict(state.cursor) or _initial_cursor(timezone.localdate(now))
    if not state.cursor:
        # Persist the frozen boundary before the first network operation. A
        # failed first submission must resume the same historical pass.
        state.cursor = cursor
        state.save(update_fields=["cursor"])
    if cursor.get("complete"):
        return {"status": "complete", "new_records": 0, "cutoff": cursor["cutoff"]}
    available = cursor.get("available_at")
    if available and datetime.fromisoformat(available) > now:
        return {"status": "deferred", "new_records": 0, "available_at": available}

    work_day, cutoff = date.fromisoformat(cursor["next_date"]), date.fromisoformat(cursor["cutoff"])
    if work_day > cutoff:
        raise ValueError("Invalid SUDOP cursor range")
    state.last_started = now
    state.save(update_fields=["last_started"])
    query_params = {"dzien-udzielenia-pomocy-od": work_day.isoformat(),
        "dzien-udzielenia-pomocy-do": work_day.isoformat(), "strona": cursor.get("page", 1)}
    query_url = requests.Request("GET", API + "/api/przypadki-pomocy", params=query_params).prepare().url

    try:
        phase = cursor.get("phase", "submit")
        if phase == "submit":
            response = session.get(API + "/api/przypadki-pomocy", params=query_params,
                timeout=(5, 60), allow_redirects=False,
                headers={"User-Agent": "spin.clinic/1.0 metadata-only SUDOP pilot"})
        elif phase == "queue":
            response = session.get(f"{API}/api/kolejka/{cursor['queue_id']}", timeout=(5, 60),
                allow_redirects=False, headers={"User-Agent": "spin.clinic/1.0 metadata-only SUDOP pilot"})
        elif phase == "result":
            response = session.get(f"{API}/api/wynik/{cursor['request_id']}", params={"csv": "false"},
                timeout=(5, 60), allow_redirects=False,
                headers={"User-Agent": "spin.clinic/1.0 metadata-only SUDOP pilot"})
        else:
            raise ValueError("Invalid SUDOP cursor phase")

        cursor["requests"] = int(cursor.get("requests", 0)) + 1
        delay = _retry_seconds(response, now) if response.status_code == 429 else INTERVAL_SECONDS
        cursor["available_at"] = (now + timedelta(seconds=delay)).isoformat()
        if response.status_code == 429:
            state.cursor, state.last_error = cursor, "rate_limited"
            state.save(update_fields=["cursor", "last_error"])
            return {"status": "deferred", "new_records": 0, "retry_after": delay}

        if phase == "submit":
            if response.status_code != 303:
                raise ValueError(f"Unexpected SUDOP submit status {response.status_code}")
            cursor.update(phase="queue", queue_id=_path_id(response.headers.get("Location", ""), "kolejka"))
        elif phase == "queue":
            if response.status_code == 200:
                pass
            elif response.status_code == 303:
                cursor.update(phase="result", request_id=_path_id(response.headers.get("Location", ""), "wynik"))
                cursor.pop("queue_id", None)
            else:
                raise ValueError(f"Unexpected SUDOP queue status {response.status_code}")
        else:
            if response.status_code != 200:
                raise ValueError(f"Unexpected SUDOP result status {response.status_code}")
            payload = response.json()
            rows = payload.get("wyniki") if isinstance(payload, dict) else None
            total = payload.get("liczba-wynikow") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or not isinstance(total, int) or total < len(rows):
                raise ValueError("Invalid SUDOP result payload")
            offset = int(cursor.get("row_offset", 0))
            batch = rows[offset:offset + MAX_RECORDS_PER_CYCLE]
            with transaction.atomic():
                created = sum(bool(_save_event(source, row, query_url, now)) for row in batch)
                next_offset = offset + len(batch)
                if next_offset < len(rows):
                    cursor.update(phase="submit", row_offset=next_offset)
                else:
                    next_page = int(cursor.get("page", 1)) + 1
                    if len(rows) == REMOTE_PAGE_SIZE and next_page * REMOTE_PAGE_SIZE <= total + REMOTE_PAGE_SIZE:
                        cursor.update(phase="submit", page=next_page, row_offset=0)
                    else:
                        next_day = work_day + timedelta(days=1)
                        cursor.update(phase="submit", next_date=next_day.isoformat(), page=1,
                            row_offset=0, complete=next_day > cutoff)
                cursor.pop("request_id", None)
                state.cursor, state.last_success, state.last_error = cursor, now, ""
                state.imported += created
                state.save(update_fields=["cursor", "last_success", "last_error", "imported"])
            return {"status": "complete" if cursor["complete"] else "ok",
                "new_records": created, "processed": len(batch), "cutoff": cursor["cutoff"]}

        state.cursor, state.last_error = cursor, ""
        state.save(update_fields=["cursor", "last_error"])
        return {"status": "deferred", "new_records": 0, "phase": cursor["phase"]}
    except Exception as exc:
        state.last_error = str(exc)[:200]
        state.save(update_fields=["last_error"])
        return {"status": "error", "new_records": 0, "error": str(exc)[:200]}


def sudop_pilot_cycle(*, session=requests, now=None):
    """Make at most one HTTP request and persist the next finite state."""
    token = uuid4().hex
    if not cache.add(LOCK, token, 90):
        return {"status": "already_running", "new_records": 0}
    try:
        return _sudop_pilot_cycle(session=session, now=now)
    finally:
        if cache.get(LOCK) == token:
            cache.delete(LOCK)
