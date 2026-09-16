"""Resolve reviewed draft sources into durable, non-sending contact records."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction, SourceContactCard


DECISIONS = {
    "https://www.uokik.gov.pl/public/aktualnosci": {
        "publisher": "Urząd Ochrony Konkurencji i Konsumentów",
        "contact": "https://uokik.gov.pl/kontakt",
        "channels": ["rss"],
        "evidence": ["https://uokik.gov.pl/public/rss"],
        "reason": "Official RSS directory was found, but no reviewed exact feed URL and reuse conditions were captured for this news route.",
    },
    "https://www.prezydent.pl": {
        "publisher": "Kancelaria Prezydenta RP",
        "contact": "https://www.prezydent.pl/kontakt",
        "channels": ["rss", "api"],
        "evidence": ["https://www.prezydent.pl/kancelaria/ponowne-wykorzystywanie-informacji-sektora-publicznego"],
        "reason": "Reuse information found for BIP, but no reviewed public news RSS/API endpoint for this source.",
    },
    "https://pk.gov.pl": {
        "publisher": "Prokuratura Krajowa",
        "contact": "https://www.gov.pl/web/prokuratura-krajowa/kontakt",
        "channels": ["rss", "api"],
        "evidence": ["https://pk.gov.pl"],
        "reason": "Official news site found, but no source-specific reuse terms or stable RSS/API endpoint were verified. Separate gov.pl justice cards remain independent.",
    },
    "https://www.nik.gov.pl": {
        "publisher": "Najwyższa Izba Kontroli",
        "contact": "https://www.nik.gov.pl/kontakt/",
        "channels": ["rss", "api"],
        "evidence": ["https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/"],
        "reason": "Reuse policy found, but no current reviewed RSS/API/export for this root source. Any distinct approved NIK feed remains separate.",
    },
    "https://www.knf.gov.pl": {
        "publisher": "Komisja Nadzoru Finansowego",
        "contact": "https://www.knf.gov.pl/o_nas/kontakt",
        "channels": ["rss", "api"],
        "evidence": ["https://bip.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego"],
        "reason": "Reuse information and an RSS registry were found, but no narrow reviewed news/export endpoint was verified.",
    },
    "https://www.sn.pl": {
        "publisher": "Sąd Najwyższy",
        "contact": "https://www.sn.pl/kontakt/",
        "channels": ["rss", "api"],
        "evidence": ["https://www.sn.pl"],
        "reason": "Previously known RSS endpoint is stale (404); a current machine-readable news channel needs confirmation.",
    },
    "https://www.europarl.europa.eu/poland": {
        "publisher": "Parlament Europejski — Biuro w Polsce",
        "contact": "https://www.europarl.europa.eu/at-your-service/pl/contact",
        "channels": ["rss"],
        "evidence": ["https://www.europarl.europa.eu/at-your-service/pl/stay-informed/rss-feeds", "https://www.europarl.europa.eu/legal-notice/en"],
        "reason": "Official RSS directory and legal notice found, but exact Polish feed URL was not independently retrievable for a narrow card.",
    },
}


def resolve(source):
    spec = DECISIONS[source.url]
    with transaction.atomic():
        source = Source.objects.select_for_update().get(pk=source.pk)
        latest = source.access_instructions.order_by("-version").first()
        if not latest or latest.status != SourceAccessInstruction.Status.DRAFT:
            raise ValueError("latest_instruction_not_draft")
        card = SourceAccessInstruction.objects.create(
            source=source, version=latest.version + 1,
            status=SourceAccessInstruction.Status.CONTACT_REQUIRED,
            channel=latest.channel, allowed_scope=latest.allowed_scope,
            endpoint=latest.endpoint, allowed_path_patterns=latest.allowed_path_patterns,
            terms_url=latest.terms_url,
            evidence={"decision": "ready_to_contact", "evidence_urls": spec["evidence"], "reason": spec["reason"]},
            minimum_interval_seconds=3, daily_request_cap=0,
        )
        SourceContactCard.objects.get_or_create(
            source=source,
            defaults={
                "status": SourceContactCard.Status.READY_FOR_REVIEW,
                "publisher_name": spec["publisher"], "contact_url": spec["contact"],
                "requested_scope": ["metadata"], "requested_channels": spec["channels"],
                "technical_findings": {"evidence_urls": spec["evidence"]},
                "reason_for_contact": spec["reason"],
                "next_review_at": timezone.now(),
            },
        )
    return card


class Command(BaseCommand):
    help = "Zmienia siedem zweryfikowanych szkiców w gotowe do kontroli karty kontaktu; nie wysyła wiadomości."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        sources = list(Source.objects.filter(url__in=DECISIONS).order_by("pk"))
        missing = set(DECISIONS) - {source.url for source in sources}
        if missing:
            raise CommandError("Brak kandydatów: " + ", ".join(sorted(missing)))
        plans = []
        for source in sources:
            latest = source.access_instructions.order_by("-version").first()
            if latest and latest.status == SourceAccessInstruction.Status.DRAFT:
                plans.append(source)
            elif latest and latest.status == SourceAccessInstruction.Status.CONTACT_REQUIRED:
                continue
            else:
                raise CommandError(f"{source.pk}: najnowsza karta ma status {latest.status if latest else 'brak'}")
        if not options["apply"]:
            self.stdout.write(f"PLAN: {len(plans)} szkiców -> gotowe do kontroli kontaktu; bez --apply nie zmieniam danych.")
            return
        for source in plans:
            card = resolve(source)
            self.stdout.write(self.style.SUCCESS(f"GOTOWE: {source.pk} -> karta kontaktowa v{card.version}."))
