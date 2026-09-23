"""Bounded discovery of official reuse-condition pages.

This module finds evidence for editorial review.  It never creates an access
card, enables a source, or authorises an importer.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from news.metadata import decode_source_html
from scraper.source_probe import ProbeError, PublisherLinks, public_link


DISCOVERY_VERSION = 1
LINK_HINTS = (
    'ponowne-wykorzyst', 'ponowne%20wykorzyst', 'reuse', 're-use',
    'warunki-korzystania', 'warunki_uzytkowania', 'licencj', 'copyright', 'prawa-autorskie',
)
POSITIVE_HINTS = (
    'ponowne wykorzystywanie', 'ponownie wykorzystywać', 'do ponownego wykorzystania',
    'reuse of public sector information', 'creative commons', 'cc by',
)
RESTRICTION_HINTS = (
    'wymaga zgody', 'wymagana zgoda', 'bez zgody', 'zakazuje się', 'zakaz',
    'all rights reserved', 'wszelkie prawa zastrzeżone',
)
PERMISSION_PATTERNS = (
    'ponowne wykorzystywanie informacji sektora publicznego',
    'ponowne wykorzystywanie informacji publicznej',
    'można ponownie wykorzystywać', 'mozna ponownie wykorzystywac',
    'creative commons', 'cc by',
)
DENIAL_PATTERNS = (
    'bez uprzedniej pisemnej zgody', 'wymaga uprzedniej zgody', 'wyłącznie za zgodą',
    'zakazuje się', 'zakazuje sie', 'zabrania się', 'zabrania sie',
    'all rights reserved', 'wszelkie prawa zastrzeżone', 'wszelkie prawa zastrzezone',
)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def value(self):
        return ' '.join(' '.join(self.parts).split())


def normal_host(url):
    return (urlsplit(url or '').hostname or '').lower().removeprefix('www.')


def looks_like_terms(url, text=''):
    value = f'{url} {text}'.lower()
    return any(hint in value for hint in LINK_HINTS)


def terms_links(base_url, parser, source_url):
    """Return only explicit links whose label or URL names reuse conditions.

    An institution may link its BIP on a different official host.  The fact
    that the link is explicit is recorded; it is still evidence for review,
    never an automatic approval.
    """
    links = [source_url] if looks_like_terms(source_url) else []
    for item in parser.links:
        url = public_link(urljoin(base_url, item['href']))
        if not url:
            continue
        if looks_like_terms(url, item.get('text', '')):
            links.append(url)
    return list(dict.fromkeys(links))[:3]


def analyse_page(raw):
    parser = PageText()
    parser.feed(decode_source_html(raw))
    text = parser.value()
    lower = text.lower()
    positive = [hint for hint in POSITIVE_HINTS if hint in lower]
    restrictions = [hint for hint in RESTRICTION_HINTS if hint in lower]
    return {
        'positive_markers': positive,
        'restriction_markers': restrictions,
        'excerpt': text[:800],
    }


def classify_terms_page(raw, has_channel):
    """Classify explicit wording; no result itself authorises a fetch."""
    parser = PageText()
    parser.feed(decode_source_html(raw))
    text = parser.value()
    lower = text.lower()
    permission = [item for item in PERMISSION_PATTERNS if item in lower]
    denial = [item for item in DENIAL_PATTERNS if item in lower]
    if denial:
        status = 'clear_denial_keep_inactive'
    elif permission and has_channel:
        status = 'proposed_metadata_card_requires_editorial_approval'
    elif permission:
        status = 'permission_wording_but_no_confirmed_channel'
    else:
        status = 'wording_requires_editorial_review'
    return {
        'status': status,
        'permission_markers': permission,
        'denial_markers': denial,
        'excerpt': text[:1200],
    }


def inspect_source_terms(source, network):
    """Inspect a source homepage and up to three explicitly linked terms pages."""
    result = {
        'version': DISCOVERY_VERSION,
        'source_url': source.url or '',
        'status': 'no_official_terms_link_found',
        'homepage': '',
        'terms_pages': [],
        'error': '',
    }
    if not source.url:
        result.update(status='missing_source_url', error='missing_source_url')
        return result
    try:
        raw, homepage, _ = network.fetch(source.url)
        result['homepage'] = homepage
        links = PublisherLinks()
        links.feed(decode_source_html(raw))
        candidates = terms_links(homepage, links, source.url)
        if not candidates:
            return result
        result['status'] = 'terms_link_found'
        for url in candidates:
            try:
                page_raw, final_url, _ = network.fetch(url)
                analysis = analyse_page(page_raw)
                result['terms_pages'].append({'url': final_url, 'status': 'ok', **analysis})
            except Exception as exc:
                error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
                result['terms_pages'].append({'url': url, 'status': 'error', 'error': error})
        if any(page.get('positive_markers') for page in result['terms_pages'] if page['status'] == 'ok'):
            result['status'] = 'possible_reuse_basis_requires_editorial_review'
        return result
    except Exception as exc:
        error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
        result.update(status='unavailable', error=error)
        return result
