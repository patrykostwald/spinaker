"""Collapse duplicate catalog entries of the same publisher.

The catalog was imported from two lists: host cards (``https://www.tvn24.pl``)
and named feed sources (``TVN24`` — ``https://tvn24.pl/najwazniejsze.xml``).
Both describe one publisher, so readers saw it twice and outreach would contact
it twice.  Entries sharing a host (``www.`` ignored; a few known news-section
aliases below) form one group.  Kept: an active/configured entry, otherwise the
one with a feed path (the name used by ``news.source_groups.TOP_MEDIA``),
otherwise the oldest.  The others — only inactive candidates — are marked
``excluded`` with a note naming the kept source; ``--restore`` reverts.
Subdomains that are separate outlets (``konkret24.tvn24.pl``,
``samorzad.pap.pl``) are different hosts and are never merged.
"""
from collections import defaultdict
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import Source

MARKER = "[Duplikat w katalogu"

# Portal i jego dział wiadomości to ten sam wydawca (jedna karta w katalogu).
HOST_ALIASES = {
    "wiadomosci.onet.pl": "onet.pl",
    "wiadomosci.wp.pl": "wp.pl",
    "fakty.interia.pl": "interia.pl",
    "rss.gazeta.pl": "gazeta.pl",
}


# Hosty współdzielone przez wielu wydawców: wydawcę wyznacza początek ścieżki
# (ministerstwa i ich BIP-y na gov.pl/web/<nazwa>, kanały YouTube, działy API Sejmu, kanały Polskiego Radia).
PATH_HOSTS = {"gov.pl": 2, "bip.gov.pl": 2, "youtube.com": 2, "api.sejm.gov.pl": 1, "polskieradio.pl": 1, "x.com": 1, "twitter.com": 1, "facebook.com": 1}


def publisher_key(url):
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower().removeprefix("www.")
    host = HOST_ALIASES.get(host, host)
    depth = PATH_HOSTS.get(host)
    if depth:
        segments = [segment for segment in parts.path.lower().split("/") if segment][:depth]
        # Kanał RSS ministerstwa (`/web/finanse/rss`) to ten sam wydawca co strona (`/web/finanse`).
        return "/".join([host, *segments])
    return host


def has_feed_path(source):
    return urlsplit(source.url or "").path.strip("/") != ""


def keep_order(source):
    configured = source.is_active or source.scrape_enabled or source.catalog_stage == "configured"
    return (0 if configured else 1, 0 if has_feed_path(source) else 1, source.pk)


def plan():
    groups = defaultdict(list)
    for source in Source.objects.exclude(catalog_stage="excluded").order_by("pk"):
        key = publisher_key(source.url)
        if key:
            groups[key].append(source)
    decisions = []
    for key, sources in sorted(groups.items()):
        if len(sources) < 2:
            continue
        ordered = sorted(sources, key=keep_order)
        kept, rest = ordered[0], ordered[1:]
        for source in rest:
            touchable = not (source.is_active or source.scrape_enabled or source.catalog_stage == "configured")
            decisions.append((key, kept, source, touchable))
    return decisions


class Command(BaseCommand):
    help = "Wyklucza z katalogu duplikaty tego samego wydawcy (ten sam host), zostawiając jedną kartę; odwracalne."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Zapisz zmiany (domyślnie tylko plan).")
        parser.add_argument("--restore", action="store_true", help="Przywróć do kandydatów źródła z tym znacznikiem.")

    def handle(self, *args, **options):
        if options["restore"]:
            return self._restore(options["apply"])
        decisions = plan()
        for key, kept, source, touchable in decisions:
            action = "WYKLUCZ " if touchable else "POMIŃ   "
            self.stdout.write(f"{action} {source.pk:5} {source.name[:34]:34} -> zostaje {kept.pk} {kept.name[:30]}  ({key})")
        todo = [row for row in decisions if row[3]]
        if not options["apply"]:
            self.stdout.write(f"PLAN: duplikatów do wykluczenia={len(todo)} pominiętych={len(decisions) - len(todo)}; bez --apply nie zmieniam bazy.")
            return
        stamp = timezone.localdate().isoformat()
        with transaction.atomic():
            for key, kept, source, _ in todo:
                note = f"{MARKER}: ten sam wydawca co źródło #{kept.pk} „{kept.name}” ({key}) — wykluczone {stamp}; cofnięcie: dedupe_source_catalog --restore --apply]"
                source.catalog_stage = "excluded"
                source.catalog_notes = (source.catalog_notes.rstrip() + "\n\n" + note).strip()
                source.save(update_fields=["catalog_stage", "catalog_notes", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"WYKLUCZONO DUPLIKATÓW: {len(todo)}."))

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
