"""Prepare fail-closed RSS access cards for the configured media catalogue."""

from urllib.parse import urlsplit

from django.core.management.base import BaseCommand

from news.models import Source, SourceAccessInstruction, SourceType
from scraper.catalog import RSS_SOURCES


class Command(BaseCommand):
    help = (
        "Create inactive media candidates and contact-required RSS metadata cards. "
        "It never enables a source or sends a request."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist the prepared cards.")

    def handle(self, *args, **options):
        apply = options["apply"]
        created_sources = 0
        created_cards = 0
        existing_cards = 0

        for spec in RSS_SOURCES:
            feed_url = spec["url"]
            source = Source.objects.filter(url=feed_url).first()
            if source is None:
                source_created = True
                defaults = {
                    "name": spec["name"],
                    "source_type": SourceType.RSS,
                    "rss_url": feed_url,
                    "is_active": False,
                    "scrape_enabled": False,
                    "catalog_stage": "candidate",
                    "catalog_notes": (
                        "Medium awaiting access review. Automated fetching is disabled "
                        "until an explicit source card is approved."
                    ),
                }
                if apply:
                    source = Source.objects.create(url=feed_url, **defaults)
            else:
                source_created = False
            if source_created:
                created_sources += 1

            if source is None:
                # Dry-run: the future source has no existing access cards.
                created_cards += 1
                continue

            if source.access_instructions.filter(channel=SourceAccessInstruction.Channel.RSS).exists():
                existing_cards += 1
                continue

            path = urlsplit(feed_url).path or "/"
            card = SourceAccessInstruction(
                source=source,
                version=(source.access_instructions.order_by("-version").values_list("version", flat=True).first() or 0) + 1,
                status=SourceAccessInstruction.Status.CONTACT_REQUIRED,
                channel=SourceAccessInstruction.Channel.RSS,
                allowed_scope=SourceAccessInstruction.Scope.METADATA,
                endpoint=feed_url,
                allowed_path_patterns=[path],
                minimum_interval_seconds=3,
                daily_request_cap=0,
                evidence={
                    "finding": (
                        "Public RSS endpoint found in the source catalogue. Its existence alone "
                        "does not approve automated reuse; awaiting publisher confirmation."
                    ),
                    "next_step": "Send the prepared metadata-only access request to the publisher.",
                },
            )
            if apply:
                card.full_clean()
                card.save()
            created_cards += 1

        mode = "utworzono" if apply else "do utworzenia"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: źródła={created_sources}, karty={created_cards}, istniejące_karty={existing_cards}."
        ))
