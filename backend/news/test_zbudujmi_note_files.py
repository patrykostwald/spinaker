"""Załączniki do uwag klientów zbudujmi (29.10): zdjęcie lub film wysyłany kawałkami, plik poza katalogiem publicznym."""
from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from news.feedback_models import ClientNote
from news.zbudujmi_note_files import cleanup

ORIGIN = 'https://zbudujmi.com'


def le(n, size):
    return n.to_bytes(size, 'little')


def jpeg_with_gps(size):
    """Najmniejszy JPG z EXIF: IFD0 wskazuje katalog GPS z „N” i szerokością 52°24'0"."""
    tiff = b'II*\x00' + le(8, 4)
    tiff += le(1, 2) + le(0x8825, 2) + le(4, 2) + le(1, 4) + le(26, 4) + le(0, 4)  # IFD0: wskaźnik GPS
    tiff += le(2, 2)  # katalog GPS od bajtu 26: dwa wpisy
    tiff += le(1, 2) + le(2, 2) + le(2, 4) + b'N\x00\x00\x00'
    tiff += le(2, 2) + le(5, 2) + le(3, 4) + le(56, 4) + le(0, 4)
    tiff += b''.join(le(n, 4) + le(1, 4) for n in (52, 24, 0))
    app1 = b'Exif\x00\x00' + tiff
    head = b'\xff\xd8\xff\xe1' + (len(app1) + 2).to_bytes(2, 'big') + app1 + b'\xff\xda\x00\x02'
    return head + bytes(size - len(head) - 2) + b'\xff\xd9'


@pytest.fixture(autouse=True)
def files_root(settings, tmp_path):
    cache.clear()
    settings.ZBUDUJMI_NOTE_FILES_ROOT = str(tmp_path)
    settings.ZBUDUJMI_NOTE_FILES_MIN_FREE_GB = 0
    settings.ACCOUNT_PUBLIC_URL = 'https://spin.clinic'
    return tmp_path


def note(data):
    return Client().post('/api/zbudujmi/uwagi/', data, content_type='application/json', HTTP_ORIGIN=ORIGIN)


def upload(note_id, token, offset, chunk):
    return Client().post(f'/api/zbudujmi/uwagi/plik/{note_id}/', chunk, content_type='application/octet-stream',
                         HTTP_ORIGIN=ORIGIN, HTTP_X_UPLOAD_TOKEN=token, HTTP_X_UPLOAD_OFFSET=str(offset))


def declare(content, name):
    r = note({'p': 'motoladies-strona', 'm': '', 'e': 'zdjęcie hero.jpg', 'f': {'name': name, 'size': len(content)}})
    assert r.status_code == 200, r.json()
    up = r.json()['upload']
    return int(up['url'].rstrip('/').rsplit('/', 1)[1]), up


def test_preflight_allows_upload_headers():
    r = Client().options('/api/zbudujmi/uwagi/plik/1/', HTTP_ORIGIN=ORIGIN)
    assert r.status_code == 204 and 'x-upload-offset' in r['Access-Control-Allow-Headers']


