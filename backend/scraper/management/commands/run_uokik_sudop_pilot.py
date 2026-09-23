from django.core.management.base import BaseCommand, CommandError

from scraper.uokik_sudop import sudop_pilot_cycle


class Command(BaseCommand):
    help = "Wykonuje najwyżej jedno żądanie ograniczonego pilota SUDOP po ustawieniu flagi środowiskowej."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not options["apply"]:
            raise CommandError("Dodaj --apply; polecenie wykonuje najwyżej jedno żądanie API.")
        self.stdout.write(str(sudop_pilot_cycle()))
