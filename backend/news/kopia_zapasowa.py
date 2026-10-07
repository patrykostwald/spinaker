"""Kopia poza serwer (Z2, przegląd architekta 7.10): nocny pg_dump szyfrowany po stronie serwera trafia do Backblaze B2.

Przepływ (deploy/backup.sh, cron 3:30 na serwerze):
  pg_dump | gzip  ->  plik lokalny (14 dni)  ->  manage.py kopia_zapasowa --z-stdin --nazwa <plik>
Polecenie w kontenerze backend: szyfruje strumień (openssl AES-256-CBC, PBKDF2 200 000 iteracji, hasło z BACKUP_PASSPHRASE,
nigdy w logach), wysyła do koszyka B2 przez API zgodne z S3 (podpis AWS SigV4 własny, bez boto3), usuwa obiekty starsze
niż 30 dni, liczy rozmiar koszyka (alarm ponad 8 GB: darmowe 10 GB) i zapisuje stan w RepairerState.
Zadanie Celery kopia_task (4:30): kontrola, czy w B2 jest kopia z ostatnich 26 h, retencja, a 1. dnia miesiąca test
odtworzenia: pobranie ostatniej kopii, odszyfrowanie, rozpakowanie i sprawdzenie spójności zrzutu (nagłówek, stopka
„PostgreSQL database dump complete”, liczba tabel wobec bieżącej bazy). Wynik w Raporcie pętli.
Dyżurny (check_backup): brak kopii zdalnej > 26 h = alarm krytyczny; nieudany test odtworzenia = krytyczny; rozmiar = ostrzeżenie.
Odtworzenie krok po kroku: docs/KOPIE-I-ODTWORZENIE.md."""
import gzip
import hashlib
import time
import base64
import hmac
import logging
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import quote

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

