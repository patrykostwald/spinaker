"""Create narrow, reviewed metadata-only cards for two documented APIs."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.structured_metadata import SPECS


SOURCES = {
    "dane_gov": {
        "terms_url": "https://dane.gov.pl/doc",
        "documentation_url": "https://api.dane.gov.pl/doc",
        "basis": "Official API documentation; preflight is limited to one dataset-list metadata response, without resources or files.",
    },
    "gus_bdl": {
        "terms_url": "https://api.stat.gov.pl/home/bdlapi",
        "documentation_url": "https://api.stat.gov.pl/home/bdlapi",
        "basis": "Official BDL API documentation states CC BY 4.0 and anonymous limits; preflight is limited to the top-level subjects metadata listing.",
    },
}


def configure(key, reviewer, *, valid_days=365, daily_cap=24):
    spec, evidence = SPECS[key], SOURCES[key]
    with transaction.atomic():
        source = Source.objects.select_for_update().get(url=spec["source_url"])
        latest = source.access_instructions.order_by("-version").first()
        if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
            raise ValueError("latest_instruction_suspended")
        now = timezone.now()
        card = SourceAccessInstruction.objects.create(
            source=source, version=(latest.version if latest else 0) + 1,
            status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.API,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=spec["endpoint"].split("?", 1)[0],
            allowed_path_patterns=["/1.4/datasets"] if key == "dane_gov" else ["/api/v1/subjects"],
            terms_url=evidence["terms_url"],
            evidence={
                "documentation_url": evidence["documentation_url"],
                "basis": evidence["basis"],
                "excluded": ["dataset resources", "files", "payload content", "other API endpoints"],
                "attribution": "Source, acquisition time, and licence evidence retained.",
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
    help = "Konfiguruje wąskie API metadanych dane.gov.pl albo BDL GUS; bez importu danych."

    def add_arguments(self, parser):
        parser.add_argument("key", choices=sorted(SOURCES))
        parser.add_argument("--reviewed-by", required=True)
        parser.add_argument("--valid-days", type=int, default=365)
        parser.add_argument("--daily-cap", type=int, default=24)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not 1 <= options["valid_days"] <= 730 or not 1 <= options["daily_cap"] <= 1000:
            raise CommandError("valid-days musi być 1..730, a daily-cap 1..1000.")
        if not options["apply"]:
            self.stdout.write("PLAN: pojedynczy endpoint API, wyłącznie metadane; bez --apply nie zmieniam karty.")
            return
        try:
            card = configure(options["key"], options["reviewed_by"], valid_days=options["valid_days"], daily_cap=options["daily_cap"])
        except Source.DoesNotExist as exc:
            raise CommandError("Brak kandydata w katalogu.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"ZAPISANO: karta API v{card.version}, wyłącznie metadane."))
