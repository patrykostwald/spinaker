"""Register the reviewed, metadata-only official Ministry of Finance listing."""

from django.core.management.base import BaseCommand

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.configure_gov_justice_source import configure
from scraper.ministry_finance_listing import SOURCE_URL


LISTING_URL = SOURCE_URL + "/wiadomosci"


class Command(BaseCommand):
    help = "Konfiguruje Ministerstwo Finansów jako oficjalne źródło metadanych wiadomości gov.pl."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", default="redakcja spin.clinic")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not options["apply"]:
            self.stdout.write("PLAN: Ministerstwo Finansów; metadane wiadomości i linki, maks. 24 żądania/dobę. Bez --apply nie zmieniam bazy.")
            return
        source, _ = Source.objects.get_or_create(
            url=SOURCE_URL,
            defaults={"name": "Ministerstwo Finansów", "source_type": "institution",
                      "is_active": False, "scrape_enabled": False, "catalog_stage": "candidate"},
        )
        cards = list(SourceAccessInstruction.objects.filter(
            source=source, status=SourceAccessInstruction.Status.APPROVED,
            evidence__listing_url=LISTING_URL,
        ).order_by("version"))
        if not cards:
            cards = list(configure(source, LISTING_URL, options["reviewed_by"], valid_days=180))
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: {source.pk} {source.name}; karty: " + ", ".join(str(card.version) for card in cards) + "."))
