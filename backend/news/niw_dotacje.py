"""Lista umów NIW-CRSO (dotacje krajowe). Identyfikatory, nigdy dopasowanie po nazwie.

Warunki Prawnika (13.10.2026):
1. tylko wiersze z poprawnym numerem KRS (rejestr KRS); bez KRS, z ewidencji albo osoba fizyczna: pominięte i policzone;
2. każdy rekord niesie źródło i stan pliku (ATTRIBUTION), bez logo NIW i bez słowa „oficjalny”;
3. PLN i EUR osobno, bez sumowania (SUMS_NOTE);
4. archiwum pobranego pliku z datą i SHA-256 (archive_file), katalog konfigurowalny, poza repo;
5. zastrzeżenie przy powiązaniach z osobami publicznymi (people_note).
"""
import hashlib
import os
import posixpath
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import requests
from django.db import transaction
from django.utils import timezone

PAGE_URL = 'https://niw.gov.pl/o-niw/lista-dotacji/'
MAX_BYTES = 20 * 1024 * 1024
MAX_MEMBER_BYTES = 200 * 1024 * 1024  # jeden plik XML po rozpakowaniu; XLSX z 10,7 tys. wierszy ma ok. 15 MB
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
USER_AGENT = 'przeszlosc.today/1.0 (+https://przeszlosc.today; NIW public grants)'

SUMS_NOTE = ('Środki krajowe, unijne i z 1,5% PIT pokazujemy osobno i nie sumujemy, '
             'bo ten sam projekt może być w kilku zbiorach.')
PEOPLE_NOTE = ('Powiązanie osoby z organizacją wynika z jawnych rejestrów (stan na {stan}). '
               'Nie oznacza, że osoba decydowała o przyznaniu środków, o nich wiedziała ani że organizacja jest od niej zależna. '
               'Nie oceniamy osób ani decyzji.')


def attribution(file_date, fetched):
    """Dopisek przy każdym wyświetlanym rekordzie (warunek 2)."""
    return (f'Źródło: NIW-CRSO, Lista dotacji, stan na {file_date}, pobrano {fetched}. '
            'Opracowanie iapply, nie jest publikacją NIW. Kwota wynika z umowy i nie oznacza wypłaty.')


def people_note(stan):
    return PEOPLE_NOTE.format(stan=stan)


def file_date(name):
    """Data stanu z nazwy pliku NIW: DD-MM-RRRR (jak u NIW) albo RRRR-MM-DD."""
    name = unquote(str(name))
    match = re.search(r'(\d{2})[-_.](\d{2})[-_.](20\d{2})', name)
    if match:
        day, month, year = map(int, match.groups())
    else:
        match = re.search(r'(20\d{2})[-_.](\d{2})[-_.](\d{2})', name)
        if not match:
            raise ValueError('Brak daty stanu w nazwie pliku (DD-MM-RRRR). Zachowaj oryginalną nazwę NIW.')
        year, month, day = map(int, match.groups())
    return date(year, month, day).isoformat()


def is_official(url):
    parts = urlsplit(url)
    return parts.scheme == 'https' and parts.hostname in ('niw.gov.pl', 'www.niw.gov.pl') and parts.port in (None, 443)


def official_url(url):
    if not is_official(url):
        raise ValueError('Dozwolone są tylko pliki HTTPS z niw.gov.pl.')
    return url


def download(url):
    """Pobranie z limitem rozmiaru; każde przekierowanie sprawdzane osobno (tylko https://niw.gov.pl)."""
    for _ in range(5):
        with requests.get(official_url(url), stream=True, timeout=(10, 60), allow_redirects=False,
                          headers={'User-Agent': USER_AGENT}) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                if not location:
                    raise ValueError('Przekierowanie NIW bez adresu docelowego.')
                url = urljoin(url, location)
                continue
            response.raise_for_status()
            try:
                declared = int(response.headers.get('Content-Length') or 0)
            except ValueError:
                declared = 0
            if declared > MAX_BYTES:
                raise ValueError('Plik przekracza limit 20 MB.')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('Plik przekracza limit 20 MB.')
                chunks.append(chunk)
            return b''.join(chunks), url
    raise ValueError('Zbyt wiele przekierowań NIW.')


