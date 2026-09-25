"""Mark catalog candidates outside the portal's topical profile as excluded.

spin.clinic serves readers who follow politics and public affairs.  Candidates
such as cooking, gossip, sport, motoring or consumer-tech sites are not
contacted for consent and are hidden from the public catalog.  The decision is
curated by hand (by address, below), never inferred, and is reversible:
``--restore`` returns every source carrying the marker to ``candidate``.

Only inactive, not-yet-configured sources are touched; an active or configured
source is reported and left alone.  Without ``--apply`` the command only plans.
"""
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import Source

MARKER = "[Poza profilem tematycznym"

OFF_PROFILE = {
    "kulinaria": ("beszamel.se.pl", "smaker.pl"),
    "lifestyle i plotki": ("pudelek.pl", "pomponik.pl", "viva.pl", "party.pl", "claudia.pl", "kobieta.pl",
                           "kafeteria.pl", "avanti24.pl", "shownews.pl", "well.pl", "deccoria.pl", "urzadzamy.pl"),
    "poradniki zdrowotne": ("medonet.pl", "poradnikzdrowie.pl", "mp.pl", "infodent24.pl"),
    "radio muzyczne": ("eska.pl", "antyradio.pl", "chillizet.pl", "meloradio.pl", "voxfm.pl", "zloteprzeboje.pl",
                       "rmf.fm", "rmfclassic.pl", "rmfmaxxx.pl", "vibefm.pl", "newonce.radio", "radiowawa.pl", "tuba.pl"),
    "sport": ("90minut.pl", "eurosport.pl", "gol24.pl", "interia.pl/sport", "meczyki.pl", "pilkanozna.pl",
              "przegladsportowy.pl", "przegladsportowy.onet.pl", "sportowefakty.wp.pl", "sport.pl", "weszlo.com"),
    "motoryzacja": ("autobild.pl", "autocentrum.pl", "autofakty.pl", "autokult.pl", "auto-motor-i-sport.pl",
                    "autoswiat.pl", "motofakty.pl", "moto.onet.pl", "moto.pl", "elektrowoz.pl"),
    "technologie konsumenckie i gry": ("android.com.pl", "antyweb.pl", "benchmark.pl", "chip.pl", "dobreprogramy.pl",
                                       "geekweek.interia.pl", "gra.pl", "instalki.pl", "ithardware.pl", "komorkomania.pl",
                                       "komputerswiat.pl", "pclab.pl", "polygamia.pl", "purepc.pl", "smartfon.pl",
                                       "spidersweb.pl", "tabletowo.pl", "telepolis.pl"),
    "rozrywka telewizyjna": ("ipla.tv", "player.pl", "polsat.pl", "tvpuls.pl", "telemagazyn.pl", "ttv.pl"),
    "film, teatr, sztuka": ("filmweb.pl", "film.org.pl", "kino.org.pl", "ekrany.pl", "didaskalia.pl", "teatr-pismo.pl",
                            "szum.pl", "artpapier.com", "klubksiazki.pl"),
    "nieruchomości i handel": ("nieruchomosci-online.pl", "rynekpierwotny.pl", "muratorplus.pl", "architektura.muratorplus.pl",
                               "obiektykomercyjne.muratorplus.pl", "propertynews.pl", "handelextra.pl", "dlahandlu.pl",
                               "portalspozywczy.pl", "retailnet.pl", "wiadomoscihandlowe.pl"),
    "finanse detaliczne": ("comparic.pl",),
    "praktyki religijne": ("liturgia.pl",),
}


def address_key(url):
    """`https://www.Example.pl/Sport/` -> `example.pl/sport` (host without www + path)."""
    parts = urlsplit(url if "://" in url else f"https://{url}")
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"


def category_for(url):
    key = address_key(url)
    for category, addresses in OFF_PROFILE.items():
        for address in addresses:
            if key == address or key.startswith(address + "/"):
                return category
    return None


class Command(BaseCommand):
    help = "Wyklucza z katalogu kandydatury spoza profilu tematycznego (ręczna lista adresów, odwracalne)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Zapisz zmiany (domyślnie tylko plan).")
        parser.add_argument("--restore", action="store_true", help="Przywróć do kandydatów źródła z tym znacznikiem.")

    def handle(self, *args, **options):
        if options["restore"]:
            return self._restore(options["apply"])
        planned, skipped = [], []
        for source in Source.objects.exclude(catalog_stage="excluded").order_by("name", "pk"):
            category = category_for(source.url or "")
            if not category:
                continue
            if source.is_active or source.scrape_enabled or source.catalog_stage == "configured":
                skipped.append((source, category))
            else:
                planned.append((source, category))
        for source, category in planned:
            self.stdout.write(f"WYKLUCZ  {source.pk:5}  {category:32}  {source.name}  <{source.url}>")
        for source, category in skipped:
            self.stdout.write(f"POMIŃ    {source.pk:5}  {category:32}  {source.name} — aktywne lub skonfigurowane, decyzja ręczna")
        if not options["apply"]:
            self.stdout.write(f"PLAN: do wykluczenia={len(planned)} pominiętych={len(skipped)}; bez --apply nie zmieniam bazy.")
            return
        stamp = timezone.localdate().isoformat()
        with transaction.atomic():
            for source, category in planned:
                note = f"{MARKER}: {category} — wykluczone {stamp}; cofnięcie: exclude_off_profile_sources --restore --apply]"
                source.catalog_stage = "excluded"
                source.catalog_notes = (source.catalog_notes.rstrip() + "\n\n" + note).strip()
                source.save(update_fields=["catalog_stage", "catalog_notes", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"WYKLUCZONO: {len(planned)}; pominięto: {len(skipped)}."))

    def _restore(self, apply):
        rows = list(Source.objects.filter(catalog_stage="excluded", catalog_notes__contains=MARKER).order_by("pk"))
        for source in rows:
            self.stdout.write(f"PRZYWRÓĆ {source.pk:5}  {source.name}")
        if not apply:
            self.stdout.write(f"PLAN: do przywrócenia={len(rows)}; bez --apply nie zmieniam bazy.")
            return
        with transaction.atomic():
            for source in rows:
                source.catalog_stage = "candidate"
                source.save(update_fields=["catalog_stage", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"PRZYWRÓCONO: {len(rows)}."))
