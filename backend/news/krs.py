"""Klient oficjalnego API KRS (api-krs.ms.gov.pl, Ministerstwo Sprawiedliwości) — bez danych osobowych.

API zwraca dane osób zamaskowane: „J**** O*****” (pierwsza litera i długość imienia i nazwiska), PESEL też
zamaskowany. Nie zapisujemy żadnych danych osób z KRS — używamy ich tylko w pamięci, żeby sprawdzić, czy w organie
podmiotu jest osoba o zgodnych inicjałach i długości imienia i nazwiska, na podanej funkcji. Zapisujemy wyłącznie
dane podmiotu (nazwa, numer KRS, forma prawna) i — przy dopasowaniu — funkcję, organ i daty wpisów.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

API = 'https://api-krs.ms.gov.pl/api/krs/{kind}/{krs}'
HEADERS = {'User-Agent': 'spin.clinic KRS check (+https://spin.clinic/o-nas)'}
# Oficjalna wyszukiwarka KRS nie ma stałych linków do podmiotów — linkujemy do publicznej strony podmiotu
# z danymi KRS (nadpisz w KRS_PUBLIC_URL, np. innym serwisem); urzędowy odpis zostaje jako dowód przy relacji.
PUBLIC_URL = os.environ.get('KRS_PUBLIC_URL', '').strip() or 'https://rejestr.io/krs/{krs_int}'

STATE_OWNERS = ('SKARB PAŃSTWA',)
MUNICIPAL_OWNERS = ('GMINA ', 'MIASTO ', 'POWIAT ', 'WOJEWÓDZTWO ', 'MIASTO STOŁECZNE')


@dataclass
class Person:
    """Zamaskowany wpis osoby z KRS — tylko w pamięci, nigdy nie zapisywany."""
    surname: str
    first: str
    second: str
    function: str
    organ: str
    since: date | None
    until: date | None


@dataclass
class Extract:
    krs: str
    register: str
    name: str
    legal_form: str
    kind: str
    owners: list[str] = field(default_factory=list)  # nazwy wspólników/założycieli będących instytucjami (np. SKARB PAŃSTWA)
    persons: list[Person] = field(default_factory=list)

    @property
    def official_url(self) -> str:
        return API.format(kind='OdpisPelny', krs=self.krs) + f'?rejestr={self.register}&format=json'

    @property
    def public_url(self) -> str:
        return PUBLIC_URL.format(krs=self.krs, krs_int=int(self.krs))

    @property
    def sector(self) -> str:
        joined = ' | '.join(self.owners).upper()
        if any(owner in joined for owner in STATE_OWNERS):
            return 'state'
        if any(owner in joined for owner in MUNICIPAL_OWNERS):
            return 'municipal'
        return 'ngo' if self.kind in ('foundation', 'association') else 'unknown'


def normalize_krs(value) -> str:
    digits = re.sub(r'\D', '', str(value or ''))
    return digits.zfill(10) if 0 < len(digits) <= 10 else ''


def _current(values: list) -> dict:
    """Aktualna wartość pola z historią (bez nrWpisuWykr), a gdy wszystkie wykreślone — ostatnia."""
    if not isinstance(values, list) or not values:
        return {}
    live = [value for value in values if isinstance(value, dict) and not value.get('nrWpisuWykr')]
    return (live or values)[-1]


def _kind(legal_form: str) -> str:
    form = legal_form.upper()
    if 'FUNDACJA' in form:
        return 'foundation'
    if 'STOWARZYSZENIE' in form:
        return 'association'
    if 'SPÓŁKA' in form or 'SPOLKA' in form:
        return 'company'
    return 'other'


def _entry_dates(header: dict) -> dict[str, date]:
    dates = {}
    for entry in header.get('wpis') or []:
        try:
            dates[str(entry.get('numerWpisu'))] = datetime.strptime(entry.get('dataWpisu', ''), '%d.%m.%Y').date()
        except ValueError:
            continue
    return dates


ORGAN_KEYS = {'reprezentacja': 'zarząd', 'organNadzoru': 'organ nadzoru', 'prokurenci': 'prokura',
              'komitetZalozycielski': 'komitet założycielski', 'organSprawujacyNadzor': 'organ nadzoru'}


def _persons(node, organ: str, dates: dict, out: list) -> None:
    if isinstance(node, list):
        for item in node:
            _persons(item, organ, dates, out)
        return
    if not isinstance(node, dict):
        return
    if 'nazwaOrganu' in node:
        organ = str(_current(node['nazwaOrganu']).get('nazwaOrganu') or organ).lower()
    if 'nazwisko' in node and 'imiona' in node:
        surname_entry = _current(node['nazwisko'])
        names = _current(node['imiona']).get('imiona') or {}
        function = _current(node.get('funkcjaWOrganie') or []).get('funkcjaWOrganie') or ''
        out.append(Person(
            surname=str((surname_entry.get('nazwisko') or {}).get('nazwiskoICzlon') or ''),
            first=str(names.get('imie') or ''), second=str(names.get('imieDrugie') or ''),
            function=str(function), organ=organ,
            since=dates.get(str(surname_entry.get('nrWpisuWprow'))), until=dates.get(str(surname_entry.get('nrWpisuWykr')))))
        return
    for key, value in node.items():
        _persons(value, ORGAN_KEYS.get(key, organ), dates, out)


OWNER_SECTIONS = ('wspolni', 'akcjonariusz', 'zalozyc', 'fundator')


def _owners(section: dict) -> list[str]:
    """Nazwy instytucji-wspólników (nie osób): np. SKARB PAŃSTWA, GMINA MIASTA… — do ustalenia, czy spółka jest publiczna."""
    found = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if 'nazwisko' in node:
                return  # osoba fizyczna — pomijamy
            for key, value in node.items():
                if key in ('nazwa', 'nazwaPodmiotu') and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
    # Tylko sekcje wspólników, akcjonariusza, założycieli i fundatorów — nie oddziały ani adresy.
    for key, value in section.items():
        if any(word in key.lower() for word in OWNER_SECTIONS):
            walk(value)
    return found


def parse(krs: str, register: str, data: dict) -> Extract:
    odpis = data.get('odpis') or {}
    body = odpis.get('dane') or {}
    header = odpis.get('naglowekP') or odpis.get('naglowekA') or {}
    subject = (body.get('dzial1') or {}).get('danePodmiotu') or {}
    name = str(_current(subject.get('nazwa') or []).get('nazwa') or '')
    legal_form = str(_current(subject.get('formaPrawna') or []).get('formaPrawna') or '')
    extract = Extract(krs=krs, register=register, name=name, legal_form=legal_form, kind=_kind(legal_form))
    extract.owners = _owners({k: v for k, v in (body.get('dzial1') or {}).items() if k != 'danePodmiotu'})
    persons: list[Person] = []
    dates = _entry_dates(header)
    for key in ('dzial1', 'dzial2'):
        _persons(body.get(key) or {}, '', dates, persons)
    extract.persons = persons
    return extract


def fetch(krs: str, full: bool = True, timeout: float = 30) -> Extract | None:
    """Odpis z oficjalnego API: najpierw rejestr przedsiębiorców, potem stowarzyszeń i fundacji. None — brak podmiotu."""
    krs = normalize_krs(krs)
    if not krs:
        return None
    for register in ('P', 'S'):
        url = API.format(kind='OdpisPelny' if full else 'OdpisAktualny', krs=krs)
        try:
            response = requests.get(url, params={'rejestr': register, 'format': 'json'}, headers=HEADERS, timeout=(5, timeout))
        except requests.RequestException as error:
            logger.warning('KRS %s: %s', krs, type(error).__name__)
            return None
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            logger.warning('KRS %s: http %s', krs, response.status_code)
            return None
        try:
            return parse(krs, register, response.json())
        except ValueError:
            return None
    return None


def _upper(value: str) -> str:
    return unicodedata.normalize('NFC', value).strip().upper()


def mask_fits(mask: str, value: str) -> bool:
    """„M***********” pasuje do „MORAWIECKI”? — ta sama pierwsza litera i ta sama długość."""
    mask, value = _upper(mask), _upper(value)
    return bool(mask and value and mask[0] == value[0] and len(mask) == len(value))


def split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in re.split(r'\s+', full_name.strip()) if part]
    return (parts[0], parts[-1]) if len(parts) >= 2 else ('', '')


def matching_persons(extract: Extract, full_name: str) -> list[Person]:
    first, surname = split_name(full_name)
    if not first:
        return []
    return [person for person in extract.persons
            if mask_fits(person.surname, surname) and (mask_fits(person.first, first) or mask_fits(person.second, first))]


STOP_WORDS = {'SPÓŁKA', 'AKCYJNA', 'Z', 'OGRANICZONĄ', 'ODPOWIEDZIALNOŚCIĄ', 'SP.', 'S.A.', 'SA', 'O.O.', 'ZOO', 'FUNDACJA',
              'STOWARZYSZENIE', 'W', 'I', 'IM.', 'IMIENIA', 'POLSKA', 'POLSKI', 'POLSKIE', 'GRUPA', 'SPÓŁKA-'}


def _tokens(name: str) -> set[str]:
    return {token for token in re.findall(r'[\wĄĆĘŁŃÓŚŹŻ.-]+', _upper(name).replace('"', ' ')) if token not in STOP_WORDS and len(token) > 1}


def names_match(claimed: str, registered: str) -> bool:
    """Czy nazwa podana przez źródło to ten sam podmiot co w KRS (np. „Fundacja Orlen” ~ „FUNDACJA ORLEN”)."""
    want, have = _tokens(claimed), _tokens(registered)
    if not want or not have:
        return False
    # Skrót nazwy: „WOŚP” = Wielka Orkiestra Świątecznej Pomocy.
    acronym = ''.join(token[0] for token in re.findall(r'[\wĄĆĘŁŃÓŚŹŻ]+', _upper(registered)) if token not in STOP_WORDS)
    if any(len(token) >= 3 and token in acronym for token in want):
        want = {token for token in want if token not in acronym}
        if not want:
            return True
    return len(want & have) / len(want) >= 0.5


def same_organ(claimed: str, organ: str, function: str) -> bool:
    """Zgodność rodzaju organu: zarząd/prezes vs rada/nadzór vs prokura vs założyciel."""
    claimed, found = _upper(claimed), _upper(f'{organ} {function}')
    groups = (('ZARZĄD', 'PREZES', 'WICEPREZES', 'DYREKTOR'), ('RAD', 'NADZ', 'KOMISJ'), ('PROKUR',), ('ZAŁOŻYCIEL', 'FUNDATOR', 'KOMITET'))
    for group in groups:
        if any(word in claimed for word in group):
            return any(word in found for word in group)
    return False
