#!/usr/bin/env python3
"""Offline, stdlib-only consultation-table extraction; run: python konsultacje.py.

Input is scanned line by line. Only keyword windows and candidate table regions
are retained, not full legislative texts. All offsets are 1-based source lines.
Counts are table rows, not individual demands within a row. Uncertain evidence
is retained separately and never silently turned into a successful submission.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import Path
import re
import unicodedata

STATUSES = ('uwzględniona', 'częściowo uwzględniona', 'nieuwzględniona',
            'wyjaśnienie', 'poza zakresem', 'nieustalone')


def clean(s):
    s = unicodedata.normalize('NFKC', s).replace('\u00ad', '').replace('\ufeff', '')
    # Repair spaced-out words, but never concatenate ordinary multiword names.
    s = re.sub(r'(?<!\w)(?:[^\W\d_]\s+){3,}[^\W\d_](?!\w)',
               lambda m: re.sub(r'\s+', '', m[0]), s)
    s = re.sub(r'(?<=\w)-\s+(?=\w)', '-', s)
    return re.sub(r'\s+', ' ', s).strip()


def key(s):
    return re.sub(r'[^\w]', '', clean(s).casefold())


# Exact aliases only: no fuzzy merging of legally distinct companies/branches.
ALIASES = {
    'Konfederacja Lewiatan': ['Lewiatan'],
    'Pracodawcy Rzeczypospolitej Polskiej': ['Pracodawcy RP'],
    'Ogólnopolskie Porozumienie Związków Zawodowych': ['OPZZ'],
    'Business Centre Club': ['BCC', 'Związek Pracodawców Business Centre Club'],
    'Związek Przedsiębiorców i Pracodawców': ['ZPP'],
    'Związek Banków Polskich': ['ZBP'],
    'Krajowa Rada Doradców Podatkowych': ['KRDP'],
    'Polska Rada Biznesu': ['PRB'],
    'Naczelna Izba Lekarska': ['NIL'],
    'Naczelna Rada Lekarska': ['NRL'],
    'Naczelna Izba Aptekarska': ['NIA'],
    'Naczelna Rada Aptekarska': ['NRA'],
    'Polskie Stowarzyszenie Energetyki Wiatrowej': ['PSEW', 'Polskiego Stowarzyszenia Energetyki Wiatrowej'],
    'Polskie Stowarzyszenie Fotowoltaiki i Magazynowania Energii': ['Polskie Stowarzyszenie Fotowoltaiki i Magazynowani a Energii'],
    'Związek Pracodawców Polska Miedź': [],
    'Związek Pracodawców Polska Rada Winiarstwa': [],
    'Polskie Stowarzyszenie Diabetyków': ['Polskie Stowarzyszenie Diabetyków Zarząd Główny', 'PSD'],
    'Deloitte Doradztwo Podatkowe Dąbrowski i Wspólnicy sp. k.': [
        'Deloitte Doradztwo Podatkowe Dąbrowski i Wspólnicy Spółka Komandytowa',
        'Deloitte Doradztwo Podatkowe Dąbrowski i Wspólnicy sp. k'],
    'Rządowe Centrum Legislacji': ['RCL'],
    'Urząd Ochrony Danych Osobowych': ['UODO', 'Prezes UODO', 'Prezes Urzędu Ochrony Danych Osobowych'],
    'Urząd Komisji Nadzoru Finansowego': ['UKNF'],
    'Komisja Nadzoru Finansowego': ['KNF'],
    'Narodowy Bank Polski': ['NBP'],
    'Zakład Ubezpieczeń Społecznych': ['ZUS'],
    'Narodowy Fundusz Zdrowia': ['NFZ'],
    'Agencja Restrukturyzacji i Modernizacji Rolnictwa': ['ARiMR'],
    'Krajowy Ośrodek Wsparcia Rolnictwa': ['KOWR'],
    'Urząd Ochrony Konkurencji i Konsumentów': ['UOKiK', 'Prezes UOKiK'],
    'Ministerstwo Finansów': ['MF'],
    'Ministerstwo Zdrowia': ['MZ'],
    'Ministerstwo Sprawiedliwości': ['MS'],
    'Ministerstwo Rolnictwa i Rozwoju Wsi': ['MRiRW'],
    'Ministerstwo Rozwoju i Technologii': ['MRiT'],
    'ORLEN S.A.': ['ORLEN', 'Orlen S.A.'],
    'NSZZ „Solidarność”': ['NSZZ "Solidarność"'],
    'Instytut Legislacji i Prac Parlamentarnych Naczelnej Rady Adwokackiej': [],
    'Stowarzyszenie Notariuszy Rzeczypospolitej Polskiej': ['Stowarzyszenie Notariuszy RP'],
    'Krajowa Izba Radców Prawnych': ['Krajowej Izby Radców Prawnych'],
    'Federacja Przedsiębiorców Polskich': ['Federacja Przedsiębiorcó w Polskich'],
    'Polska Izba Przemysłu Chemicznego': ['Polska Izba Przemysłu Chemiczneg o'],
    'Polska Organizacja Handlu i Dystrybucji': ['Polska Organizacja Handlu i Dystrybucji POHiD'],
    'Polish Vodka Association': ['Polish Vodka Associations'],
    'Stowarzyszenie Księgowych w Polsce': [],
    'Polska Izba Spedycji i Logistyki': [],
    'Związek Rzemiosła Polskiego': [],
    'Izba POLMED': [],
    'PGE Polska Grupa Energetyczna S.A.': ['PGE Polska Grupa Energetyczn a S.A.', 'PGE S.A.'],
    'PwC': [], 'Deloitte': [], 'EY': [], 'KPMG': [], 'OW Legal': [],
}
ALIAS_LOOKUP = {key(v): c for c, variants in ALIASES.items() for v in [c] + variants}
ALIAS_PATTERNS = sorted([(re.compile(r'^' + r'\s*'.join(re.escape(w) for w in v.split()) +
                                     r'(?!\w)', re.I), c, v)
                         for c, variants in ALIASES.items() for v in [c] + variants],
                        key=lambda x: len(x[2]), reverse=True)


def canonical(s):
    s = clean(s).strip(' ;,–-')
    s = re.sub(r'\s*\([A-ZŻŹĆĄŚĘŁÓŃa-z0-9]{2,12}\)\s*$', '', s)
    return ALIAS_LOOKUP.get(key(s), s)


ADMIN = re.compile(r'(?i)minister|^urząd|^urzęd|^prezes urzędu|^sąd|^sądu|^sądy|'
                   r'^prokur|^rządowe centrum|^narodowy bank|^komisja nadzoru|'
                   r'^wojewod|^wojewódzki (?:urząd|inspektorat|fundusz)|^wfoś|^nfoś|'
                   r'^starost|^marszałek|^burmistrz|^wójt|^gmina |^powiat |'
                   r'^prezydent miasta|^zarząd województwa|^kancelaria (?:sejmu|senatu|prezydenta|prezesa)|'
                   r'^zakład ubezpieczeń|^narodowy fundusz|^agencja (?:restrukturyzacji|bezpieczeństwa)|'
                   r'^krajowy ośrodek wsparcia|^rzecznik |^najwyższa izba kontroli|'
                   r'^główny (?:urząd|inspektor)|^generaln[ay] dyrek|^państwowa inspek|'
                   r'^komisja wspólna|^rząd |^rada ministrów|^straż graniczna|^komendant|'
                   r'^naczelny sąd|^krajowa rada sądownictwa|^krajowe centrum przeciwdziałania|'
                   r'^prezes (?:kasy|polskiej agencji|agencji|zarządu (?:narodowego|państwowego))|'
                   r'^marszałkowski|^generalna dyrekcja|^krajow\w* administracj|^(?:SA|SO|SR) (?:w|we) |^agencja oceny technologii|'
                   r'^związek (?:powiatów|województw|miast|gmin)|^rada działalności pożytku publicznego')
ORG_START = re.compile(r'^(?:Polsk\w*|Polish|Ogólnopolsk\w*|Krajow\w*|Naczeln\w*|'
                       r'Niezależn[yae]|Samorządn\w*|Konfederacj\w*|Federacj\w*|'
                       r'Związek|Związku|Zrzeszeni\w*|Stowarzyszeni\w*|Fundacj\w*|'
                       r'Izb\w*|Rada|Rady|Towarzystw\w*|Pracodawc\w*|Kancelari\w*|'
                       r'Minister\w*|Urząd|Urzędu|Prezes|Sąd\w*|Prokur\w*|Rzecznik\w*|'
                       r'Starost\w*|Marszał\w*|Burmistrz|Wójt|Gmin\w*|Powiat\w*|'
                       r'Wojewódzk\w*|Wojewod\w*|Agencj\w*|Instytut\w*|Bank\w*|'
                       r'Zarząd|Komisj\w*|NSZZ|SA|SO|SR|Brytyjsko-Polska|Francusko-Polska|Hutnicza|'
                       r'FBSerwis|WFOŚiGW|NFOŚiGW|PGE|TAURON|Tauron|ENEA|Enea|'
                       r'Energa|PSE|PSEW|PKP|PKO|KUKE|PZU|Orange|T-Mobile|Play|'
                       r'Philip|British|Japan|Imperial|JTI|BAT|Amazon|Google|Microsoft|'
                       r'Żabka|Coca-Cola|PepsiCo|Dentons|MDDP|CRIDO|Crido|PwC|Deloitte|EY|KPMG)\b')
STOP = re.compile(r'(?i)^(?:art\.?|ust\.?|pkt\.?|uwag\w*|projekt\w*|ustaw\w*|'
                  r'uzasadnienie|propozycj\w*|postulat\w*|stanowisko|treść|ogólne|nowy|nowe|cały|całość|osr|'
                  r'zmiana|zmiany|zmianę|zwracamy|wnosimy|wskazujemy|proponujemy|'
                  r'zaproponowane|przesłane|dotyczy|rozwiązanie|proponowane|w ocenie|'
                  r'zgodnie|jednostka|przepis\w*|w zakresie|§|\d)\b')
VERB = re.compile(r'\b(?:wnosi|wnoszą|proponuje|wskazuje|uważa|postuluje|zauważa|'
                  r'przedstawia|ocenia|zgłasza|zwraca|popiera|jest|są|został\w*|należy|'
                  r'zwracamy|wnosimy|wskazujemy|proponujemy|wnioskujemy|zgłaszamy|wykonuje|może|zmiana|zmiany|uwaga)\b', re.I)
ROW = re.compile(r'^\s*(\d{1,4})(\.)?(?:\s+|$)(.*)$')


def source(path, lines):
    return {'plik': path.name, 'linia_od': lines[0][0], 'linia_do': lines[-1][0]}


def scan(path):
    """Streaming scan, retaining table sections and +/- keyword windows only."""
    tables, windows, buf = [], {}, deque(maxlen=28)
    active = None
    pending = 0
    total = chars = replacement = 0
    for total, raw in enumerate(path.open(encoding='utf-8-sig', errors='replace'), 1):
        chars += len(raw)
        replacement += raw.count('\ufffd')
        line = clean(raw)
        item = (total, line)
        buf.append(item)
        if re.search(r'raport\s*z\s*konsultacji|lobbing|zgłosi\w* zainteresowanie|'
                     r'zgłoszeń zainteresowan|uwagi.*zgłosi|zgłosi.*uwagi', line, re.I):
            for n, s in buf:
                windows[n] = s
            pending = 35
        elif pending:
            windows[total] = line
            pending -= 1
        recent = ' '.join(s for _, s in list(buf)[-26:]).casefold()
        header = (re.search(r'\b(?:lp\.|l\.p\.|podmiot|zgłaszający|nazwa)', recent)
                  and re.search(r'treść uwag|treść zgłoszon|treść stanowisk|uwaga/|propozycja zmian|stanowisko/opinia podmiotu|odniesienie się .* do uwag', recent)
                  and re.search(r'stanowisko|komentarz projektodawcy|odniesienie się .* do uwag', recent))
        stop = re.search(r'^(?:lista zgłoszeń lobbingowych|wzór urzędowego|'
                         r'tytuł projektu|tabela zgodności|ocena skutków regulacji|'
                         r'projekt rozporządzenia|tabela zbieżności)', line, re.I)
        if stop and active:
            tables.append(active)
            active = None
            buf.clear()
        if active is None and header and not stop:
            active = list(buf)
        elif active is not None:
            active.append(item)
    if active:
        tables.append(active)
    return tables, sorted(windows.items()), {'liczba_linii': total, 'znaki': chars,
                                            'błędy_dekodowania': replacement}


def entity_at(lines, index):
    """Recognize only the beginning of a cell; never search comment bodies for names."""
    first = lines[index][1].strip(' •−–;')
    prefix = 0
    if re.match(r'(?i)^(?:art\.|uwag[ai] ogóln\w*|uzasadnienie|osr)', first):
        for m in re.finditer(r'\b[A-ZĄĆĘŁŃÓŚŹŻ][\w„”"-]*', first):
            tail = first[m.start():]
            if m.start() and (ORG_START.match(tail) or any(p.match(tail) for p, _, _ in ALIAS_PATTERNS)):
                prefix = m.start()
                first = tail
                break
    if not first or STOP.match(first):
        return None
    pieces = [first]
    for _, s in lines[index+1:index+16]:
        if not s or STOP.match(s) or len(s) > 68 or VERB.search(s):
            break
        pieces.append(s)
    joined = clean(' '.join(pieces))
    for pattern, canon, _ in ALIAS_PATTERNS:
        m = pattern.match(joined)
        if m:
            consumed = 1
            length = len(first)
            while length < m.end() and consumed < len(pieces):
                length += 1 + len(pieces[consumed])
                consumed += 1
            tail = joined[m.end():].strip()
            # A base brand must not erase a subsidiary's legal name.
            if canon in ('Deloitte', 'PwC', 'EY', 'KPMG', 'ORLEN S.A.') and tail and re.match(r'^(?:Doradztwo|Polska|Tax|Legal|S\.A\.|sp\.)', tail):
                continue
            return canon, consumed, m.end() + prefix, joined[:m.end()]
    if not ORG_START.match(first):
        if not (len(first) < 65 and re.search(r'\b(?:sp\.|S\.A\.|S\.A|Spółka)\b', first)):
            return None
    chosen = []
    for s in pieces:
        if chosen and ORG_START.match(s) and len(chosen[-1]) > 20 and not re.search(r'(?:Naczelnej|Krajowej|Polskiej|Pracodawców|Związków|Związek|Federacja)$', chosen[-1]):
            break
        if len(s) > 160:
            break
        chosen.append(s)
        if re.search(r'(?:sp\.\s*(?:z\s*o\.\s*o\.|k\.)|S\.A\.|\([A-Z]{2,8}\))\s*$', s):
            break
    full = clean(' '.join(chosen))
    # Cell boundaries are often lost even within a single extracted line.
    boundary = re.search(r'\s+(?:(?:art\.|Art\.|OSR|§|pkt\b|ust\.|nowy przepis|nowe\b|cały projekt|Cały projekt|Całość projektu)|'
                         r'(?:Wnioskujemy|Zgłaszamy|Brak|Szczególne|Napoje|Sprzeciw|Proponowany|Zakaz|Analiza|Zmiana|Zmiany|'
                         r'Zwracamy|Wnosimy|Wskazujemy|Proponujemy|Postulat|Uwaga|Projekt|Rozwiązanie|'
                         r'Według|Zdaniem|Konstrukcja|Zastrzeżenia|Wymaganie|Pozytywnie|Zawarta|'
                         r'Negatywna|Obowiązek|Opiniodawca|Definicja|Luka|Dotychczasowa|Odesłanie|Opinia|'
                         r'Płatnikom|Taka|Wypłata|Wątpliwości|Skoro|Wykreślenie|Kontrowersje|Przed|Kolejna|Zakres|Propozycja)\b)', full)
    if boundary:
        full = full[:boundary.start()]
    # Names normally use capitals plus a small set of connecting/legal words.
    # Stop before prose rather than manufacture an organization from a sentence.
    allowed = {'i', 'w', 'we', 'z', 'ze', 'na', 'rzecz', 'dla', 'do', 'o', 'oraz', 'im.',
               'sp.', 'sp', 'k.', 'k', 'o.o.', 'o.o', 's.a.', 's.a', 's.', 'a.', 'of', 'the', 'and'}
    tokens = full.split()
    kept = []
    for token in tokens:
        t = token.strip('„”"(),;–-')
        if t and not (t[0].isupper() or t.casefold() in allowed or t in {'&', '/'}):
            break
        kept.append(token)
    name = clean(' '.join(kept))
    if not name or len(name) > 210 or len(name.split()) < 2:
        return None
    if re.search(r'\b(?:który|której|przez|zgodnie|nie|powinien|wprowadzenie|przewiduje)\b', name, re.I):
        return None
    if name in {'Izba Gospodarcza', 'Polska Federacja', 'Instytut Badawczy', 'Instytut Ekologii',
                'Polska Izba Gospodarcza', 'Polskie Towarzystwo', 'Krajowej Izby', 'Izba Gospodarki',
                'Związek Pracodawców', 'Krajowa Izba Gospodarcza Przemysłu', 'Związek Zawodowy Rolnictwa i Obszarów',
                'Polska Organizacja Przemysłu i Handlu', 'Krajowy Związek Pracodawców Producentów',
                'Krajowych i Autostard', 'Bank Gospodarst'}:
        return None
    if name.split()[-1].casefold() in {'i', 'w', 'z', 'na', 'do', 'oraz', 'rzecz', 'ochrony', 'dla', 'o', 'komitet', '(komitet'}:
        return None
    used, length = 0, 0
    for part in pieces:
        used += 1
        length += len(part) + (1 if used > 1 else 0)
        if length >= len(name):
            break
    return canonical(name), used, len(name) + prefix, name


def label(line):
    """Decision labels, not incidental occurrences in substantive comment text."""
    s = clean(line).casefold()
    s = re.sub(r'^(?:ad\.?\s*\d+[.)]?\s*|\d+[.)]\s*)', '', s)
    s = re.sub(r'^(?:uwag[aię]|uwagi|postulat|propozycja)\s+(?:(?:został[ay]?|jest|zostały)\s+)?', '', s)
    if re.match(r'(?:częściowo\s+(?:uwzględnion|zasadn)|uwzględnion\w*\s+(?:częściowo|w części)|w części uwzględnion)', s):
        return 'częściowo uwzględniona'
    if re.match(r'(?:nie\s*(?:został[ay]?\s+)?uwzględnion|niezasadn|odrzucon)', s):
        return 'nieuwzględniona'
    if re.match(r'uwzględnion', s):
        return 'uwzględniona'
    if re.match(r'(?:wyjaśnion|wyjaśnienie)', s):
        return 'wyjaśnienie'
    if re.match(r'(?:poza zakresem|wykracza poza zakres)', s):
        return 'poza zakresem'
    return None


def decision(lines):
    found = []
    for i, (n, s) in enumerate(lines):
        v = label(s)
        if v is None and len(s) < 38 and i+1 < len(lines):
            v = label(s + ' ' + lines[i+1][1])
        if v:
            found.append({'stanowisko': v, 'linia': n, 'cytat': s[:200]})
    kinds = {x['stanowisko'] for x in found}
    if len(kinds) == 1:
        result = next(iter(kinds))
    elif kinds and kinds <= {'uwzględniona', 'częściowo uwzględniona'}:
        result = 'częściowo uwzględniona'
    else:
        # Mixed labels may belong to different subpoints or misordered columns.
        result = 'nieustalone'
    return result, found


def header_lines(lines):
    skip = set()
    for i, (_, s) in enumerate(lines):
        if re.match(r'^(?:Lp\.|L\.p\.|Podmiot$)', s, re.I):
            for j in range(i, min(i+19, len(lines))):
                skip.add(j)
                if re.search(r'stanowisko|komentarz projektodawcy|odniesienie się .* do uwag', lines[j][1], re.I):
                    # Some headers have the ministry name on the next line.
                    break
    return [x for i, x in enumerate(lines) if i not in skip]


def find_entity(lines, start, limit=24):
    for j in range(start, min(start+limit, len(lines))):
        e = entity_at(lines, j)
        if e:
            return j, e
        # A long substantive sentence before a name means this is not a name cell.
        s = lines[j][1]
        if len(s) > 70 and not re.match(r'^(?:art\.|ust\.|pkt)', s, re.I):
            break
        if VERB.search(s) and not STOP.match(s):
            break
    return None


def parse_table(path, raw, table_no):
    if any(re.match(r'Lp\.? Przepis Treść uwagi', s, re.I) for _, s in raw):
        return parse_reverse_table(path, raw, table_no)
    lines = header_lines(raw)
    starts = []
    for i, (n, s) in enumerate(lines):
        m = ROW.match(s)
        if not m:
            continue
        number, dot, tail = m.groups()
        if not dot and not tail:
            # Bare page numbers are never row boundaries; bare row numbers only
            # if immediately followed by a recognizable name and sequential.
            if not starts or int(number) != starts[-1][2]+1:
                continue
        modified = lines[i:i+26]
        modified = [(n, tail)] + modified[1:]
        got = find_entity(modified, 0, 24 if dot or re.match(r'(?i)art\b', tail) else 12)
        if not got:
            continue
        j, e = got
        if j > 0 and tail and not re.match(r'(?i)^(?:art\.?|§|uwag|cał|ogóln|uzasadn|osr|projekt|pkt|ust)', tail):
            continue
        starts.append((i, n, int(number), tail, j, e))
    # Tables with empty Lp cells (e.g. 3148): require a name followed by a
    # substantive text on the same line, or a short isolated exact alias.
    unnumbered = any('Propozycja podmiotu zgłaszającego' in s for _, s in raw)
    if not starts or unnumbered:
        starts = []
        for i, (n, s) in enumerate(lines):
            e = entity_at(lines, i)
            if e and key(e[0]) in ALIAS_LOOKUP and not ADMIN.search(e[0]) and (len(s) > len(e[3])+8 or s == e[3]):
                starts.append((i, n, 0, s, 0, e))
    rows = []
    for k, (i, n, num, tail, j, e) in enumerate(starts):
        end = starts[k+1][0] if k+1 < len(starts) else len(lines)
        block = [(n, tail)] + lines[i+1:end]
        if j >= len(block):
            continue
        names = []
        cursor = j
        while cursor < min(len(block), j+45):
            ent = entity_at(block, cursor)
            if not ent:
                if not block[cursor][1]:
                    cursor += 1
                    continue
                break
            name, used, length, original = ent
            names.append({'nazwa': name, 'wariant': original,
                          'linia': block[cursor][0]})
            # Remove the name from the last consumed line to retain inline comment.
            span = ' '.join(x[1] for x in block[cursor:cursor+used])
            rest = span[length:].strip()
            cursor += used
            if rest and not re.fullmatch(r'\([\w]+\)', rest):
                block.insert(cursor, (block[cursor-1][0], rest))
                break
        names = list({x['nazwa']: x for x in names}.values())
        status, evidence = decision(block[cursor:])
        text_lines = []
        for ln, s in block[cursor:]:
            if evidence and ln >= evidence[0]['linia']:
                break
            if not s or re.fullmatch(r'\d+|Strona\s*\|?\s*\d+', s, re.I):
                continue
            text_lines.append(s)
        content = clean(' '.join(text_lines))
        content = re.sub(r'^(?:art\.|pkt|ust\.)\s*\d+[a-z]?(?:\s+(?:ust\.|pkt)\s*\d+[a-z]?)?\s*', '', content, flags=re.I)
        quote = content[:197] + '…' if len(content) > 200 else content
        if not names or not content:
            continue
        rows.append({'id': f'{path.stem}:t{table_no}:l{n}', 'lp': num or None,
                     'podmioty': names, 'stanowisko': status,
                     'co_najmniej_częściowo': status in STATUSES[:2],
                     'sygnały_stanowisk': evidence, 'cytat_uwagi': quote,
                     'streszczenie': f'Uwaga dotyczy następującego zagadnienia: „{quote}”.',
                     'źródło': source(path, lines[i:end]),
                     'wspólny_wiersz': len(names) > 1,
                     'pewność': 'heurystyczna',
                     '_text': content})
    return rows


def parse_reverse_table(path, raw, table_no):
    """Layout: number, provision, comment, author, ministry response."""
    lines = header_lines(raw)
    starts = [i for i, (_, s) in enumerate(lines)
              if re.match(r'^\d+\.\s+(?:art\.|Art\.|uwag|Uwagi|Uwaga|projekt|Projekt)', s)]
    rows = []
    for k, start in enumerate(starts):
        end = starts[k+1] if k+1 < len(starts) else len(lines)
        block = lines[start:end]
        if not block:
            continue
        stop = next((i for i, (_, s) in enumerate(block) if label(s)), None)
        if stop is None:
            continue
        candidates = []
        for j in range(max(1, stop-12), stop):
            e = entity_at(block, j)
            if e:
                name, used, length, variant = e
                # The author cell ends immediately before the response label.
                if all(not s for _, s in block[j+used:stop]):
                    candidates.append((j, e))
        if not candidates:
            continue
        j, e = candidates[0]
        status, evidence = decision(block[stop:])
        content = clean(' '.join(s for _, s in block[1:j] if s and not re.fullmatch(r'\d+', s)))
        quote = content[:197] + '…' if len(content) > 200 else content
        rows.append({'id': f'{path.stem}:t{table_no}:l{block[0][0]}',
                     'lp': int(re.match(r'\d+', block[0][1])[0]),
                     'podmioty': [{'nazwa': e[0], 'wariant': e[3], 'linia': block[j][0]}],
                     'stanowisko': status, 'co_najmniej_częściowo': status in STATUSES[:2],
                     'sygnały_stanowisk': evidence, 'cytat_uwagi': quote,
                     'streszczenie': f'Uwaga dotyczy następującego zagadnienia: „{quote}”.',
                     'źródło': source(path, block), 'wspólny_wiersz': False,
                     'pewność': 'heurystyczna', '_text': content})
    return rows


DATE = r'\b\d{1,2}[.\-/]\d{1,2}[.\-/]20\d{2}\b'

