"""Create the two narrow cards required by a reviewed gov.pl justice listing.

This command deliberately does no network discovery.  A human or research
review supplies the exact official listing URL first; ``--apply`` then records
that review as versioned, auditable cards and activates only that source.
"""
from datetime import timedelta
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


TERMS_URL = "https://www.gov.pl/web/gov/warunki-korzystania"
ROBOTS_URL = "https://www.gov.pl/robots.txt"


def validate_listing(source, listing_url):
    base = urlsplit(source.url or "")
    listing = urlsplit(listing_url)
    base_path = base.path.rstrip("/")
    if (base.scheme != "https" or base.hostname != "www.gov.pl"
            or listing.scheme != "https" or listing.hostname != "www.gov.pl"
            or listing.query or listing.fragment
            or not listing.path.startswith(base_path + "/")):
        raise CommandError("Adres listy musi być adresem HTTPS we własnej sekcji gov.pl danego źródła.")
    return base_path


def validate_base_url(base_url):
    base = urlsplit(base_url)
    if (base.scheme != "https" or base.hostname != "www.gov.pl" or base.query
            or base.fragment or not base.path.startswith("/web/") or base.path.count("/") != 2):
        raise CommandError("Adres bazowy musi być dokładną sekcją HTTPS gov.pl, np. https://www.gov.pl/web/po-miasto.")
    return base_url.rstrip("/")


def configure(source, listing_url, reviewer, valid_days=365, terms_url=None, license_note=None):
    base_path = validate_listing(source, listing_url)
    now = timezone.now()
    evidence = {
        "purpose": "official gov.pl metadata listing",
        "listing_url": listing_url,
        "reviewed_url": listing_url,
        "license": license_note or "Stopka gov.pl deklaruje CC BY-SA 4.0 dla treści tekstowych; karta nie obejmuje materiałów audiowizualnych.",
    }
    latest = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
    next_version = (latest.version if latest else 0) + 1
    common = {
        "status": SourceAccessInstruction.Status.APPROVED,
        "terms_url": terms_url or TERMS_URL,
        "evidence": evidence,
        "minimum_interval_seconds": 3,
        "daily_request_cap": 24,
        "reviewed_at": now,
        "reviewed_by": reviewer,
        "valid_until": now + timedelta(days=valid_days),
    }
    html = SourceAccessInstruction.objects.create(
        source=source, version=next_version,
        channel=SourceAccessInstruction.Channel.HTML,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=f"https://www.gov.pl{base_path}/",
        allowed_path_patterns=[], **common)
    robots = SourceAccessInstruction.objects.create(
        source=source, version=next_version + 1,
        channel=SourceAccessInstruction.Channel.SITEMAP,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=ROBOTS_URL, allowed_path_patterns=["/robots.txt"], **common)
    source.is_active = True
    source.scrape_enabled = True
    source.catalog_stage = "configured"
    source.save(update_fields=["url", "is_active", "scrape_enabled", "catalog_stage"])
    return html, robots


class Command(BaseCommand):
    help = "Zapisuje wersjonowane karty dla uprzednio zweryfikowanej listy aktualności gov.pl."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument("--listing-url", required=True)
        parser.add_argument("--base-url", help="Zweryfikowany adres własnej sekcji gov.pl dla dotychczasowego kandydata.")
        parser.add_argument("--reviewer", default="spin.admin")
        parser.add_argument("--valid-days", type=int, default=365)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not 1 <= options["valid_days"] <= 730:
            raise CommandError("valid-days musi być w zakresie 1..730")
        source = Source.objects.filter(pk=options["source_id"]).first()
        if source is None:
            raise CommandError("Nie znaleziono źródła.")
        if options["base_url"]:
            if source.is_active or source.scrape_enabled or source.catalog_stage != "candidate":
                raise CommandError("Adres bazowy można ustawić wyłącznie dla nieaktywnego kandydata.")
            source.url = validate_base_url(options["base_url"])
        validate_listing(source, options["listing_url"])
        if not options["apply"]:
            self.stdout.write("PLAN: zweryfikowano adres; bez --apply nie zmieniam kart ani źródła.")
            return
        html, robots = configure(source, options["listing_url"], options["reviewer"], options["valid_days"])
        self.stdout.write(self.style.SUCCESS(
            f"GOTOWE: źródło={source.pk}; karta HTML v{html.version}, robots v{robots.version}."))
