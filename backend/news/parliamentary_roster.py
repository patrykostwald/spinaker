"""Official parliamentary roster adapters. They only stage public roster facts."""
from dataclasses import dataclass
from html import unescape
import re
from typing import Iterable
from urllib.parse import urljoin

import requests
from django.core.management.base import CommandError

SEJM_URL = 'https://api.sejm.gov.pl/sejm/term10/MP'
SENAT_URL = 'https://www.senat.gov.pl/sklad/senatorowie/'
EP_CURRENT_URL = 'https://data.europarl.europa.eu/api/v2/meps/show-current?format=application%2Fld%2Bjson'
EP_PERSON_URL = 'https://data.europarl.europa.eu/person/'

# A Senator profile URL carries both the stable profile ID and the current
# Senate term.  The list page is the official authority for which profiles
# are current; do not construct or guess profiles from names.
_SENATOR_PROFILE_RE = re.compile(
    r'''href\s*=\s*["'](?P<href>[^"']*/sklad/senatorowie/senator(?:%2C|,)(?P<id>\d+)(?:%2C|,)(?P<term>\d+)(?:%2C|,)[^"']+\.html)["'][^>]*>(?P<name>.*?)</a>''',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r'<[^>]+>')
_INACTIVE_SENATOR_RE = re.compile(r'\b(?:mandat\s+wygasł|zmarł)\b', re.IGNORECASE)
_SENAT_MIN_CURRENT_ROWS = 50


@dataclass(frozen=True)
class RosterRow:
    external_id: str
    full_name: str
    club: str = ''
    district: str = ''
    profile_url: str = ''
    source_url: str = ''
    active: bool = True


def _string(value):
    return str(value or '').strip()


def _get_json(url, *, http_get=requests.get, accept='application/json'):
    try:
        response = http_get(url, timeout=20, headers={'Accept': accept})
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CommandError(f'Nie udało się pobrać oficjalnej listy: {exc}') from exc


def _get_html(url, *, http_get=requests.get):
    try:
        response = http_get(url, timeout=20, headers={'Accept': 'text/html'})
        response.raise_for_status()
        text = response.text
    except (requests.RequestException, AttributeError) as exc:
        raise CommandError(f'Nie udało się pobrać oficjalnej listy: {exc}') from exc
    if not isinstance(text, str) or not text.strip():
        raise CommandError('Oficjalna strona Senatu zwróciła pustą odpowiedź HTML.')
    return text


def sejm_rows(*, http_get=requests.get) -> list[RosterRow]:
    payload = _get_json(SEJM_URL, http_get=http_get)
    if not isinstance(payload, list):
        raise CommandError('Oficjalne API Sejmu zwróciło nieoczekiwany format listy.')
    rows = []
    for item in payload:
        if not isinstance(item, dict) or item.get('active') is not True:
            continue
        external_id = _string(item.get('id'))
        full_name = _string(item.get('firstLastName') or item.get('name'))
        if not external_id or not full_name:
            raise CommandError('Oficjalne API Sejmu zwróciło aktywną pozycję bez id lub imienia i nazwiska.')
        profile = _string(item.get('profileUrl'))
        if not profile:
            profile = f'https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id={external_id}'
        rows.append(RosterRow(external_id=external_id, full_name=full_name,
            club=_string(item.get('club')), district=_string(item.get('districtName') or item.get('district')),
            profile_url=profile, source_url=SEJM_URL, active=True))
    return rows


