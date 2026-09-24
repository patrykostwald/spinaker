"""Fail closed after a verified source requires human or adapter review."""
from copy import deepcopy

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


def suspend(source_id, reason, reviewer="spin.system"):
    with transaction.atomic():
        source = Source.objects.select_for_update().get(pk=source_id)
        active_cards = list(SourceAccessInstruction.objects.select_for_update().filter(
            source=source, status=SourceAccessInstruction.Status.APPROVED).order_by("version"))
        if not active_cards:
            raise ValueError("no_approved_cards")
        version = SourceAccessInstruction.objects.filter(source=source).order_by("-version").values_list("version", flat=True).first() + 1
        for card in active_cards:
            evidence = deepcopy(card.evidence)
            evidence["suspension_reason"] = reason
            evidence["suspended_at"] = timezone.now().isoformat()
            SourceAccessInstruction.objects.create(
                source=source, version=version, status=SourceAccessInstruction.Status.SUSPENDED,
                channel=card.channel, allowed_scope=card.allowed_scope, endpoint=card.endpoint,
                allowed_path_patterns=card.allowed_path_patterns, terms_url=card.terms_url,
                evidence=evidence, minimum_interval_seconds=card.minimum_interval_seconds,
                daily_request_cap=0, reviewed_at=timezone.now(), reviewed_by=reviewer,
                valid_until=card.valid_until,
            )
            version += 1
        source.is_active = False
        source.scrape_enabled = False
        source.last_error = reason
        source.save(update_fields=["is_active", "scrape_enabled", "last_error"])
    return len(active_cards)


class Command(BaseCommand):
    help = "Wstrzymuje źródło przez nowe wersje kart, bez usuwania historii."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--reviewer", default="spin.system")

    def handle(self, *args, **options):
        try:
            count = suspend(options["source_id"], options["reason"], options["reviewer"])
        except Source.DoesNotExist as exc:
            raise CommandError("Nie znaleziono źródła.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.WARNING(f"WSTRZYMANE: źródło={options['source_id']}; kart={count}."))
