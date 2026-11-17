"""Wykaz MF: wskazania podatników, osobno od dotacji. Parser XLSX bez zależności."""
import hashlib
import json
import os
import posixpath
import re
from datetime import date
from decimal import InvalidOperation
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile

import requests
from django.db import transaction
from django.utils import timezone
from news import niw_dotacje as niw

PAGE_URL = 'https://dane.gov.pl/pl/dataset/171'
RESOURCES_URL = 'https://api.dane.gov.pl/1.4/datasets/171/resources?per_page=100&sort=-data_date'
MAX_BYTES = 20 * 1024 * 1024
NOTE = ('Kwoty z 1,5% podatku to wskazania podatników, nie decyzje organu i nie dotacje; '
        'pokazujemy je osobno i nie sumujemy z dotacjami krajowymi ani unijnymi.')


def attribution(tax_year, file_date):
    return (f'Źródło: Ministerstwo Finansów, wykaz OPP, rok podatkowy {tax_year}, stan na {file_date}. '
            'Kwota pochodzi z 1,5% podatku wskazanego przez podatników, nie jest dotacją i nie sumuje się z dotacjami.')


def official_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'api.dane.gov.pl' or p.port not in (None, 443) or p.username or p.password:
        raise ValueError('Dozwolone są tylko adresy HTTPS z api.dane.gov.pl.')
    return url


def download(url):
    for _ in range(5):
        with requests.get(official_url(url), stream=True, timeout=(10, 60), allow_redirects=False,
                          headers={'User-Agent': 'przeszlosc.today/1.0 (+https://przeszlosc.today; MF OPP)'}) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                if not location:
                    raise ValueError('Przekierowanie MF bez adresu docelowego.')
                url = urljoin(url, location)
                continue
            response.raise_for_status()
            if int(response.headers.get('Content-Length') or 0) > MAX_BYTES:
                raise ValueError('Plik przekracza limit 20 MB.')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('Plik przekracza limit 20 MB.')
                chunks.append(chunk)
            return b''.join(chunks), url
    raise ValueError('Zbyt wiele przekierowań MF.')


def select_resources(payload, years=None):
    """Lata oznaczają rok wpłaty; jedna najnowsza wersja pliku dla każdego roku."""
    selected = {}
    for item in payload['data']:
        a = item['attributes']
        title = a.get('title') or ''
        match = re.match(r'^Wykaz OPP, które w (20\d{2}) r\. otrzymały', title, re.I)
        if not match or str(a.get('format')).lower() != 'xlsx':
            continue
        payment = int(match[1])
        tax = re.search(r'\bza\s+(?:rok\s+)?(20\d{2})\b', title, re.I)
        resource = {'payment_year': payment, 'tax_year': int(tax[1]) if tax else payment - 1,
                    'file_date': date.fromisoformat(a['data_date'][:10]).isoformat(),
                    'resource_url': official_url(a['download_url'])}
        if payment not in selected or resource['file_date'] > selected[payment]['file_date']:
            selected[payment] = resource
    if not selected:
        raise ValueError('Nie znaleziono wykazu OPP XLSX.')
    wanted = set(years) if years else {max(selected)}
    if wanted - selected.keys():
        raise ValueError(f'Brak wykazu dla lat wpłaty: {sorted(wanted - selected.keys())}.')
    return [selected[y] for y in sorted(wanted)]


def resources(years=None):
    # Kolejne strony też przechodzą kontrolę hosta, przekierowań i rozmiaru.
    items, seen, url = [], set(), RESOURCES_URL
    while url:
        if url in seen or len(seen) >= 20:
            raise ValueError('Nieprawidłowa paginacja zasobów MF.')
        seen.add(url)
        raw, _ = download(url)
        payload = json.loads(raw)
        items.extend(payload['data'])
        url = (payload.get('links') or {}).get('next')
    return select_resources({'data': items}, years)


