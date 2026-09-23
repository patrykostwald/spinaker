"""Configure the official NIK RSS as a bounded metadata source."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceType

SOURCE_URL = "https://www.nik.gov.pl/rss/"
TERMS_URL = "https://www.nik.gov.pl/zasady/prawa-autorskie.html"


def configure(reviewer, *, valid_days=365, daily_cap=24):
    """Create or reuse the narrow NIK RSS metadata card."""
    with transaction.atomic():
        source, _ = Source.objects.select_for_update().get_or_create(
            url=SOURCE_URL,
            defaults={"name": "Najwy\u017csza Izba Kontroli", "rss_url": SOURCE_URL,
                      "source_type": SourceType.INSTITUTION, "is_active": False,
                      "scrape_enabled": False, "catalog_stage": "candidate",
                      "scrape_frequency_minutes": 60},
        )
        latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
        if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
            raise ValueError("latest_instruction_suspended")
        now = timezone.now()
        card = SourceAccessInstruction.objects.filter(
            source=source, status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.RSS,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=SOURCE_URL, terms_url=TERMS_URL, valid_until__gt=now,
        ).order_by("-version").first()
        if card is None:
            card = SourceAccessInstruction.objects.create(
                source=source, version=(latest.version if latest else 0) + 1,
                status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.RSS,
                allowed_scope=SourceAccessInstruction.Scope.METADATA,
                endpoint=SOURCE_URL, allowed_path_patterns=["/rss"], terms_url=TERMS_URL,
                evidence={"rss_url": SOURCE_URL, "terms_url": TERMS_URL,
                          "purpose": "Official NIK RSS headlines, URLs, publication dates and feed summaries only.",
                          "excluded": ["article HTML", "archive traversal", "images", "video", "full-text snapshots"],
                          "attribution": "Najwy\u017csza Izba Kontroli (nik.gov.pl), direct URL and acquisition time retained."},
                minimum_interval_seconds=3, daily_request_cap=daily_cap,
                reviewed_at=now, reviewed_by=reviewer, valid_until=now + timedelta(days=valid_days),
            )
        source.name = "Najwy\u017csza Izba Kontroli"
        source.rss_url = SOURCE_URL
        source.source_type = SourceType.INSTITUTION
        source.scrape_frequency_minutes = 60
        source.is_active = source.scrape_enabled = True
        source.catalog_stage = "configured"
        source.full_clean()
        source.save()
    return source, card


class Command(BaseCommand):
    help = "Enable official NIK RSS: metadata and links without archive or full text."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", required=True)
        parser.add_argument("--valid-days", type=int, default=365)
        parser.add_argument("--daily-cap", type=int, default=24)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not 1 <= options["valid_days"] <= 730 or not 1 <= options["daily_cap"] <= 1000:
            raise CommandError("valid-days must be 1..730 and daily-cap must be 1..1000.")
        if not options["apply"]:
            self.stdout.write("PLAN: NIK RSS metadata and links only; --apply is required to change the card.")
            return
        try:
            source, card = configure(options["reviewed_by"], valid_days=options["valid_days"], daily_cap=options["daily_cap"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"NIK: source={source.pk}; RSS card v{card.version}."))
