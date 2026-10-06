"""Deterministic parsers; no network, OCR, model calls or name-based matching."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO, StringIO
import re
from urllib.parse import urljoin, urlsplit, urlunsplit


def day(value):
    return date.fromisoformat(str(value)[:10]) if value else None


def public_url(value, base=''):
    url = urljoin(base, value)
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('invalid_public_url')
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c, Node) else c
                                for c in self.children).split())

    def find(self, tag=None, css=None):
        for c in self.children:
            if isinstance(c, Node):
                if (tag is None or c.tag == tag) and (css is None or css in c.attrs.get('class', '').split()):
                    yield c
                yield from c.find(tag, css)


class HTML(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(raw.decode('utf-8-sig') if isinstance(raw, bytes) else raw)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'wbr', 'area', 'base', 'embed', 'param', 'col'}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        if self.current.tag not in {'script', 'style'}:
            self.current.children.append(data)


BOT_WALL_MARKERS = (b'_Incapsula_Resource', b'Incapsula incident', b'/cdn-cgi/challenge-platform', b'cf-browser-verification')


def bot_wall(raw):
    """Strona zabezpieczenia przed botami zamiast treści (Imperva/Incapsula, Cloudflare). Tylko początek odpowiedzi."""
    head = bytes(raw[:8192]) if isinstance(raw, (bytes, bytearray)) else str(raw)[:8192].encode('utf-8', 'ignore')
    return any(marker in head for marker in BOT_WALL_MARKERS)


def links(raw, base):
    out = []
    for a in HTML(raw).root.find('a'):
        href = a.attrs.get('href', '')
        if not href or href.startswith(('#', 'mailto:', 'javascript:')):
            continue
        try:
            url = public_url(href, base)
        except ValueError:
            continue
        parent = a.parent
        while parent.parent and parent.tag not in {'li', 'tr', 'p', 'div'}:
            parent = parent.parent
        out.append({'url': url, 'title': a.text(), 'context': parent.text()[:3000]})
    return list({r['url']: r for r in out}.values())


def speech(raw):
    root = HTML(raw).root
    body = next(root.find('blockquote'), None)
    if body is None:
        raise ValueError('transcript_structure_changed')
    agenda = '\n'.join(n.text() for n in body.find(css='punkt-tytul'))
    paragraphs = [p.text() for p in body.find('p') if 'punkt-tytul' not in p.attrs.get('class', '').split()]
    text = '\n'.join(p for p in paragraphs if p)
    if not text:
        raise ValueError('empty_statement')
    return {'agenda': agenda, 'text': text}


def ballots(payload, term, sitting, number):
    from scraper.official import VOTE_CODES
    if (payload['term'], payload['sitting'], payload['votingNumber']) != (term, sitting, number):
        raise ValueError('voting_identity_mismatch')
    rows = payload['votes']
    if not isinstance(rows, list) or not rows:
        raise ValueError('missing_roll_call')
    ids = [int(v['MP']) for v in rows]
    if len(ids) != len(set(ids)) or any(i <= 0 for i in ids):
        raise ValueError('invalid_member_ids')
    if any(v['vote'] not in VOTE_CODES for v in rows):
        raise ValueError('invalid_vote')
    if 'totalVoted' in payload and 'notParticipating' in payload:
        if len(rows) != payload['totalVoted'] + payload['notParticipating']:
            raise ValueError('incomplete_roll_call')
    return rows


def question(row, term):
    if row['term'] != term or int(row['num']) <= 0 or not row['title']:
        raise ValueError('question_identity_mismatch')
    authors = [int(i) for i in row['from']]
    if any(i <= 0 for i in authors):
        raise ValueError('invalid_author_id')
    # API attachments/replies are metadata only: no body URL is fetched.
    return {k: row[k] for k in ('num', 'term', 'title', 'from', 'to', 'receiptDate',
            'sentDate', 'lastModified', 'replies', 'links', 'recipientDetails') if k in row}, authors


def assets(raw, base):
    result = []
    for item in links(raw, base):
        if not urlsplit(item['url']).path.lower().endswith('.pdf'):
            continue
        # Do not accidentally index CVs or unrelated PDFs linked from navigation.
        if not re.search(r'osw|oświadcze|majątk', item['url'] + ' ' + item['title'], re.I):
            continue
        # The report year differs from the receipt year in the next cell.
        annual = re.search(r'(?:za rok\s+|^)(20\d{2})(?!\d)', item['context'], re.I)
        years = [annual[1]] if annual else re.findall(r'(?<!\d)(20\d{2})(?!\d)', item['context'])
        if not years:
            years = re.findall(r'(?<!\d)(20\d{2})(?!\d)', item['url'])
        result.append({**item, 'year': int(years[0]) if len(set(years)) == 1 else None,
                       'year_status': 'reported' if len(set(years)) == 1 else 'unresolved'})
    if not result:
        # Never silently claim an unavailable profile is a complete empty index.
        raise ValueError('asset_index_empty_or_changed')
    return result


def amount(value):
    value = re.sub(r'\s|PLN|zł', '', value, flags=re.I).replace(',', '.')
    if not re.fullmatch(r'-?\d+(?:\.\d{1,2})?', value):
        return None
    try:
        return str(Decimal(value))
    except InvalidOperation:
        return None


def financial_tables(raw, *, csv_file=False, xlsx_file=False):
    """Keep headers and cells; a number is money only under a monetary header."""
    if xlsx_file:
        tables = xlsx_tables(raw)
    elif csv_file:
        text = raw.decode('utf-8-sig')
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=';,\t')
        tables = [list(csv.reader(StringIO(text), dialect))]
    else:
        tables = [[[c.text() for c in row.children if isinstance(c, Node) and c.tag in {'th', 'td'}]
                   for row in t.find('tr')] for t in HTML(raw).root.find('table')]
    out = []
    for ti, table in enumerate(tables):
        if not table:
            continue
        headers = table[0]
        money_cols = [i for i, h in enumerate(headers) if re.search(r'kwota|zł|PLN|przychod|wydatk|wpływ', h, re.I)]
        for ri, cells in enumerate(table[1:], 1):
            amounts = {headers[i]: amount(cells[i]) for i in money_cols if i < len(cells) and amount(cells[i]) is not None}
            if amounts:
                out.append({'table': ti, 'row': ri, 'headers': headers, 'cells': cells,
                            'amounts': amounts, 'currency': 'PLN'})
    return out


def xlsx_tables(raw):
    """Read values (not formulas) from bounded OOXML worksheets, stdlib only."""
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with ZipFile(BytesIO(raw)) as archive:
        infos = [i for i in archive.infolist() if i.filename == 'xl/sharedStrings.xml' or
                 re.fullmatch(r'xl/worksheets/sheet\d+\.xml', i.filename)]
        if len(infos) > 30 or sum(i.file_size for i in infos) > 5_000_000:
            raise ValueError('spreadsheet_expansion_limit')
        roots = {}
        for info in infos:
            xml = archive.read(info)
            if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                raise ValueError('unsafe_spreadsheet_xml')
            roots[info.filename] = ET.fromstring(xml)
    shared = [''.join(t.itertext()) for t in roots.get('xl/sharedStrings.xml', [])]
    tables = []
    for name, root in roots.items():
        if name == 'xl/sharedStrings.xml':
            continue
        table = []
        for row in root.iter(ns + 'row'):
            cells = []
            for cell in row.findall(ns + 'c'):
                ref = re.fullmatch(r'([A-Z]{1,3})\d+', cell.get('r', ''))
                if not ref:
                    raise ValueError('spreadsheet_cell_reference')
                column = 0
                for c in ref[1]:
                    column = column * 26 + ord(c) - 64
                if column > 256:
                    raise ValueError('spreadsheet_column_limit')
                cells.extend([''] * (column - len(cells)))
                value = cell.findtext(ns + 'v', '')
                if cell.find(ns + 'f') is not None:
                    value = ''  # A stale cached formula result is not evidence.
                elif cell.get('t') == 's':
                    value = shared[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.iter(ns + 't'))
                cells[column - 1] = value
            table.append(cells)
        tables.append(table)
    return tables


def pdf_text(raw):
    """Bounded text layer extraction, never OCR. PDFs are not persisted."""
    if not raw.startswith(b'%PDF-') or len(raw) > 5_000_000:
        raise ValueError('invalid_or_large_pdf')
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 500:
        raise ValueError('pdf_requires_manual_review')
    parts, size = [], 0
    for page in reader.pages:
        value = page.extract_text() or ''
        size += len(value)
        if size > 2_000_000:
            raise ValueError('pdf_text_limit')
        parts.append(value)
    return '\n'.join(parts)


def consultations(text, print_number):
    from scraper.consultation_parser import scan, parse_table
    # Adapter for the pilot's streaming scan; no local corpus path is required.
    class TextPath:
        name = str(print_number) + '.txt'
        stem = str(print_number)

        def open(self, **kwargs):
            return StringIO(text)
    path = TextPath()
    tables, _, stats = scan(path)
    rows = {}
    for index, table in enumerate(tables, 1):
        for row in parse_table(path, table, index):
            row.pop('streszczenie', None)
            rows[row['id']] = row
    return list(rows.values()), {'tables': len(tables), 'rows': len(rows), 'characters': stats['znaki'],
        'quality': 'heuristic' if rows else 'table_unparsed' if tables else 'no_readable_table',
        'ocr': False}


def lobby_register(text):
    """Conservative numbered entries; retain an unparsed snapshot for review."""
    starts = list(re.finditer(r'(?m)^\s*(\d{5})\s+(\d{1,2}\.\d{1,2}\.\d{4})\s*', text))
    rows = []
    for i, m in enumerate(starts):
        body = text[m.end():starts[i+1].start() if i+1 < len(starts) else len(text)].strip()
        if body:
            rows.append({'registration_number': m[1], 'registration_date': m[2],
                         'entry_text': body, 'quality': 'heuristic'})
    return rows


def meta_ad(row):
    if not str(row['id']).isdigit() or not str(row['page_id']).isdigit():
        raise ValueError('invalid_ad_identity')
    keys = ('id', 'page_id', 'page_name', 'bylines', 'currency', 'spend', 'impressions',
            'ad_creation_time', 'ad_delivery_start_time', 'ad_delivery_stop_time',
            'delivery_by_region', 'ad_creative_bodies')
    # In particular, never retain ad_snapshot_url (it can contain an access token).
    return {key: row[key] for key in keys if key in row}


# --- 092: procesy, komisje, KRS, TED, rejestr przejrzystości UE --------------------------------------------

PRINT_REF = re.compile(r'druk(?:i|ów|u|ach)?\s+(?:sejmow\w*\s+)?nr\s*((?:\d+(?:-[A-Za-z0-9]+)?(?:\s*(?:,|i|oraz)\s*)?)+)', re.I)


def strip_tags(value):
    """Agenda fields are small official HTML fragments; keep text only."""
    if not value:
        return ''
    return HTML(value).root.text() if '<' in value else ' '.join(value.split())


def print_refs(text):
    found = []
    for match in PRINT_REF.finditer(text or ''):
        for number in re.findall(r'\d+(?:-[A-Za-z0-9]+)?', match.group(1)):
            if number not in found:
                found.append(number)
    return found


def process_stages(stages, parent=''):
    """Flatten the Sejm stage tree; keep voting identity for linking ballots."""
    rows = []
    for stage in stages or []:
        if not isinstance(stage, dict):
            raise ValueError('process_stage_shape')
        row = {k: stage[k] for k in ('date', 'stageName', 'stageType', 'printNumber', 'committeeCode',
                                       'decision', 'sittingNum', 'type', 'comment') if stage.get(k) not in (None, '')}
        if parent:
            row['parent'] = parent
        voting = stage.get('voting')
        if isinstance(voting, dict) and voting.get('sitting') and voting.get('votingNumber'):
            row['voting'] = {k: voting.get(k) for k in ('term', 'sitting', 'votingNumber', 'date', 'yes', 'no',
                                                         'abstain', 'notParticipating', 'totalVoted', 'title')}
        rows.append(row)
        rows.extend(process_stages(stage.get('children'), stage.get('stageName', '')))
    return rows


def process(payload, term):
    if not isinstance(payload, dict) or payload.get('term') != term or not payload.get('number'):
        raise ValueError('process_identity_mismatch')
    stages = process_stages(payload.get('stages'))
    prints = [str(payload['number'])]
    for value in [s.get('printNumber') for s in stages] + list(payload.get('printsConsideredJointly') or []):
        if value and str(value) not in prints:
            prints.append(str(value))
    votings = []
    for stage in stages:
        v = stage.get('voting')
        if v:
            key = f"{term}/{int(v['sitting'])}/{int(v['votingNumber'])}"
            if key not in [x['key'] for x in votings]:
                votings.append({**v, 'key': key, 'stage': stage.get('parent') or stage.get('stageName', '')})
    data = {k: payload.get(k) for k in ('number', 'documentType', 'documentTypeEnum', 'passed', 'UE', 'urgencyStatus',
                                         'ELI', 'displayAddress', 'closureDate', 'changeDate', 'processStartDate',
                                         'documentDate', 'titleFinal', 'description', 'shortenProcedure',
                                         'legislativeCommittee', 'principleOfSubsidiarity') if payload.get(k) not in (None, '')}
    data.update(stages=stages, prints=prints, votings=votings,
                links=[x['href'] for x in payload.get('links') or [] if isinstance(x, dict) and x.get('href')])
    return data


def committee(row):
    if not isinstance(row, dict) or not re.fullmatch(r'[A-Z0-9]{2,8}', str(row.get('code', ''))):
        raise ValueError('committee_shape')
    members = [{k: m.get(k) for k in ('id', 'lastFirstName', 'club', 'function', 'joinDate', 'leaveDate') if m.get(k)}
               for m in row.get('members') or [] if isinstance(m, dict) and m.get('id')]
    data = {k: row.get(k) for k in ('code', 'name', 'nameGenitive', 'type', 'appointmentDate', 'compositionDate',
                                     'scope', 'subCommittees') if row.get(k) not in (None, '')}
    data['members'] = members
    return data, [m['id'] for m in members]


def committee_sitting(row, code):
    if not isinstance(row, dict) or not isinstance(row.get('num'), int) or not row.get('date'):
        raise ValueError('committee_sitting_shape')
    if row.get('code') and row['code'] != code:
        raise ValueError('committee_sitting_identity_mismatch')
    agenda = strip_tags(row.get('agenda'))
    data = {k: row.get(k) for k in ('num', 'date', 'startDateTime', 'endDateTime', 'closed', 'remote', 'city',
                                     'room', 'status', 'notes', 'comments', 'audio') if row.get(k) not in (None, '')}
    data.update(code=code, jointWith=[j for j in row.get('jointWith') or [] if isinstance(j, dict)],
                video=[v.get('videoLink') or v.get('playerLink') for v in row.get('video') or []
                       if isinstance(v, dict) and (v.get('videoLink') or v.get('playerLink'))],
                prints=print_refs(agenda))
    return data, agenda


def krs_number(value):
    value = str(value).strip()
    if not value.isdecimal() or len(value) > 10:
        raise ValueError('krs_bulletin_shape')
    return value.zfill(10)


def krs_bulletin(payload):
    """Biuletyn KRS: lista numerów (powtórzenie = kolejny wpis tego dnia)."""
    if not isinstance(payload, list):
        raise ValueError('krs_bulletin_shape')
    counts = {}
    for value in payload:
        number = krs_number(value)
        counts[number] = counts.get(number, 0) + 1
    return counts


def pl_date(value):
    if not value:
        return None
    match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', str(value).strip())
    return f'{match[3]}-{match[2]}-{match[1]}' if match else str(value)[:10]


def krs_header(payload, krs):
    """Tylko nagłówek odpisu (stan, ostatni wpis, sąd); dane osób nigdy nie są czytane ani zapisywane."""
    try:
        header = payload['odpis']['naglowekA']
    except (KeyError, TypeError):
        raise ValueError('krs_extract_shape')
    if str(header.get('numerKRS', '')).zfill(10) != krs:
        raise ValueError('krs_identity_mismatch')
    name, subject = '', {}
    try:
        subject = payload['odpis']['dane']['dzial1']['danePodmiotu']
        name = subject['nazwa']
    except (KeyError, TypeError):
        pass
    from news.krs import identifiers
    return {
        'krs': krs, 'register': header.get('rejestr', ''), 'name': name, **identifiers(subject if isinstance(subject, dict) else {}),
        'state_date': pl_date(header.get('stanZDnia')),
        'last_entry_number': header.get('numerOstatniegoWpisu'),
        'last_entry_date': pl_date(header.get('dataOstatniegoWpisu')),
        'case_reference': header.get('sygnaturaAktSprawyDotyczacejOstatniegoWpisu', ''),
        'court': header.get('oznaczenieSaduDokonujacegoOstatniegoWpisu', ''),
    }


def _lang(value, order=('pol', 'eng')):
    """TED multilingual field: dict lang -> str | [str]."""
    if isinstance(value, dict):
        for lang in order:
            if value.get(lang):
                return value[lang]
        return next((v for v in value.values() if v), '')
    return value or ''


def _unique(values):
    seen = []
    for value in values or []:
        if value not in (None, '') and value not in seen:
            seen.append(value)
    return seen


# Forma prawna w nazwie wykonawcy: bez niej traktujemy wykonawcę jak osobę fizyczną prowadzącą działalność
# (LEGAL: osoby prywatne nie są wyszukiwane ani profilowane). Spółka cywilna (s.c.) to umowa osób fizycznych - też chroniona.
LEGAL_FORM = re.compile(
    r'(sp(ó|o)łk|\bsp\.?\s*z\s*o\.?\s*o|\bs\.?\s?a\.?(?=\W|$)|\bp\.?\s?s\.?\s?a\b|\bsp\.?\s?[kjp]\b|'
    r'fundacj|stowarzysz|przedsi(ę|e)biorstw\w*\s+pa(ń|n)stw|sp(ó|o)łdziel|\bgmin|\bmiast|\bpowiat|wojew(ó|o)dztw|skarb\s+pa(ń|n)stwa|'
    r'uniwersytet|politechnik|akademi|instytut|szpital|zak(ł|l)ad|centrum|urz(ą|a)d|agencj|\bizba|konsorcj|\bgrupa|holding|'
    r'szko(ł|l)|uczelni|przedszkol|o(ś|s)rod(ek|ka)|muzeum|bibliotek|teatr|parafi|zgromadzeni|zwi(ą|a)zek|komend|starostw|'
    r'\bklub|kuratori|filharmoni|regionaln|krajow|narodow|pa(ń|n)stwow|'
    r'\b(ltd|limited|gmbh|ag|kg|s\.?r\.?o|a\.?s|inc|llc|plc|b\.?v|n\.?v|sarl|s\.?p\.?a|s\.?r\.?l|ab|a/s|kft|zrt|d\.?o\.?o|corp)\b)',
    re.I)
NATURAL_PERSON = 'wykonawca - osoba fizyczna prowadząca działalność'


def is_natural_person(name, flags=None):
    """True, gdy nazwa nie ma formy prawnej albo TED oznacza wykonawcę jako osobę fizyczną."""
    if flags and (flags.get('natural_person') or (flags.get('size') == 'micro' and not flags.get('org_id'))):
        return True
    return not LEGAL_FORM.search(name or '')


def ted_winners(names, ids, flags=None):
    """Wykonawcy ogłoszenia. Osoba fizyczna: tylko nazwa w kontekście ogłoszenia, bez NIP i bez identyfikatora.
    Identyfikatory zostają tylko, gdy da się je jednoznacznie przypisać (tyle samo co nazw) i tylko dla organizacji."""
    flags = flags or []
    paired = len(ids) == len(names)
    winners = []
    for i, name in enumerate(names):
        natural = is_natural_person(name, flags[i] if i < len(flags) else None)
        row = {'name': name, 'osoba_fizyczna': natural}
        if natural:
            row['label'] = NATURAL_PERSON
        elif paired:
            row['id'] = ids[i]
        winners.append(row)
    return winners


def ted_notice(row):
    if not isinstance(row, dict) or not re.fullmatch(r'\d{1,8}-\d{4}', str(row.get('publication-number', ''))):
        raise ValueError('ted_notice_shape')
    number = row['publication-number']
    buyers = _lang(row.get('buyer-name'))
    winners = _lang(row.get('winner-name'))
    title = _lang(row.get('notice-title'))
    value = row.get('total-value')
    currency = row.get('total-value-cur')
    return {
        'id': number,
        'date': str(row.get('publication-date', ''))[:10],
        'notice_type': row.get('notice-type', ''),
        'buyer': _unique(buyers if isinstance(buyers, list) else [buyers]),
        'buyer_country': _unique(row.get('buyer-country') or ['POL']),
        'title': title if isinstance(title, str) else ' '.join(title),
        'cpv': _unique(row.get('classification-cpv')),
        'value': value[0] if isinstance(value, list) and value else value,
        'currency': (currency[0] if isinstance(currency, list) and currency else currency) or '',
        'winners': ted_winners(_unique(winners if isinstance(winners, list) else [winners]), _unique(row.get('winner-identifier'))),
        'winner_country': _unique(row.get('winner-country')),
        'url': f'https://ted.europa.eu/pl/notice/-/detail/{number}',
    }


# XML 1.1: odwołania do znaków sterujących, których expat (XML 1.0) nie przyjmie.
_XML11_CONTROL = re.compile(rb'&#(?:[xX]0*(?:[0-8bBcCeE]|1[0-9a-fA-F])|0*(?:[0-8]|1[124-9]|2[0-9]|3[01]));')
_XML11_DECL = re.compile(rb"^(<\?xml[^>]*version=)(?:'1\.1'|\"1\.1\")")
TR_POLISH = re.compile(r'\b(polsk|poland|polish|pologne|polen)', re.I)


def _text(el, path):
    return ' '.join((el.findtext(path) or '').split())


def transparency_entry(el):
    """Organizacja z rejestru przejrzystości UE; bez telefonów, adresów i nazw osób."""
    code = _text(el, 'identificationCode')
    if not re.fullmatch(r'\d{6,15}-\d{2}', code):
        raise ValueError('transparency_entry_shape')
    head, eu = _text(el, 'headOffice/country'), _text(el, 'EUOffice/country')
    closed = el.find('financialData/closedYear')
    finance = {}
    if closed is not None:
        costs = closed.find('costs')
        finance = {
            'start': _text(closed, 'startDate'), 'end': _text(closed, 'endDate'),
            'cost_min': _text(closed, 'costs/range/min') or None, 'cost_max': _text(closed, 'costs/range/max') or None,
            'cost_exact': _text(closed, 'costs/absoluteCost') or None,
            'currency': costs.get('currency', '') if costs is not None else '',
            'total_budget': _text(closed, 'totalBudget/absoluteCost') or _text(closed, 'totalBudget') or None,
            'grants': [{'source': _text(g, 'source'), 'amount': _text(g, 'amount/absoluteCost') or None}
                       for g in closed.findall('grants/grant')][:50],
            'clients': _unique(_text(c, 'name') for c in closed.findall('.//client'))[:100],
            'intermediaries': _unique(_text(i, 'name') for i in closed.findall('.//intermediary'))[:100],
            # Darczyńcy mogą być osobami prywatnymi: tylko liczba, bez nazw.
            'contributors': len(closed.findall('.//contributor')),
        }
    return {
        'id': code, 'name': _text(el, 'name/originalName'), 'acronym': _text(el, 'acronym'),
        'form': _text(el, 'entityForm'), 'website': _text(el, 'webSiteURL'),
        'category': _text(el, 'registrationCategory'),
        'head_office_city': _text(el, 'headOffice/city'), 'head_office_country': head, 'eu_office_country': eu,
        'registered': _text(el, 'registrationDate')[:10], 'updated': _text(el, 'lastUpdateDate')[:10],
        'goals': _text(el, 'goals')[:2000], 'proposals': _text(el, 'EULegislativeProposals')[:2000],
        'interests': _unique(_text(i, 'name') for i in el.findall('interests/interest')),
        'levels': _unique(_text(i, 'levelOfInterest') for i in el.findall('levelsOfInterest/levelOfInterest')),
        'members_fte': _text(el, 'members/membersFTE') or None,
        'ep_accredited': _text(el, 'EPAccreditedNumber') or None,
        'represented': _text(el, 'interestRepresented'),
        'finance': finance,
        'match': 'siedziba' if 'POLAND' in (head, eu) else 'wzmianka',
    }


def transparency_polish(chunks, max_bytes=300_000_000):
    """Strumień eksportu XML -> tylko organizacje z Polski albo z polskim interesem (bez całego pliku w pamięci)."""
    from xml.etree.ElementTree import XMLPullParser
    parser = XMLPullParser(events=('end',))
    rows, buffer, size, started, total = [], b'', 0, False, [0]

    def drain():
        for _, el in parser.read_events():
            if el.tag != 'interestRepresentative':
                continue
            total[0] += 1
            head, eu = _text(el, 'headOffice/country'), _text(el, 'EUOffice/country')
            if 'POLAND' in (head, eu) or TR_POLISH.search(_text(el, 'name/originalName') + ' ' + _text(el, 'goals')):
                rows.append(transparency_entry(el))
            el.clear()

    def feed(part):
        parser.feed(_XML11_CONTROL.sub(b'', part))
        drain()

    for chunk in chunks:
        size += len(chunk)
        if size > max_bytes:
            raise ValueError('Source response too large')
        buffer += chunk
        if not started:
            if len(buffer) < 4096:
                continue
            if b'<!DOCTYPE' in buffer[:4096] or b'<!ENTITY' in buffer[:4096]:
                raise ValueError('unsafe_xml')
            buffer, started = _XML11_DECL.sub(rb"\g<1>'1.0'", buffer), True
        # Odwołanie znakowe może być rozcięte między kawałkami: zostaw ogon od ostatniego '&'.
        cut = buffer.rfind(b'&')
        if cut == -1 or len(buffer) - cut > 16:
            cut = len(buffer)
        part, buffer = buffer[:cut], buffer[cut:]
        feed(part)
    if not started:
        if b'<!DOCTYPE' in buffer or b'<!ENTITY' in buffer:
            raise ValueError('unsafe_xml')
        buffer = _XML11_DECL.sub(rb"\g<1>'1.0'", buffer)
    feed(buffer)
    parser.close()
    drain()
    if not total[0]:
        raise ValueError('transparency_export_empty')
    return rows
