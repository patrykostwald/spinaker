"""Make the runtime source registry reviewable without deleting history.

The master catalogue is an import input.  Older imports can leave additional
``Source`` rows behind, often without an access card.  Those rows must not be
silently treated as harvestable merely because their publisher resembles a
catalogue entry.  This command writes a deterministic ledger and can create a
*draft contact card* for each uncovered row.  It never enables harvesting,
changes a URL, merges records or excludes a source automatically.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import OuterRef, Subquery

from news.models import Source, SourceAccessInstruction, SourceContactCard
from news.source_catalog import public_catalog_url


def source_identity(url: str | None) -> tuple[str, str]:
    """Return a stable host/path identity; query strings are never identity."""
    parsed = urlsplit(url or "")
    return (
        (parsed.hostname or "").lower().removeprefix("www."),
        (parsed.path or "").rstrip("/").lower(),
    )


def related_path(left: str, right: str) -> bool:
    """RSS may be a child of a catalogue home path, never the reverse host hop."""
    return bool(left and right and (left == right or left.startswith(right + "/") or right.startswith(left + "/")))


def catalog_matches(source: Source, catalog_sources: list[Source]) -> list[Source]:
    host, path = source_identity(source.url or source.rss_url)
    if not host:
        return []
    return [
        candidate for candidate in catalog_sources
        if source_identity(candidate.url)[0] == host
        and related_path(path, source_identity(candidate.url)[1])
    ]


def build_ledger(catalog_sources: list[Source], runtime_sources: list[Source]) -> list[dict]:
    rows = []
    for source in runtime_sources:
        matches = catalog_matches(source, catalog_sources)
        if not (source.url or source.rss_url):
            classification = "contact_missing_address"
            reason = "Rekord nie ma adresu; nie można utworzyć karty pobrania ani wykonać próby sieciowej."
        elif len(matches) == 1:
            classification = "contact_possible_catalog_alias"
            reason = "Adres wskazuje ten sam host/ścieżkę co rekord katalogu, ale historia pozostaje osobna do ręcznej decyzji."
        elif len(matches) > 1:
            classification = "contact_ambiguous_catalog_alias"
            reason = "Adres pasuje do więcej niż jednego rekordu katalogu; nie wolno scalać automatycznie."
        else:
            classification = "contact_unmapped_legacy_source"
            reason = "Rekord runtime nie ma karty ani jednoznacznego odpowiednika w katalogu."
        rows.append({
            "source_id": source.pk,
            "source_name": source.name,
            "url": source.url or "",
            "rss_url": source.rss_url or "",
            "classification": classification,
            "reason": reason,
            "catalog_match_ids": [candidate.pk for candidate in matches],
            "catalog_match_names": [candidate.name for candidate in matches],
            "proposed_next_state": "contact_required",
        })
    return rows


def render_markdown(rows: list[dict]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    lines = [
        "# Normalizacja runtime źródeł",
        "",
        "Ten rejestr nie usuwa historii, nie scala rekordów i nie aktywuje harvestera.",
        "Wpis `contact_*` oznacza wyłącznie gotowość do przygotowania kontaktu; nie wysyła wiadomości.",
        "",
        "## Liczby",
        "",
    ]
    lines.extend(f"- `{key}`: **{value}**" for key, value in sorted(counts.items()))
    lines.extend(["", "## Rekordy bez karty dostępu", ""])
    for row in rows:
        matches = ", ".join(str(value) for value in row["catalog_match_ids"]) or "—"
        lines.extend([
            f"### {row['source_id']} — {row['source_name']}",
            f"- Klasyfikacja: `{row['classification']}`",
            f"- Adres: {row['url'] or '—'}",
            f"- RSS: {row['rss_url'] or '—'}",
            f"- Dopasowania katalogowe (ID): {matches}",
            f"- Powód: {row['reason']}",
            "- Następny stan: `contact_required`",
            "",
        ])
    return "\n".join(lines)


def create_contact_cards(rows: list[dict]) -> int:
    """Create idempotent drafts; a later workflow owns review and sending."""
    created = 0
    with transaction.atomic():
        locked = Source.objects.select_for_update().in_bulk([row["source_id"] for row in rows])
        existing = set(SourceContactCard.objects.select_for_update().filter(
            source_id__in=locked).values_list("source_id", flat=True))
        for row in rows:
            if row["source_id"] in existing:
                continue
            source = locked[row["source_id"]]
            SourceContactCard.objects.create(
                source=source,
                status=SourceContactCard.Status.DRAFT,
                publisher_name=source.name,
                requested_scope=["metadata"],
                requested_channels=["rss", "api", "export", "sitemap"],
                technical_findings={
                    "runtime_normalization": row["classification"],
                    "catalog_match_ids": row["catalog_match_ids"],
                    "catalog_match_names": row["catalog_match_names"],
                    "url": row["url"],
                    "rss_url": row["rss_url"],
                },
                reason_for_contact=row["reason"],
            )
            created += 1
    return created


class Command(BaseCommand):
    help = "Tworzy rejestr źródeł runtime bez karty; opcjonalnie zakłada szkice kontaktu."

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument("--catalog", default=str(root / "sources.md"))
        parser.add_argument("--report", required=True)
        parser.add_argument("--apply-contact-cards", action="store_true")

    def handle(self, *args, **options):
        catalog_path = Path(options["catalog"])
        report_path = Path(options["report"])
        if not catalog_path.is_file():
            raise CommandError("Brak katalogu źródeł.")
        # The catalogue is deliberately read to validate that the chosen file is
        # a master catalogue; Source rows remain the only source of IDs.
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            catalog = list(csv.DictReader(handle))
        if not catalog or not {"name", "base_url"}.issubset(catalog[0]):
            raise CommandError("Katalog ma nieprawidłowy nagłówek.")
        expected_urls = {public_catalog_url(row["base_url"].strip(), resolve=False) for row in catalog}
        catalog_sources = list(Source.objects.filter(url__in=expected_urls).order_by("pk"))
        latest = SourceAccessInstruction.objects.filter(source_id=OuterRef("pk")).order_by("-version")
        runtime_sources = list(Source.objects.annotate(
            latest_instruction=Subquery(latest.values("pk")[:1])
        ).filter(latest_instruction__isnull=True).order_by("pk"))
        rows = build_ledger(catalog_sources, runtime_sources)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(rows), encoding="utf-8")
        report_path.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        created = create_contact_cards(rows) if options["apply_contact_cards"] else 0
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: katalog={len(catalog)} runtime_bez_karty={len(rows)} "
            f"szkice_kontaktu_nowe={created} raport={report_path}"))
