"""Register the reviewed, metadata-only official MSWiA listing."""

from django.core.management.base import BaseCommand

from news.models import Source, SourceAccessInstruction
from scraper.management.commands.configure_gov_justice_source import configure
from scraper.mswia_listing import SOURCE_URL


LISTING_URL = SOURCE_URL + "/aktualnosci"


def configure_mswia(reviewer):
    source, _ = Source.objects.get_or_create(
        url=SOURCE_URL,
        defaults={"name": "Ministerstwo Spraw Wewnętrznych i Administracji",
                  "source_type": "institution", "is_active": False,
                  "scrape_enabled": False, "catalog_stage": "candidate"},
    )
    existing = list(SourceAccessInstruction.objects.filter(
        source=source, status=SourceAccessInstruction.Status.APPROVED,
        evidence__listing_url=LISTING_URL,
    ).order_by("version"))
    if existing:
        return source, existing
    cards = configure(source, LISTING_URL, reviewer, valid_days=180)
    return source, list(cards)


class Command(BaseCommand):
    help = "Konfiguruje MSWiA jako oficjalne źródło metadanych aktualności gov.pl."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", default="redakcja spin.clinic")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not options["apply"]:
            self.stdout.write("PLAN: MSWiA; metadane aktualności i linki, maks. 24 żądania/dobę. Bez --apply nie zmieniam bazy.")
            return
        source, cards = configure_mswia(options["reviewed_by"])
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: {source.pk} {source.name}; karty: " + ", ".join(str(card.version) for card in cards) + "."))
