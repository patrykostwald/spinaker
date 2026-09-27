"""Kariera sejmowa z oficjalnego API Sejmu (api.sejm.gov.pl): każda kadencja, w której osoba była posłem — z datami i klubem.

Źródło podaje listy posłów każdej kadencji. Datę urodzenia z tych list używamy WYŁĄCZNIE w pamięci, żeby odróżnić
imienników (np. Kornel i Mateusz Morawiecki, dwóch posłów o tym samym nazwisku w różnych latach) — nie zapisujemy jej.
Zapisujemy: kadencję, daty mandatu (ślubowanie — wygaśnięcie albo koniec kadencji) i klub w tej kadencji.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date

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


def load() -> tuple[list[dict], dict[int, list[dict]]]:
    terms = [term for term in _get('term') if isinstance(term, dict) and term.get('num')]
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


def run(figures=None) -> dict:
    terms, members = load()
    if not members:
        return {'status': 'api_unavailable'}
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
