"""Apply a catalogue reconnaissance as versioned, fail-closed access cards.

Reports are matched to their named or linked source, not merely to an ordinal.
This prevents a changed catalogue from assigning a decision to the next source.
No decision in this command activates a harvester.
"""
import csv
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from news.source_catalog import public_catalog_url


ROW = re.compile(
    r"^\|\s*(?P<position>\d+)\s*\|\s*(?P<source>.*?)\s*\|\s*"
    r"\*{0,2}(?P<decision>[ABC])\*{0,2}\s*\|", re.M)
LINK = re.compile(r"\[([^]]+)\]\((https?://[^)]+)\)")


def source_key(value):
    parsed = urlsplit(value or "")
    return ((parsed.hostname or "").lower().removeprefix("www.") +
            (parsed.path or "").rstrip("/")).lower()


def reviewed_rows(report):
    """Read decisions while retaining the report's source identity."""
    records = []
    for match in ROW.finditer(Path(report).read_text(encoding="utf-8")):
        raw = match.group("source").strip()
        linked = LINK.search(raw)
        records.append({
            "position": int(match.group("position")), "decision": match.group("decision"),
            "name": (linked.group(1) if linked else raw).strip().strip("`"),
            "url": linked.group(2) if linked else "",
        })
    return records


def card_status(decision):
    return {
        "A": SourceAccessInstruction.Status.DRAFT,
        "B": SourceAccessInstruction.Status.CONTACT_REQUIRED,
        "C": SourceAccessInstruction.Status.SUSPENDED,
    }[decision]


def set_source_stage(source, decision):
    Source.objects.filter(pk=source.pk).update(
        is_active=False, scrape_enabled=False,
        catalog_stage="candidate" if decision in ("A", "B") else "excluded",
    )


def new_card(source, record, now, report_name, *, reconciliation_pending=False):
    latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
    decision = "B" if reconciliation_pending else record["decision"]
    if reconciliation_pending:
        reason = "Wykryto przesunięcie pozycji w raporcie; wymagany ponowny, ręczny przegląd."
    elif decision == "A":
        reason = "Kanał wygląda obiecująco, ale wymaga osobnej konfiguracji i bieżącego dowodu przed aktywacją."
    elif decision == "B":
        reason = "Brak potwierdzonego kanału i warunków; wymagany kontakt lub węższy dowód."
    else:
        reason = "Pozycja zbiorcza, historyczna lub poza zakresem; nie aktywować harvestera."
    SourceAccessInstruction.objects.create(
        source=source, version=(latest.version if latest else 0) + 1,
        status=card_status(decision), channel=SourceAccessInstruction.Channel.HTML,
        allowed_scope=SourceAccessInstruction.Scope.METADATA, endpoint=source.url,
        evidence={
            "catalog_position": record["catalog_position"], "catalog_name": record["catalog_name"],
            "report_source_name": record["name"], "report_source_url": record["url"],
            "catalog_recon_report": report_name, "decision": decision, "reason": reason,
            "reconciliation_pending": reconciliation_pending,
        },
        reviewed_at=now, reviewed_by="spin.system", daily_request_cap=0,
    )
    set_source_stage(source, decision)
    return card_status(decision)


def resolve_records(catalog, records):
    by_url = {source_key(row["base_url"]): (position, row)
              for position, row in enumerate(catalog, start=1)}
    by_name = {row["name"].strip().casefold(): (position, row)
               for position, row in enumerate(catalog, start=1)}
    resolved = []
    for record in records:
        match = by_url.get(source_key(record["url"])) if record["url"] else None
        match = match or by_name.get(record["name"].casefold())
        if not match:
            raise CommandError(f"Nie umiem bezpiecznie dopasować raportu: {record['name']!r}.")
        position, row = match
        resolved.append({**record, "catalog_position": position, "catalog_name": row["name"],
                         "catalog_url": public_catalog_url(row["base_url"].strip(), resolve=False)})
    return resolved


def apply_rows(catalog, records, *, report_name="manual", reconcile=False):
    if isinstance(records, dict):
        records = [{"position": p, "decision": d, "name": catalog[p - 1]["name"], "url": ""}
                   for p, d in records.items()]
    records = resolve_records(catalog, records)
    created = {"draft": 0, "contact_required": 0, "suspended": 0,
               "already_decided": 0, "reconciled": 0, "reconciliation_pending": 0}
    now = timezone.now()
    with transaction.atomic():
        sources = {source.url: source for source in Source.objects.select_for_update().exclude(url__isnull=True)}
        matched_source_ids = set()
        for record in records:
            source = sources.get(record["catalog_url"])
            if source is None:
                raise CommandError(f"Brak źródła w bazie dla: {record['catalog_name']}")
            matched_source_ids.add(source.pk)
            latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
            evidence = latest.evidence if latest and isinstance(latest.evidence, dict) else {}
            mismatched_report_card = (
                latest and latest.reviewed_by == "spin.system" and
                "catalog_position" in evidence and evidence.get("catalog_position") != record["catalog_position"]
            )
            legacy_position_only_card = (
                latest and latest.reviewed_by == "spin.system" and
                evidence.get("catalog_position") in {item["position"] for item in records} and
                not evidence.get("catalog_recon_report")
            )
            needs_reconciliation = mismatched_report_card or legacy_position_only_card
            if latest and not (reconcile and needs_reconciliation):
                created["already_decided"] += 1
                continue
            outcome = new_card(source, record, now, report_name)
            created[outcome] += 1
            if needs_reconciliation:
                created["reconciled"] += 1
        if reconcile:
            report_positions = {record["position"] for record in records}
            latest_by_source = {}
            for card in SourceAccessInstruction.objects.select_for_update().filter(
                    reviewed_by="spin.system", source_id__in=sources.values()).order_by("source_id", "-version"):
                latest_by_source.setdefault(card.source_id, card)
            for source_id, card in latest_by_source.items():
                evidence = card.evidence if isinstance(card.evidence, dict) else {}
                if source_id not in matched_source_ids and evidence.get("catalog_position") in report_positions:
                    source = Source.objects.get(pk=source_id)
                    record = {"position": evidence["catalog_position"], "catalog_position": evidence["catalog_position"],
                              "catalog_name": source.name, "name": source.name, "url": source.url, "decision": "B"}
                    new_card(source, record, now, report_name, reconciliation_pending=True)
                    created["reconciliation_pending"] += 1
    return created


class Command(BaseCommand):
    help = "Zapisuje wersjonowane, nieaktywujące decyzje A/B/C z raportu rekonesansu katalogu."

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument("--report", required=True)
        parser.add_argument("--catalog", default=str(root / "sources.md"))
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--reconcile", action="store_true")

    def handle(self, *args, **options):
        report, catalog_path = Path(options["report"]), Path(options["catalog"])
        if not report.is_file() or not catalog_path.is_file():
            raise CommandError("Brak raportu albo katalogu.")
        records = reviewed_rows(report)
        if not records:
            raise CommandError("Nie rozpoznano żadnej decyzji A/B/C w raporcie.")
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            catalog = list(csv.DictReader(handle))
        resolve_records(catalog, records)
        if not options["apply"]:
            self.stdout.write(f"PLAN: decyzji={len(records)}; bez --apply nie zmieniam kart.")
            return
        result = apply_rows(catalog, records, report_name=report.name, reconcile=options["reconcile"])
        self.stdout.write(self.style.SUCCESS("GOTOWE: " + " ".join(
            f"{key}={value}" for key, value in result.items())))
