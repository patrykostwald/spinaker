"""Write a plain-language, read-only source-verification register."""
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import ImportState, Source, SourceReviewDecision
from scraper.management.commands.source_review_queue import hostname, review_bucket


DECISIONS = {
    "00_juz_aktywne_pod_innym_rekordem": (
        "already covered", "Do not create a second harvester; reconcile the duplicate record."),
    "01_blad_techniczny": (
        "technical recheck", "Do not ingest. Record the technical failure and retry only after it is resolved."),
    "02_instytucja_rss_do_warunkow": (
        "terms review", "Confirm published reuse terms for this exact channel before enabling metadata."),
    "03_instytucja_bez_potwierdzonego_kanalu": (
        "channel discovery", "Find an official RSS or API endpoint; do not guess one."),
    "04_wydawca_lub_organizacja_wymaga_zgody": (
        "later contact list", "Keep inactive until published terms or explicit permission are recorded."),
}

MANUAL_DECISIONS = {
    SourceReviewDecision.Decision.COVERED: DECISIONS['00_juz_aktywne_pod_innym_rekordem'],
    SourceReviewDecision.Decision.TECHNICAL_RECHECK: DECISIONS['01_blad_techniczny'],
    SourceReviewDecision.Decision.TERMS_REVIEW: DECISIONS['02_instytucja_rss_do_warunkow'],
    SourceReviewDecision.Decision.CHANNEL_DISCOVERY: DECISIONS['03_instytucja_bez_potwierdzonego_kanalu'],
    SourceReviewDecision.Decision.CONTACT_REQUIRED: DECISIONS['04_wydawca_lub_organizacja_wymaga_zgody'],
}


class Command(BaseCommand):
    help = "Creates a plain-language register for every inactive candidate; never sends mail or enables a source."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="reports/source-verification-register-current.md")

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
            result = states.get(f"source-check:{source.pk}", {}) or {}
            bucket = ("00_juz_aktywne_pod_innym_rekordem" if hostname(source.url) in active_hosts
                      else review_bucket(source, result))
            manual = getattr(source, 'review_decision', None)
            if manual and not manual.is_automated:
                status, next_step = MANUAL_DECISIONS[manual.decision]
                reason = manual.reason
            else:
                status, next_step = DECISIONS[bucket]
                reason = ''
            rss = result.get("rss") or {}
            rows.append({
                "id": source.pk, "name": source.name, "url": source.url or "", "bucket": bucket,
                "decision": status, "next_step": next_step,
                "audit_status": result.get("audit_status", "not audited"),
                "rss_status": rss.get("status", "unknown"), "rss_url": rss.get("url", ""),
                "reason": reason,
            })

        counts = Counter(row["decision"] for row in rows)
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Source verification register", "",
            "This is a review register only. It does not send mail, approve access, enable a source, or download articles.",
            "", f"Candidates: **{len(rows)}**.", "",
            "| Decision | Count |", "|---|---:|",
        ]
        for decision in DECISIONS.values():
            lines.append(f"| {decision[0]} | {counts[decision[0]]} |")
        lines += ["", "| ID | Source | Audit | RSS | Decision | Next step |", "|---:|---|---|---|---|---|"]
        for row in rows:
            label = row["name"].replace("|", "\\|")
            source = f"[{label}]({row['url']})" if row["url"] else label
            feed = f"[RSS]({row['rss_url']})" if row["rss_url"] else "—"
            lines.append(
                f"| {row['id']} | {source} | {row['audit_status']} | {feed} | "
                f"{row['decision']} | {row['reason'] or row['next_step']} |"
            )
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = " ".join(
            f"{decision[0].replace(' ', '_')}={counts[decision[0]]}"
            for decision in DECISIONS.values()
        )
        self.stdout.write(self.style.SUCCESS(
            f"SOURCE_VERIFICATION_REGISTER: {len(rows)} candidates; {summary}; {output}"
        ))
