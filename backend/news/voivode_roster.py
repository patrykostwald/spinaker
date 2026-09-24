"""Fail-closed reader for the current official KPRM list of voivodes."""
from dataclasses import dataclass
from html.parser import HTMLParser
import re

import requests
from django.core.management.base import CommandError
from django.utils.text import slugify


KPRM_VOIVODES_URL = 'https://www.gov.pl/web/premier/wojewodowie3'
_NAME_RE = re.compile(r"^[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż.'’ -]{2,}$")
_ROW_RE = re.compile(r'^(?P<name>.+?)\s+-\s+wojewoda\s+(?P<region>[a-ząćęłńóśźż-]+)$', re.IGNORECASE)

VOIVODE_CONFIG = {
    'dolnoslaski': ('dolnoslaskie', 'Wojewoda Dolnośląski', 'Dolnośląski Urząd Wojewódzki we Wrocławiu'),
    'kujawsko-pomorski': ('kujawsko-pomorskie', 'Wojewoda Kujawsko-Pomorski', 'Kujawsko-Pomorski Urząd Wojewódzki w Bydgoszczy'),
    'lubelski': ('lubelskie', 'Wojewoda Lubelski', 'Lubelski Urząd Wojewódzki w Lublinie'),
    'lubuski': ('lubuskie', 'Wojewoda Lubuski', 'Lubuski Urząd Wojewódzki w Gorzowie Wielkopolskim'),
    'lodzki': ('lodzkie', 'Wojewoda Łódzki', 'Łódzki Urząd Wojewódzki w Łodzi'),
    'malopolski': ('malopolskie', 'Wojewoda Małopolski', 'Małopolski Urząd Wojewódzki w Krakowie'),
    'mazowiecki': ('mazowieckie', 'Wojewoda Mazowiecki', 'Mazowiecki Urząd Wojewódzki w Warszawie'),
    'opolski': ('opolskie', 'Wojewoda Opolski', 'Opolski Urząd Wojewódzki w Opolu'),
    'podkarpacki': ('podkarpackie', 'Wojewoda Podkarpacki', 'Podkarpacki Urząd Wojewódzki w Rzeszowie'),
    'podlaski': ('podlaskie', 'Wojewoda Podlaski', 'Podlaski Urząd Wojewódzki w Białymstoku'),
    'pomorski': ('pomorskie', 'Wojewoda Pomorski', 'Pomorski Urząd Wojewódzki w Gdańsku'),
    'slaski': ('slaskie', 'Wojewoda Śląski', 'Śląski Urząd Wojewódzki w Katowicach'),
    'swietokrzyski': ('swietokrzyskie', 'Wojewoda Świętokrzyski', 'Świętokrzyski Urząd Wojewódzki w Kielcach'),
    'warminsko-mazurski': ('warminsko-mazurskie', 'Wojewoda Warmińsko-Mazurski', 'Warmińsko-Mazurski Urząd Wojewódzki w Olsztynie'),
    'wielkopolski': ('wielkopolskie', 'Wojewoda Wielkopolski', 'Wielkopolski Urząd Wojewódzki w Poznaniu'),
    'zachodniopomorski': ('zachodniopomorskie', 'Wojewoda Zachodniopomorski', 'Zachodniopomorski Urząd Wojewódzki w Szczecinie'),
}


@dataclass(frozen=True)
class VoivodeRow:
    region: str
    canonical_name: str
    role_title: str
    organisation: str
    source_url: str


class _VisibleLines(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self._buffer, self._ignored = [], [], 0

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
        text = ' '.join(''.join(self._buffer).split())
        self._buffer.clear()
        if text:
            self.lines.append(text)


def _visible_lines(html):
    parser = _VisibleLines()
    parser.feed(html)
    parser.close()
    return parser.lines


def get_rows(*, http_get=requests.get):
    try:
        response = http_get(KPRM_VOIVODES_URL, timeout=20, headers={'Accept': 'text/html'})
        response.raise_for_status()
        html = response.text
    except (requests.RequestException, AttributeError) as exc:
        raise CommandError(f'Nie udało się pobrać oficjalnej listy wojewodów KPRM: {exc}') from exc
    if not isinstance(html, str) or not html.strip():
        raise CommandError('Oficjalna strona KPRM zwróciła pustą odpowiedź HTML.')
    rows = {}
    for line in _visible_lines(html):
        match = _ROW_RE.match(line)
        if not match:
            continue
        name = match.group('name').strip()
        config = VOIVODE_CONFIG.get(slugify(match.group('region')))
        if not config:
            continue
        if not _NAME_RE.match(name) or len(name.split()) < 2:
            raise CommandError('Oficjalna lista KPRM zawiera niejednoznaczne imię wojewody; import przerwany.')
        region, title, organisation = config
        row = VoivodeRow(region, name, title, organisation, KPRM_VOIVODES_URL)
        prior = rows.get(region)
        if prior and prior != row:
            raise CommandError('Oficjalna lista KPRM zawiera sprzeczne wpisy wojewody; import przerwany.')
        rows[region] = row
    expected = {config[0] for config in VOIVODE_CONFIG.values()}
    if set(rows) != expected:
        raise CommandError(f'Oficjalna lista KPRM nie potwierdza pełnych 16 wojewodów (znaleziono {len(rows)}); import przerwany.')
    return list(rows.values())
