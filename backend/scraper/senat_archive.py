"""Metadata-only discovery of the Senate's own current-affairs entries."""

import re

from django.db import transaction

from news.models import ArchiveJob, Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.utils import HostRateLimited, fetch_feed


SOURCE_URL = "https://www.senat.gov.pl"
LISTING_URL = SOURCE_URL + "/aktualnoscilista/"
ARTICLE_RE = re.compile(r'https?://www\.senat\.gov\.pl/aktualnoscilista/art,[0-9]+,[^"\'<>\s]+\.html')


def discover_senat():
    source = Source.objects.filter(url=SOURCE_URL, is_active=True, scrape_enabled=True,
                                   catalog_stage="configured").first()
    if source is None:
        return {"status": "disabled", "queued": 0}
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.HTML, LISTING_URL)
    if instruction is None:
        return {"status": "blocked_access_review", "queued": 0}
    try:
        raw = fetch_feed(LISTING_URL, hostname_transport=True, audit_source=source,
                         audit_instruction=instruction, requested_kind="page")
    except HostRateLimited as exc:
        return {"status": "deferred", "queued": 0,
                "retry_after_seconds": round(exc.retry_after_seconds, 1)}
    urls = list(dict.fromkeys(ARTICLE_RE.findall(raw.decode("utf-8", errors="replace"))))[:20]
    if not urls:
        return {"status": "error", "queued": 0, "error": "senat_listing_structure_changed"}
    with transaction.atomic():
        current = Source.objects.select_for_update().get(pk=source.pk)
        if approved_instruction(current, SourceAccessInstruction.Channel.HTML, LISTING_URL) is None:
            return {"status": "blocked_access_review", "queued": 0}
        ArchiveJob.objects.bulk_create(
            [ArchiveJob(source=current, url=url, kind="page") for url in urls],
            ignore_conflicts=True,
        )
    return {"status": "ok", "source_id": source.pk, "queued": len(urls)}
