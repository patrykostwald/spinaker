"""Run one audited, bounded current-contract check for a structured API."""
from django.core.management.base import BaseCommand

from scraper.structured_metadata import preflight


class Command(BaseCommand):
    help = "Jednorazowo sprawdza zatwierdzony endpoint metadanych; nie importuje danych."

    def add_arguments(self, parser):
        parser.add_argument("key", choices=["dane_gov", "gus_bdl"])

    def handle(self, *args, **options):
        result = preflight(options["key"])
        self.stdout.write(self.style.SUCCESS("PREFLIGHT_OK: " + str(result)))
