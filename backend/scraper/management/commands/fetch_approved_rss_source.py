"""Fetch exactly one approved RSS source through the normal audited worker path."""

from django.core.management.base import BaseCommand, CommandError

from news.models import Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.rss_scraper import scrape_rss_source


class Command(BaseCommand):
    help = "Pobiera jeden zatwierdzony RSS; bez --apply tylko sprawdza gotowość."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        source = Source.objects.filter(pk=options["source_id"]).first()
        if source is None:
            raise CommandError("Nie znaleziono źródła.")
        if not source.is_active or not source.scrape_enabled or not source.rss_url:
            raise CommandError("Źródło nie jest operacyjnie aktywne albo nie ma RSS.")
        card = approved_instruction(source, SourceAccessInstruction.Channel.RSS, source.rss_url)
        if card is None:
            raise CommandError("Brak zatwierdzonej karty RSS dla dokładnego adresu feedu.")
        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                f"GOTOWY: {source.name}; karta v{card.version}, limit {card.daily_request_cap}/dzień."))
            return
        total = scrape_rss_source(source.pk)
        self.stdout.write(self.style.SUCCESS(f"ZAKOŃCZONO: {source.name}; nowe boxy: {total}."))
