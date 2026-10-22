"""Kopia poza serwer (Z2): podpis SigV4, wysyłka i retencja, kontrola dzienna, test odtworzenia, bezpiecznik, raport."""
import gzip
import io
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from news import kopia_zapasowa as kz
from news.models import RepairerState

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 4, 30, tzinfo=ZoneInfo('Europe/Warsaw'))


class Ctx:
    def __init__(self, now):
        self.now = now


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})  # key -> (bytes, modified)
        self.deleted, self.uploaded = [], []

    def upload_file(self, key, path):
        with open(path, 'rb') as handle:
            data = handle.read()
        self.objects[key] = (data, NOW)
        self.uploaded.append(key)
        return len(data)

    def list_objects(self, prefix=''):
        return [{'key': k, 'size': len(v[0]), 'modified': v[1]} for k, v in self.objects.items() if k.startswith(prefix)]

    def delete_object(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)

    def download(self, key, path):
        with open(path, 'wb') as handle:
            handle.write(self.objects[key][0])
        return len(self.objects[key][0])


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for name, value in (('B2_KEY_ID', '003abc0000000000000000001'), ('B2_APP_KEY', 'K003SECRETSECRETSECRETSECRETSECRET'),
                        ('B2_BUCKET', 'spin-clinic-kopie'), ('BACKUP_PASSPHRASE', 'haslo-testowe'), ('BACKUP_TMP', str(tmp_path))):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(kz, 'encrypt', lambda src, dst: shutil.copy(src, dst))
    monkeypatch.setattr(kz, 'decrypt', lambda src, dst: shutil.copy(src, dst))
    with patch('django.utils.timezone.now', return_value=NOW), patch('requests.request', side_effect=AssertionError('Bez sieci')):
        yield


def dump(tables=None, complete=True):
    tables = len(connection.introspection.table_names()) if tables is None else tables
    lines = ['--', '-- PostgreSQL database dump', '--', 'SET statement_timeout = 0;']
    for n in range(tables):
        lines += [f'CREATE TABLE public.t{n} (', '    id integer NOT NULL', ');', f'COPY public.t{n} (id) FROM stdin;', '1', '\\.']
    if complete:
        lines += ['--', '-- PostgreSQL database dump complete', '--']
    return gzip.compress('\n'.join(lines).encode() + b'\n')


def test_sigv4_headers_are_deterministic_and_secret_dependent():
    client = kz.S3()
    at = datetime(2026, 10, 7, 2, 30, tzinfo=dt_timezone.utc)
    a = client._headers('PUT', 'pg/spin.sql.gz.enc', None, kz._sha256(b'abc'), at)
    b = client._headers('PUT', 'pg/spin.sql.gz.enc', None, kz._sha256(b'abc'), at)
    assert a == b and a['x-amz-date'] == '20261007T023000Z'
    assert a['Authorization'].startswith('AWS4-HMAC-SHA256 Credential=003abc0000000000000000001/20261007/eu-central-003/s3/aws4_request, '
                                         'SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=')
    assert len(a['Authorization'].rsplit('=', 1)[1]) == 64
    client.cfg['secret'] = 'inny'
    assert client._headers('PUT', 'pg/spin.sql.gz.enc', None, kz._sha256(b'abc'), at)['Authorization'] != a['Authorization']
    assert client._url('pg/a b.enc') == 'https://s3.eu-central-003.backblazeb2.com/spin-clinic-kopie/pg/a%20b.enc'
    assert 'K003SECRET' not in a['Authorization']


def test_list_objects_parses_xml_with_continuation(monkeypatch):
    pages = iter([
        b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>true</IsTruncated><NextContinuationToken>tok</NextContinuationToken>'
        b'<Contents><Key>pg/a.enc</Key><Size>10</Size><LastModified>2026-10-06T01:30:00.000Z</LastModified></Contents></ListBucketResult>',
        b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>false</IsTruncated>'
        b'<Contents><Key>pg/b.enc</Key><Size>20</Size><LastModified>2026-10-07T01:30:00.000Z</LastModified></Contents></ListBucketResult>'])
    seen = []

    def fake(method, url, params=None, data=b'', headers=None, timeout=None, stream=False):
        seen.append(params)
        response = type('R', (), {'status_code': 200, 'content': next(pages)})()
        return response
    with patch('requests.request', side_effect=fake):
        rows = kz.S3().list_objects('pg/')
    assert [r['key'] for r in rows] == ['pg/a.enc', 'pg/b.enc'] and rows[1]['size'] == 20
    assert rows[0]['modified'] == datetime(2026, 10, 6, 1, 30, tzinfo=dt_timezone.utc) and seen[1]['continuation-token'] == 'tok'


