"""Załączniki do uwag klientów zbudujmi (właściciel 29.10: klientki podmieniają zdjęcia i filmy na podglądzie).

Klient zgłasza plik razem z uwagą (nazwa, rozmiar, typ), dostaje jednorazowy token i wysyła plik kawałkami
po 8 MB (duże filmy nie idą jednym żądaniem przez gunicorna, a zerwane połączenie wznawia się od ostatniego
kawałka). Typ sprawdzamy po pierwszych bajtach pliku, nie tylko po rozszerzeniu. Plik leży poza katalogiem
publicznym; zespół otwiera go podpisanym linkiem z e-maila albo z panelu. Ze zdjęć JPG usuwamy lokalizację GPS.
Po ZBUDUJMI_NOTE_FILES_KEEP_DAYS dniach plik usuwa zadanie nocne (cleanup)."""
import os
import re
import secrets
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from news.account_mail import send_account_mail

CHUNK = 8 * 1024 * 1024
CHUNK_MAX = 10 * 1024 * 1024
TYPES = {'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'webp': 'image', 'heic': 'image', 'heif': 'image',
         'mp4': 'video', 'mov': 'video'}
MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp', 'heic': 'image/heic',
        'heif': 'image/heif', 'mp4': 'video/mp4', 'mov': 'video/quicktime'}
HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis', b'mif1', b'msf1'}
MOV_ATOMS = {b'ftyp', b'moov', b'mdat', b'wide', b'free', b'skip', b'pnot'}
SALT = 'zbudujmi-note-file'
UPLOAD_HEADERS = 'content-type, x-upload-token, x-upload-offset'