def latest_file(html):
    """Najnowszy (po dacie w nazwie) odnośnik do XLSX „Lista-dotacji” na stronie NIW; obce hosty pomijane."""
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get('href') or ''
            path = unquote(urlsplit(href).path).lower()
            if tag != 'a' or not path.endswith('.xlsx') or 'lista-dotacji' not in path:
                return
            url = urljoin(PAGE_URL, href)
            if not is_official(url):
                return
            try:
                self.links.append((file_date(url), url))
            except ValueError:
                pass

    parser = Links()
    parser.feed(html)
    if not parser.links:
        raise ValueError('Na stronie NIW nie znaleziono listy dotacji XLSX z datą w nazwie.')
    return max(parser.links)[1]


def archive_file(raw, name, directory=None):
    """Kopia pobranego pliku z datą stanu, datą pobrania i SHA-256 w nazwie (warunek 4). Zwraca ścieżkę.

    Katalog: argument, zmienna NIW_ARCHIWUM_DIR albo backend/reports/niw (poza repo: backend/reports/ jest w .gitignore).
    Ten sam plik (ta sama suma) nie jest zapisywany drugi raz.
    """
    if directory is None:
        directory = os.environ.get('NIW_ARCHIWUM_DIR')
    if not directory:
        from django.conf import settings
        directory = Path(settings.BASE_DIR) / 'reports' / 'niw'
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    existing = sorted(directory.glob(f'*-{digest[:16]}.xlsx'))
    if existing:
        return existing[0]
    target = directory / f'Lista-dotacji-NIW-CRSO-stan-{file_date(name)}-pobrano-{timezone.localdate().isoformat()}-{digest[:16]}.xlsx'
    target.write_bytes(raw)
    return target


def normal(value):
    value = unicodedata.normalize('NFKD', str(value).casefold().replace('ł', 'l'))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if not unicodedata.combining(c))).strip()


ALIASES = {
    'subject': ('tytul', 'tytul wniosku', 'tytul zadania', 'tytul zadania publicznego', 'tytul projektu', 'nazwa zadania', 'tytul oferty'),
    'programme': ('program', 'nazwa programu'),
    'competition': ('konkurs', 'nazwa konkursu', 'edycja'),
    'amount': ('kwota', 'kwota dotacji', 'kwota dotacji zl', 'kwota dotacji w zl', 'kwota przyznanej dotacji', 'przyznana dotacja',
               'wysokosc dotacji', 'kwota umowy'),
    'contract_no': ('numer umowy', 'nr umowy'),
    'signed': ('data umowy', 'data zawarcia umowy', 'data podpisania umowy'),
    'beneficiary': ('nazwa oferenta', 'oferent', 'nazwa organizacji', 'beneficjent', 'nazwa podmiotu'),
    'nip': ('nip', 'nip oferenta'),
    'register': ('rejestr', 'nazwa rejestru', 'rodzaj rejestru'),
    'krs': ('krs', 'numer krs', 'nr krs', 'numer w rejestrze', 'nr w rejestrze', 'numer rejestru',
            'krs inny rejestr', 'numer krs lub innego rejestru'),
}
# Opcjonalna kolumna: numer wniosku jest unikalny (np. 3_FIO2018), a numer umowy powtarza się między konkursami.
OPTIONAL_ALIASES = {'application_no': ('numer wniosku', 'nr wniosku')}
KRS_REGISTER = ('krs', 'krajowy rejestr sadowy', 'rejestr stowarzyszen', 'rejestr przedsiebiorcow')
PERSON_REGISTER = ('osoba', 'fizycz')  # fragmenty w kolumnie „rejestr” oznaczające osobę fizyczną