def ep_rows(*, http_get=requests.get) -> list[RosterRow]:
    """Stage today's Polish MEPs from the official EP JSON-LD roster.

    The compact endpoint exposes the EU political group, not a national-party
    field. ``club`` therefore contains only that official group value; no
    affiliation is inferred.
    """
    payload = _get_json(EP_CURRENT_URL, http_get=http_get, accept='application/ld+json')
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise CommandError('Oficjalne API Parlamentu Europejskiego zwróciło nieoczekiwany format JSON-LD.')

    rows = []
    for item in payload['data']:
        if not isinstance(item, dict):
            raise CommandError('Oficjalne API Parlamentu Europejskiego zawiera nieprawidłową pozycję listy.')
        if _string(item.get('api:country-of-representation')) != 'PL':
            continue
        external_id = _string(item.get('identifier'))
        full_name = _string(item.get('label'))
        if not external_id or not full_name:
            raise CommandError('Oficjalne API Parlamentu Europejskiego zwróciło polską pozycję bez identifier lub label.')
        rows.append(RosterRow(
            external_id=external_id,
            full_name=full_name,
            club=_string(item.get('api:political-group')),
            district='PL',
            profile_url=f'{EP_PERSON_URL}{external_id}',
            source_url=EP_CURRENT_URL,
            active=True,
        ))
    if not rows:
        raise CommandError('Oficjalne API Parlamentu Europejskiego nie zwróciło aktywnych posłów reprezentujących Polskę.')
    return rows


def _clean_html(value):
    return ' '.join(unescape(_TAG_RE.sub(' ', value)).split())


def senat_rows(*, http_get=requests.get) -> list[RosterRow]:
    """Parse the current official Senate list without following profile links.

    The Senate page also retains former senators.  Each list item is therefore
    evaluated through the text until the next official profile link; entries
    explicitly marked ``mandat wygasł`` or ``zmarł`` are not staged as active.
    The minimum count and single-term guard deliberately fail closed if the
    public HTML contract changes.
    """
    html = _get_html(SENAT_URL, http_get=http_get)
    matches = list(_SENATOR_PROFILE_RE.finditer(html))
    if not matches:
        raise CommandError('Oficjalna strona Senatu nie zawiera rozpoznawalnych profili senatorów.')

    terms = {match.group('term') for match in matches}
    if len(terms) != 1:
        raise CommandError('Oficjalna strona Senatu zawiera profile z więcej niż jednej kadencji; import przerwany.')

    rows_by_id = {}
    for index, match in enumerate(matches):
        # The official status label belongs to the current list item and occurs
        # before the next senator profile on the list page.
        item_end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        item_text = _clean_html(html[match.start():item_end])
        if _INACTIVE_SENATOR_RE.search(item_text):
            continue

        external_id = _string(match.group('id'))
        full_name = _clean_html(match.group('name'))
        profile_url = urljoin(SENAT_URL, unescape(match.group('href')))
        if not external_id or not full_name:
            raise CommandError('Oficjalna strona Senatu zwróciła profil bez identyfikatora lub imienia i nazwiska.')
        candidate = RosterRow(
            external_id=external_id, full_name=full_name, profile_url=profile_url,
            source_url=SENAT_URL, active=True,
        )
        existing = rows_by_id.get(external_id)
        if existing and existing != candidate:
            raise CommandError('Oficjalna strona Senatu zawiera sprzeczne dane dla tego samego profilu; import przerwany.')
        rows_by_id[external_id] = candidate

    rows = list(rows_by_id.values())
    if len(rows) < _SENAT_MIN_CURRENT_ROWS:
        raise CommandError(
            f'Oficjalna strona Senatu zwróciła tylko {len(rows)} aktywnych profili; import przerwany dla bezpieczeństwa.'
        )
    return rows


def unavailable_adapter(source):
    labels = {}
    raise CommandError(
        f'Importer {labels[source]} jest przygotowany jako adapter, ale nie ma jeszcze zatwierdzonego, '
        'stabilnego oficjalnego endpointu JSON. Nie wykonano żadnego importu ani zmian w bazie.'
    )


def get_rows(source: str, *, http_get=requests.get) -> Iterable[RosterRow]:
    if source == 'sejm':
        return sejm_rows(http_get=http_get)
    if source == 'senat':
        return senat_rows(http_get=http_get)
    if source == 'ep':
        return ep_rows(http_get=http_get)
    raise CommandError('Źródło musi być jednym z: sejm, senat, ep.')