def test_multipart_upload_for_large_file(monkeypatch, tmp_path):
    monkeypatch.setattr(kz, 'PART_SIZE', 1024)
    path = tmp_path / 'big.enc'
    path.write_bytes(os.urandom(2500))
    calls = []

    def fake(method, url, params=None, data=b'', headers=None, timeout=None, stream=False):
        calls.append((method, dict(params or {}), len(data or b'')))
        body = b'<InitiateMultipartUploadResult><UploadId>UP1</UploadId></InitiateMultipartUploadResult>' if params == {'uploads': ''} else b''
        return type('R', (), {'status_code': 200, 'content': body, 'headers': {'ETag': f'"e{len(calls)}"'}})()
    with patch('requests.request', side_effect=fake):
        assert kz.S3().upload_file('pg/big.enc', str(path)) == 2500
    assert calls[0] == ('POST', {'uploads': ''}, 0)
    assert [c[2] for c in calls[1:4]] == [1024, 1024, 452] and all(c[1]['uploadId'] == 'UP1' for c in calls[1:])
    assert calls[-1][0] == 'POST' and calls[-1][1] == {'uploadId': 'UP1'} and calls[-1][2] > 0


def test_backup_uploads_applies_retention_and_records_state():
    old = NOW - timedelta(days=40)
    client = FakeS3({'pg/stara.sql.gz.enc': (b'x' * 10, old), 'pg/wczoraj.sql.gz.enc': (b'y' * 10, NOW - timedelta(days=1))})
    result = kz.backup('spin_clinic-20261007-0330.sql.gz', io.BytesIO(dump()), 'pg', NOW, client)
    assert result['status'] == 'ok' and result['key'] == 'pg/spin_clinic-20261007-0330.sql.gz.enc' and result['deleted'] == 1
    assert client.deleted == ['pg/stara.sql.gz.enc'] and client.uploaded == ['pg/spin_clinic-20261007-0330.sql.gz.enc']
    state = RepairerState.objects.get(key=kz.STATE_KEY).data
    assert state['last_pg_key'] == result['key'] and state['runs'] == [NOW.isoformat()] and state['remote_count'] == 2
    assert state['last_local_at'] == NOW.isoformat() and not state.get('last_error')
    assert kz.runs_since(NOW - timedelta(hours=1)) == (1, NOW)
    assert not list((kz._tmpdir() and __import__('pathlib').Path(kz._tmpdir())).glob('spin_clinic-*'))  # pliki tymczasowe usunięte
    line = kz.report_line(NOW)
    assert line.startswith('Kopia: lokalna 04:30, zdalna 04:30') and '2 plików / 30 dni' in line and 'jeszcze nie było' in line


def test_backup_without_config_or_empty_stream(monkeypatch):
    client = FakeS3()
    assert kz.backup('x.sql.gz', io.BytesIO(b'krotkie'), 'pg', NOW, client)['status'] == 'error' and not client.uploaded
    monkeypatch.delenv('BACKUP_PASSPHRASE')
    assert kz.backup('x.sql.gz', io.BytesIO(dump()), 'pg', NOW, client)['status'] == 'not_configured'
    monkeypatch.delenv('B2_BUCKET')
    assert kz.backup('x.sql.gz', io.BytesIO(dump()), 'pg', NOW, client)['status'] == 'not_configured'
    assert kz.daily_check(NOW, client) == {'status': 'disabled'} and kz.check_backup(Ctx(NOW)) == []
    assert 'nieskonfigurowana' in kz.report_line(NOW)


