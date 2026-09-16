"""Create the non-fetching catalogue for justice-system sources.

These rows deliberately have no access card and cannot run a harvester.  They
are a work queue for verifying a specific publication endpoint, its terms and
the right channel for each institution.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceType


REGIONAL_PROSECUTORS = (
    ("Prokuratura Regionalna w Białymstoku", "https://www.gov.pl/web/pr-bialystok"),
    ("Prokuratura Regionalna w Gdańsku", "https://www.gov.pl/web/pr-gdansk"),
    ("Prokuratura Regionalna w Katowicach", "https://www.gov.pl/web/pr-katowice"),
    ("Prokuratura Regionalna w Krakowie", "https://www.gov.pl/web/pr-krakow"),
    ("Prokuratura Regionalna w Lublinie", "https://www.gov.pl/web/pr-lublin"),
    ("Prokuratura Regionalna w Łodzi", "https://www.gov.pl/web/pr-lodz"),
    ("Prokuratura Regionalna w Poznaniu", "https://www.gov.pl/web/pr-poznan"),
    ("Prokuratura Regionalna w Rzeszowie", "https://www.gov.pl/web/pr-rzeszow"),
    ("Prokuratura Regionalna w Szczecinie", "https://www.gov.pl/web/pr-szczecin"),
    ("Prokuratura Regionalna w Warszawie", "https://www.gov.pl/web/pr-warszawa"),
    ("Prokuratura Regionalna we Wrocławiu", "https://www.gov.pl/web/pr-wroclaw"),
)

DISTRICT_PROSECUTORS = (
    "Prokuratura Okręgowa w Białymstoku", "Prokuratura Okręgowa w Łomży",
    "Prokuratura Okręgowa w Olsztynie", "Prokuratura Okręgowa w Ostrołęce",
    "Prokuratura Okręgowa w Suwałkach", "Prokuratura Okręgowa w Bydgoszczy",
    "Prokuratura Okręgowa w Elblągu", "Prokuratura Okręgowa w Gdańsku",
    "Prokuratura Okręgowa w Słupsku", "Prokuratura Okręgowa w Toruniu",
    "Prokuratura Okręgowa we Włocławku", "Prokuratura Okręgowa w Bielsku-Białej",
    "Prokuratura Okręgowa w Częstochowie", "Prokuratura Okręgowa w Gliwicach",
    "Prokuratura Okręgowa w Katowicach", "Prokuratura Okręgowa w Sosnowcu",
    "Prokuratura Okręgowa w Kielcach", "Prokuratura Okręgowa w Krakowie",
    "Prokuratura Okręgowa w Tarnowie", "Prokuratura Okręgowa w Lublinie",
    "Prokuratura Okręgowa w Radomiu", "Prokuratura Okręgowa w Siedlcach",
    "Prokuratura Okręgowa w Zamościu", "Prokuratura Okręgowa w Łodzi",
    "Prokuratura Okręgowa w Ostrowie Wielkopolskim", "Prokuratura Okręgowa w Piotrkowie Trybunalskim",
    "Prokuratura Okręgowa w Płocku", "Prokuratura Okręgowa w Sieradzu",
    "Prokuratura Okręgowa w Koninie", "Prokuratura Okręgowa w Poznaniu",
    "Prokuratura Okręgowa w Zielonej Górze", "Prokuratura Okręgowa w Krośnie",
    "Prokuratura Okręgowa w Rzeszowie", "Prokuratura Okręgowa w Tarnobrzegu",
    "Prokuratura Okręgowa w Koszalinie", "Prokuratura Okręgowa w Szczecinie",
    "Prokuratura Okręgowa w Warszawie", "Prokuratura Okręgowa w Jeleniej Górze",
    "Prokuratura Okręgowa w Legnicy", "Prokuratura Okręgowa w Opolu",
    "Prokuratura Okręgowa we Wrocławiu",
)

NATIONAL_JUSTICE = (
    ("Prokuratura Krajowa", "https://www.gov.pl/web/prokuratura-krajowa/aktualnosci"),
    ("Sąd Najwyższy", "https://www.sn.pl/"),
    ("Naczelny Sąd Administracyjny", "https://www.nsa.gov.pl/"),
    ("Trybunał Konstytucyjny", "https://trybunal.gov.pl/"),
    ("Krajowa Rada Sądownictwa", "https://krs.pl/"),
)


class Command(BaseCommand):
    help = "Dodaje nieaktywne kandydatury prokuratur i instytucji wymiaru sprawiedliwości."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Zapisuje kandydatury; bez flagi tylko pokazuje plan.")
        parser.add_argument("--approve-gov-text", action="store_true",
            help="Dodaje karty HTML/content dla stron gov.pl objętych CC BY-SA 4.0; nie włącza pobierania.")

    def handle(self, *args, **options):
        candidates = list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS)
        candidates.extend((name, None) for name in DISTRICT_PROSECUTORS)
        created = existing = 0
        for name, url in candidates:
            item = Source.objects.filter(name=name).first()
            if item:
                existing += 1
                continue
            if options["apply"]:
                item = Source(
                    name=name, url=url, source_type=SourceType.INSTITUTION,
                    is_active=False, scrape_enabled=False, catalog_stage="candidate",
                    scrape_frequency_minutes=240,
                    catalog_notes=(
                        "Kandydat wymiaru sprawiedliwości. Przed aktywacją ustal konkretny kanał "
                        "(RSS/API/sitemap/HTML), warunki ponownego wykorzystywania i kartę dostępu."
                    ),
                )
                item.full_clean()
                item.save()
            created += 1
        action = "ZAPISANO" if options["apply"] else "PLAN"
        self.stdout.write(f"{action}: nowych={created}, już w katalogu={existing}, razem={len(candidates)}.")
        self.stdout.write("Żadna kandydatura nie ma aktywnej karty dostępu i żadna nie uruchamia pobierania.")
        if options["approve_gov_text"] and not options["apply"]:
            raise ValueError("--approve-gov-text wymaga --apply.")
        if not options["approve_gov_text"]:
            return
        now = timezone.now()
        terms_url = "https://www.gov.pl/web/gov/warunki-korzystania"
        reviewed = 0
        for name, base_url in list(NATIONAL_JUSTICE[:1]) + list(REGIONAL_PROSECUTORS):
            source = Source.objects.get(name=name)
            # A regional card starts from its exact published news listing.  It
            # only permits its own section, and does not cover images or any
            # other gov.pl service.
            endpoint = base_url if name == "Prokuratura Krajowa" else base_url.rstrip("/") + "/aktualnosci"
            existing_card = SourceAccessInstruction.objects.filter(source=source).order_by("-version").first()
            if existing_card:
                continue
            path = "/".join(endpoint.split("/", 3)[3:])
            card = SourceAccessInstruction(
                source=source, version=1, status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.HTML,
                allowed_scope=SourceAccessInstruction.Scope.CONTENT,
                endpoint=endpoint, allowed_path_patterns=["/" + path.split("/")[0] + "/" + path.split("/")[1] + "/"],
                terms_url=terms_url,
                evidence={
                    "terms_url": terms_url,
                    "basis": "Stopka oficjalnych stron gov.pl określa dla treści tekstowych licencję CC BY-SA 4.0; karta nie obejmuje materiałów audiowizualnych.",
                    "review_method": "official-gov-pl-footer-and-terms",
                    "reviewed_on": now.date().isoformat(),
                },
                minimum_interval_seconds=3, daily_request_cap=24,
                reviewed_at=now, reviewed_by="spin.admin",
                valid_until=now + timedelta(days=365),
            )
            card.full_clean()
            card.save()
            reviewed += 1
        self.stdout.write(self.style.SUCCESS(
            f"KARTY GOV.PL: zapisano={reviewed}; źródła pozostają nieaktywne do czasu adaptera."))
