"""Fail-closed discovery for a gov.pl justice-unit news listing.

The adapter only discovers the publisher's own article links.  Fetching each
article is left to ``scraper.archive`` so the normal access card, host gate,
daily cap and FetchAttempt receipt are checked again for every page.
"""
import re
from html.parser import HTMLParser
from datetime import datetime, timezone as dt_timezone
from urllib.parse import parse_qs, urljoin, urlsplit

from django.db import transaction
from django.utils import timezone

from news.models import ArchiveJob, Source, SourceAccessInstruction
from news.metadata import decode_source_html
from news.metadata import extract_metadata
from scraper.access_gate import approved_instruction
from scraper.utils import fetch_feed, safe_url


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
MAX_ITEMS = 20


class InvalidGovArticleLink(ValueError):
    """A bounded diagnostic for a reviewed listing whose item links changed."""
    def __init__(self, links):
        self.links = links[:MAX_ITEMS]
        super().__init__("invalid_gov_article_link")


def _listing_url(section, url, listing_path=None):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.gov.pl" or parsed.fragment:
        raise ValueError("invalid_gov_listing_url")
    expected = listing_path or section.rstrip("/") + "/aktualnosci"
    if parsed.path != expected:
        raise ValueError("invalid_gov_listing_url")
    params = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
    if set(params) - {"page", "size"} or any(len(value) != 1 for value in params.values()):
        raise ValueError("invalid_gov_listing_query")
    if params.get("size", ["10"])[0] != "10":
        raise ValueError("invalid_gov_listing_query")
    page = int(params.get("page", ["1"])[0])
    if not 1 <= page <= 100000:
        raise ValueError("invalid_gov_listing_page")
    return page


