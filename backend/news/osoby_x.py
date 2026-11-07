"""Konta X osób publicznych: jeden plik news/data/osoby_x.csv dla spin.clinic i przeszłość.today.

Każdy wiersz to jedno konto jednej osoby ze źródłem: oficjalna strona (gov.pl, prezydent.pl, partia, PE) albo
Wikidata (właściwość P2002 „X username”, CC0, przez SPARQL). Bez skrobania X.com. Konto bez źródła nie trafia do pliku.

Dopasowanie do osób z naszych danych, od najpewniejszego:
1. identyfikator PE (P1186) albo profil posła na sejm.gov.pl (P973) — dokładny klucz, pewność „wysoka”;
2. imię i nazwisko (etykieta polska w Wikidata; nazwiska PE pisane wielkimi literami sprowadzamy do zwykłej
   pisowni, wynik porównujemy bez polskich znaków i wielkości liter) — tylko gdy w Wikidata jest dokładnie jeden człowiek
   z obywatelstwem polskim i stanowiskiem albo partią o tym nazwisku, a u nas jedna osoba; pewność „wysoka”, gdy ma
   też stanowisko (P39), inaczej „średnia”.
Konto z datą końca (P582) albo z rangą „deprecated” oznaczamy jako byłe. Import na produkcji bierze tylko konta
aktualne o pewności „wysoka”, i tylko po dokładnym kluczu osoby (osoba_id = PublicFigure.import_key).
"""
import csv
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent / 'data'
CSV_PATH = DATA / 'osoby_x.csv'
CAREER_PATH = DATA / 'sejm_career.json'
ROSTER_PATH = Path(__file__).resolve().parent.parent / 'tmp' / 'x_kandydatury_osoby_publiczne_2026-09-24.csv'
FIELDS = ['imie_nazwisko', 'osoba_id', 'konto', 'zrodlo', 'data_sprawdzenia', 'pewnosc', 'stan_konta', 'uwagi']
HIGH, MEDIUM = 'wysoka', 'średnia'
CURRENT, FORMER = 'aktualne', 'byłe'
WIKIDATA = 'https://query.wikidata.org/sparql'
USER_AGENT = 'spin.clinic/1.0 (kontakt@spin.clinic)'
HANDLE = re.compile(r'[A-Za-z0-9_]{1,15}')
QID = re.compile(r'https?://www\.wikidata\.org/entity/(Q\d{1,12})')
SEJM_PROFILE = re.compile(r'sejm\.gov\.pl/sejm10\.nsf/posel\.xsp\?id=0*(\d{1,4})', re.I)
DEPRECATED = 'http://wikiba.se/ontology#DeprecatedRank'
PREFERRED = 'http://wikiba.se/ontology#PreferredRank'
NAME_BATCH = 80


def fold(text):
    """„Marek JAKUBIAK”, „marek jakubiak”, „Władysław Kosiniak-Kamysz” → klucz bez znaków i wielkości liter."""
    text = unicodedata.normalize('NFKD', (text or '').replace('ł', 'l').replace('Ł', 'L'))
    text = ''.join(c for c in text if not unicodedata.combining(c)).casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def display_name(name):
    """Dane PE piszą nazwiska wielkimi literami („Janusz LEWANDOWSKI”) — etykieta w Wikidata ma zwykłą pisownię."""
    return ' '.join(part.title() if part.isupper() and len(part) > 1 else part for part in (name or '').split())


@dataclass
class Person:
    osoba_id: str
    name: str
    roles: list = field(default_factory=list)
    aliases: set = field(default_factory=set)

    @property
    def ep_id(self):
        match = re.fullmatch(r'parliamentary:ep:(\d+)', self.osoba_id)
        return match.group(1) if match else ''

    @property
    def sejm_id(self):
        match = re.fullmatch(r'parliamentary:sejm:(\d+)', self.osoba_id)
        return match.group(1) if match else ''


def roster_id(row):
    """Klucz osoby z listy kandydatur 24.09: identyfikator PE jest dokładny, reszta to klucz listy."""
    source, external = row.get('official_roster_source', ''), (row.get('official_roster_external_id') or '').split(' | ')[0]
    if source.startswith('europarl') and external.isdigit():
        return f'parliamentary:ep:{external}'
    return f'lista-2026-09-24:{external.strip()}'


