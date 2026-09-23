"""Point the existing UOKiK candidate at its official news RSS, without enabling it."""

from django.core.management.base import BaseCommand, CommandError

from news.models import Source, SourceType


LISTING_URL = "https://www.uokik.gov.pl/public/aktualnosci"
RSS_URL = "https://uokik.gov.pl/feed"


class Command(BaseCommand):
    help = "Przygotowuje nieaktywną kandydaturę UOKiK do niezależnego audytu oficjalnego RSS."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        source = Source.objects.filter(pk=options["source_id"]).first()
        if source is None:
            raise CommandError("Nie znaleziono źródła.")
        if source.is_active or source.scrape_enabled or source.catalog_stage != "candidate":
            raise CommandError("Można przygotować wyłącznie nieaktywną kandydaturę; aktywne źródło wymaga osobnej kontroli.")
        if not options["apply"]:
            self.stdout.write(f"PLAN: {source.pk} {source.name}; RSS {RSS_URL}; nadal bez aktywacji.")
            return
        source.name = "Urząd Ochrony Konkurencji i Konsumentów"
        source.url = LISTING_URL
        source.rss_url = RSS_URL
        source.source_type = SourceType.INSTITUTION
        source.full_clean()
        source.save()
        self.stdout.write(self.style.SUCCESS(
            f"PRZYGOTOWANO: {source.pk} {source.name}; audyt RSS jest wymagany przed aktywacją."))
