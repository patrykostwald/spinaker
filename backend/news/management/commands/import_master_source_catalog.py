"""Import the master source list as fail-closed candidates.

``sources.md`` is planning input, not authority to harvest.  Every imported
row remains inactive until a reviewed access instruction and adapter exist.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.models import Source, SourceType
from news.source_catalog import public_catalog_url


TYPE_MAP = {
    "official": SourceType.INSTITUTION,
    "bip": SourceType.INSTITUTION,
    "courts": SourceType.INSTITUTION,
    "registry": SourceType.INSTITUTION,
    "media": SourceType.PORTAL,
}


class Command(BaseCommand):
    help = "Wczytuje sources.md jako nieaktywne kandydatury; nie uruchamia harvestingu."

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument("--catalog", default=str(root / "sources.md"))
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            with Path(options["catalog"]).open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            raise CommandError(f"Nie odczytano katalogu: {exc}") from exc
        required = {"name", "base_url", "source_type", "tier", "crawl_mode", "rate_limit_per_min", "content_policy", "evidence_mode", "enabled"}
        if not rows or not required.issubset(rows[0]):
            raise CommandError("Katalog ma nieprawidłowy nagłówek.")
        prepared = []
        for row in rows:
            url = public_catalog_url(row["base_url"].strip(), resolve=False)
            prepared.append((row, url))
        if not options["apply"]:
            self.stdout.write(f"PLAN: {len(prepared)} kandydatur; bez --apply nie zmieniam bazy.")
            return
        created = linked = 0
        with transaction.atomic():
            by_url = {source.url: source for source in Source.objects.select_for_update().exclude(url__isnull=True)}
            for row, url in prepared:
                note = ("[Katalog główny — kandydatura, nie zgoda]\n"
                        f"typ: {row['source_type']}\ntier: {row['tier']}\n"
                        f"planowany kanał: {row['crawl_mode']}\n"
                        f"planowana polityka treści: {row['content_policy']}\n"
                        f"tryb dowodu: {row['evidence_mode']}\n"
                        "Wymaga osobnej weryfikacji warunków, kanału i karty dostępu.")
                source = by_url.get(url)
                if source is None:
                    source = Source.objects.create(name=row["name"].strip(), url=url,
                        source_type=TYPE_MAP.get(row["source_type"], SourceType.PORTAL),
                        is_active=False, scrape_enabled=False, catalog_stage="candidate",
                        scrape_frequency_minutes=60, catalog_notes=note)
                    by_url[url] = source
                    created += 1
                else:
                    linked += 1
                    if note not in source.catalog_notes:
                        source.catalog_notes = (source.catalog_notes.rstrip() + "\n\n" + note).strip()
                        source.save(update_fields=["catalog_notes"])
        self.stdout.write(self.style.SUCCESS(
            f"KATALOG: pozycji={len(prepared)} nowych_kandydatów={created} powiązanych={linked} aktywacje=0."))