STATE_KEY = 'kopia-zapasowa'
RETENTION_DAYS = 30
MAX_AGE = timedelta(hours=26)
SIZE_GUARD = 8 * 1024 ** 3
PART_SIZE = 16 * 1024 ** 2  # mniejsze części: wolne łącze VPS->B2 przerywało zapis 64 MB (7.10)
PREFIXES = {'pg': 'pg/', 'media': 'media/'}
RUNS_KEEP = 60
TIMEOUT = (10, 300)
OPENSSL = ('openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '200000', '-salt', '-pass', 'env:BACKUP_PASSPHRASE')
RESTORE_DOC = 'docs/KOPIE-I-ODTWORZENIE.md'


def config():
    region = os.environ.get('B2_REGION', 'eu-central-003').strip() or 'eu-central-003'
    return {'key_id': os.environ.get('B2_KEY_ID', '').strip(), 'secret': os.environ.get('B2_APP_KEY', '').strip(),
            'bucket': os.environ.get('B2_BUCKET', '').strip(), 'region': region,
            'endpoint': os.environ.get('B2_ENDPOINT', f's3.{region}.backblazeb2.com').strip()}


def enabled():
    c = config()
    return bool(c['key_id'] and c['secret'] and c['bucket'])


def passphrase_set():
    return bool(os.environ.get('BACKUP_PASSPHRASE', '').strip())


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _hmac(key, message):
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


class S3:
    """Minimalny klient S3 (B2 S3-compatible API) z podpisem AWS SigV4; klucze tylko w pamięci procesu."""

    def __init__(self, cfg=None):
        self.cfg = cfg or config()

    def _path(self, key):
        return f"/{self.cfg['bucket']}/" + quote(key, safe='/-_.~')

    def _url(self, key):
        return f"https://{self.cfg['endpoint']}" + self._path(key)

    def _headers(self, method, key, query, payload_hash, now):
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        scope = f"{now:%Y%m%d}/{self.cfg['region']}/s3/aws4_request"
        canonical_uri = self._path(key)
        canonical_query = '&'.join(f"{quote(str(k), safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in sorted((query or {}).items()))
        headers = {'host': self.cfg['endpoint'], 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}
        signed = ';'.join(headers)
        canonical_headers = ''.join(f'{k}:{headers[k]}\n' for k in headers)
        canonical = '\n'.join([method, canonical_uri, canonical_query, canonical_headers, signed, payload_hash])
        to_sign = '\n'.join(['AWS4-HMAC-SHA256', amz_date, scope, _sha256(canonical.encode())])
        k_date = _hmac(('AWS4' + self.cfg['secret']).encode(), f'{now:%Y%m%d}')
        k_region = _hmac(k_date, self.cfg['region'])
        k_service = _hmac(k_region, 's3')
        k_signing = _hmac(k_service, 'aws4_request')
        signature = hmac.new(k_signing, to_sign.encode(), hashlib.sha256).hexdigest()
        auth = f"AWS4-HMAC-SHA256 Credential={self.cfg['key_id']}/{scope}, SignedHeaders={signed}, Signature={signature}"
        return {'Authorization': auth, 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}

    def request(self, method, key='', query=None, data=b'', stream=False, extra_headers=None):
        now = datetime.now(dt_timezone.utc)
        payload_hash = _sha256(data if isinstance(data, (bytes, bytearray)) else b'')
        headers = {**self._headers(method, key, query, payload_hash, now), **(extra_headers or {})}
        response = requests.request(method, self._url(key), params=query, data=data, headers=headers, timeout=TIMEOUT, stream=stream)
        if response.status_code >= 300:
            raise requests.HTTPError(f'B2 HTTP {response.status_code} ({method} {key or "/"})')
        return response

    def _put_part(self, key, number, upload_id, chunk, tries=3):
        # Content-MD5 wymagane przy koszyku z Object Lock; przerwany zapis części ponawiamy
        md5 = base64.b64encode(hashlib.md5(chunk).digest()).decode()
        for attempt in range(tries):
            try:
                return self.request('PUT', key, query={'partNumber': number, 'uploadId': upload_id}, data=chunk,
                                    extra_headers={'Content-MD5': md5})
            except requests.ConnectionError:
                if attempt == tries - 1:
                    raise
                time.sleep(2 ** attempt)

    def put_object(self, key, data):
        self.request('PUT', key, data=data, extra_headers={'Content-MD5': base64.b64encode(hashlib.md5(data).digest()).decode()})

    def upload_file(self, key, path):
        """Jeden PUT do PART_SIZE, powyżej - wysyłka wieloczęściowa (B2: pojedynczy PUT najwyżej 5 GB)."""
        size = os.path.getsize(path)
        with open(path, 'rb') as handle:
            if size <= PART_SIZE:
                self.put_object(key, handle.read())
                return size
            upload_id = ET.fromstring(self.request('POST', key, query={'uploads': ''}).content).findtext('{*}UploadId')
            etags = []
            number = 1
            try:
                while True:
                    chunk = handle.read(PART_SIZE)
                    if not chunk:
                        break
                    response = self._put_part(key, number, upload_id, chunk)
                    etags.append((number, response.headers.get('ETag', '').strip()))
                    number += 1
                body = ('<CompleteMultipartUpload>' + ''.join(f'<Part><PartNumber>{n}</PartNumber><ETag>{tag}</ETag></Part>' for n, tag in etags)
                        + '</CompleteMultipartUpload>').encode()
                self.request('POST', key, query={'uploadId': upload_id}, data=body)
            except requests.RequestException:
                try:
                    self.request('DELETE', key, query={'uploadId': upload_id})
                except requests.RequestException:
                    pass
                raise
        return size

    def list_objects(self, prefix=''):
        out = []
        token = None
        for _ in range(50):
            query = {'list-type': 2, 'prefix': prefix, 'max-keys': 1000}
            if token:
                query['continuation-token'] = token
            root = ET.fromstring(self.request('GET', '', query=query).content)
            for node in root.findall('{*}Contents'):
                modified = node.findtext('{*}LastModified') or ''
                try:
                    at = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                except ValueError:
                    at = None
                out.append({'key': node.findtext('{*}Key') or '', 'size': int(node.findtext('{*}Size') or 0), 'modified': at})
            token = root.findtext('{*}NextContinuationToken')
            if (root.findtext('{*}IsTruncated') or 'false').lower() != 'true' or not token:
                break
        return out

    def delete_object(self, key):
        self.request('DELETE', key)

    def download(self, key, path):
        with self.request('GET', key, stream=True) as response, open(path, 'wb') as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)
        return os.path.getsize(path)


# --- szyfrowanie (openssl w kontenerze; hasło tylko przez zmienną środowiska procesu) -----------------------------

def _openssl(args, src, dst):
    env = {**os.environ}
    if not env.get('BACKUP_PASSPHRASE'):
        raise RuntimeError('Brak BACKUP_PASSPHRASE')
    result = subprocess.run([*OPENSSL, *args, '-in', src, '-out', dst], env=env, capture_output=True, timeout=3600, check=False)
    if result.returncode != 0:
        raise RuntimeError(f'openssl zakończył się kodem {result.returncode}')


def encrypt(src, dst):
    _openssl([], src, dst)


def decrypt(src, dst):
    _openssl(['-d'], src, dst)


# --- stan ----------------------------------------------------------------------------------------------------------

def _row():
    from news.models import RepairerState
    row, _ = RepairerState.objects.get_or_create(key=STATE_KEY)
    return row


def _save(**data):
    row = _row()
    row.data = {**(row.data or {}), **data}
    row.save(update_fields=['data'])
    return row.data


def snapshot():
    from news.models import RepairerState
    row = RepairerState.objects.filter(key=STATE_KEY).first()
    return dict(row.data or {}) if row else {}


def _stamp(value):
    from news.repairer import stamp
    return stamp(value)


def runs_since(since):
    """Licznik dla Raportu pętli: udane kopie zdalne od chwili since i czas ostatniej."""
    runs = [r for r in (_stamp(v) for v in snapshot().get('runs') or []) if r]
    return sum(r >= since for r in runs), max(runs, default=None)


def _tmpdir():
    path = os.environ.get('BACKUP_TMP', '').strip() or tempfile.gettempdir()
    os.makedirs(path, exist_ok=True)
    return path


def _human(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{size} B'
        size /= 1024
    return f'{size:.1f} GB'


# --- kopia (polecenie z serwera) -----------------------------------------------------------------------------------

def retention(client, now, prefixes=PREFIXES.values()):
    """Usuwa obiekty starsze niż RETENTION_DAYS; zwraca (usunięte, pozostałe obiekty)."""
    cutoff = now - timedelta(days=RETENTION_DAYS)
    deleted, kept = [], []
    for prefix in prefixes:
        for obj in client.list_objects(prefix):
            if obj['modified'] and obj['modified'] < cutoff:
                client.delete_object(obj['key'])
                deleted.append(obj['key'])
            else:
                kept.append(obj)
    return deleted, kept


def backup(name, stream, kind='pg', now=None, client=None):
    """Szyfruje strumień (stdin skryptu) i wysyła do B2 jako <kind>/<name>.enc; potem retencja i stan."""
    if not enabled():
        return {'status': 'not_configured', 'error': 'Brak B2_KEY_ID, B2_APP_KEY albo B2_BUCKET'}
    if not passphrase_set():
        return {'status': 'not_configured', 'error': 'Brak BACKUP_PASSPHRASE (deploy/wdrozenie-0610.sh generuje je raz)'}
    now = now or timezone.now()
    client = client or S3()
    prefix = PREFIXES.get(kind, PREFIXES['pg'])
    key = f'{prefix}{os.path.basename(name)}.enc'
    folder = _tmpdir()
    plain, enc = os.path.join(folder, os.path.basename(name)), os.path.join(folder, os.path.basename(name) + '.enc')
    try:
        raw = 0
        with open(plain, 'wb') as handle:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                raw += len(chunk)
        if raw < 100:
            return {'status': 'error', 'error': f'Pusty strumień kopii ({raw} B) - nic nie wysłano'}
        encrypt(plain, enc)
        size = client.upload_file(key, enc)
        deleted, kept = retention(client, now)
        total = sum(o['size'] for o in kept)
        data = snapshot()
        runs = ([*(data.get('runs') or []), now.isoformat()] if kind == 'pg' else data.get('runs') or [])[-RUNS_KEEP:]
        _save(**{f'last_{kind}_at': now.isoformat(), f'last_{kind}_key': key, f'last_{kind}_bytes': size, 'runs': runs,
                 'last_local_at': now.isoformat() if kind == 'pg' else data.get('last_local_at'),
                 'remote_total_bytes': total, 'remote_count': len(kept), 'retention_deleted': len(deleted), 'last_error': ''})
        return {'status': 'ok', 'key': key, 'bytes': size, 'raw_bytes': raw, 'remote_total_bytes': total, 'remote_count': len(kept),
                'deleted': len(deleted), 'size_guard': total > SIZE_GUARD}
    except (requests.RequestException, RuntimeError, OSError, ET.ParseError) as error:
        _save(last_error=f'{type(error).__name__}: {str(error)[:160]}', last_error_at=now.isoformat())
        return {'status': 'error', 'error': f'{type(error).__name__}: {str(error)[:160]}'}
    finally:
        for path in (plain, enc):
            try:
                os.remove(path)
            except OSError:
                pass


# --- kontrola dzienna i test odtworzenia (zadanie Celery) ---------------------------------------------------------

def _newest(objects):
    rows = [o for o in objects if o['modified']]
    return max(rows, key=lambda o: o['modified']) if rows else None


def inspect_dump(path):
    """Spójność rozpakowanego zrzutu SQL: nagłówek, stopka, liczba tabel i tabel z danymi (COPY)."""
    from collections import deque
    tables = copies = 0
    last = deque(maxlen=5)  # stopka pg_dump: „-- PostgreSQL database dump complete” i linia „--” po niej
    with gzip.open(path, 'rb') as handle:
        head_ok = b'PostgreSQL database dump' in handle.read(4096)
        handle.seek(0)
        for line in handle:
            if line.startswith(b'CREATE TABLE'):
                tables += 1
            elif line.startswith(b'COPY '):
                copies += 1
            if line.strip():
                last.append(line)
    tail = any(b'PostgreSQL database dump complete' in line for line in last)
    return {'header': head_ok, 'trailer': tail, 'tables': tables, 'copies': copies}


def restore_test(now=None, client=None):
    """Pobiera ostatnią kopię, odszyfrowuje, rozpakowuje i porównuje z bieżącą bazą (test odtworzenia bez drugiej bazy)."""
    from django.db import connection
    now = now or timezone.now()
    client = client or S3()
    folder = _tmpdir()
    enc, plain = os.path.join(folder, 'restore-test.sql.gz.enc'), os.path.join(folder, 'restore-test.sql.gz')
    result = {'at': now.isoformat(), 'status': 'failed', 'detail': ''}
    try:
        newest = _newest(client.list_objects(PREFIXES['pg']))
        if not newest:
            result['detail'] = 'Brak kopii w koszyku.'
            return _finish(result)
        size = client.download(newest['key'], enc)
        decrypt(enc, plain)
        info = inspect_dump(plain)
        db_tables = len(connection.introspection.table_names())
        ratio = info['tables'] / db_tables if db_tables else 0
        ok = info['header'] and info['trailer'] and ratio >= .9
        result.update(status='ok' if ok else 'failed', key=newest['key'], bytes=size, tables_dump=info['tables'], tables_db=db_tables,
                      copies=info['copies'],
                      detail=(f"{newest['key']}: {_human(size)}, tabel w kopii {info['tables']} / w bazie {db_tables}, danych (COPY) {info['copies']}"
                              + ('' if ok else '; ' + ', '.join(filter(None, ['brak nagłówka' if not info['header'] else '',
                                                                           'brak stopki (zrzut urwany)' if not info['trailer'] else '',
                                                                           f'za mało tabel ({ratio:.0%})' if ratio < .9 else ''])))))
        return _finish(result)
    except (requests.RequestException, RuntimeError, OSError, EOFError, ET.ParseError) as error:
        result['detail'] = f'{type(error).__name__}: {str(error)[:160]}'
        return _finish(result)
    finally:
        for path in (enc, plain):
            try:
                os.remove(path)
            except OSError:
                pass


def _finish(result):
    _save(last_restore_test=result)
    return result


def daily_check(now=None, client=None):
    """4:30: świeża kopia zdalna (26 h), retencja, rozmiar; 1. dnia miesiąca (albo gdy ostatni test > 35 dni) test odtworzenia."""
    if not enabled():
        return {'status': 'disabled'}
    now = now or timezone.now()
    client = client or S3()
    try:
        deleted, kept = retention(client, now)
        newest = _newest([o for o in kept if o['key'].startswith(PREFIXES['pg'])])
        total = sum(o['size'] for o in kept)
        fresh = bool(newest and now - newest['modified'] <= MAX_AGE)
        known = _stamp(snapshot().get('last_pg_at'))
        newer = {'last_pg_at': newest['modified'].isoformat(), 'last_pg_key': newest['key'], 'last_pg_bytes': newest['size']} \
            if newest and (not known or newest['modified'] > known) else {}
        data = _save(checked_at=now.isoformat(), remote_total_bytes=total, remote_count=len(kept), retention_deleted=len(deleted),
                     remote_newest_at=newest['modified'].isoformat() if newest else None, remote_newest_key=newest['key'] if newest else '', **newer)
        last_test = _stamp((data.get('last_restore_test') or {}).get('at'))
        local = now.astimezone(timezone.get_current_timezone())
        tested = None
        if fresh and (local.day == 1 and (not last_test or now - last_test > timedelta(days=20)) or (last_test and now - last_test > timedelta(days=35))
                      or (not last_test and os.environ.get('BACKUP_RESTORE_TEST_FIRST', 'true').lower() == 'true')):
            tested = restore_test(now, client)
        result = {'status': 'ok' if fresh else 'error', 'produced': int(fresh), 'remote_count': len(kept), 'deleted': len(deleted),
                  'total_mb': round(total / 1024 ** 2, 1)}
        if not fresh:
            result['error'] = 'Brak kopii zdalnej z ostatnich 26 h' + (f" (ostatnia {newest['modified'].astimezone(local.tzinfo):%d.%m %H:%M})" if newest else '')
        if total > SIZE_GUARD:
            result['size_guard'] = True
        if tested:
            result['restore_test'] = tested['status']
        return result
    except (requests.RequestException, RuntimeError, OSError, ET.ParseError) as error:
        _save(last_error=f'{type(error).__name__}: {str(error)[:160]}', last_error_at=now.isoformat())
        return {'status': 'error', 'error': f'Kontrola kopii: {type(error).__name__}'}


# --- Dyżurny i Raport pętli (bez sieci) ---------------------------------------------------------------------------

BACKUP_CMD = 'ssh ubuntu@148.113.242.109 "sh /srv/spin-clinic/deploy/backup.sh && crontab -l | grep backup.sh"'


def check_backup(ctx):
    """Dyżurny: kopia zdalna starsza niż 26 h = krytyczny; nieudany test odtworzenia = krytyczny; koszyk > 8 GB = ostrzeżenie."""
    from news.duty import alarm
    if not enabled():
        return []
    data = snapshot()
    now = ctx.now
    out = []
    last = _stamp(data.get('last_pg_at'))
    if not last or now - last > MAX_AGE:
        hours = round((now - last).total_seconds() / 3600, 1) if last else None
        out.append(alarm('backup:stale', 'critical', 'Kopia poza serwer: brak kopii z ostatnich 26 h' if last else 'Kopia poza serwer: jeszcze żadnej kopii w B2',
                         {'hours': hours, 'last_error': data.get('last_error', '')}, last or now,
                         f'Uruchom kopię ręcznie i sprawdź cron: {BACKUP_CMD}'))
    total = int(data.get('remote_total_bytes') or 0)
    if total > SIZE_GUARD:
        out.append(alarm('backup:size', 'warning', f'Kopia poza serwer: koszyk B2 ma {_human(total)} (próg 8 GB, darmowe 10 GB)',
                         {'bytes': total, 'count': data.get('remote_count')}, now,
                         'Skróć retencję (RETENTION_DAYS w news/kopia_zapasowa.py) albo wyłącz kopię mediów; sprawdź, czy baza nie puchnie.'))
    test = data.get('last_restore_test') or {}
    if test.get('status') == 'failed':
        out.append(alarm('backup:restore-test', 'critical', 'Kopia poza serwer: test odtworzenia nie przeszedł',
                         {'detail': test.get('detail', '')[:200]}, _stamp(test.get('at')) or now,
                         'Sprawdź BACKUP_PASSPHRASE i kopię: manage.py kopia_zapasowa --test-odtworzenia; procedura w ' + RESTORE_DOC))
    return out


def report_line(now=None):
    """„Kopia: lokalna HH:MM, zdalna HH:MM (rozmiar, N plików / 30 dni), test odtworzenia DD.MM ok”."""
    if not enabled():
        return 'Kopia poza serwer: nieskonfigurowana (B2_KEY_ID, B2_APP_KEY, B2_BUCKET w .env.production) - kopia tylko na dysku VPS.'
    data = snapshot()
    tz = timezone.get_current_timezone()

    def when(value, fmt='%H:%M'):
        at = _stamp(value)
        return at.astimezone(tz).strftime(fmt) if at else 'brak'
    local_at, remote_at = _stamp(data.get('last_local_at')), _stamp(data.get('last_pg_at'))
    stale = now and remote_at and now - remote_at > MAX_AGE
    line = f"Kopia: lokalna {when(data.get('last_local_at'))}, zdalna {when(data.get('last_pg_at'))}"
    if remote_at and now and now.astimezone(tz).date() != remote_at.astimezone(tz).date():
        line += f" ({remote_at.astimezone(tz):%d.%m})"
    if data.get('remote_count'):
        line += f" ({_human(int(data.get('remote_total_bytes') or 0))}, {data['remote_count']} plików / {RETENTION_DAYS} dni)"
    test = data.get('last_restore_test') or {}
    line += f", test odtworzenia {when(test.get('at'), '%d.%m')} {'ok' if test.get('status') == 'ok' else 'NIEUDANY' if test else 'jeszcze nie było'}"
    if stale:
        line += ' - UWAGA: kopia zdalna starsza niż 26 h'
    if int(data.get('remote_total_bytes') or 0) > SIZE_GUARD:
        line += ' - UWAGA: koszyk ponad 8 GB'
    if data.get('last_error'):
        line += f"; ostatni błąd: {data['last_error'][:120]}"
    return line
