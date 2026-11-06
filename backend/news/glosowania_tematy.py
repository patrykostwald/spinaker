"""Etykieta tematu głosowania z oficjalnych powiązań Sejmu (6.11.2026, decyzja właściciela: opcja B, bez zgadywania po słowach).

Głosowanie → proces legislacyjny (API Sejmu /processes: lista głosowań procesu) → druk, tytuł i komisje z etapów procesu
(committeeCode → nazwa komisji z /committees). Głosowanie bez procesu (np. wnioski formalne, uchwały) nie dostaje etykiety:
brak etykiety znaczy „brak powiązania w naszych danych”, nigdy „bez tematu”.
"""
from django.core.cache import cache

CACHE_KEY = 'przeszlosc:glosowania-tematy:v1'
TTL = 26 * 3600
TITLE_MAX = 200


def build_index():
    """{'10/12/3': {'druk': '3300', 'tytul': ..., 'rodzaj': ..., 'komisje': ['Komisja Zdrowia']}} ze wszystkich procesów."""
    from news.public_records_models import PublicRecord
    names = {}
    for title, data in PublicRecord.objects.filter(source='committees', kind='committee').values_list('title', 'data'):
        code = (data or {}).get('code')
        if code:
            names[code] = (title or (data or {}).get('name') or code).strip()
    index = {}
    rows = PublicRecord.objects.filter(source='processes', kind='process').values_list('print_number', 'title', 'data')
    for number, title, data in rows.iterator(chunk_size=200):
        data = data or {}
        votings = data.get('votings') or []
        if not votings:
            continue
        codes = []
        for stage in data.get('stages') or []:
            code = stage.get('committeeCode')
            if code and code not in codes:
                codes.append(code)
        entry = {'druk': str(number or data.get('number') or ''),
                 'tytul': str(data.get('titleFinal') or title or '')[:TITLE_MAX],
                 'rodzaj': str(data.get('documentType') or ''),
                 'komisje': [names[c] for c in codes if c in names]}
        for voting in votings:
            key = voting.get('key')
            if key:
                index.setdefault(str(key), entry)   # głosowanie należy do jednego procesu; przy duplikacie wygrywa pierwszy
    return index


def index(rebuild=False):
    data = None if rebuild else cache.get(CACHE_KEY)
    if data is None:
        data = build_index()
        cache.set(CACHE_KEY, data, TTL)
    return data


def topic_for(term, sitting, number, idx=None):
    return (idx if idx is not None else index()).get(f'{term}/{sitting}/{number}')
