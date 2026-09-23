"""Configure the reviewed Senate listing without authorising media assets."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.senat_archive import LISTING_URL, SOURCE_URL


TERMS_URL = SOURCE_URL + "/ponowne-wykorzystywanie-informacji-sektora-publicznego/"


class Command(BaseCommand):
    help = "Konfiguruje Senat jako źródło metadanych własnych aktualności, bez obrazów i materiałów PAP."

    def add_arguments(self, parser):
        parser.add_argument("--reviewed-by", default="redakcja spin.clinic")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not options["apply"]:
            self.stdout.write("PLAN: Senat; tytuł, data, opis metadanych i link własnych aktualności, maks. 24 żądania/dobę.")
            return
        # The catalogue initially carries the obsolete RSS URL. Reuse that
        # candidate rather than silently creating a second Senate source.
        source = (Source.objects.filter(url=SOURCE_URL).first()
                  or Source.objects.filter(name__iexact="Senat RP").first()
                  or Source.objects.filter(name__icontains="Senat").first())
        if source is None:
            raise CommandError("Brakuje kandydatury Senatu w katalogu; nie tworzę źródła poza katalogiem.")
        now = timezone.now()
        cards = list(SourceAccessInstruction.objects.filter(
            source=source, status=SourceAccessInstruction.Status.APPROVED,
            evidence__listing_url=LISTING_URL, valid_until__gt=now,
        ).order_by("version"))
        if not cards:
            latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
            common = {"status": SourceAccessInstruction.Status.APPROVED,
                      "allowed_scope": SourceAccessInstruction.Scope.METADATA,
                      "terms_url": TERMS_URL,
                      "evidence": {"listing_url": LISTING_URL,
                                   "scope": "Own Senate news metadata and original links only. Ignore all images and every item marked PAP.",
                                   "attribution": "Show the Senate source link and acquisition time."},
                      "minimum_interval_seconds": 3, "daily_request_cap": 24,
                      "reviewed_at": now, "reviewed_by": options["reviewed_by"],
                      "valid_until": now + timedelta(days=180)}
            version = (latest.version if latest else 0) + 1
            cards = [
                SourceAccessInstruction.objects.create(source=source, version=version,
                    channel=SourceAccessInstruction.Channel.HTML, endpoint=LISTING_URL,
                    allowed_path_patterns=[], **common),
                SourceAccessInstruction.objects.create(source=source, version=version + 1,
                    channel=SourceAccessInstruction.Channel.SITEMAP,
                    endpoint=SOURCE_URL + "/robots.txt", allowed_path_patterns=["/robots.txt"], **common),
            ]
        source.name, source.url, source.source_type = "Senat Rzeczypospolitej Polskiej", SOURCE_URL, "institution"
        source.is_active = source.scrape_enabled = True
        source.catalog_stage = "configured"
        source.full_clean()
        source.save()
        self.stdout.write(self.style.SUCCESS(f"GOTOWE: {source.pk} {source.name}; karty: {cards[0].version}, {cards[1].version}."))
