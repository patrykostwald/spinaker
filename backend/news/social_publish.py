"""Silne spiny poza X: Facebook (film), Instagram (Reels), Bluesky (karta obrazkowa) i mail z filmem na TikTok i Shorts.

Te same zasady co na X (news/x_publish.py): ten sam próg siły spinu, limit dzienny, bez oznaczania polityka
i bez linku do jego wpisu (wpis to nasza grafika), treść diagnozy bez zmian. Gdy autor usunie wpis — usuwamy nasze
wpisy tam, gdzie API na to pozwala; gdzie nie (TikTok, Shorts, czasem Instagram) — alarm mailem do ręcznego usunięcia.

Kanał działa, gdy ma klucze w .env.production:
- Facebook: META_PAGE_ID, META_PAGE_TOKEN (token strony — `python manage.py meta_setup`)
- Instagram: META_IG_USER_ID (+ token strony powyżej; film pobiera Meta z naszego adresu /api/social/video/…)
- Bluesky: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD (hasło aplikacji, nie hasło konta)
- TikTok i Shorts: SOCIAL_VIDEO_EMAIL (albo X_POST_ALERT_EMAIL) — mail z gotowym filmem i opisem
Włącznik całości: SOCIAL_POST_ENABLED=true. Limit: SOCIAL_DAILY_LIMIT (domyślnie 2), próg: SOCIAL_MIN_INTENSITY
(domyślnie jak X_POST_MIN_INTENSITY).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

import requests
from django.conf import settings
from django.http import FileResponse, Http404
from django.utils import timezone

logger = logging.getLogger(__name__)

GRAPH = 'https://graph.facebook.com'
GRAPH_VIDEO = 'https://graph-video.facebook.com'
BSKY = 'https://bsky.social/xrpc'
VIDEO_NAME = re.compile(r'^\d+-[0-9a-f]{20}\.mp4$')
HASHTAGS = '#polityka #spin #edukacjamedialna #sprawdzam #dezinformacja'
FOOTER = 'Rządzący i opozycja — ta sama miara. Bez reklam i bez pieniędzy partii.'


def _env(name: str) -> str:
    return os.environ.get(name, '').strip()


def _graph_version() -> str:
    return _env('META_GRAPH_VERSION') or 'v23.0'


def channels() -> list[str]:
    """Kanały z kompletem kluczy (przy włączonym SOCIAL_POST_ENABLED)."""
    if _env('SOCIAL_POST_ENABLED').lower() != 'true':
        return []
    ready = []
    if _env('META_PAGE_ID') and _env('META_PAGE_TOKEN'):
        ready.append('facebook')
        if _env('META_IG_USER_ID'):
            ready.append('instagram')
    if _env('BLUESKY_HANDLE') and _env('BLUESKY_APP_PASSWORD'):
        ready.append('bluesky')
    if _video_email():
        ready.append('manual')
    return ready


def _video_email() -> str:
    return _env('SOCIAL_VIDEO_EMAIL') or _env('X_POST_ALERT_EMAIL')


# --- pliki filmów ---------------------------------------------------------------------------

def video_dir() -> Path:
    path = Path(_env('SOCIAL_MEDIA_DIR') or '/app/media/social')
    path.mkdir(parents=True, exist_ok=True)
    return path


def video_name(diagnosis_id: int) -> str:
    """Nazwa nie do zgadnięcia (HMAC z SECRET_KEY) — film jest publiczny tylko dla tego, kto dostał adres."""
    digest = hmac.new(settings.SECRET_KEY.encode(), f'social-video-v4-{diagnosis_id}'.encode(), hashlib.sha256).hexdigest()
    return f'{diagnosis_id}-{digest[:20]}.mp4'


def video_url(diagnosis_id: int) -> str:
    return f"https://{_env('SPIN_DOMAIN') or 'spin.clinic'}/api/social/video/{video_name(diagnosis_id)}"


def ensure_video(diagnosis) -> Path:
    from news.social_video import for_diagnosis
    path = video_dir() / video_name(diagnosis.pk)
    if not path.exists():
        for_diagnosis(diagnosis, str(path))
    return path


def serve_video(request, name: str):
    """GET /api/social/video/<nazwa>.mp4 — Instagram pobiera film spod tego adresu."""
    if not VIDEO_NAME.match(name):
        raise Http404
    path = video_dir() / name
    diagnosis_id = int(name.split('-', 1)[0])
    from news.clinic import published_diagnoses
    if not path.exists() or name != video_name(diagnosis_id) or not published_diagnoses().filter(pk=diagnosis_id).exists():
        raise Http404
    response = FileResponse(path.open('rb'), content_type='video/mp4')
    response['Cache-Control'] = 'no-store'
    return response


# --- teksty ---------------------------------------------------------------------------------

def texts(diagnosis, save=True) -> dict:
    from news.social_content import prepare
    return texts_from_data(prepare(diagnosis, save=save))


def texts_from_data(data: dict) -> dict:
    from news.x_share import build, diagnosis_url, heading
    posts = build(data, account=True)
    if not posts:
        return {}
    link = diagnosis_url(data['id'])
    from news.x_share import shorten
    synthesis = data['x_thread']
    if any(shorten(text, len(text)) != text for text in synthesis):
        return {}
    full = '\n\n'.join([heading(data), *synthesis])
    return {
        'facebook': f'{full}\n\nPełna diagnoza ze źródłami: {link}\n\n{FOOTER}',
        'instagram': f'{posts[0]}\n\nPełna diagnoza ze źródłami: spin.clinic (link w bio)\n\n{FOOTER}\n\n{HASHTAGS}',
        'bluesky': _bluesky_text(posts[0], link),
        'link': link,
    }


def _bluesky_text(body: str, link: str) -> str:
    """Usuwa całe zdania lub wiersze, nigdy fragment zdania."""
    from news.x_share import shorten
    room = 300 - len(link) - 2
    lines = body.splitlines()
    while len('\n'.join(lines)) > room and len(lines) > 2:
        lines.pop()
    if len('\n'.join(lines)) > room:
        if len(lines) == 2:
            lines[1] = shorten(lines[1], room - len(lines[0]) - 1)
        else:
            lines = [shorten(body, room)]
    body = '\n'.join(line for line in lines if line)
    return f'{body}\n\n{link}' if len(body) <= room else link


# --- Facebook i Instagram -------------------------------------------------------------------

def _meta_error(response) -> str:
    try:
        error = response.json().get('error') or {}
        return f"meta_{response.status_code}: {error.get('message', '')[:150]}"
    except ValueError:
        return f'meta_{response.status_code}: {response.text[:150]}'


def post_facebook(path: Path, text: str) -> tuple[str, str]:
    from news.social_video import first_frame_jpeg
    page = _env('META_PAGE_ID')
    thumbnail = first_frame_jpeg(path)
    with path.open('rb') as handle:
        response = requests.post(f'{GRAPH_VIDEO}/{_graph_version()}/{page}/videos', timeout=(10, 300),
                                 data={'description': text, 'access_token': _env('META_PAGE_TOKEN')},
                                 files={'source': (path.name, handle, 'video/mp4'),
                                        'thumb': ('cover.jpg', thumbnail, 'image/jpeg')})
    if response.status_code != 200:
        raise RuntimeError(_meta_error(response))
    video_id = str(response.json()['id'])
    return video_id, f'https://www.facebook.com/{page}/videos/{video_id}'


def post_instagram(diagnosis_id: int, caption: str, wait_seconds: int = 300) -> tuple[str, str]:
    """Reels: kontener z adresem filmu → Meta pobiera i przetwarza → publikacja."""
    user, token, version = _env('META_IG_USER_ID'), _env('META_PAGE_TOKEN'), _graph_version()
    response = requests.post(f'{GRAPH}/{version}/{user}/media', timeout=(10, 60), data={
        'media_type': 'REELS', 'video_url': video_url(diagnosis_id), 'caption': caption, 'share_to_feed': 'true',
        'access_token': token, 'thumb_offset': 0})
    if response.status_code != 200:
        raise RuntimeError(_meta_error(response))
    container = response.json()['id']
    deadline = time.monotonic() + wait_seconds
    while True:
        status = requests.get(f'{GRAPH}/{version}/{container}', timeout=(10, 30),
                              params={'fields': 'status_code', 'access_token': token}).json().get('status_code')
        if status == 'FINISHED':
            break
        if status in ('ERROR', 'EXPIRED') or time.monotonic() > deadline:
            raise RuntimeError(f'instagram_container_{status or "timeout"}')
        time.sleep(10)
    response = requests.post(f'{GRAPH}/{version}/{user}/media_publish', timeout=(10, 60),
                             data={'creation_id': container, 'access_token': token})
    if response.status_code != 200:
        raise RuntimeError(_meta_error(response))
    media_id = str(response.json()['id'])
    link = requests.get(f'{GRAPH}/{version}/{media_id}', timeout=(10, 30),
                        params={'fields': 'permalink', 'access_token': token}).json().get('permalink', '')
    return media_id, link


def delete_meta(object_id: str) -> None:
    response = requests.delete(f'{GRAPH}/{_graph_version()}/{object_id}', timeout=(10, 30),
                               params={'access_token': _env('META_PAGE_TOKEN')})
    if response.status_code not in (200, 404):
        raise RuntimeError(_meta_error(response))


# --- Bluesky --------------------------------------------------------------------------------

def _bsky_session() -> dict:
    response = requests.post(f'{BSKY}/com.atproto.server.createSession', timeout=(10, 30),
                             json={'identifier': _env('BLUESKY_HANDLE'), 'password': _env('BLUESKY_APP_PASSWORD')})
    if response.status_code != 200:
        raise RuntimeError(f'bluesky_login_{response.status_code}: {response.text[:150]}')
    return response.json()


def link_facets(text: str) -> list[dict]:
    """Linki w tekście jako „facets” Bluesky — pozycje w BAJTACH UTF-8, nie w znakach."""
    facets = []
    for match in re.finditer(r'https?://\S+', text):
        start = len(text[:match.start()].encode('utf-8'))
        end = start + len(match.group(0).encode('utf-8'))
        facets.append({'index': {'byteStart': start, 'byteEnd': end},
                       'features': [{'$type': 'app.bsky.richtext.facet#link', 'uri': match.group(0)}]})
    return facets


def post_bluesky(text: str, png: bytes, alt: str) -> tuple[str, str]:
    session = _bsky_session()
    auth = {'Authorization': f"Bearer {session['accessJwt']}"}
    response = requests.post(f'{BSKY}/com.atproto.repo.uploadBlob', timeout=(10, 60), data=png,
                             headers={**auth, 'Content-Type': 'image/png'})
    if response.status_code != 200:
        raise RuntimeError(f'bluesky_blob_{response.status_code}: {response.text[:150]}')
    record = {
        '$type': 'app.bsky.feed.post', 'text': text, 'langs': ['pl'], 'facets': link_facets(text),
        'createdAt': datetime.now(dt_timezone.utc).isoformat().replace('+00:00', 'Z'),
        'embed': {'$type': 'app.bsky.embed.images', 'images': [
            {'alt': alt[:1000], 'image': response.json()['blob'], 'aspectRatio': {'width': 1200, 'height': 675}}]},
    }
    response = requests.post(f'{BSKY}/com.atproto.repo.createRecord', timeout=(10, 60), headers=auth,
                             json={'repo': session['did'], 'collection': 'app.bsky.feed.post', 'record': record})
    if response.status_code != 200:
        raise RuntimeError(f'bluesky_post_{response.status_code}: {response.text[:150]}')
    uri = response.json()['uri']
    rkey = uri.rsplit('/', 1)[-1]
    return uri, f"https://bsky.app/profile/{session.get('handle') or _env('BLUESKY_HANDLE')}/post/{rkey}"


def delete_bluesky(uri: str) -> None:
    session = _bsky_session()
    rkey = uri.rsplit('/', 1)[-1]
    response = requests.post(f'{BSKY}/com.atproto.repo.deleteRecord', timeout=(10, 30),
                             headers={'Authorization': f"Bearer {session['accessJwt']}"},
                             json={'repo': session['did'], 'collection': 'app.bsky.feed.post', 'rkey': rkey})
    if response.status_code not in (200, 400):
        raise RuntimeError(f'bluesky_delete_{response.status_code}: {response.text[:150]}')


# --- poczta (TikTok, Shorts, alarmy) --------------------------------------------------------

def _mail(to: str, subject: str, body: str, attachment: Path | None = None) -> bool:
    import smtplib
    from email.message import EmailMessage
    from news.clinic import _smtp_ready
    if not to or not _smtp_ready():
        return False
    email = EmailMessage()
    email['From'], email['To'], email['Subject'] = settings.SOURCE_MAIL_SMTP_FROM, to, subject
    email.set_content(body)
    if attachment is not None:
        email.add_attachment(attachment.read_bytes(), maintype='video', subtype='mp4', filename=f'spin-clinic-{attachment.name.split("-")[0]}.mp4')
    try:
        with smtplib.SMTP_SSL(settings.SOURCE_MAIL_SMTP_HOST, settings.SOURCE_MAIL_SMTP_PORT, timeout=60) as client:
            client.login(settings.SOURCE_MAIL_SMTP_USERNAME, settings.SOURCE_MAIL_SMTP_PASSWORD)
            client.send_message(email)
    except (OSError, smtplib.SMTPException) as error:
        logger.warning('social mail failed: %s', type(error).__name__)
        return False
    return True


def post_manual(path: Path, caption: str, link: str) -> tuple[str, str]:
    body = ('Gotowy film do wrzucenia na TikTok i YouTube Shorts (w załączniku).\n\n'
            f'Opis do wklejenia:\n\n{caption}\n\nLink do diagnozy (do bio / pierwszego komentarza): {link}\n\n'
            'Jeśli polityk usunie wpis, dostaniesz osobny mail — wtedy usuń film ręcznie z TikToka i YouTube.')
    if not _mail(_video_email(), 'spin.clinic: film do TikToka i Shorts', body, path):
        raise RuntimeError('mail_failed')
    return '', ''


def alert(subject: str, body: str) -> None:
    from django.core.cache import cache
    to = _env('X_POST_ALERT_EMAIL') or _env('CLINIC_REVIEW_EMAIL')
    if cache.add(f'social-alert-{hashlib.sha1(subject.encode()).hexdigest()[:10]}', '1', timeout=6 * 3600):
        _mail(to, subject, body)


# --- przebieg -------------------------------------------------------------------------------

def candidates(limit: int, ready: list[str]):
    from news.clinic import published_diagnoses
    from news.clinic_models import SocialPost
    from news.social_selection import day_start, select
    minimum = int(_env('SOCIAL_MIN_INTENSITY') or _env('X_POST_MIN_INTENSITY') or 55)
    rows = published_diagnoses().filter(verdict='spin', intensity__gte=minimum, diagnosed_at__gte=day_start(),
                                       post__available=True).prefetch_related('social_posts').order_by('-intensity', '-diagnosed_at', '-pk')
    rows = [row for row in rows if not {item.platform for item in row.social_posts.all()} >= set(ready)]
    history = list(SocialPost.objects.filter(platform__in=ready).order_by('-posted_at')
                   .values_list('diagnosis__post__camp_at_collection', 'posted_at'))
    return select(rows, history, limit)


def run(dry_run: bool = False) -> dict:
    from news.clinic_models import SocialPost
    from news.clinic_card import share_png as card  # ta sama karta z panelem danych co na X
    ready = channels()
    if not ready and not dry_run:
        return {'status': 'disabled'}
    from news.social_selection import day_start
    start = day_start()
    limit = int(_env('SOCIAL_DAILY_LIMIT') or 2)
    posted_today = SocialPost.objects.filter(posted_at__gte=start).values('diagnosis').distinct().count()
    room = max(0, limit - posted_today) if not dry_run else 1
    failed: set[str] = set()
    results = []
    for diagnosis in candidates(room, ready or ['facebook']):
        if not diagnosis.post.available:
            continue
        text = texts(diagnosis, save=not dry_run)
        if not text:
            results.append({'id': diagnosis.pk, 'posted': False, 'error': 'synthesis_unavailable'})
            continue
        if dry_run:
            results.append({'id': diagnosis.pk, 'texts': text})
            continue
        done = {item.platform for item in diagnosis.social_posts.all()}
        path = None
        for platform in ready:
            if platform in done or platform in failed:
                continue
            try:
                if platform in ('facebook', 'instagram', 'manual') and path is None:
                    path = ensure_video(diagnosis)
                from news.clinic import published_diagnoses
                if not published_diagnoses().filter(pk=diagnosis.pk).exists():
                    break
                if platform == 'facebook':
                    external, url = post_facebook(path, text['facebook'])
                elif platform == 'instagram':
                    external, url = post_instagram(diagnosis.pk, text['instagram'])
                elif platform == 'bluesky':
                    alt = f'Wpis polityka i ocena Dr. Spina: {diagnosis.get_verdict_display()} {diagnosis.intensity}/100.'
                    external, url = post_bluesky(text['bluesky'], card(diagnosis), alt)
                else:
                    external, url = post_manual(path, text['instagram'], text['link'])
            except (requests.RequestException, RuntimeError, KeyError, ValueError, OSError) as error:
                logger.warning('social %s %s: %s', platform, diagnosis.pk, error)
                failed.add(platform)
                alert(f'spin.clinic: wpis na {platform} się nie udał',
                      f'Diagnoza {diagnosis.pk} nie trafiła na {platform}.\n\nOdpowiedź: {str(error)[:500]}\n\n'
                      'Najczęstsze przyczyny: wygasły token (META_PAGE_TOKEN — uruchom meta_setup), złe hasło aplikacji '
                      'Bluesky albo limit serwisu. Kolejna próba przy następnym przebiegu.')
                results.append({'id': diagnosis.pk, 'platform': platform, 'posted': False, 'error': str(error)[:200]})
                continue
            SocialPost.objects.create(diagnosis=diagnosis, platform=platform, external_id=external, url=url)
            results.append({'id': diagnosis.pk, 'platform': platform, 'posted': True})
    return {'status': 'dry_run' if dry_run else 'ok', 'channels': ready, 'results': results}


def unpublish_deleted(diagnosis) -> None:
    """Autor usunął wpis — usuwamy nasze wpisy z jego treścią; czego nie da się usunąć przez API — alarm."""
    manual = []
    for item in diagnosis.social_posts.filter(deleted_at__isnull=True):
        try:
            if item.platform in ('facebook', 'instagram') and item.external_id:
                delete_meta(item.external_id)
            elif item.platform == 'bluesky' and item.external_id:
                delete_bluesky(item.external_id)
            else:
                manual.append(item)
                continue
        except (requests.RequestException, RuntimeError) as error:
            logger.warning('social unpublish %s %s: %s', item.platform, diagnosis.pk, error)
            manual.append(item)
            continue
        item.deleted_at = timezone.now()
        item.save(update_fields=['deleted_at'])
    if manual:
        where = ', '.join(f'{item.get_platform_display()} {item.url}'.strip() for item in manual)
        _mail(_env('X_POST_ALERT_EMAIL') or _env('CLINIC_REVIEW_EMAIL'),
              f'spin.clinic: usuń ręcznie film diagnozy {diagnosis.pk}',
              f'Polityk usunął wpis, którego dotyczy diagnoza {diagnosis.pk}. Zasady serwisów: usuwamy też nasze materiały.\n\n'
              f'Usuń ręcznie: {where}\n(TikTok i YouTube Shorts — jeśli film tam wrzuciłeś.)')
        for item in manual:
            item.deleted_at = timezone.now()
            item.save(update_fields=['deleted_at'])
    try:
        (video_dir() / video_name(diagnosis.pk)).unlink(missing_ok=True)
    except OSError:
        pass