def nip_valid(nip):
    """Suma kontrolna NIP (wagi 6 5 7 2 3 4 5 6 7, mod 11)."""
    if len(nip) != 10 or not nip.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(nip[:9], (6, 5, 7, 2, 3, 4, 5, 6, 7)))
    return total % 11 == int(nip[9])


def identifier(value, kind):
    value = str(value).strip()
    if re.fullmatch(r'\d+\.0+', value):
        value = value.split('.')[0]
    value = re.sub(r'^(?:PL|KRS)\s*', '', value, flags=re.I)
    value = re.sub(r'[\s-]', '', value)
    if not value.isascii() or not value.isdigit():
        return ''
    if kind == 'krs':
        return value.zfill(10) if 1 <= len(value) <= 10 else ''
    return value if kind == 'nip' and nip_valid(value) else ''


def signed_date(value, epoch1904=False):
    """Numer seryjny Excela (także 1904) albo tekst daty; brak wartości = None."""
    value = str(value or '').strip()
    if not value:
        return None
    try:
        serial = int(Decimal(value))
    except (InvalidOperation, ValueError, OverflowError):
        for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                pass
        raise ValueError(f'Nieprawidłowa data umowy: {value!r}')
    if not (0 if epoch1904 else 1) <= serial <= 80000:  # 1900-01-01 (1904-01-01) .. ok. 2119; poza zakresem = błąd danych
        raise ValueError(f'Data umowy poza zakresem: {value!r}')
    # Excel błędnie uznaje 1900 za rok przestępny (serial 60 = fikcyjny 29.02.1900).
    base = date(1904, 1, 1) if epoch1904 else date(1899, 12, 31)
    return (base + timedelta(days=serial if epoch1904 or serial < 60 else serial - 1)).isoformat()


def amount_value(text):
    """„1 250,50”, „1.250,50 zł”, „1,250.50 PLN”, „1250.5” -> Decimal z dwoma miejscami; ujemne i nieskończone odrzucone."""
    money = re.sub(r'\s|PLN|zł|zl', '', str(text), flags=re.I)
    if ',' in money and '.' in money:
        decimal_sep = ',' if money.rfind(',') > money.rfind('.') else '.'
        money = money.replace('.' if decimal_sep == ',' else ',', '').replace(',', '.')
    elif ',' in money:
        money = money.replace(',', '.') if money.count(',') == 1 else money.replace(',', '')
    try:
        amount = Decimal(money)
    except InvalidOperation:
        raise ValueError(f'Nieprawidłowa kwota dotacji: {text!r}')
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'Nieprawidłowa kwota dotacji: {text!r}')
    return amount.quantize(Decimal('.01'))


def _member(archive, path, limit=MAX_MEMBER_BYTES):
    """Czyta jeden plik z archiwum z twardym limitem rozpakowanych bajtów (nagłówek ZIP może kłamać o rozmiarze)."""
    if path not in archive.namelist():
        raise ValueError(f'Brak części {path} w XLSX.')
    chunks, size = [], 0
    with archive.open(path) as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError('Rozpakowany XLSX przekracza limit 200 MB.')
            chunks.append(chunk)
    raw = b''.join(chunks)
    if b'<!DOCTYPE' in raw[:4096] or b'<!ENTITY' in raw:
        raise ValueError('XLSX zawiera deklaracje DTD/ENTITY, których nie przetwarzamy.')
    return raw


def _xml(archive, path):
    return ET.fromstring(_member(archive, path))


def _column(ref):
    return re.sub(r'\d', '', ref or '')


def _next_column(col):
    """A -> B, Z -> AA (komórki bez atrybutu r idą w kolejności)."""
    if not col:
        return 'A'
    letters = list(col)
    i = len(letters) - 1
    while i >= 0:
        if letters[i] != 'Z':
            letters[i] = chr(ord(letters[i]) + 1)
            return ''.join(letters)
        letters[i] = 'A'
        i -= 1
    return 'A' + ''.join(letters)


