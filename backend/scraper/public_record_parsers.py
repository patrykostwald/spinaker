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