@pytest.mark.django_db
def test_photo_in_chunks_strips_gps_and_mails_signed_link(files_root):
    photo = jpeg_with_gps(3 * 1024 * 1024 + 7)  # więcej niż DATA_UPLOAD_MAX_MEMORY_SIZE: czytamy strumieniem
    half = 2 * 1024 * 1024
    with mock.patch('news.zbudujmi_note_files.send_account_mail', return_value=True) as send:
        note_id, up = declare(photo, 'nowe hero.JPG')
        assert not send.called  # e-mail dopiero po całym pliku
        first = upload(note_id, up['t'], 0, photo[:half])
        assert first.json() == {'ok': True, 'received': half, 'done': False}
        assert first['Access-Control-Allow-Origin'] == ORIGIN
        again = upload(note_id, up['t'], 0, photo[:10])
        assert again.status_code == 409 and again.json()['received'] == half
        assert upload(note_id, up['t'], half, photo[half:]).json()['done'] is True
    saved = ClientNote.objects.get()
    assert (saved.text, saved.element, saved.file_kind) == ('Podmień na załączony plik.', 'zdjęcie hero.jpg', 'image')
    stored = (files_root / saved.file_path).read_bytes()
    assert len(stored) == len(photo) and stored[-2:] == b'\xff\xd9'
    assert le(52, 4) + le(1, 4) not in stored[:200] and b'N\x00\x00' not in stored[:200]
    subject, body = send.call_args[0][1:3]
    assert '+ plik' in subject and 'nowe hero.JPG' in body
    link = body.split('https://spin.clinic', 1)[1].split()[0]
    got = Client().get(link)
    assert got.status_code == 200 and got['Content-Type'] == 'image/jpeg'
    assert b''.join(got.streaming_content) == stored and 'sandbox' in got['Content-Security-Policy']
    assert Client().get(f'/api/zbudujmi/uwagi/plik/{note_id}/').status_code == 404
    assert Client().get(link.replace(f'/{note_id}/', f'/{note_id + 1}/')).status_code == 404
    assert upload(note_id, up['t'], len(photo), b'x').status_code == 403  # po końcu token nie działa


@pytest.mark.django_db
def test_video_and_rejections(files_root, settings):
    settings.ZBUDUJMI_NOTE_VIDEO_MAX_MB = 1
    video = (20).to_bytes(4, 'big') + b'ftypqt  ' + bytes(500_000)
    with mock.patch('news.zbudujmi_note_files.send_account_mail', return_value=True) as send:
        too_big = note({'p': 'x', 'm': 'film', 'f': {'name': 'a.mov', 'size': 2 * 1024 * 1024}})
        assert too_big.status_code == 400 and 'limit filmu to 1 MB' in too_big.json()['detail']
        assert note({'p': 'x', 'm': 'zły', 'f': {'name': 'a.svg', 'size': 10}}).status_code == 400
        assert ClientNote.objects.count() == 0
        note_id, up = declare(video, 'intro.mov')
        assert upload(note_id, 'zly-token', 0, video).status_code == 403
        assert upload(note_id, up['t'], 0, b'<svg onload=alert(1)>' + bytes(50)).status_code == 415
        assert upload(note_id, up['t'], 0, video).json()['done'] is True
    assert send.called
    saved = ClientNote.objects.get()
    assert saved.file_kind == 'video' and (files_root / saved.file_path).stat().st_size == len(video)
    assert not list(files_root.rglob('*.part'))


@pytest.mark.django_db
def test_files_per_address_limit_and_cleanup(files_root, settings):
    settings.ZBUDUJMI_NOTE_FILES_PER_DAY = 2
    photo = jpeg_with_gps(4000)
    with mock.patch('news.zbudujmi_note_files.send_account_mail', return_value=True):
        sent = [declare(photo, 'a.jpg') for _ in range(2)]
        limited = note({'p': 'x', 'm': 'trzeci', 'f': {'name': 'c.jpg', 'size': 4000}})
        assert limited.status_code == 400 and 'Za dużo plików' in limited.json()['detail']
        upload(sent[0][0], sent[0][1]['t'], 0, photo[:1000])
        upload(sent[1][0], sent[1][1]['t'], 0, photo)
    keep = settings.ZBUDUJMI_NOTE_FILES_KEEP_DAYS
    ClientNote.objects.filter(pk=sent[0][0]).update(created_at=timezone.now() - timedelta(days=2))
    ClientNote.objects.filter(pk=sent[1][0]).update(created_at=timezone.now() - timedelta(days=keep + 1))
    assert cleanup() == 2  # porzucona wysyłka po dobie i gotowy plik po okresie przechowywania
    assert not [p for p in files_root.rglob('*') if p.is_file()]
    assert ClientNote.objects.filter(file_deleted_at__isnull=False, file_token='').count() == 2
