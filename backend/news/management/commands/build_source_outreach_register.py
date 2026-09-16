"""Build the review-only outreach register for unresolved source cards.

The command deliberately does not send mail, approve a card, or reactivate a
source.  It turns the two non-runnable terminal states into a durable human
worklist and records why a suspended source needs either adapter work, contact,
or no further action.
"""
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceContactCard, SourceRecoveryCase


def classify(source, instruction):
    """Return (class, human reason) without making a permission decision."""
    if instruction.status == SourceAccessInstruction.Status.CONTACT_REQUIRED:
        return "contact", "Brak potwierdzonej zgody dla wskazanego kanału i zakresu."

    error = (source.last_error or "").lower()
    cases = list(source.recovery_cases.all())
    fingerprints = " ".join(
        f"{case.failure_fingerprint} {case.sample_error} {case.decision_reason}".lower()
        for case in cases
    )
    if "non_article_route" in fingerprints:
        return "excluded", "Adres prowadzi do trasy technicznej lub listy, nie do materiału."
    if error == "adapter_feed_returns_404":
        # The bounded retry has already established that the reviewed feed is
        # gone.  Do not keep re-requesting a known 404 endpoint: ask the
        # publisher for its current documented channel instead.
        return "contact", "Zweryfikowany kanał RSS zwraca 404 po kontrolowanej próbie; potrzebne aktualne wskazanie endpointu od wydawcy."
    if error == "gov_listing_has_no_own_articles_after_adapter_review":
        return "contact", "Listing nie ujawnił własnych materiałów po kontroli adaptera; potrzebne właściwe wskazanie kanału."
    return "contact", "Karta jest wstrzymana; nie ma udokumentowanego kanału bezpiecznego do wznowienia."


def latest_instructions():
    """One authoritative card per source; versions are append-only."""
    for source in Source.objects.prefetch_related("access_instructions", "recovery_cases").order_by("pk"):
        instruction = max(source.access_instructions.all(), key=lambda card: card.version, default=None)
        if instruction and instruction.status in {
            SourceAccessInstruction.Status.CONTACT_REQUIRED,
            SourceAccessInstruction.Status.SUSPENDED,
        }:
            yield source, instruction


class Command(BaseCommand):
    help = "Tworzy rejestr kontaktowy dla kart wymagających kontaktu i klasyfikuje wstrzymane źródła."

    def add_arguments(self, parser):
        parser.add_argument("--report", type=Path, help="Opcjonalny plik Markdown z bieżącym rejestrem.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counts = {"contact": 0, "retry_adapter": 0, "excluded": 0, "created": 0, "existing": 0}
        rows = []
        now = timezone.now()

        with transaction.atomic():
            for source, instruction in latest_instructions():
                disposition, reason = classify(source, instruction)
                counts[disposition] += 1
                evidence = instruction.evidence or {}
                row = {
                    "source": source,
                    "instruction": instruction,
                    "disposition": disposition,
                    "reason": reason,
                    "evidence_url": evidence.get("evidence_url") or instruction.terms_url,
                }
                rows.append(row)

                if disposition == "retry_adapter":
                    # Keep the technical branch visible independently of the
                    # contact worklist.  This does not schedule a retry; a
                    # maintainer must repair and re-review the endpoint.
                    if not dry_run and not source.recovery_cases.exclude(
                        status__in=[SourceRecoveryCase.Status.CLOSED, SourceRecoveryCase.Status.RETIRED]
                    ).exists():
                        SourceRecoveryCase.objects.create(
                            source=source,
                            status=SourceRecoveryCase.Status.TRIAGE,
                            trigger="terminal_error",
                            failure_fingerprint="adapter_feed_returns_404",
                            sample_error=source.last_error,
                            failed_instruction=instruction,
                            audit_evidence={"classification": "retry_adapter", "endpoint": instruction.endpoint},
                            decision_reason=reason,
                        )
                if disposition != "contact":
                    continue
                SourceRecoveryCase.objects.filter(
                    source=source,
                    status__in=[SourceRecoveryCase.Status.DETECTED, SourceRecoveryCase.Status.TRIAGE,
                                SourceRecoveryCase.Status.COOLDOWN, SourceRecoveryCase.Status.AUDITING,
                                SourceRecoveryCase.Status.DRY_RUN, SourceRecoveryCase.Status.MANUAL_REVIEW],
                ).update(status=SourceRecoveryCase.Status.CONTACT_REQUIRED,
                         decision_reason=reason, decided_by="source_outreach_register", decided_at=now)
                # A source may already have a contact card because a recovery case
                # created one.  Do not overwrite any human review or reply.
                card = SourceContactCard.objects.filter(source=source).exclude(
                    status__in=[SourceContactCard.Status.CLOSED, SourceContactCard.Status.DECLINED]
                ).first()
                if card:
                    counts["existing"] += 1
                    continue
                if not dry_run:
                    SourceContactCard.objects.create(
                        source=source,
                        status=SourceContactCard.Status.READY_FOR_REVIEW,
                        publisher_name=source.name,
                        requested_scope=[instruction.allowed_scope],
                        requested_channels=[instruction.channel],
                        technical_findings={
                            "disposition": "contact",
                            "card_version": instruction.version,
                            "endpoint": instruction.endpoint,
                            "evidence_url": row["evidence_url"],
                            "follow_up_rule": "Telefon lub ponowne przypomnienie 3 dni po ręcznej wysyłce.",
                        },
                        reason_for_contact=reason,
                    )
                counts["created"] += 1

            if dry_run:
                transaction.set_rollback(True)

        report = options.get("report")
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# Rejestr decyzji źródłowych",
                "",
                f"Wygenerowano: {now.isoformat()}",
                "",
                "Ten raport nie wysyła wiadomości i nie zmienia zgód. Termin kontaktu telefonicznego: 3 dni po ręcznej wysyłce.",
                "",
                "| Źródło | Decyzja | Kanał / zakres | Dowód | Powód |",
                "| --- | --- | --- | --- | --- |",
            ]
            for row in rows:
                card = row["instruction"]
                evidence_url = row["evidence_url"] or "—"
                lines.append(
                    f"| {row['source'].name} | {row['disposition']} | {card.channel} / {card.allowed_scope} | {evidence_url} | {row['reason']} |"
                )
            report.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(
            "contact={contact} retry_adapter={retry_adapter} excluded={excluded} "
            "cards_created={created} cards_existing={existing}".format(**counts)
        ))