def parse_xlsx(raw, resource):
    if len(raw) > MAX_BYTES:
        raise ValueError('Plik przekracza limit 20 MB.')
    digest = hashlib.sha256(raw).hexdigest()
    records, seen = [], set()
    stats = {'bledne': 0, 'duplikaty': 0}
    aliases = {'krs': 'numer krs', 'name': 'nazwa organizacji pozytku publicznego', 'amount': 'kwota w zl'}
    with ZipFile(BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > niw.MAX_MEMBER_BYTES:
            raise ValueError('Rozpakowany XLSX przekracza limit 200 MB.')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//s:t', niw.NS))
                       for si in niw._xml(archive, 'xl/sharedStrings.xml')]
        workbook = niw._xml(archive, 'xl/workbook.xml')
        sheets = workbook.findall('s:sheets/s:sheet', niw.NS)
        if len(sheets) != 1:
            raise ValueError('Wykaz OPP musi mieć jeden arkusz.')
        rels = {r.get('Id'): r.get('Target') for r in niw._xml(archive, 'xl/_rels/workbook.xml.rels')}
        target = rels[sheets[0].get(niw.REL_ID)]
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        sheet = niw._xml(archive, path)
        # Scalenia nagłówka nie przenoszą wartości między organizacjami.
        for merged in sheet.findall('s:mergeCells', niw.NS):
            sheet.remove(merged)
        headers = None
        for cells in niw._rows(sheet, strings):
            if headers is None:
                candidate = {key: col for col, value in cells.items() for key, alias in aliases.items()
                             if niw.normal(value) == alias}
                if set(candidate) == set(aliases):
                    headers = candidate
                continue
            if not any(cells.values()):
                continue
            data = {key: cells.get(col, '') for key, col in headers.items()}
            try:
                if not re.fullmatch(r'[0-9]{10}', data['krs']) or not data['name']:
                    raise ValueError('Błędny KRS lub brak nazwy.')
                data['amount'] = str(niw.amount_value(data['amount']))
            except (ValueError, InvalidOperation):
                stats['bledne'] += 1
                continue
            if data['krs'] in seen:
                stats['duplikaty'] += 1
                raise ValueError(f"Powtórzony KRS w wykazie: {data['krs']}.")
            seen.add(data['krs'])
            data.update(resource, file_sha256=digest)
            records.append(data)
        if headers is None:
            raise ValueError('Nie rozpoznano kompletu kolumn wykazu OPP.')
    return records, stats


def archive_file(raw, resource, directory=None):
    from django.conf import settings
    directory = Path(directory or os.environ.get('OPP_ARCHIWUM_DIR') or Path(settings.BASE_DIR) / 'reports' / 'opp')
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    prefix = f"OPP-{resource['payment_year']}-stan-{resource['file_date']}"
    existing = sorted(directory.glob(f'{prefix}-pobrano-*-{digest}.xlsx'))
    if existing:
        return existing[0]
    path = directory / f'{prefix}-pobrano-{timezone.localdate().isoformat()}-{digest}.xlsx'
    path.write_bytes(raw)
    return path


def save_records(records, remove_stale=True):
    """Upsert KRS:rok podatkowy; starszy stan nie zmienia nowszego. Pusty import nie usuwa."""
    from news.public_records_models import PublicRecord
    counts = dict(created=0, updated=0, unchanged=0, removed=0)
    if not records:
        return counts
    years = {r['tax_year'] for r in records}
    if len(years) != 1 or len({r['file_date'] for r in records}) != 1:
        raise ValueError('Zapis wymaga jednego roku podatkowego i stanu pliku.')
    year = records[0]['tax_year']
    with transaction.atomic():
        existing = {r.external_id: r for r in PublicRecord.objects.select_for_update().filter(
            source='mf_opp', kind='opp_15', data__tax_year=year)}
        stamp = records[0]['file_date']
        if stamp < max((r.data.get('file_date', '') for r in existing.values()), default=''):
            counts['unchanged'] = len(records)
            return counts
        keys, new, changed = set(), [], []
        now = timezone.now()
        for data in records:
            key = f"{data['krs']}:{year}"
            if key in keys:
                raise ValueError('Powtórzony KRS i rok podatkowy.')
            keys.add(key)
            fields = dict(source_url=PAGE_URL, response_url=data['resource_url'], response_sha256=data['file_sha256'],
                          date=data['file_date'], title=data['name'], text=data['name'], data=data, fetched_at=now)
            row = existing.get(key)
            if row is None:
                new.append(PublicRecord(source='mf_opp', kind='opp_15', external_id=key, **fields))
                counts['created'] += 1
            elif row.data != data:
                for field, value in fields.items():
                    setattr(row, field, value)
                changed.append(row)
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1
        PublicRecord.objects.bulk_create(new, batch_size=500)
        if changed:
            PublicRecord.objects.bulk_update(changed, list(fields), batch_size=500)
        if remove_stale:
            stale = [r.pk for key, r in existing.items() if key not in keys]
            counts['removed'] = PublicRecord.objects.filter(pk__in=stale).delete()[0] if stale else 0
    return counts
