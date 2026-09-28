"""Kariera sejmowa z oficjalnego API Sejmu (api.sejm.gov.pl): każda kadencja, w której osoba była posłem — z datami i klubem.

Źródło podaje listy posłów każdej kadencji. Datę urodzenia z tych list używamy WYŁĄCZNIE w pamięci, żeby odróżnić
imienników (np. Kornel i Mateusz Morawiecki, dwóch posłów o tym samym nazwisku w różnych latach) — nie zapisujemy jej.
Zapisujemy: kadencję, daty mandatu (ślubowanie — wygaśnięcie albo koniec kadencji) i klub w tej kadencji.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

import requests
from django.db import transaction
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureRole

logger = logging.getLogger(__name__)

API = 'https://api.sejm.gov.pl/sejm'
HEADERS = {'User-Agent': 'spin.clinic career (+https://spin.clinic/o-nas)'}
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI', 12: 'XII'}
SEJM_KEY = re.compile(r'^parliamentary:sejm:(\d+)$')


def _get(path: str):
    response = requests.get(f'{API}/{path}', headers=HEADERS, timeout=(5, 60))
    response.raise_for_status()
    return response.json()


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _norm(value: str) -> str:
    value = unicodedata.normalize('NFC', value or '').strip().lower()
    return re.sub(r'\s+', ' ', value)


# Daty kadencji z api.sejm.gov.pl/sejm/term (stan z 27.09.2026) — zapas, gdy lista kadencji jest chwilowo niedostępna.
KNOWN_TERMS = [
    {'num': 1, 'from': '1991-11-25', 'to': '1993-05-31'}, {'num': 2, 'from': '1993-10-14', 'to': '1997-10-19'},
    {'num': 3, 'from': '1997-10-20', 'to': '2001-10-18'}, {'num': 4, 'from': '2001-10-19', 'to': '2005-10-18'},
    {'num': 5, 'from': '2005-10-19', 'to': '2007-11-04'}, {'num': 6, 'from': '2007-11-05', 'to': '2011-11-07'},
    {'num': 7, 'from': '2011-11-08', 'to': '2015-11-11'}, {'num': 8, 'from': '2015-11-12', 'to': '2019-11-11'},
    {'num': 9, 'from': '2019-11-12', 'to': '2023-11-12'}, {'num': 10, 'from': '2023-11-13', 'to': None, 'current': True},
]


def _terms() -> list[dict]:
    """Lista kadencji: najpierw zbiorczo, potem po jednej, a na końcu stałe daty z KNOWN_TERMS."""
    try:
        return [term for term in _get('term') if isinstance(term, dict) and term.get('num')]
    except (requests.RequestException, ValueError) as error:
        logger.warning('Sejm term list: %s — pobieram kadencje po kolei', type(error).__name__)
    terms = []
    for known in KNOWN_TERMS:
        try:
            term = _get(f"term{known['num']}")
            terms.append(term if isinstance(term, dict) and term.get('num') else known)
        except (requests.RequestException, ValueError):
            terms.append(known)
    return terms


def load() -> tuple[list[dict], dict[int, list[dict]]]:
    terms = _terms()
    members = {}
    for term in terms:
        try:
            members[term['num']] = _get(f"term{term['num']}/MP")
        except requests.RequestException as error:
            logger.warning('Sejm term %s: %s', term['num'], type(error).__name__)
    return terms, members


def _anchor(figure: PublicFigure, members: dict[int, list[dict]], current: int) -> str | None:
    """Data urodzenia z bieżącej kadencji (tylko w pamięci) — klucz do odróżnienia imienników."""
    match = SEJM_KEY.match(figure.import_key or '')
    if match:
        for mp in members.get(current, []):
            if str(mp.get('id')) == match.group(1):
                return mp.get('birthDate')
    # Poza bieżącą kadencją (np. europosłowie): tylko gdy imię i nazwisko wskazuje jedną osobę we wszystkich kadencjach.
    births = {mp.get('birthDate') for term in members.values() for mp in term if _norm(mp.get('firstLastName', '')) == _norm(figure.canonical_name)}
    return births.pop() if len(births) == 1 else None


def mandates(figure: PublicFigure, terms: list[dict], members: dict[int, list[dict]]) -> list[dict]:
    current = max(members) if members else 0
    birth = _anchor(figure, members, current)
    if not birth:
        return []
    by_num = {term['num']: term for term in terms}
    found = []
    for num, term_members in sorted(members.items()):
        for mp in term_members:
            if _norm(mp.get('firstLastName', '')) != _norm(figure.canonical_name) or mp.get('birthDate') != birth:
                continue
            term = by_num.get(num, {})
            ended = _day(mp.get('mandateExpiryDate')) or (None if term.get('current') else _day(term.get('to')))
            found.append({'term': num, 'id': mp.get('id'), 'club': mp.get('club') or '',
                          'since': _day(mp.get('oathDate')) or _day(term.get('from')), 'until': ended,
                          'active': bool(mp.get('active', True)) and bool(term.get('current'))})
    return found


@transaction.atomic
def save(figure: PublicFigure, found: list[dict]) -> int:
    saved = 0
    for mandate in found:
        key = f"sejm-term:{mandate['term']}:{mandate['id']}"
        # Bieżąca kadencja — uzupełniamy istniejącą rolę posła (z importu rejestru) zamiast dublować.
        role = None
        if mandate['active']:
            role = (figure.public_roles.filter(import_key__endswith=f"parliamentary:sejm:{mandate['id']}").first()
                    or figure.public_roles.filter(role_title='Poseł na Sejm RP', status='current').first())
        defaults = {'role_category': 'parliamentary', 'role_title': 'Poseł na Sejm RP',
                    'organisation': f"Sejm RP · {ROMAN.get(mandate['term'], mandate['term'])} kadencja",
                    'status': 'current' if mandate['active'] else 'former', 'since': mandate['since'], 'until': mandate['until'],
                    'party': mandate['club'][:64], 'evidence_url': f"{API}/term{mandate['term']}/MP/{mandate['id']}",
                    'official_profile_url': '', 'source_checked_at': timezone.now()}
        if role:
            for field in ('since', 'until', 'party', 'source_checked_at'):
                setattr(role, field, defaults[field])
            role.save(update_fields=['since', 'until', 'party', 'source_checked_at'])
        else:
            PublicFigureRole.objects.update_or_create(import_key=key, defaults={**defaults, 'public_figure': figure})
        saved += 1
    return saved


def current_term_fallback(figures) -> int:
    """Bez list posłów z API: poseł z rejestru bieżącej kadencji dostaje jej datę początku i klub z rejestru."""
    current = next(term for term in KNOWN_TERMS if term.get('current'))
    updated = 0
    for figure in figures:
        if not SEJM_KEY.match(figure.import_key or ''):
            continue
        club = figure.parliamentary_roster_entry.club if figure.parliamentary_roster_entry_id else ''
        roles = figure.public_roles.filter(role_title='Poseł na Sejm RP', status='current', since__isnull=True)
        updated += roles.update(since=_day(current['from']), party=club[:64], source_checked_at=timezone.now())
    return updated


BUNDLE = Path(__file__).resolve().parent / 'data' / 'sejm_career.json'


def export_bundle() -> int:
    """Zapisuje mandaty (kadencja, daty, klub — bez dat urodzenia) do pliku w repozytorium, na wypadek gdy serwer nie ma dostępu do API."""
    rows = []
    for role in PublicFigureRole.objects.filter(import_key__startswith='sejm-term:').select_related('public_figure'):
        rows.append({'figure_key': role.public_figure.import_key, 'figure_name': role.public_figure.canonical_name,
                     'key': role.import_key, 'organisation': role.organisation, 'status': role.status,
                     'since': role.since.isoformat() if role.since else None, 'until': role.until.isoformat() if role.until else None,
                     'party': role.party, 'evidence_url': role.evidence_url})
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
    return len(rows)


@transaction.atomic
def import_bundle() -> int:
    """Mandaty z pliku (gdy API Sejmu jest niedostępne z serwera). Profil szukamy po kluczu rejestru, potem po nazwisku."""
    if not BUNDLE.exists():
        return 0
    saved = 0
    for row in json.loads(BUNDLE.read_text(encoding='utf-8')):
        figure = (PublicFigure.objects.filter(import_key=row['figure_key']).first() if row['figure_key'] else None) \
            or PublicFigure.objects.filter(canonical_name=row['figure_name'], archived=False).first()
        if not figure:
            continue
        PublicFigureRole.objects.update_or_create(import_key=row['key'], defaults={
            'public_figure': figure, 'role_category': 'parliamentary', 'role_title': 'Poseł na Sejm RP',
            'organisation': row['organisation'], 'status': row['status'], 'since': _day(row['since']), 'until': _day(row['until']),
            'party': row['party'], 'evidence_url': row['evidence_url'], 'official_profile_url': '', 'source_checked_at': timezone.now()})
        saved += 1
    return saved


def run(figures=None) -> dict:
    terms, members = load()
    if not members:
        figures = PublicFigure.objects.filter(archived=False).select_related('parliamentary_roster_entry')
        return {'status': 'api_unavailable', 'from_bundle': import_bundle(), 'current_term_fallback': current_term_fallback(figures)}
    figures = list(figures if figures is not None else PublicFigure.objects.filter(archived=False))
    # Najpierw profile powiązane z rejestrem Sejmu; duplikat bez powiązania nie przejmuje ich mandatów.
    figures.sort(key=lambda figure: not SEJM_KEY.match(figure.import_key or ''))
    claimed: set[tuple[int, int]] = set()
    people = updated = 0
    for figure in figures:
        found = [m for m in mandates(figure, terms, members) if (m['term'], m['id']) not in claimed]
        if found:
            claimed.update((m['term'], m['id']) for m in found)
            people += 1
            updated += save(figure, found)
    return {'status': 'ok', 'figures': people, 'mandates': updated}