def _merged(sheet):
    """{adres komórki: adres lewej górnej} dla scalonych zakresów; wartość stoi tylko w lewej górnej."""
    out = {}
    for merge in sheet.findall('s:mergeCells/s:mergeCell', NS):
        ref = merge.get('ref') or ''
        match = re.fullmatch(r'([A-Z]+)(\d+):([A-Z]+)(\d+)', ref)
        if not match:
            continue
        c1, r1, c2, r2 = match.group(1), int(match.group(2)), match.group(3), int(match.group(4))
        col = c1
        while True:
            for row in range(r1, r2 + 1):
                out[f'{col}{row}'] = f'{c1}{r1}'
            if col == c2:
                break
            col = _next_column(col)
    return out


def _rows(sheet, strings):
    """Kolejne wiersze arkusza jako {kolumna: tekst}; scalone komórki dostają wartość lewej górnej."""
    merged = _merged(sheet)
    anchors = {}
    for row in sheet.findall('s:sheetData/s:row', NS):
        cells, col = {}, ''
        for cell in row.findall('s:c', NS):
            ref = cell.get('r') or ''
            col = _column(ref) or _next_column(col)
            ref = ref or f'{col}{row.get("r", "")}'
            kind = cell.get('t')
            if kind == 'inlineStr':
                value = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
            else:
                value = cell.findtext('s:v', default='', namespaces=NS)
                if kind == 's':
                    value = strings[int(value)]
            value = value.strip()
            if ref in merged:
                if merged[ref] == ref:
                    anchors[ref] = value
                elif not value:
                    value = anchors.get(merged[ref], '')
            cells[col] = value
        yield cells


