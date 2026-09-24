import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction

from scraper.gov_justice_archive import InvalidGovArticleLink, parse_listing, extract_article_metadata


SECTION = "/web/prokuratura-krajowa"
URL = "https://www.gov.pl/web/prokuratura-krajowa/aktualnosci"


def listing(link="/web/prokuratura-krajowa/komunikat-1"):
    return f'''<div class="art-prev"><li><div class="title"><a href="{link}">Komunikat 1</a></div></li></div>
    <input id="js-pagination-page" value="1"><a id="js-pagination-pages-count" href="?page=1&size=10"></a>'''.encode()


def test_gov_listing_accepts_own_article_link():
    parsed = parse_listing(listing(), URL, SECTION)
    assert parsed["urls"] == ["https://www.gov.pl/web/prokuratura-krajowa/komunikat-1"]


def test_gov_listing_accepts_reviewed_nondefault_listing_path():
    regional_section = "/web/pr-warszawa"
    regional_url = "https://www.gov.pl/web/pr-warszawa/aktualnosci-prokuratury-regionalnej2"
    parsed = parse_listing(listing("/web/pr-warszawa/komunikat-1"), regional_url,
        regional_section, "/web/pr-warszawa/aktualnosci-prokuratury-regionalnej2")
    assert parsed["urls"] == ["https://www.gov.pl/web/pr-warszawa/komunikat-1"]


def test_gov_listing_accepts_first_page_without_pagination_controls():
    raw = b'''<div class="art-prev"><li><div class="title"><a href="/web/prokuratura-krajowa/komunikat-1">Komunikat 1</a></div></li></div>'''
    parsed = parse_listing(raw, URL, SECTION)
    assert parsed == {"urls": ["https://www.gov.pl/web/prokuratura-krajowa/komunikat-1"],
                      "next_url": None, "page": 1, "last_page": 1}


def test_gov_listing_ignores_sibling_navigation_that_uses_art_prev_shell():
    raw = b'''<div class="art-prev art-prev--under-title"><li><div class="title"><a href="/web/prokuratura-krajowa/kategoria">Kategoria</a></div></li></div>
    <div class="art-prev art-prev--near-menu"><li><div class="title"><a href="/web/prokuratura-krajowa/komunikat-1">Komunikat 1</a></div></li></div>'''
    parsed = parse_listing(raw, URL, SECTION)
    assert parsed["urls"] == ["https://www.gov.pl/web/prokuratura-krajowa/komunikat-1"]


@pytest.mark.parametrize("link", ["https://evil.example/a", "/web/prokuratura-krajowa/aktualnosci"])
def test_gov_listing_rejects_outside_or_listing_links(link):
    with pytest.raises(InvalidGovArticleLink, match="invalid_gov_article_link"):
        parse_listing(listing(link), URL, SECTION)


def test_gov_listing_ignores_national_shell_links_outside_reviewed_section():
    raw = (listing("/web/premier/komunikat-ogolny") +
           listing("/web/prokuratura-krajowa/komunikat-1"))
    parsed = parse_listing(raw, URL, SECTION)
    assert parsed["urls"] == ["https://www.gov.pl/web/prokuratura-krajowa/komunikat-1"]


@pytest.mark.django_db
def test_section_html_card_does_not_authorize_robots_but_exact_robots_card_does():
    source = Source.objects.create(name="Gov test", url="https://www.gov.pl/web/test")
    common = {
        "status": "approved", "allowed_scope": "metadata",
        "terms_url": "https://www.gov.pl/web/gov/warunki-korzystania",
        "evidence": {"basis": "test"}, "reviewed_at": timezone.now(),
        "reviewed_by": "test", "minimum_interval_seconds": 3,
        "daily_request_cap": 24,
    }
    SourceAccessInstruction.objects.create(source=source, version=1, channel="html",
        endpoint="https://www.gov.pl/web/test", **common)
    assert approved_instruction(source, "html", "https://www.gov.pl/web/test/item")
    assert approved_instruction(source, "sitemap", "https://www.gov.pl/robots.txt") is None
    SourceAccessInstruction.objects.create(source=source, version=2, channel="sitemap",
        endpoint="https://www.gov.pl/robots.txt", allowed_path_patterns=["/robots.txt"], **common)
    assert approved_instruction(source, "sitemap", "https://www.gov.pl/robots.txt")


def test_gov_justice_article_fallback_requires_article_shell_and_visible_date():
    raw = b'''<meta property="og:title" content="Komunikat testowy - Prokuratura Krajowa - Portal Gov.pl">
    <meta property="og:type" content="website"><article class="article-area__article"><p class="event-date">15.09.2026</p></article>'''
    metadata = extract_article_metadata(raw, "https://www.gov.pl/web/prokuratura-krajowa/komunikat-testowy", SECTION)
    assert metadata["title"] == "Komunikat testowy"
    assert metadata["published_date"] == "2026-09-15T00:00:00+00:00"
    assert metadata["page_classification"] == "article"


def test_gov_justice_article_fallback_refuses_missing_article_shell():
    with pytest.raises(ValueError, match="gov_article_structure_changed"):
        extract_article_metadata(b'<p class="event-date">15.09.2026</p>',
            "https://www.gov.pl/web/prokuratura-krajowa/komunikat-testowy", SECTION)


def test_gov_justice_article_fallback_supports_a_reviewed_regional_section():
    raw = b'<meta property="og:title" content="Komunikat - Portal Gov.pl"><article class="article-area__article"><p class="event-date">15.09.2026</p></article>'
    result = extract_article_metadata(raw, "https://www.gov.pl/web/pr-warszawa/komunikat", "/web/pr-warszawa")
    assert result["page_classification"] == "article"


def test_gov_import_reports_host_gate_delay_without_an_error(monkeypatch):
    from scraper.utils import HostRateLimited
    monkeypatch.setattr("scraper.management.commands.import_gov_justice_html.discover",
        lambda source_id: (_ for _ in ()).throw(HostRateLimited(2.5)))
    output = StringIO()
    call_command("import_gov_justice_html", "--source-id=1", "--apply", stdout=output)
    assert "ODROCZONE" in output.getvalue()
