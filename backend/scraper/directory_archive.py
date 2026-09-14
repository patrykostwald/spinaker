"""URL discovery from three publisher listing templates verified on 2026-09-09.

This module never extracts publication metadata or follows network links. A known
route still needs publication links inside its publisher's actual list container.
"""
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from news.metadata import decode_source_html
from scraper.utils import safe_url


MAX_DIRECTORY_LINKS = 200
_VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
         'link', 'meta', 'param', 'source', 'track', 'wbr'}


@dataclass(frozen=True)
class DirectorySpec:
    family: str
    root: str
    page: int


def directory_spec(url):
    """Recognize only the observed tag/topic/person routes, not arbitrary pages."""
    parsed = urlsplit(url)
    host, path = parsed.hostname, parsed.path
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        return None
    if host == 'niebezpiecznik.pl':
        match = re.fullmatch(r'(/tag/[\w%-]+)(?:/page/([1-9]\d{0,5}))?/?', path)
        if match and not parsed.query:
            return DirectorySpec('niebezpiecznik', match[1], int(match[2] or 1))
    elif host in ('www.polityka.pl', 'www.nowiny.pl'):
        family, pattern, key = ('polityka', r'/tematy/[\w%-]+/?', 'page') if host == 'www.polityka.pl' else (
            'nowiny', r'/ludzie/[1-9]\d*-[\w%-]+/?', 'p')
        if not re.fullmatch(pattern, path):
            return None
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if not pairs:
            return DirectorySpec(family, path.rstrip('/'), 1)
        if len(pairs) == 1 and pairs[0][0] == key and re.fullmatch(r'[1-9]\d{0,5}', pairs[0][1]):
            return DirectorySpec(family, path.rstrip('/'), int(pairs[0][1]))
    return None


def _public_url(href, requested):
    try:
        url = safe_url(urljoin(requested, href))
        if not url or len(url) > 1024:
            return ''
        parsed, source = urlsplit(url), urlsplit(requested)
        # Do not broaden the Source to sibling domains, subdomains, or custom ports.
        if parsed.hostname != source.hostname or parsed.port != source.port:
            return ''
        if parsed.username or parsed.password:
            return ''
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))
    except ValueError:
        # One broken publisher link must not discard the valid list around it.
        return ''


class _DirectoryParser(HTMLParser):
    def __init__(self, url, spec):
        super().__init__(convert_charrefs=True)
        self.url, self.spec = url, spec
        self.stack = []
        self.publications, self.pages = {}, {}
        self.overflow = False

    def _has(self, *, tag=None, cls=None, id=None):
        return any((tag is None or tag == t) and (cls is None or cls in a.get('class', '').split())
                   and (id is None or id == a.get('id')) for t, a in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self._link(attrs)
        if tag not in _VOID:
            self.stack.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def _link(self, attrs):
        url = _public_url(attrs['href'], self.url)
        if not url:
            return
        parsed = urlsplit(url)
        family = self.spec.family
        publication = pagination = False
        if family == 'niebezpiecznik' and self._has(id='main'):
            publication = (self._has(cls='post') and self._has(tag='h2')
                and 'bookmark' in attrs.get('rel', '').split()
                and bool(re.fullmatch(r'/post/[\w%-]+/?', parsed.path)))
            pagination = self._has(cls='navigation')
        elif family == 'polityka' and self._has(tag='section', cls='cg_tag_index'):
            publication = bool(re.fullmatch(r'/tygodnikpolityka/(?:[\w-]+/)+[1-9]\d*,[1-9]\d*,[\w%-]+\.read', parsed.path))
            pagination = self._has(cls='cg_pager')
        elif family == 'nowiny' and self._has(id='content-wall'):
            publication = (self._has(cls='c-news') and bool(re.fullmatch(
                r'/(?:wiadomosci|opinie|sport|ekonowiny)/[1-9]\d*-[\w%-]+\.html', parsed.path)))
            pagination = 'c-button' in attrs.get('class', '').split()
        if publication and not parsed.query:
            if url not in self.publications and len(self.publications) >= MAX_DIRECTORY_LINKS:
                self.overflow = True
            else:
                self.publications[url] = None
        if pagination:
            candidate = directory_spec(url)
            # Only an observed next page of this exact listing. No calendars,
            # arbitrary query combinations, other tags, or invented pagination.
            if candidate == DirectorySpec(family, self.spec.root, self.spec.page + 1):
                self.pages[url] = None


def directory_links(raw, url):
    """Return URLs, None for unsupported routes, or a visible error for empty lists."""
    spec = directory_spec(url)
    if spec is None:
        return None
    parser = _DirectoryParser(url, spec)
    parser.feed(decode_source_html(raw))
    if parser.overflow:
        raise ValueError('directory_link_limit')
    if not parser.publications:
        # directory_spec positively identified this as a supported catalogue;
        # an empty result is therefore a terminal technical page, not an
        # ambiguous article whose publisher markup may have drifted.
        raise ValueError('empty_directory')
    return tuple(parser.publications), tuple(parser.pages)
