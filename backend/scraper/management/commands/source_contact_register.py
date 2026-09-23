"""Create the later-contact list without contacting anybody."""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import ImportState, Source, SourceReviewDecision
from scraper.management.commands.source_review_queue import hostname, review_bucket


class Command(BaseCommand):
    help = "Writes a later-contact source list; it never sends email, enables sources, or downloads content."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="reports/source-contact-register-current.md")

    def handle(self, *args, **options):
        candidates = list(Source.objects.select_related('review_decision').filter(
            catalog_stage="candidate", is_active=False, scrape_enabled=False,
        ).order_by("pk"))
        states = dict(ImportState.objects.filter(
            name__in=[f"source-check:{source.pk}" for source in candidates]
        ).values_list("name", "cursor"))
        active_hosts = {
            hostname(source.url) for source in Source.objects.filter(
                catalog_stage="configured", is_active=True, scrape_enabled=True,
            ) if hostname(source.url)
        }
        rows = []
        for source in candidates:
            if hostname(source.url) in active_hosts:
                continue
            result = states.get(f"source-check:{source.pk}", {}) or {}
            manual = getattr(source, 'review_decision', None)
            requires_contact = manual and not manual.is_automated and manual.decision == SourceReviewDecision.Decision.CONTACT_REQUIRED
            if not requires_contact and review_bucket(source, result) != "04_wydawca_lub_organizacja_wymaga_zgody":
                continue
            rows.append({
                "id": source.pk, "source": source.name, "host": hostname(source.url),
                "url": source.url or "", "reason": (manual.reason if requires_contact else "No published terms or explicit permission recorded for automated metadata reuse."),
                "status": "Do not contact yet; prepare for editorial review.",
            })

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Source contact register", "",
            "This is a preparation list only. It does not send mail, create accounts, approve access, enable a source, or download content.",
            "", f"Sources requiring later confirmation: **{len(rows)}**.", "",
            "| ID | Source | Host | Reason | Status |", "|---:|---|---|---|---|",
        ]
        for row in rows:
            label = row["source"].replace("|", "\\|")
            linked = f"[{label}]({row['url']})" if row["url"] else label
            lines.append(f"| {row['id']} | {linked} | {row['host']} | {row['reason']} | {row['status']} |")
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=("id", "source", "host", "url", "reason", "status"))
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(
            f"SOURCE_CONTACT_REGISTER: {len(rows)} sources; {output}"
        ))