def client_ip(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    return re.sub(r'[^0-9a-f.:]', '', ip.lower())


def limit_bytes(kind):
    mb = settings.ZBUDUJMI_NOTE_IMAGE_MAX_MB if kind == 'image' else settings.ZBUDUJMI_NOTE_VIDEO_MAX_MB
    return mb * 1024 * 1024


def _root():
    return Path(settings.ZBUDUJMI_NOTE_FILES_ROOT)


def _mb(size):
    return f'{size / 1024 / 1024:.1f} MB'


def check_declared(data, ip):
    """Sprawdza zgłoszony plik (f: {name, size}) przed zapisem uwagi. Zwraca (pola do ClientNote, None)
    albo (None, komunikat dla klienta)."""
    name = re.sub(r'[\x00-\x1f/\\]', '', str(data.get('name', ''))).strip()[-120:]
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    kind = TYPES.get(ext)
    if not kind:
        return None, 'Dołącz zdjęcie (JPG, PNG, WebP, HEIC) albo film (MP4, MOV).'
    try:
        size = int(data.get('size'))
    except (TypeError, ValueError):
        return None, 'Niepoprawny plik.'
    if size <= 0:
        return None, 'Plik jest pusty.'
    if size > limit_bytes(kind):
        what = 'zdjęcia' if kind == 'image' else 'filmu'
        return None, f'Plik ma {_mb(size)}, a limit {what} to {limit_bytes(kind) // 1024 // 1024} MB. Wklej w uwadze link do pliku.'
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free - size < settings.ZBUDUJMI_NOTE_FILES_MIN_FREE_GB * 1024 ** 3:
        return None, 'Brak miejsca na plik. Wklej w uwadze link do pliku.'
    key = 'zbudujmi-note-file:' + ip
    count = cache.get(key, 0)
    if count >= settings.ZBUDUJMI_NOTE_FILES_PER_DAY:
        return None, 'Za dużo plików na dziś. Wklej w uwadze link do pliku.'
    cache.set(key, count + 1, 86400)
    return {'file_name': name, 'file_kind': kind, 'file_size': size, 'file_token': secrets.token_urlsafe(32)}, None


def start(note):
    """Ścieżkę zapisujemy po utworzeniu uwagi (potrzebne id); plik w budowie ma końcówkę .part."""
    ext = note.file_name.rsplit('.', 1)[-1].lower()
    note.file_path = f'{note.project}/{note.pk}-{secrets.token_hex(6)}.{ext}'
    note.save(update_fields=['file_path'])
    return {'url': f'/api/zbudujmi/uwagi/plik/{note.pk}/', 't': note.file_token, 'chunk': CHUNK}


def sniff(head):
    """Rozszerzenie wykryte z pierwszych bajtów (None = nie zdjęcie ani film z listy)."""
    if head[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    if head[4:8] == b'ftyp':
        brand = head[8:12]
        if brand in HEIF_BRANDS:
            return 'heic'
        return 'mov' if brand == b'qt  ' else 'mp4'
    if head[4:8] in MOV_ATOMS:
        return 'mov'
    return None


def strip_jpeg_gps(path):
    """Zeruje w miejscu katalog GPS z EXIF zdjęcia JPG (rozmiar i reszta danych bez zmian, obraz bez przekodowania)."""
    with open(path, 'r+b') as f:
        data = bytearray(f.read(min(os.path.getsize(path), 256 * 1024)))
        pos = 2
        while pos + 4 <= len(data) and data[pos] == 0xFF:
            marker, length = data[pos + 1], int.from_bytes(data[pos + 2:pos + 4], 'big')
            if marker == 0xDA:
                return False
            if marker == 0xE1 and data[pos + 4:pos + 10] == b'Exif\x00\x00':
                tiff = pos + 10
                end = pos + 2 + length
                order = 'little' if data[tiff:tiff + 2] == b'II' else 'big'

                def u(at, n):
                    return int.from_bytes(data[at:at + n], order) if at + n <= end else 0
                ifd0 = tiff + u(tiff + 4, 4)
                for i in range(u(ifd0, 2)):
                    entry = ifd0 + 2 + 12 * i
                    if u(entry, 2) != 0x8825:
                        continue
                    gps = tiff + u(entry + 8, 4)
                    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
                    for j in range(u(gps, 2)):
                        item = gps + 2 + 12 * j
                        if item + 12 > end:
                            break
                        size = sizes.get(u(item + 2, 2), 1) * u(item + 4, 4)
                        if 4 < size and tiff + u(item + 8, 4) + size <= end:
                            start_at = tiff + u(item + 8, 4)
                            data[start_at:start_at + size] = bytes(size)
                        data[item:item + 12] = bytes(12)
                    if gps + 2 <= end:
                        data[gps:gps + 2] = bytes(2)
                    f.seek(0)
                    f.write(data)
                    return True
                return False
            pos += 2 + length
    return False


def signed_link(note):
    key = signing.dumps(note.pk, salt=SALT)
    return f'{settings.ACCOUNT_PUBLIC_URL}/api/zbudujmi/uwagi/plik/{note.pk}/?k={key}'


def note_mail(note):
    body = (f"Nowa uwaga do podglądu: {note.project}\n\nMiejsce: {note.anchor or '-'} "
            f"({'%.0f%%' % (note.y * 100) if note.y is not None else '-'} wysokości strony)\n"
            f"Wskazany element: {note.element or '-'}\n"
            f"Uwaga: {note.text}\nOd: {note.name or '-'}\nEkran: {note.viewport or '-'}\nStrona: {note.page or '-'}\n")
    if note.file_done_at:
        body += (f"\nPlik: {note.file_name} ({_mb(note.file_size)})\n{signed_link(note)}\n"
                 f"Link działa {settings.ZBUDUJMI_NOTE_FILES_KEEP_DAYS} dni, potem plik jest usuwany.\n"
                 f"Panel: {settings.ACCOUNT_PUBLIC_URL}/admin/news/clientnote/{note.pk}/change/\n")
    return send_account_mail('kontakt@iapply.pl', f'Uwaga klienta ({note.project})' + (' + plik' if note.file_done_at else ''), body)


def _cors(response, request):
    from news.zbudujmi_inquiry import _cors as base
    response = base(response, request)
    if 'Access-Control-Allow-Origin' in response:
        response['Access-Control-Allow-Headers'] = UPLOAD_HEADERS
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response


@csrf_exempt
def note_file(request, note_id):
    """POST: kolejny kawałek pliku (nagłówki X-Upload-Token, X-Upload-Offset). GET: podgląd pliku dla zespołu."""
    from news.feedback_models import ClientNote
    if request.method == 'OPTIONS':
        return _cors(HttpResponse(status=204), request)
    if request.method == 'GET':
        return _download(request, note_id)
    if request.method != 'POST':
        return _cors(JsonResponse({'detail': 'Tylko POST.'}, status=405), request)
    note = ClientNote.objects.filter(pk=note_id).exclude(file_token='').first()
    token = request.headers.get('X-Upload-Token', '')
    if not note or not secrets.compare_digest(note.file_token, token) or note.file_done_at or not note.file_path:
        return _cors(JsonResponse({'detail': 'Wysyłka pliku wygasła. Dodaj uwagę ponownie.'}, status=403), request)
    try:
        offset = int(request.headers.get('X-Upload-Offset', ''))
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return _cors(JsonResponse({'detail': 'Niepoprawne dane.'}, status=400), request)
    if offset != note.file_received:
        return _cors(JsonResponse({'detail': 'Wznów od właściwego miejsca.', 'received': note.file_received}, status=409), request)
    if length <= 0 or length > CHUNK_MAX or offset + length > note.file_size:
        return _cors(JsonResponse({'detail': 'Niepoprawny kawałek pliku.'}, status=400), request)
    part = _root() / (note.file_path + '.part')
    part.parent.mkdir(parents=True, exist_ok=True)
    on_disk = part.stat().st_size if part.exists() else 0
    if on_disk < offset:  # kawałek zapisany w bazie, ale nie na dysku: wznów od tego, co naprawdę jest
        note.file_received = on_disk
        note.save(update_fields=['file_received'])
        return _cors(JsonResponse({'detail': 'Wznów od właściwego miejsca.', 'received': on_disk}, status=409), request)
    written = 0
    with open(part, 'ab') as f:
        f.truncate(offset)  # po zerwanym kawałku zostają resztki; zaczynamy dokładnie od offset
        while written < length:
            piece = request.read(min(1024 * 1024, length - written))
            if not piece:
                break
            if offset == 0 and written == 0:
                found = sniff(piece[:16])
                if not found or TYPES[found] != note.file_kind:
                    f.truncate(0)
                    return _cors(JsonResponse({'detail': 'To nie jest zdjęcie ani film z listy (JPG, PNG, WebP, HEIC, MP4, MOV).'}, status=415), request)
            f.write(piece)
            written += len(piece)
        if written != length:
            f.truncate(offset)
            return _cors(JsonResponse({'detail': 'Przerwane połączenie. Wznów wysyłkę.', 'received': offset}, status=400), request)
    note.file_received = offset + written
    fields = ['file_received']
    if note.file_received == note.file_size:
        with open(part, 'rb') as f:
            found = sniff(f.read(16))
        stem, ext = note.file_path.rsplit('.', 1)
        if found != ext and {found, ext} != {'jpg', 'jpeg'}:  # np. HEIC z końcówką .jpg: zapis pod prawdziwym typem
            note.file_path = f'{stem}.{found}'
        final = _root() / note.file_path
        os.replace(part, final)
        if found == 'jpg':
            strip_jpeg_gps(final)
        note.file_done_at = timezone.now()
        fields += ['file_done_at', 'file_path']
    note.save(update_fields=fields)
    if note.file_done_at:
        note_mail(note)
    return _cors(JsonResponse({'ok': True, 'received': note.file_received, 'done': bool(note.file_done_at)}), request)


def _download(request, note_id):
    from news.feedback_models import ClientNote
    allowed = bool(getattr(request.user, 'is_staff', False))
    if not allowed and request.GET.get('k'):
        try:
            max_age = settings.ZBUDUJMI_NOTE_FILES_KEEP_DAYS * 86400
            allowed = signing.loads(request.GET['k'], salt=SALT, max_age=max_age) == note_id
        except signing.BadSignature:
            allowed = False
    note = ClientNote.objects.filter(pk=note_id, file_done_at__isnull=False, file_deleted_at__isnull=True).first()
    path = _root() / note.file_path if allowed and note else None
    if not path or not path.is_file():
        return JsonResponse({'detail': 'Nie ma takiego pliku albo link wygasł.'}, status=404)
    ext = note.file_path.rsplit('.', 1)[-1]
    response = FileResponse(open(path, 'rb'), content_type=MIME.get(ext, 'application/octet-stream'),
                            filename=note.file_name, as_attachment=ext in ('heic', 'heif'))
    response['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; media-src 'self'; sandbox"
    response['X-Robots-Tag'] = 'noindex'
    response['Cache-Control'] = 'private, no-store'
    return response


def cleanup(now=None):
    """Usuwa pliki starsze niż ZBUDUJMI_NOTE_FILES_KEEP_DAYS i porzucone wysyłki (.part) starsze niż dobę."""
    from news.feedback_models import ClientNote
    now = now or timezone.now()
    removed = 0
    old = ClientNote.objects.exclude(file_path='').filter(file_deleted_at__isnull=True)
    expired = old.filter(created_at__lt=now - timedelta(days=settings.ZBUDUJMI_NOTE_FILES_KEEP_DAYS))
    stale = old.filter(file_done_at__isnull=True, created_at__lt=now - timedelta(days=1))
    for note in expired | stale:
        for path in (_root() / note.file_path, _root() / (note.file_path + '.part')):
            if path.is_file():
                path.unlink()
                removed += 1
        note.file_deleted_at = now
        note.file_token = ''
        note.save(update_fields=['file_deleted_at', 'file_token'])
    return removed