class _GovJusticeListing(HTMLParser):
    def __init__(self, url, section, listing_path):
        super().__init__(convert_charrefs=True)
        self.url, self.section, self.listing_path = url, section.rstrip("/"), listing_path
        self.stack, self.items = [], []
        self.current, self.current_page, self.last_url, self.next_url = None, None, None, None
        self.container_seen = False
        self.content_depth = 0

    def inside(self, cls):
        return any(cls in attrs.get("class", "").split() for _, attrs in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("id") in {"js-pagination-page-next", "js-pagination-pages-count"}:
            candidate = urljoin(self.url, attrs.get("href", ""))
            _listing_url(self.section, candidate, self.listing_path)
            if attrs["id"] == "js-pagination-page-next":
                self.next_url = candidate
            else:
                self.last_url = candidate
        if tag == "input" and attrs.get("id") == "js-pagination-page":
            self.current_page = int(attrs.get("value", ""))
        classes = attrs.get("class", "").split()
        # gov.pl uses an ``art-prev--under-title`` block for sibling-category
        # navigation.  It looks like a feed, but it is not one: accepting it
        # would enqueue category pages as material.  Other art-prev variants
        # are the publisher's actual listing shell.
        if "art-prev" in classes and "art-prev--under-title" not in classes:
            self.container_seen = True
            self.content_depth += 1
        if tag == "li" and self.content_depth and self.current is None:
            self.current = {"url": "", "title": []}
        if self.current is not None and tag == "a" and self.inside("title"):
            self.current["url"] = urljoin(self.url, attrs.get("href", ""))
        if tag not in VOID:
            self.stack.append((tag, attrs))

    def handle_data(self, value):
        if self.current is not None and self.inside("title"):
            self.current["title"].append(value)

    def handle_endtag(self, tag):
        if tag == "li" and self.current is not None:
            self.items.append(self.current)
            self.current = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                closed_attrs = self.stack[index][1]
                closed_classes = closed_attrs.get("class", "").split()
                if "art-prev" in closed_classes and "art-prev--under-title" not in closed_classes:
                    self.content_depth -= 1
                del self.stack[index:]
                break


def parse_listing(raw, url, section, listing_path=None):
    listing_path = listing_path or urlsplit(url).path
    page = _listing_url(section, url, listing_path)
    parser = _GovJusticeListing(url, section, listing_path)
    parser.feed(decode_source_html(raw))
    parser.close()
    unpaginated_first_page = (
        page == 1 and parser.current_page is None and parser.last_url is None and parser.next_url is None
    )
    if (not parser.container_seen or (not unpaginated_first_page and (
            not parser.last_url or parser.current_page != page))
            or not 1 <= len(parser.items) <= MAX_ITEMS):
        raise ValueError("gov_listing_structure_changed")
    if unpaginated_first_page:
        return {"urls": _records(parser.items, section), "next_url": None, "page": 1, "last_page": 1}
    last_page = _listing_url(section, parser.last_url, listing_path)
    if last_page < page or (parser.next_url and _listing_url(section, parser.next_url, listing_path) != page + 1):
        raise ValueError("gov_listing_pagination_changed")
    return {"urls": _records(parser.items, section), "next_url": parser.next_url, "page": page, "last_page": last_page}


def _records(items, section):
    records, seen = [], set()
    pattern = re.compile(re.escape(section.rstrip("/")) + r"/[^/]+$")
    invalid = []
    for item in items:
        link = item["url"]
        parsed = urlsplit(link)
        title = " ".join(" ".join(item["title"]).split())
        # The shared gov.pl shell may place national headlines beside this
        # institution's listing.  They are outside the reviewed section and
        # are ignored; the card is never widened to cover them.
        if parsed.hostname == "www.gov.pl" and not parsed.path.startswith(section.rstrip("/") + "/"):
            continue
        if (not safe_url(link) or parsed.hostname != "www.gov.pl" or parsed.path == section.rstrip("/") + "/aktualnosci"
                or not pattern.fullmatch(parsed.path)
                or parsed.query or parsed.fragment or not title):
            invalid.append(link)
            continue
        if link not in seen:
            records.append(link)
            seen.add(link)
    if invalid:
        raise InvalidGovArticleLink(invalid)
    return records


def extract_article_metadata(raw, url, section):
    """Recognize the stable, publisher-declared gov.pl justice article shell.

    gov.pl declares every page as OpenGraph ``website``.  For the reviewed
    justice section that would discard genuine press notices.  This narrow
    fallback requires the exact section URL, the site's semantic ``article``
    shell and its visible publisher date; it never promotes an arbitrary
    gov.pl page to an article.
    """
    parsed = urlsplit(url)
    base = section.rstrip("/")
    if parsed.scheme != "https" or parsed.hostname != "www.gov.pl" or not re.fullmatch(
            re.escape(base) + r"/[^/]+", parsed.path):
        raise ValueError("invalid_gov_article_url")
    text = decode_source_html(raw)
    if not re.search(r"<article\b[^>]*\barticle-area__article\b", text, re.I):
        raise ValueError("gov_article_structure_changed")
    date_match = re.search(r'<p[^>]*\bclass=["\'][^"\']*\bevent-date\b[^"\']*["\'][^>]*>\s*([^<]+?)\s*</p>', text, re.I)
    if not date_match:
        raise ValueError("gov_article_date_missing")
    try:
        published = datetime.strptime(" ".join(date_match.group(1).split()), "%d.%m.%Y").replace(tzinfo=dt_timezone.utc)
    except ValueError as exc:
        raise ValueError("gov_article_date_invalid") from exc
    metadata = extract_metadata(raw, url)
    title = metadata["title"]
    # The portal appends its source and portal labels to og:title.  Preserve
    # the publisher wording while removing only that predictable shell.
    title = re.sub(r"\s+-\s+[^-]+?\s+-\s+Portal Gov\.pl$", "", title).strip()
    if not title:
        raise ValueError("missing_source_title")
    metadata.update(
        title=title[:500], published_date=published.isoformat(),
        date_raw=date_match.group(1).strip(), date_source="gov.pl:event-date",
        publisher_type="article", page_classification="article",
        category="statement", category_evidence="Semantyczny element article i data widoczna w materiale gov.pl.",
    )
    return metadata


def discover(source_id):
    source = Source.objects.get(pk=source_id)
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.HTML)
    if instruction is None:
        raise ValueError("no_approved_instruction")
    section = urlsplit(instruction.endpoint).path.rstrip("/")
    listing_url = instruction.evidence.get("listing_url") or ("https://www.gov.pl" + section + "/aktualnosci")
    parsed_listing = urlsplit(listing_url)
    if (parsed_listing.scheme != "https" or parsed_listing.hostname != "www.gov.pl"
            or not parsed_listing.path.startswith(section + "/")):
        raise ValueError("invalid_gov_listing_url")
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.HTML, listing_url)
    if instruction is None:
        raise ValueError("listing_not_covered_by_instruction")
    parsed = parse_listing(fetch_feed(listing_url, hostname_transport=True, audit_source=source,
        audit_instruction=instruction, requested_kind="page"), listing_url, section,
        parsed_listing.path)
    with transaction.atomic():
        source = Source.objects.select_for_update().get(pk=source_id)
        if approved_instruction(source, SourceAccessInstruction.Channel.HTML, listing_url) is None:
            raise ValueError("source_changed_during_discovery")
        for url in parsed["urls"]:
            ArchiveJob.objects.get_or_create(source=source, url=url, defaults={"kind": "page"})
    return {"queued": len(parsed["urls"]), "page": parsed["page"], "last_page": parsed["last_page"]}