def parse_xlsx(raw, name):
    """Umowy z pliku NIW. Zwraca (rekordy, statystyki pominięć). Tylko wiersze z KRS (warunek 1)."""
    stamp = file_date(name)
    digest = hashlib.sha256(raw).hexdigest()
    records = []
    stats = {'bez_krs': 0, 'osoby_fizyczne': 0, 'bledne': 0, 'duplikaty': 0}
    with ZipFile(BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > MAX_MEMBER_BYTES:
            raise ValueError('Rozpakowany XLSX przekracza limit 200 MB.')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//s:t', NS)) for si in _xml(archive, 'xl/sharedStrings.xml')]
        workbook = _xml(archive, 'xl/workbook.xml')
        prop = workbook.find('s:workbookPr', NS)
        epoch1904 = prop is not None and prop.get('date1904') in ('1', 'true')
        rels = {r.get('Id'): r.get('Target') for r in _xml(archive, 'xl/_rels/workbook.xml.rels')}
        found = False
        for sheet in workbook.findall('s:sheets/s:sheet', NS):
            target = rels.get(sheet.get(REL_ID)) or ''
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            headers = None
            for cells in _rows(_xml(archive, path), strings):
                if headers is None:
                    candidate = {field: col for col, value in cells.items() for field, aliases in {**ALIASES, **OPTIONAL_ALIASES}.items() if normal(value) in aliases}
                    if set(ALIASES) <= candidate.keys():
                        headers, found = candidate, True
                    continue
                if not any(cells.values()):
                    continue
                data = {key: cells.get(col, '') for key, col in headers.items()}
                data.setdefault('application_no', '')
                register = normal(data['register'])
                data['nip'] = identifier(data['nip'], 'nip')
                data['krs'] = identifier(data['krs'], 'krs') if register in KRS_REGISTER else ''
                if not data['krs']:
                    stats['bez_krs'] += 1
                    if any(p in register for p in PERSON_REGISTER):
                        stats['osoby_fizyczne'] += 1
                    continue
                try:
                    if not data['contract_no'] or len(data['contract_no']) > 200:
                        raise ValueError('Brak numeru umowy albo numer dłuższy niż 200 znaków.')
                    if normal(str(data['signed'])) not in ('', 'brak danych', 'brak', 'nd', 'b d'):
                        signed = signed_date(data['signed'], epoch1904)
                    else:  # brak daty umowy w źródle nie unieważnia wiersza z KRS i kwotą; pokazujemy go bez daty
                        signed = None
                        stats['bez_daty'] = stats.get('bez_daty', 0) + 1
                    data.update(amount=str(amount_value(data['amount'])), signed=signed)
                except ValueError:
                    stats['bledne'] += 1
                    continue
                data.update(file_date=stamp, file_sha256=digest)
                records.append(data)
        if not found:
            raise ValueError('Nie rozpoznano kompletu kolumn listy dotacji NIW.')
    return dedupe(records, stats), stats


def record_key(data):
    # Numer wniosku identyfikuje umowę jednoznacznie; sam numer umowy bywa powtarzany w kolejnych konkursach.
    return (data.get('application_no') or '').strip() or data['contract_no'].strip()


def dedupe(records, stats):
    """Ten sam numer umowy: identyczny wiersz odpada; inny podmiot/kwota/data dostaje klucz z programem i KRS."""
    by_key, out = {}, []
    for data in records:
        key = record_key(data)
        fingerprint = (data['krs'], data['amount'], data['signed'], normal(data['programme']))
        if key in by_key:
            if fingerprint in by_key[key]:
                stats['duplikaty'] += 1
                continue
            key = f"{key}|{normal(data['programme'])[:40]}|{data['krs']}"[:256]
            if key in by_key:
                stats['duplikaty'] += 1
                continue
        by_key.setdefault(key, set()).add(fingerprint)
        data['external_id'] = key
        out.append(data)
    return out


def save_records(records, response_url, remove_stale=True):
    """Zapis zbiorczy (upsert po numerze umowy). Zwraca liczby: created, updated, unchanged, removed.

    Rekordy, których nie ma już w nowszym pliku, są usuwane (stan listy = stan pliku), chyba że remove_stale=False
    albo wgrywany plik jest starszy niż ten w bazie.
    """
    from news.public_records_models import PublicRecord
    now = timezone.now()
    counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'removed': 0}
    columns = ['source_url', 'response_url', 'response_sha256', 'date', 'title', 'text', 'data', 'fetched_at']
    with transaction.atomic():
        existing = {r.external_id: r for r in PublicRecord.objects.filter(source='niw', kind='grant_pl')}
        newest_in_db = max((r.data.get('file_date') or '' for r in existing.values()), default='')
        new, changed = [], []
        for data in records:
            key = data.get('external_id') or record_key(data)
            fields = {'source_url': PAGE_URL, 'response_url': response_url or PAGE_URL, 'response_sha256': data['file_sha256'],
                      'date': data['signed'], 'title': data['subject'], 'text': data['beneficiary'], 'data': data}
            row = existing.get(key)
            if row is None:
                new.append(PublicRecord(source='niw', kind='grant_pl', external_id=key, fetched_at=now, **fields))
                counts['created'] += 1
            elif row.data != data:
                for field, value in fields.items():
                    setattr(row, field, value)
                row.fetched_at = now
                changed.append(row)
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        if new:
            PublicRecord.objects.bulk_create(new, batch_size=500)
        if changed:
            PublicRecord.objects.bulk_update(changed, columns, batch_size=500)
        if remove_stale and records:
            current = records[0]['file_date']
            if current >= newest_in_db:
                keys = {data.get('external_id') or record_key(data) for data in records}
                stale = [pk for key, r in existing.items() if key not in keys for pk in (r.pk,)]
                counts['removed'] = PublicRecord.objects.filter(pk__in=stale).delete()[0] if stale else 0
    return counts