def people_from_repo():
    """Osoby z danych w repo: mandaty w Sejmie (kadencje III–X, posłowie obecni i poprzedni, w tym dzisiejsi senatorowie
    i europosłowie) oraz lista z 24.09 (rząd, wojewodowie, europosłowie, prezydent, liderzy partii)."""
    people = {}
    for entry in json.loads(CAREER_PATH.read_text(encoding='utf-8')):
        person = people.setdefault(entry['figure_key'], Person(entry['figure_key'], display_name(entry['figure_name'])))
        role = f"{entry['organisation']} ({'obecnie' if entry['status'] == 'current' else 'dawniej'})"
        if role not in person.roles:
            person.roles.append(role)
    if ROSTER_PATH.is_file():
        by_name = {fold(p.name): p for p in people.values()}
        with ROSTER_PATH.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                key, name = roster_id(row), display_name(row['public_figure_name'])
                # Ta sama osoba w dwóch spisach liczy się raz (tylko do pokrycia; konto łączymy wyłącznie po kluczu).
                person = people.get(key) or by_name.get(fold(name))
                if person is None:
                    person = people[key] = Person(key, name)
                    by_name[fold(name)] = person
                elif person.osoba_id != key:
                    person.aliases.add(key)
                if row.get('role_title') and row['role_title'] not in person.roles:
                    person.roles.append(row['role_title'])
    return list(people.values())


def people_from_db():
    from news.political_models import PublicFigure
    return [Person(f.import_key or f'pk:{f.pk}', display_name(f.canonical_name), [f.role_title])
            for f in PublicFigure.objects.filter(archived=False).exclude(role_category='party').order_by('pk')]


def read_rows(path=CSV_PATH):
    if not Path(path).is_file():
        return []
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_rows(rows, path=CSV_PATH):
    seen, unique = set(), []
    for row in rows:
        key = (row['osoba_id'], row['konto'].casefold())
        if key not in seen:
            seen.add(key)
            unique.append({name: row.get(name, '') for name in FIELDS})
    unique.sort(key=lambda r: (fold(r['imie_nazwisko']), r['osoba_id'], r['stan_konta'] != CURRENT, r['konto'].casefold()))
    with Path(path).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(unique)
    return unique


# --- Wikidata --------------------------------------------------------------------------------------------------

STATEMENT = ('?item p:P2002 ?st . ?st ps:P2002 ?x ; wikibase:rank ?rank . OPTIONAL { ?st pq:P582 ?end . }')


def sparql(query, post=requests.post):
    response = post(WIKIDATA, data={'query': query, 'format': 'json'}, timeout=(5, 90),
                    headers={'User-Agent': USER_AGENT, 'Accept': 'application/sparql-results+json'})
    response.raise_for_status()
    return response.json()['results']['bindings']


def _value(binding, key):
    return (binding.get(key) or {}).get('value', '')


def _accounts(bindings):
    """{QID: {handle: stan}} z wierszy z ?item ?x ?rank ?end."""
    result = {}
    for b in bindings:
        match, handle = QID.fullmatch(_value(b, 'item')), _value(b, 'x')
        if not match or not HANDLE.fullmatch(handle):
            continue
        former = bool(_value(b, 'end')) or _value(b, 'rank') == DEPRECATED
        accounts = result.setdefault(match.group(1), {})
        state = FORMER if former else (PREFERRED if _value(b, 'rank') == PREFERRED else CURRENT)
        if accounts.get(handle) not in (CURRENT, PREFERRED):
            accounts[handle] = state
    return result


def ep_query(ids):
    values = ' '.join(f'"{i}"' for i in ids)
    return f'SELECT ?item ?ep ?x ?rank ?end WHERE {{ VALUES ?ep {{ {values} }} ?item wdt:P1186 ?ep . {STATEMENT} }}'


SEJM_QUERY = ('SELECT ?item ?url ?x ?rank ?end WHERE { ?item wdt:P973 ?url . '
              'FILTER(CONTAINS(LCASE(STR(?url)), "sejm.gov.pl/sejm10.nsf/posel.xsp")) ' + STATEMENT + ' }')


def name_query(names):
    values = ' '.join(json.dumps(name, ensure_ascii=False) + '@pl' for name in names)
    return ('SELECT ?item ?label ?pl ?pos ?party ?x ?rank ?end WHERE { VALUES ?label { ' + values + ' } '
            '?item rdfs:label ?label ; wdt:P31 wd:Q5 . '
            'BIND(EXISTS { ?item wdt:P27 wd:Q36 } AS ?pl) BIND(EXISTS { ?item wdt:P39 ?anyPosition } AS ?pos) '
            'BIND(EXISTS { ?item wdt:P102 ?anyParty } AS ?party) '
            'OPTIONAL { ' + STATEMENT + ' } }')


def _rows_for(person, qid, accounts, confidence, method, today):
    rows = []
    preferred = any(state == PREFERRED for state in accounts.values())
    for handle, state in sorted(accounts.items()):
        level = confidence
        if state == CURRENT and preferred:
            level = MEDIUM  # obok konta z rangą „preferred” — zwykle starsze konto osoby
        rows.append({'imie_nazwisko': person.name, 'osoba_id': person.osoba_id, 'konto': handle,
                     'zrodlo': f'https://www.wikidata.org/wiki/{qid}', 'data_sprawdzenia': today, 'pewnosc': level,
                     'stan_konta': FORMER if state == FORMER else CURRENT,
                     'uwagi': f'Wikidata P2002; dopasowanie: {method}'})
    return rows


