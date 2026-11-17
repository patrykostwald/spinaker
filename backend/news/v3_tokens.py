"""Tokeny w linkach e-mail (recenzja Codex 3): w bazie tylko skrót sha256, porównanie stałoczasowe, termin ważności,
jednorazowość (data użycia). Jawny token trafia wyłącznie do wiadomości e-mail."""
from __future__ import annotations

import hashlib
import secrets


def new() -> tuple[str, str]:
    """(token do linku, skrót do bazy)."""
    raw = secrets.token_urlsafe(32)
    return raw, digest(raw)


def digest(raw) -> str:
    return hashlib.sha256(str(raw or '').encode('utf-8')).hexdigest()


def find(queryset, field, raw):
    """Wiersz o skrócie tokenu (porównanie stałoczasowe po pobraniu kandydata); None, gdy brak albo pusty token."""
    if not raw or len(str(raw)) > 200:
        return None
    wanted = digest(raw)
    row = queryset.filter(**{field: wanted}).first()
    if row is None or not secrets.compare_digest(getattr(row, field), wanted):
        return None
    return row
