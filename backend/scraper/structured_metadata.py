"""Bounded, metadata-only preflight for documented public data APIs.

This module deliberately does not turn catalogue entries into articles and does
not enumerate a provider.  One reviewed endpoint is requested once to prove
that its current JSON contract remains usable before a future dedicated
importer is considered.
"""
from __future__ import annotations

import json
from hashlib import sha256

from news.models import FetchAttempt, Source, SourceAccessInstruction
from scraper.access_gate import AccessDenied, approved_instruction
from scraper.utils import fetch_feed


class StructuredMetadataPreflightError(ValueError):
    pass


SPECS = {
    "dane_gov": {
        "source_url": "https://dane.gov.pl",
        "endpoint": "https://api.dane.gov.pl/1.4/datasets",
        "required_keys": ("data",),
    },
    "gus_bdl": {
        "source_url": "https://stat.gov.pl",
        "endpoint": "https://bdl.stat.gov.pl/api/v1/subjects?lang=pl&format=json",
        "required_keys": ("results",),
    },
}


def preflight(key: str) -> dict:
    """Fetch exactly one documented JSON listing and return no provider data."""
    try:
        spec = SPECS[key]
    except KeyError as exc:
        raise StructuredMetadataPreflightError("unknown_structured_metadata_source") from exc
    source = Source.objects.get(url=spec["source_url"])
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.API, spec["endpoint"])
    if instruction is None:
        raise AccessDenied("no_approved_instruction")
    raw = fetch_feed(
        spec["endpoint"], hostname_transport=True, audit_source=source,
        audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.API_RECORD,
    )
    if len(raw) > 2_000_000:
        raise StructuredMetadataPreflightError("preflight_response_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StructuredMetadataPreflightError("invalid_json") from exc
    if not isinstance(payload, dict) or any(key not in payload for key in spec["required_keys"]):
        raise StructuredMetadataPreflightError("unexpected_json_contract")
    return {
        "source": key,
        "endpoint": spec["endpoint"],
        "bytes": len(raw),
        "response_sha256": sha256(raw).hexdigest(),
        "contract": "ok",
    }