def collect(people, post=requests.post, today=None, pause=1.0):
    """Wiersze CSV z Wikidata dla podanych osób oraz lista osób z niejednoznacznym nazwiskiem."""
    today = today or date.today().isoformat()
    rows, matched, ambiguous = [], set(), []
    ep_people = {p.ep_id: p for p in people if p.ep_id}
    sejm_people = {p.sejm_id: p for p in people if p.sejm_id}

    ep_ids = sorted(ep_people)
    for start in range(0, len(ep_ids), NAME_BATCH):
        bindings = sparql(ep_query(ep_ids[start:start + NAME_BATCH]), post)
        by_qid = {QID.fullmatch(_value(b, 'item')).group(1): _value(b, 'ep') for b in bindings if QID.fullmatch(_value(b, 'item'))}
        for qid, accounts in _accounts(bindings).items():
            person = ep_people.get(by_qid.get(qid))
            if person and person.osoba_id not in matched:
                matched.add(person.osoba_id)
                rows += _rows_for(person, qid, accounts, HIGH, 'identyfikator PE (P1186)', today)
        time.sleep(pause)

    if sejm_people:
        bindings = sparql(SEJM_QUERY, post)
        by_qid = {}
        for b in bindings:
            item, url = QID.fullmatch(_value(b, 'item')), SEJM_PROFILE.search(_value(b, 'url'))
            if item and url:
                by_qid.setdefault(item.group(1), set()).add(url.group(1))
        for qid, accounts in _accounts(bindings).items():
            ids = by_qid.get(qid, set())
            person = sejm_people.get(next(iter(ids))) if len(ids) == 1 else None
            if person and person.osoba_id not in matched:
                matched.add(person.osoba_id)
                rows += _rows_for(person, qid, accounts, HIGH, 'profil posła X kadencji (P973)', today)
        time.sleep(pause)

    ours = {}
    for person in people:
        ours.setdefault(fold(person.name), []).append(person)
    rest = [p for p in people if p.osoba_id not in matched]
    # Etykieta w SPARQL musi być dokładna; porównanie wyniku z naszą osobą idzie już po fold().
    names = sorted({display_name(p.name) for p in rest})
    for start in range(0, len(names), NAME_BATCH):
        bindings = sparql(name_query(names[start:start + NAME_BATCH]), post)
        humans = {}
        for b in bindings:
            item = QID.fullmatch(_value(b, 'item'))
            if not item:
                continue
            human = humans.setdefault(item.group(1), {'name': fold(_value(b, 'label')), 'pl': _value(b, 'pl') == 'true',
                                                      'pos': _value(b, 'pos') == 'true', 'party': _value(b, 'party') == 'true'})
            human.setdefault('bindings', []).append(b)
        by_name = {}
        for qid, human in humans.items():
            if human['pl'] and (human['pos'] or human['party']):
                by_name.setdefault(human['name'], []).append(qid)
        for key, qids in by_name.items():
            candidates = [p for p in ours.get(key, []) if p.osoba_id not in matched]
            if len(qids) != 1 or len(candidates) != 1 or len(ours.get(key, [])) != 1:
                if candidates:
                    ambiguous.append((candidates[0], sorted(qids)))
                continue
            qid, person = qids[0], candidates[0]
            accounts = _accounts(humans[qid]['bindings']).get(qid)
            if not accounts:
                continue
            matched.add(person.osoba_id)
            level = HIGH if humans[qid]['pos'] else MEDIUM
            rows += _rows_for(person, qid, accounts, level,
                              'imię i nazwisko (jedyny polityk z obywatelstwem PL o tym nazwisku w Wikidata)', today)
        time.sleep(pause)
    return rows, ambiguous


def merge(existing, wikidata_rows):
    """Wiersze z oficjalnych stron zostają; wiersze z Wikidata zastępujemy świeżymi (import jest idempotentny)."""
    official = [row for row in existing if not row.get('zrodlo', '').startswith('https://www.wikidata.org/')]
    return official + list(wikidata_rows)


# --- Pokrycie --------------------------------------------------------------------------------------------------

def coverage(people, rows):
    """Ile osób ma aktualne konto X w pliku (po kluczu osoby albo kluczu z drugiego spisu), ile nie i kto."""
    with_account = {row['osoba_id'] for row in rows if row.get('stan_konta') == CURRENT and row.get('konto')}
    covered, missing = [], []
    for person in people:
        (covered if ({person.osoba_id} | person.aliases) & with_account else missing).append(person)
    return {'osoby': len(people), 'z_kontem': len(covered), 'bez_konta': len(missing),
            'braki': sorted(missing, key=lambda p: fold(p.name))}
