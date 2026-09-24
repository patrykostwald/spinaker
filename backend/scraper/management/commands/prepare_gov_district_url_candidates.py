"""Prepare non-authoritative gov.pl URL suggestions for district prosecutors.

The command is intentionally offline and never changes a source's active
state, access cards, or harvesting settings.  It turns a large list of names
into a review queue: a reviewer must still confirm that the suggested section
and its news listing exist before ``configure_gov_justice_source --apply``
can be used.
"""
from django.core.management.base import BaseCommand

from news.models import Source


DISTRICT_SLUGS = {
    69: "bialystok", 70: "lomza", 71: "olsztyn", 72: "ostroleka", 73: "suwalki",
    74: "bydgoszcz", 75: "elblag", 76: "gdansk", 77: "slupsk", 78: "torun",
    79: "wloclawek", 80: "bielsko-biala", 81: "czestochowa", 82: "gliwice",
    83: "katowice", 84: "sosnowiec", 85: "kielce", 86: "krakow", 87: "tarnow",
    88: "lublin", 89: "radom", 90: "siedlce", 91: "zamosc", 92: "lodz",
    93: "ostrow-wielkopolski", 94: "piotrkow-trybunalski", 95: "plock", 96: "sieradz",
    97: "konin", 98: "poznan", 99: "zielona-gora", 100: "krosno", 101: "rzeszow",
    102: "tarnobrzeg", 103: "koszalin", 104: "szczecin", 105: "warszawa",
    106: "jelenia-gora", 107: "legnica", 108: "opole", 109: "wroclaw",
}


def suggested_url(source_id):
    try:
        return "https://www.gov.pl/web/po-" + DISTRICT_SLUGS[source_id]
    except KeyError as exc:
        raise ValueError("not_a_reviewed_district_prosecutor") from exc


class Command(BaseCommand):
    help = "Tworzy offline listę kandydackich adresów gov.pl dla prokuratur okręgowych; niczego nie aktywuje."

    def add_arguments(self, parser):
        parser.add_argument("--apply-notes", action="store_true", help="Zapisuje sugestię wyłącznie w notatce katalogowej.")

    def handle(self, *args, **options):
        # Match the ASCII-stable prefix only.  Historic catalog imports can
        # contain differently normalized Polish diacritics, which must not
        # make a read-only review queue silently empty.
        sources = [
            source for source in Source.objects.filter(name__startswith="Prokuratura Okr").order_by("id")
            if source.name.startswith("Prokuratura Okr")
        ]
        changed = 0
        for source in sources:
            url = suggested_url(source.id)
            note = (
                "Kandydacki adres do ręcznej weryfikacji (nie jest kartą dostępu ani zgodą): "
                f"{url}/aktualnosci"
            )
            if options["apply_notes"]:
                # Replace only earlier suggestions from this command.  Match
                # the ASCII URL fragment rather than Polish display text: old
                # catalog imports may contain a different Unicode encoding.
                previous = "\n".join(line for line in source.catalog_notes.splitlines()
                                     if "https://www.gov.pl/web/po-" not in line)
                if note in previous:
                    continue
                source.catalog_notes = (previous.rstrip() + "\n\n" + note).strip()
                source.save(update_fields=["catalog_notes"])
                changed += 1
            self.stdout.write(f"{source.id}|{source.name}|{url}/aktualnosci")
        self.stdout.write(self.style.SUCCESS(
            f"KANDYDACI={len(sources)} ZAPISANE_NOTATKI={changed} AKTYWACJE=0 KARTY=0"))
