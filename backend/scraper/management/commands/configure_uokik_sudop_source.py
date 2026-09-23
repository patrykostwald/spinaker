"""Configure the reviewed UOKiK SUDOP API as a metadata-only pilot."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceType
from scraper.uokik_sudop import API


TERMS_URL = "https://uokik.gov.pl/sudop"
ENDPOINT = API + "/api"


def configure(reviewer, *, valid_days=180, daily_cap=120):
    with transaction.atomic():
        source, _ = Source.objects.select_for_update().get_or_create(
            url=API,
            defaults={
                "name": "UOKiK — System Udostępniania Danych o Pomocy Publicznej",
                "source_type": SourceType.INSTITUTION,
                "is_active": False,
                "scrape_enabled": False,
                "catalog_stage": "candidate",
                "scrape_frequency_minutes": 60,
            },
        )
        latest = source.access_instructions.order_by("-version").first()
        if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
            raise ValueError("latest_instruction_suspended")
        now = timezone.now()
        card = SourceAccessInstruction.objects.filter(
            source=source,
            status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.API,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=ENDPOINT,
            terms_url=TERMS_URL,
            valid_until__gt=now,
        ).order_by("-version").first()
        if card is None:
            card = SourceAccessInstruction.objects.create(
                source=source,
                version=(latest.version if latest else 0) + 1,
                status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.API,
                allowed_scope=SourceAccessInstruction.Scope.METADATA,
                endpoint=ENDPOINT,
                allowed_path_patterns=["/sudop-api/api"],
                terms_url=TERMS_URL,
                evidence={
                    "documentation_url": "https://api-sudop.uokik.gov.pl:9443/devportal/apis",
                    "scope": "Dated aid-event metadata from the official API only; no article pages, media, or full-text snapshots.",
                    "rate_policy": "At most one request every 4 seconds; honor queued responses and Retry-After.",
                    "attribution": "Retain direct source URL, acquisition date, change notice, provider-responsibility notice and auxiliary-status notice.",
                    "excluded": ["article HTML", "images", "video", "full-text snapshots", "training"],
                },
                minimum_interval_seconds=4,
                daily_request_cap=daily_cap,
                reviewed_at=now,
                reviewed_by=reviewer,
                valid_until=now + timedelta(days=valid_days),
            )
        source.name = "UOKiK — System Udostępniania Danych o Pomocy Publicznej"
        source.source_type = SourceType.INSTITUTION
        source.scrape_frequency_minutes = 60
        source.is_active = source.scrape_enabled = True
        source.catalog_stage = "configured"
        source.full_clean()
        source.save()
    return source, card


class Command(BaseCommand):
    help = "Konfiguruje ograniczony pilot API SUDOP UOKiK; pobieranie pozostaje wyłączone bez osobnej flagi środowiskowej."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", required=True)
        parser.add_argument("--valid-days", type=int, default=180)
        parser.add_argument("--daily-cap", type=int, default=120)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not 1 <= options["valid_days"] <= 730 or not 1 <= options["daily_cap"] <= 1000:
            raise CommandError("valid-days musi być 1..730, a daily-cap 1..1000.")
        if not options["apply"]:
            self.stdout.write("PLAN: SUDOP API, zdarzenia z datą i wymaganym opisem źródła; bez --apply nie zmieniam karty.")
            return
        try:
            source, card = configure(
                options["reviewed_by"], valid_days=options["valid_days"], daily_cap=options["daily_cap"]
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: {source.pk} {source.name}; API karta v{card.version}. Pilot nadal wymaga UOKIK_SUDOP_PILOT_ENABLED=true."
        ))
