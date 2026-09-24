"""Fail-closed adapter for the official current Polish cabinet page.

It stages only names and current cabinet roles.  It never discovers social
accounts, creates candidates, or reads from X.
"""
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata

import requests
from django.core.management.base import CommandError


KPRM_CABINET_URL = 'https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2'
KPRM_CABINET_TITLE = 'Członkowie Rady Ministrów'
_MIN_CURRENT_MEMBERS = 10
_ROLE_RE = re.compile(
    r'^(?:(?:pierwszy |wice)?prezes rady ministrów(?:,\s*)?)?(?:minister(?:\s|$)|prezes rady ministrów$)',
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"^[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż.'’ -]{2,}$")


@dataclass(frozen=True)
class CabinetRow:
    canonical_name: str
    role_title: str
    source_url: str
    import_key: str


class _TextLines(HTMLParser):
    """Collect visible text lines without accepting scripts or hidden markup."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self._ignored = 0
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self._ignored += 1
        if tag in {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'article', 'section', 'br'}:
            self._flush()

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self._ignored:
            self._ignored -= 1
        if tag in {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'article', 'section'}:
            self._flush()

    def handle_data(self, data):
        if not self._ignored:
            self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()

    def _flush(self):
        value = ' '.join(''.join(self._buffer).split())
        self._buffer.clear()
        if value:
            self.lines.append(value)


def _normalise(value: str) -> str:
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def cabinet_office_import_key(role_title: str) -> str:
    """Stable registry key for the function named on the official roster.

    A holder's name is deliberately not part of this key: a cabinet reshuffle
    changes the holder, not the historical record of the function.
    """
    return f'public-office:cabinet:{_normalise(role_title)}'


def _visible_lines(html: str) -> list[str]:
    parser = _TextLines()
    parser.feed(html)
    parser.close()
    return parser.lines


def cabinet_rows(*, http_get=requests.get) -> list[CabinetRow]:
    """Read only the explicitly listed current cabinet members from KPRM.

    The page must identify itself and yield a sufficiently large, unique list.
    Any changed/ambiguous structure fails before the command can archive data.
    """
    try:
        response = http_get(KPRM_CABINET_URL, timeout=20, headers={'Accept': 'text/html'})
        response.raise_for_status()
        html = response.text
    except (requests.RequestException, AttributeError) as exc:
        raise CommandError(f'Nie udało się pobrać oficjalnej listy KPRM: {exc}') from exc
    if not isinstance(html, str) or not html.strip():
        raise CommandError('Oficjalna strona KPRM zwróciła pustą odpowiedź HTML.')

    lines = _visible_lines(html)
    if KPRM_CABINET_TITLE not in lines:
        raise CommandError('Strona KPRM nie potwierdza tytułu „Członkowie Rady Ministrów”; import przerwany.')

    rows_by_key = {}
    for index, role in enumerate(lines):
        if not _ROLE_RE.match(role):
            continue
        if index == 0:
            raise CommandError('Strona KPRM zawiera rolę bez poprzedzającego imienia i nazwiska.')
        name = lines[index - 1]
        if not _NAME_RE.match(name) or len(name.split()) < 2:
            raise CommandError('Strona KPRM zawiera niejednoznaczne imię przy roli członka rządu; import przerwany.')
        key = f'kprm-cabinet:{_normalise(name)}'
        candidate = CabinetRow(name, role, KPRM_CABINET_URL, key)
        prior = rows_by_key.get(key)
        if prior and prior != candidate:
            raise CommandError('Strona KPRM zawiera sprzeczne role dla tej samej osoby; import przerwany.')
        rows_by_key[key] = candidate

    rows = list(rows_by_key.values())
    if len(rows) < _MIN_CURRENT_MEMBERS:
        raise CommandError(
            f'Strona KPRM zawiera tylko {len(rows)} jednoznacznych członków rządu; import przerwany dla bezpieczeństwa.'
        )
    return rows
