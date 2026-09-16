"""Activate only the documented incremental ELI metadata endpoint."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


SOURCE_URL = "https://api.sejm.gov.pl/eli"
ENDPOINT = "https://api.sejm.gov.pl/eli/changes/acts"
DOCS_URL = "https://api.sejm.gov.pl/eli_pl.html"
TERMS_URL = "https://www.sejm.gov.pl/Sejm10.nsf/page.xsp/dane_publiczne"


def configure(reviewer, *, valid_days=365, daily_cap=24):
    with transaction.atomic():
        source = Source.objects.select_for_update().get(url=SOURCE_URL)
        latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
        if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
            raise ValueError("latest_instruction_suspended")
        now = timezone.now()
        card = SourceAccessInstruction.objects.create(
            source=source, version=(latest.version if latest else 0) + 1,
            status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.API,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=ENDPOINT, allowed_path_patterns=["/eli/changes/acts"],
            terms_url=TERMS_URL,
            evidence={
                "documentation_url": DOCS_URL,
                "terms_url": TERMS_URL,
                "purpose": "Incremental metadata for DU and MP acts only.",
                "excluded": ["/eli/*/text.pdf", "/eli/*/text.html", "other API paths"],
                "attribution": "Kancelaria Sejmu: source and acquisition time retained.",
            },
            minimum_interval_seconds=3, daily_request_cap=daily_cap,
            reviewed_at=now, reviewed_by=reviewer, valid_until=now + timedelta(days=valid_days),
        )
        source.is_active = True
        source.scrape_enabled = True
        source.catalog_stage = "configured"
        source.save(update_fields=["is_active", "scrape_enabled", "catalog_stage"])
    return card


class Command(BaseCommand):
    help = "Konfiguruje wąskie, przyrostowe API ELI bez pobierania plików aktów."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", required=True)
        parser.add_argument("--valid-days", type=int, default=365)
        parser.add_argument("--daily-cap", type=int, default=24)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not 1 <= options["valid_days"] <= 730 or not 1 <= options["daily_cap"] <= 1000:
            raise CommandError("valid-days musi być 1..730, a daily-cap 1..1000.")
        if not options["apply"]:
            self.stdout.write("PLAN: ELI changes/acts, wyłącznie metadane; bez --apply nie zmieniam karty.")
            return
        try:
            card = configure(options["reviewed_by"], valid_days=options["valid_days"],
                             daily_cap=options["daily_cap"])
        except Source.DoesNotExist as exc:
            raise CommandError("Brak kandydata ELI w katalogu.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"ZAPISANO: ELI karta API v{card.version}."))
