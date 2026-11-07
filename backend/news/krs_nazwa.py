"""Wyszukiwanie podmiotów w KRS po nazwie przez UPRAWNIONY interfejs (6.11.2026).

Otwarte API KRS (api-krs.ms.gov.pl) wyszukuje tylko po numerze. Wyszukiwarka KRS w przeglądarce ma własny interfejs z kluczem wbudowanym
w stronę; **nie używamy tego klucza ani nagłówków origin/referer aplikacji urzędu**. Ten klient działa wyłącznie, gdy właściciel
ustawi w .env.production adres i klucz uzyskany legalnie (odpowiedź Ministerstwa na wniosek docs/WNIOSEK_MS_WYSZUKIWANIE_KRS_PO_NAZWIE.md
albo komercyjny odpowiednik z takim samym formatem):
  KRS_NAME_SEARCH_URL        pełny adres usługi (bez niego klient jest wyłączony)
  KRS_NAME_SEARCH_APIKEY     klucz (opcjonalny); KRS_NAME_SEARCH_APIKEY_HEADER nazwa nagłówka (domyślnie apikey)
Format zapytania i odpowiedzi z obserwacji publicznej strony (pola, nie klucze): zapytanie {rejestr, podmiot{nazwa, wojewodztwo, powiat, gmina,
miejscowosc, dokladnaNazwa}, paginacja}, odpowiedź {listaPodmiotow:[{nazwa, miejscowosc, numer (KRS bez zer), typRejestru, czyOPP, czyUpadlosc}]}.
Grzeczność: najwyżej 1 zapytanie na sekundę globalnie, cache 24 h (także „nie ma”), identyfikowalny User-Agent, tylko dane podmiotów.
"""
import hashlib
import json
import logging
import os
import time

import requests
from django.core.cache import cache

from news import dopasowanie_nazw as dn

logger = logging.getLogger(__name__)
HEADERS = {'User-Agent': 'przeszlosc.today KRS name lookup (+https://przeszlosc.today/przeszlosc/jak-to-dziala)',
           'Accept': 'application/json', 'Content-Type': 'application/json'}
CACHE_TTL = 24 * 3600
MIN_INTERVAL = 1.0
LOCK_KEY = 'krs_nazwa:interval'


def url():
    return os.environ.get('KRS_NAME_SEARCH_URL', '').strip()


def enabled():
    return bool(url())


def _headers():
    headers = dict(HEADERS)
    key = os.environ.get('KRS_NAME_SEARCH_APIKEY', '').strip()
    if key:
        headers[os.environ.get('KRS_NAME_SEARCH_APIKEY_HEADER', 'apikey').strip() or 'apikey'] = key
    return headers


def request_body(name, city='', voivodeship='', exact=False):
    return {'rejestr': ['P', 'S'], 'podmiot': {'krs': None, 'nip': None, 'regon': None, 'nazwa': name, 'wojewodztwo': voivodeship or None,
            'powiat': None, 'gmina': None, 'miejscowosc': city or None, 'dokladnaNazwa': bool(exact)},
            'status': {'czyOpp': None, 'czyWpisDotyczacyPostepowaniaUpadlosciowego': None, 'dataPrzyznaniaStatutuOppOd': None,
                       'dataPrzyznaniaStatutuOppDo': None},
            'paginacja': {'liczbaElementowNaStronie': 100, 'maksymalnaLiczbaWynikow': 100, 'numerStrony': 1}}


def parse(payload):
    """[{'krs','name','city','registers','opp','bankruptcy'}] bez powtórzeń (ten sam numer w P i S to jeden podmiot)."""
    from news.krs import normalize_krs
    merged = {}
    for row in (payload or {}).get('listaPodmiotow') or []:
        if not isinstance(row, dict):
            continue
        number = normalize_krs(row.get('numer'))
        if not number or not row.get('nazwa'):
            continue
        hit = merged.setdefault(number, {'krs': number, 'name': str(row['nazwa']).strip(), 'city': str(row.get('miejscowosc') or '').strip(),
                                         'registers': [], 'opp': bool(row.get('czyOPP')), 'bankruptcy': bool(row.get('czyUpadlosc'))})
        register = str(row.get('typRejestru') or '')
        if register and register not in hit['registers']:
            hit['registers'].append(register)
    return list(merged.values())


def _wait():
    """Globalny odstęp między zapytaniami (cache.add jako zamek na MIN_INTERVAL)."""
    for _ in range(30):
        if cache.add(LOCK_KEY, 1, timeout=max(1, int(MIN_INTERVAL + 0.999))):
            return True
        time.sleep(0.2)
    return False


def search(name, city='', voivodeship='', exact=False):
    """(lista kandydatów, status ok|error|disabled). Wyniki z cache 24 h."""
    if not enabled():
        return [], 'disabled'
    key = 'krs_nazwa:' + hashlib.sha256(json.dumps([dn.normalize_name(name), dn.fold(city), dn.fold(voivodeship), bool(exact)]).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached, 'ok'
    if not _wait():
        return [], 'error'
    try:
        response = requests.post(url(), json=request_body(name, city, voivodeship, exact), headers=_headers(), timeout=(5, 30))
    except requests.RequestException as error:
        logger.warning('KRS po nazwie: %s', type(error).__name__)
        return [], 'error'
    if response.status_code != 200:
        logger.warning('KRS po nazwie: http %s', response.status_code)
        return [], 'error'
    try:
        found = parse(response.json())
    except ValueError:
        return [], 'error'
    cache.set(key, found, CACHE_TTL)
    return found, 'ok'


def resolve(name, city='', voivodeship='', postal_code=''):
    """Dopasowanie nazwy beneficjenta do podmiotu z KRS według zasady dwóch danych; None, gdy brak albo niejednoznaczne."""
    found, status = search(name, city, voivodeship)
    if status != 'ok':
        return {'status': status}
    kind, hit, conflict = dn.choose(found, name, city=city, postal_code=postal_code, voivodeship=voivodeship)
    if kind is None:
        return {'status': 'ok', 'class': None, 'candidates': len(found)}
    return {'status': 'ok', 'class': kind, 'conflict': conflict, 'krs_number': hit['krs'], 'name': hit['name'], 'city': hit['city'],
            'registers': hit['registers'], 'opp': hit['opp'], 'bankruptcy': hit['bankruptcy']}
