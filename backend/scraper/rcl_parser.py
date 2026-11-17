"""Czysty parser stron legislacja.rcl.gov.pl (bez sieci, bez bazy): lista projektów, strona projektu, katalog etapu.

Struktura stron wg kopii z września i października 2026 (tests: scraper/fixtures/rcl); markup może się zmienić,
dlatego parser jest tolerancyjny (kolumny listy wg nagłówków, brakujące pola puste) i zgłasza RclParseError,
gdy strona nie przypomina żadnej z oczekiwanych (wtedy zbieracz zostawia dane bez zmian i zapisuje zdarzenie).
Serwis nie ma API; odpowiedź HTTP 200 z tytułem "Request Rejected" to odrzucenie przez zaporę, nie strona (is_rejected).
Uwaga o danych osobowych: pole "wprowadzony przez" (imię i nazwisko pracownika) jest pomijane, zapisujemy tylko "Autora dokumentu".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from scraper.rcl_guard import RCL_BASE_URL

VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())
SKIPPED = frozenset({'script', 'style', 'noscript'})


class RclParseError(ValueError):
    """Strona nie ma oczekiwanej struktury."""


class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    @property
    def classes(self):
        return set((self.attrs.get('class') or '').split())

    def get(self, name, default=''):
        return self.attrs.get(name) or default

    def iter(self):
        """Wszystkie elementy potomne w kolejności dokumentu."""
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag=None, cls=None, **attrs):
        for node in self.iter():
            if tag and node.tag != tag:
                continue
            if cls and cls not in node.classes:
                continue
            if any(node.attrs.get(key) != value for key, value in attrs.items()):
                continue
            yield node

    def find(self, tag=None, cls=None, **attrs):
        return next(self.find_all(tag, cls, **attrs), None)

    def child_nodes(self, tag=None):
        return [c for c in self.children if isinstance(c, Node) and (tag is None or c.tag == tag)]

    def text(self):
        parts = []

        def walk(node):
            for child in node.children:
                if isinstance(child, str):
                    parts.append(child)
                else:
                    walk(child)
        walk(self)
        return squash(' '.join(parts))

    def own_text(self):
        return squash(' '.join(c for c in self.children if isinstance(c, str)))

    def inside(self, tag=None, cls=None):
        node = self.parent
        while node is not None:
            if (tag is None or node.tag == tag) and (cls is None or cls in node.classes):
                return True
            node = node.parent
        return False


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.stack = [self.root]
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED:
            self.skip += 1
            return
        node = Node(tag, {k: (v or '') for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag in SKIPPED:
            return
        self.stack[-1].children.append(Node(tag, {k: (v or '') for k, v in attrs}, self.stack[-1]))

    def handle_endtag(self, tag):
        if tag in SKIPPED:
            self.skip = max(0, self.skip - 1)
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if not self.skip and data:
            self.stack[-1].children.append(data)


def build_dom(html):
    if isinstance(html, bytes):
        html = html.decode('utf-8', errors='replace')
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root


def squash(text):
    return ' '.join(str(text or '').split())


def fold(text):
    """Małe litery bez polskich znaków diakrytycznych, do dopasowań słów kluczowych."""
    table = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')
    return squash(text).translate(table).casefold()


def parse_date(text):
    match = re.search(r'(\d{2})-(\d{2})-(\d{4})', text or '')
    if not match:
        return None
    try:
        return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        return None


def is_rejected(html):
    """HTTP 200 z podmienioną stroną zapory (F5): tytuł "Request Rejected" albo jej typowy komunikat."""
    if isinstance(html, bytes):
        html = html.decode('utf-8', errors='replace')
    head = html[:4096].casefold()
    return ('<title>request rejected</title>' in head
            or ('the requested url was rejected' in head and 'support id' in html[:8192].casefold()))


def normalize_wykaz(text):
    return re.sub(r'\s+', '', squash(text)).upper()


def absolute(href, base=RCL_BASE_URL):
    return urljoin(base + '/', href) if href else ''


# --- rodzaje i klasyfikacja (heurystyki; zapisywane z adnotacją, że to heurystyka) ---

def stage_kind(name):
    n = fold(name)
    for needle, kind in (('lobbing', 'lobbing'), ('uzgodnien', 'uzgodnienia'), ('konsultacj', 'konsultacje'),
                         ('opiniowan', 'opiniowanie'), ('notyfikacj', 'notyfikacja'), ('komitet', 'komitet'),
                         ('komisja', 'komisja'), ('rada ministr', 'rada_ministrow'), ('sejm', 'sejm'), ('senat', 'senat')):
        if needle in n:
            return kind
    return 'inne'


def document_category(folder_name, doc_name, kind):
    """Kategoria dokumentu po nazwie etapu, folderu i pliku.  Heurystyka: w razie wątpliwości 'other'."""
    folder, name = fold(folder_name), fold(doc_name)
    if kind == 'lobbing':
        return 'lobbying'
    if 'odniesien' in folder or re.search(r'tabel\w* uwag|zestawieni\w* uwag|uwagi? i odniesien', name):
        return 'comment_table'
    if 'stanowisk' in folder or re.search(r'\buwag', folder):
        return 'position'
    if 'pism' in folder:
        return 'cover_letter'
    if 'tabel' in name and 'zgodnosci' in name:
        return 'other'
    # Plik łączący projekt z uzasadnieniem i OSR to wersja projektu.
    if 'uzasadnien' in name and 'projekt' in name:
        return 'project'
    if re.search(r'\bosr\b|ocen\w* skutkow', name):
        return 'osr'
    if 'uzasadnien' in name:
        return 'justification'
    if re.match(r'projekt\b', folder) or (not folder and re.search(r'projekt|ustaw|rozporzadz', name)):
        return 'cover_letter' if re.match(r'pismo\b', name) else 'project'
    return 'other'


# --- lista projektów ---

@dataclass
class ListPage:
    rows: list = field(default_factory=list)
    total: int | None = None
    types: dict = field(default_factory=dict)


_HEADERS = (('title', 'tytul'), ('applicant', 'wnioskodawca'), ('number', 'numer'),
            ('created', 'utworzon'), ('modified', 'zmodyfikowan'))
_PROJECT_ID = re.compile(r'/projekt/(\d+)')


def menu_types(root):
    """typeId -> etykieta z menu rodzajów aktów (jest na każdej stronie serwisu)."""
    types = {}
    for link in root.find_all('a'):
        parts = urlsplit(link.get('href'))
        if parts.path == '/lista':
            values = parse_qs(parts.query)
            if list(values) == ['typeId'] and values['typeId'][0].isdigit():
                label = link.text()
                if label:
                    types.setdefault(int(values['typeId'][0]), label)
    return types


def parse_list(html):
    root = build_dom(html)
    if is_rejected(html):
        raise RclParseError('request_rejected')
    table = root.find('table', id='table')
    if table is None:
        raise RclParseError('list_table_missing')
    columns = {}
    head = table.find('thead')
    for index, th in enumerate(head.find_all('th') if head else []):
        label = fold(th.text())
        for key, needle in _HEADERS:
            if label.startswith(needle):
                columns[key] = index
    if 'title' not in columns:
        columns = {key: index for index, (key, _) in enumerate(_HEADERS)}
    page = ListPage(types=menu_types(root))
    body = table.find('tbody') or table
    for tr in body.find_all('tr'):
        cells = tr.child_nodes('td')
        if len(cells) <= max(columns.values()):
            continue
        link = cells[columns['title']].find('a')
        match = _PROJECT_ID.search(link.get('href')) if link else None
        if not match:
            continue
        applicant_link = cells[columns['applicant']].find('a') if 'applicant' in columns else None
        applicant_id = parse_qs(urlsplit(applicant_link.get('href')).query).get('applicantId', [''])[0] if applicant_link else ''
        number_cell = cells[columns['number']] if 'number' in columns else None
        number_link = number_cell.find('a') if number_cell else None
        page.rows.append({
            'rcl_id': int(match[1]),
            'title': link.text(),
            'applicant': cells[columns['applicant']].text() if 'applicant' in columns else '',
            'applicant_id': applicant_id,
            'wykaz_number': normalize_wykaz(number_cell.text()) if number_cell else '',
            'wykaz_url': number_link.get('href') if number_link else '',
            'created_on': parse_date(cells[columns['created']].text()) if 'created' in columns else None,
            'modified_on': parse_date(cells[columns['modified']].text()) if 'modified' in columns else None,
        })
    text = root.text()
    total = re.search(r'wybranych kryteriów:\s*(\d+)', text)
    page.total = int(total[1]) if total else None
    if page.total and not page.rows:
        raise RclParseError('list_rows_missing')
    return page


# --- strona projektu ---

_STAGE_LABEL = re.compile(r'^\s*(\d+)\s*\.\s*(.+?)\s*$')
_FLAGS = {'cbp_tmicon_notstart': 'not_started', 'cbp_tmicon_active': 'active', 'cbp_tmicon': 'reached'}


def _stage_state(node):
    icon = next((c for c in node.child_nodes('div') if any(k.startswith('cbp_tmicon') for k in c.classes)), None)
    classes = icon.classes if icon else set()
    for key in ('cbp_tmicon_notstart', 'cbp_tmicon_active'):
        if key in classes:
            return _FLAGS[key]
    return 'reached' if icon is not None else 'not_started'


def parse_stage_node(node, project_id=None):
    label = next((c for c in node.child_nodes('div') if any(k.startswith('cbp_tmlabel') for k in c.classes)), None)
    if label is None:
        raise RclParseError('stage_label_missing')
    inner = label.child_nodes('div')
    inner = inner[0] if inner else label
    link = inner.find('a')
    title = (link.text() if link else inner.own_text()) or inner.own_text()
    match = _STAGE_LABEL.match(title)
    started = ended = None
    for p in node.find_all('p'):
        if p.inside(cls='cbp_tmtime'):
            text = fold(p.text())
            if text.startswith('rozpoczecie'):
                started = parse_date(text)
            elif text.startswith('zakonczenie'):
                ended = parse_date(text)
    small = next((d for d in label.find_all('div', cls='small2') if 'modyfikacji' in fold(d.text()) and not d.inside(cls='clearbox')), None)
    href = link.get('href') if link else ''
    stage_id = node.get('id')
    if not stage_id.isdigit():
        raise RclParseError('stage_id_missing')
    name = (match[2] if match else title).strip()
    return {
        'rcl_id': int(stage_id),
        'number': int(match[1]) if match else None,
        'name': name,
        'kind': stage_kind(name),
        'state': _stage_state(node),
        'started_on': started,
        'ended_on': ended,
        'modified_on': parse_date(small.text()) if small else None,
        'catalog_url': absolute(href.split('#')[0]) if href else '',
    }


def timeline_nodes(root):
    nodes = []
    for ul in root.find_all('ul', cls='cbp_tmtimeline'):
        nodes += [li for li in ul.child_nodes('li') if li.get('id')]
    return nodes


_INFO_NOTES = ('clearbox-grey',)


def parse_project(html, rcl_id):
    if is_rejected(html):
        raise RclParseError('request_rejected')
    root = build_dom(html)
    title_node = root.find('div', cls='rcl-title')
    info_node = root.find('div', cls='info')
    if title_node is None or info_node is None:
        raise RclParseError('project_title_or_info_missing')
    info, cells = {}, {}
    for row in info_node.child_nodes('div'):
        parts = row.child_nodes('div')
        if len(parts) >= 2:
            label = squash(parts[0].text()).rstrip(':')
            info[label] = parts[1].text()
            cells[fold(label)] = parts[1]
    stages = []
    skipped = 0
    nodes = timeline_nodes(root)
    for node in nodes:
        try:
            stages.append(parse_stage_node(node))
        except RclParseError:
            skipped += 1
    if not nodes or (nodes and not stages):
        raise RclParseError('stage_timeline_missing')

    def cell(label):
        return cells.get(fold(label))

    def links(label):
        node = cell(label)
        return [a.text() for a in node.find_all('a') if a.text()] if node else []

    applicant_cell, wykaz_cell = cell('Wnioskodawca'), cell('Numer z wykazu')
    applicant_link = applicant_cell.find('a') if applicant_cell else None
    wykaz_link = wykaz_cell.find('a') if wykaz_cell else None
    sejm_url = rm_number = ''
    for link in root.find_all('a'):
        href = link.get('href')
        if 'sejm.gov.pl' in href:
            sejm_url = href
            rm_number = parse_qs(urlsplit(href).query).get('Id', [''])[0]
            break
    notes = [p.text() for box in root.find_all('div', cls='clearbox-grey') for p in box.find_all('p') if p.text()]
    changelog = next((a.get('href') for a in root.find_all('a') if '/projekt/rejestr/' in a.get('href')), '')
    return {
        'rcl_id': int(rcl_id),
        'title': title_node.text(),
        'applicant': applicant_cell.text() if applicant_cell else '',
        'applicant_id': parse_qs(urlsplit(applicant_link.get('href')).query).get('applicantId', [''])[0] if applicant_link else '',
        'created_on': parse_date(cell('Data utworzenia').text()) if cell('Data utworzenia') else None,
        'departments': links('Działy'),
        'keywords': links('Hasła'),
        'status': cell('Status projektu').text() if cell('Status projektu') else '',
        'wykaz_name': cell('Wykaz prac legislacyjnych').text() if cell('Wykaz prac legislacyjnych') else '',
        'wykaz_number': normalize_wykaz(wykaz_cell.text()) if wykaz_cell else '',
        'wykaz_url': wykaz_link.get('href') if wykaz_link else '',
        'term': cell('Kadencja').text() if cell('Kadencja') else '',
        'info': info,
        'notes': notes,
        'sejm_url': sejm_url,
        'rm_number': rm_number,
        'changelog_url': absolute(changelog) if changelog else '',
        'stages': stages,
        'stages_skipped': skipped,
        'types': menu_types(root),
    }


# --- katalog etapu ---

_DOC_ID = re.compile(r'dokument(\d+)\.([A-Za-z0-9]{1,8})(?:$|\?)')


def _parse_document(li, folder, stage_kind_name):
    link = li.find('a')
    href = link.get('href') if link else ''
    match = _DOC_ID.search(href)
    if not match:
        return None
    author = created = None
    for small in li.find_all('div', cls='small3'):
        text = small.text()
        if 'Autor dokumentu:' in text:
            # Tylko podmiot; imię i nazwisko pracownika po "wprowadzony przez:" nie jest zapisywane.
            author = squash(text.split('Autor dokumentu:', 1)[1].split('wprowadzony przez', 1)[0]).rstrip(' ,')
        if 'Data utworzenia:' in text:
            created = parse_date(text.split('Data utworzenia:', 1)[1])
    name = link.text()
    folder_name = folder['name'] if folder else ''
    return {
        'rcl_doc_id': int(match[1]),
        'name': name,
        'file_url': absolute(href),
        'file_ext': match[2].lower(),
        'author': author or '',
        'created_on': created,
        'folder_rcl_id': folder['rcl_id'] if folder else None,
        'folder_name': folder_name,
        'category': document_category(folder_name, name, stage_kind_name),
    }


def parse_stage_catalog(html, stage_rcl_id):
    """Etap o numerze ``stage_rcl_id`` z katalogiem folderów i dokumentów (strona /projekt/<id>/katalog/<etap>)."""
    if is_rejected(html):
        raise RclParseError('request_rejected')
    root = build_dom(html)
    node = next((n for n in timeline_nodes(root) if n.get('id') == str(stage_rcl_id)), None)
    if node is None:
        raise RclParseError('stage_not_on_page')
    stage = parse_stage_node(node)
    folders, documents = [], []
    state = {'folder': None}

    def walk(parent):
        for child in parent.children:
            if not isinstance(child, Node):
                continue
            if 'clearbox' in child.classes:
                state['folder'] = None
            if child.tag == 'li' and 'childdir' in child.classes and child.get('id').isdigit():
                modified = child.find('div', cls='small2')
                state['folder'] = {'rcl_id': int(child.get('id')), 'name': child.own_text(),
                                   'modified_on': parse_date(modified.text()) if modified else None}
                folders.append(state['folder'])
                continue
            if child.tag == 'li' and 'doc' in child.classes:
                doc = _parse_document(child, state['folder'], stage['kind'])
                if doc:
                    documents.append(doc)
                continue
            walk(child)

    walk(node)
    return {'stage': stage, 'folders': folders, 'documents': documents}


def project_id_from_url(url):
    match = _PROJECT_ID.search(unquote(urlsplit(url).path))
    return int(match[1]) if match else None