def test_daily_check_fresh_stale_and_first_restore_test():
    client = FakeS3({'pg/kopia.sql.gz.enc': (dump(), NOW - timedelta(hours=1))})
    result = kz.daily_check(NOW, client)
    assert result['status'] == 'ok' and result['produced'] == 1 and result['restore_test'] == 'ok'
    state = RepairerState.objects.get(key=kz.STATE_KEY).data
    assert state['last_restore_test']['status'] == 'ok' and state['last_restore_test']['tables_dump'] == state['last_restore_test']['tables_db']
    assert state['last_pg_at'] == (NOW - timedelta(hours=1)).isoformat()
    assert 'test odtworzenia 07.10 ok' in kz.report_line(NOW)
    # kopia starsza niż 26 h = błąd zadania (czerwony puls) i brak wyniku
    client.objects['pg/kopia.sql.gz.enc'] = (dump(), NOW - timedelta(hours=30))
    result = kz.daily_check(NOW, client)
    assert result['status'] == 'error' and result['produced'] == 0 and '26 h' in result['error']


def test_restore_test_detects_truncated_dump_and_wrong_passphrase(monkeypatch):
    client = FakeS3({'pg/urwana.sql.gz.enc': (dump(complete=False), NOW)})
    result = kz.restore_test(NOW, client)
    assert result['status'] == 'failed' and 'stopki' in result['detail']
    client = FakeS3({'pg/mala.sql.gz.enc': (dump(tables=1), NOW)})
    assert 'za mało tabel' in kz.restore_test(NOW, client)['detail']

    def bad(src, dst):
        raise RuntimeError('openssl zakończył się kodem 1')
    monkeypatch.setattr(kz, 'decrypt', bad)
    result = kz.restore_test(NOW, client)
    assert result['status'] == 'failed' and 'RuntimeError' in result['detail']
    alarms = {a['key']: a for a in kz.check_backup(Ctx(NOW))}
    assert alarms['backup:restore-test']['severity'] == 'critical' and 'KOPIE-I-ODTWORZENIE' in alarms['backup:restore-test']['instruction']


def test_duty_fuse_stale_size_and_registration():
    assert {a['key'] for a in kz.check_backup(Ctx(NOW))} == {'backup:stale'}  # jeszcze żadnej kopii
    RepairerState.objects.create(key=kz.STATE_KEY, data={'last_pg_at': (NOW - timedelta(hours=27)).isoformat(), 'remote_total_bytes': 9 * 1024 ** 3,
                                                        'remote_count': 31})
    alarms = {a['key']: a for a in kz.check_backup(Ctx(NOW))}
    assert alarms['backup:stale']['severity'] == 'critical' and alarms['backup:stale']['details']['hours'] == 27 and 'backup.sh' in alarms['backup:stale']['instruction']
    assert alarms['backup:size']['severity'] == 'warning' and '9.0 GB' in alarms['backup:size']['title']
    RepairerState.objects.filter(key=kz.STATE_KEY).update(data={'last_pg_at': (NOW - timedelta(hours=2)).isoformat(), 'remote_total_bytes': 10})
    assert kz.check_backup(Ctx(NOW)) == []
    from news import duty, duty_extra, raport_petli
    from news.daily_schedule import BEAT_PLAN
    assert kz.check_backup in duty_extra.CHECKS and kz.check_backup in duty.CHECKS
    assert raport_petli.BY_KEY['kopia']['counter'] == 'backups' and BEAT_PLAN['kopia-kontrola-daily'][0] == 'kopia_task'
    report = raport_petli.build(NOW)
    assert report['zewnetrzne']['kopia'].startswith('Kopia:')
    assert 'Kopia:' in raport_petli.text(report)


def test_openssl_passphrase_never_in_command_line(monkeypatch):
    seen = {}

    def fake_run(cmd, env=None, capture_output=None, timeout=None, check=None):
        seen['cmd'], seen['env'] = cmd, env
        return type('R', (), {'returncode': 0})()
    monkeypatch.setattr(kz.subprocess, 'run', fake_run)
    kz._openssl([], 'a', 'b')
    assert 'haslo-testowe' not in ' '.join(seen['cmd']) and 'env:BACKUP_PASSPHRASE' in seen['cmd'] and seen['env']['BACKUP_PASSPHRASE'] == 'haslo-testowe'
    assert '-pbkdf2' in seen['cmd'] and '-aes-256-cbc' in seen['cmd']
    monkeypatch.delenv('BACKUP_PASSPHRASE')
    with pytest.raises(RuntimeError):
        kz._openssl([], 'a', 'b')
    assert ET is not None
