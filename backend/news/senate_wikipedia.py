"""Senatorowie XI kadencji z polskiej Wikipedii (licencja CC BY-SA), z kontrolą krzyżową dwóch tabel.

senat.gov.pl odpowiada naszemu serwerowi 403 (WAF), a Wikidata ma dane tylko o 2 z 99 senatorów
(sprawdzone 2.10.2026). Strona „Senatorowie XI kadencji…” jest aktualizowana na bieżąco i ma dwie
niezależnie redagowane tabele: (1) wybrani 15.10.2023 + wybory uzupełniające - wygaśnięte mandaty,
(2) „Stan aktualny” - przynależność klubowa. Zapis tylko wtedy, gdy obie dają ten sam zbiór osób;
każda rozbieżność zatrzymuje import (fail closed), poprzednia lista zostaje bez zmian.
"""
import re

import requests
from django.core.management.base import CommandError

WIKI_API = 'https://pl.wikipedia.org/w/api.php'
PAGE = 'Senatorowie XI kadencji Senatu Rzeczypospolitej Polskiej'
PAGE_URL = 'https://pl.wikipedia.org/wiki/' + PAGE.replace(' ', '_')
# Wikimedia wymaga opisowego User-Agenta z kontaktem.
HEADERS = {'User-Agent': 'spin.clinic roster/1.0 (https://spin.clinic/o-nas; kontakt@spin.clinic)',
           'Accept': 'application/json'}
TERM = 11
MIN_ROWS, MAX_ROWS = 90, 100
CLUB_SHORT = (('Koalicja Obywatelska', 'KO'), ('Prawo i Sprawiedliwość', 'PiS'), ('Trzecia Droga', 'TD'),
              ('Lewic', 'Lewica'), ('Nowa Polska', 'Nowa Polska - Centrum'), ('Rozwój Plus', 'Rozwój Plus'),
              ('niezrzesz', 'niezrzeszeni'))
_REF = re.compile(r'<ref[^>/]*/>|<ref[^>]*>.*?</ref>', re.S)
_LINK = re.compile(r'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]')
_DISTRICT = re.compile(r'Okręg wyborczy nr (\d{1,3}) do Senatu')


def fetch_wikitext(*, http_get=requests.get):
    try:
        response = http_get(WIKI_API, params={'action': 'parse', 'page': PAGE, 'prop': 'wikitext|revid',
                                              'format': 'json', 'formatversion': 2},
                            headers=HEADERS, timeout=(5, 30))
        response.raise_for_status()
        payload = response.json()['parse']
        return payload['wikitext'], payload.get('revid')
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        raise CommandError(f'Wikipedia: lista senatorów niedostępna ({type(error).__name__}).') from error


def section(text, start, end=None):
    """Treść między nagłówkiem zawierającym `start` a nagłówkiem zawierającym `end`."""
    head = re.search(r'^=+\s*' + re.escape(start) + r'[^\n]*=+\s*$', text, re.M)
    if not head:
        raise CommandError(f'Wikipedia: brak sekcji „{start}”; format strony się zmienił.')
    rest = text[head.end():]
    if end:
        stop = re.search(r'^=+\s*' + re.escape(end), rest, re.M)
        rest = rest[:stop.start()] if stop else rest
    return rest


def person(raw):
    """[[Tytuł (polityk)|Imię Nazwisko]] -> (tytuł strony, imię i nazwisko)."""
    title, label = raw
    title = title.strip()
    name = (label or re.sub(r'\s*\([^)]*\)$', '', title)).strip()
    return title, name


def first_person(chunk):
    for match in _LINK.finditer(_REF.sub('', chunk)):
        if not match.group(1).startswith(('Plik:', 'File:', 'Okręg wyborczy', 'Wybory ')):
            return person(match.groups())
    return None


def table_rows(block):
    return [chunk for chunk in re.split(r'\n\|-[^\n]*', block) if _DISTRICT.search(chunk)]


def elected(text):
    seats = {}
    for name in ('Senatorowie wybrani 15 października 2023', 'Senatorowie wybrani w wyborach uzupełniających'):
        stop = 'Senatorowie wybrani w wyborach uzupełniających' if '2023' in name else 'Senatorowie, których mandat'
        for chunk in table_rows(section(text, name, stop)):
            sort = re.search(r'\{\{sort\|[^|]*\|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', chunk)
            who = person(sort.groups()) if sort else first_person(chunk)
            if not who:
                raise CommandError('Wikipedia: wiersz senatora bez nazwiska.')
            seats.setdefault(int(_DISTRICT.search(chunk).group(1)), []).append(who)
    return seats


def expired(text):
    block = section(text, 'Senatorowie, których mandat wygasł', 'Przynależność klubowa')
    return {who[0] for chunk in re.split(r'\n\|-[^\n]*', block) if (who := first_person(chunk)) and '{{Dts' in chunk}


def clubs(text):
    block = section(text, 'Stan aktualny', 'Zmiany liczebności')
    result, club = {}, ''
    for line in block.splitlines():
        header = re.match(r'^!\s*colspan="?\d+"?\s*\|\s*(.+)$', line)
        if header:
            label = _LINK.sub(lambda m: m.group(2) or m.group(1), header.group(1))
            club = next((short for key, short in CLUB_SHORT if key.casefold() in label.casefold()), label.strip())
        elif line.startswith('*') and club:
            who = first_person(line)
            if who:
                result[who[0]] = (who[1], club)
    return result


def rows_from_wikitext(text, revid=None):
    from news.parliamentary_roster import RosterRow
    seats, gone, current_clubs = elected(text), expired(text), clubs(text)
    current = {}
    for district, people in seats.items():
        active = [who for who in people if who[0] not in gone]
        if len(active) > 1:
            raise CommandError(f'Wikipedia: okręg {district} ma więcej niż jednego aktywnego senatora.')
        if active:
            current[active[0][0]] = (active[0][1], district)
    if not MIN_ROWS <= len(current) <= MAX_ROWS:
        raise CommandError(f'Wikipedia: {len(current)} senatorów; oczekiwano {MIN_ROWS}-{MAX_ROWS}. Import przerwany.')
    if set(current) != set(current_clubs):
        diff = sorted(set(current) ^ set(current_clubs))
        raise CommandError('Wikipedia: tabele mandatów i klubów się różnią: ' + ', '.join(diff)[:800])
    source = PAGE_URL + (f'?oldid={revid}' if revid else '')
    return [RosterRow(external_id='plwiki:' + title.replace(' ', '_')[:120], full_name=name,
                      club=current_clubs[title][1], district=str(district),
                      profile_url='https://pl.wikipedia.org/wiki/' + title.replace(' ', '_'),
                      source_url=source, term=TERM, active=True)
            for title, (name, district) in sorted(current.items(), key=lambda item: item[1][1])]


def senat_rows(*, http_get=requests.get):
    return rows_from_wikitext(*fetch_wikitext(http_get=http_get))
