"""Configure one whitelisted, reviewed gov.pl metadata listing."""

from django.core.management.base import BaseCommand

from news.models import Source, SourceAccessInstruction
from scraper.gov_metadata_listing import OFFICIAL_GOV_LISTINGS
from scraper.management.commands.configure_gov_justice_source import configure


class Command(BaseCommand):
    help = "Konfiguruje wyłącznie wskazane w kodzie źródło gov.pl jako źródło metadanych."

    def add_arguments(self, parser):
        parser.add_argument("--source-key", choices=sorted(OFFICIAL_GOV_LISTINGS), required=True)
        parser.add_argument("--reviewed-by", default="redakcja spin.clinic")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        item = OFFICIAL_GOV_LISTINGS[options["source_key"]]
        if not options["apply"]:
            self.stdout.write(f"PLAN: {item['name']}; metadane aktualności i linki, maks. 24 żądania/dobę. Bez --apply nie zmieniam bazy.")
            return
        source, _ = Source.objects.get_or_create(
            url=item["source_url"],
            defaults={"name": item["name"], "source_type": "institution",
                      "is_active": False, "scrape_enabled": False, "catalog_stage": "candidate"},
        )
        cards = list(SourceAccessInstruction.objects.filter(
            source=source, status=SourceAccessInstruction.Status.APPROVED,
            evidence__listing_url=item["listing_url"],
        ).order_by("version"))
        if not cards:
            cards = list(configure(source, item["listing_url"], options["reviewed_by"], valid_days=180,
                                   terms_url=item.get("terms_url")))
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: {source.pk} {source.name}; karty: " + ", ".join(str(card.version) for card in cards) + "."))
