"""Załączniki posta do diagnozy: co jest na zdjęciach i dokąd prowadzą linki — żeby oceniać cały post, nie sam tekst.

- Zdjęcia: Gemini (wizja) rzeczowo opisuje obraz i przepisuje tekst z grafiki (ułamek centa za obraz).
- Linki: skrócony link t.co rozwijamy do adresu docelowego i czytamy tylko tytuł i opis strony (jak podgląd linku).
Bez klucza Gemini zdjęcie zostaje opisane jako „bez opisu” — diagnoza zaznaczy to w ograniczeniach.
"""
import base64
import os
import re
from html import unescape
from urllib.parse import urlsplit

import requests

from news import clinic_ai

LINK = re.compile(r'https?://\S+')
MAX_IMAGES = 3
MAX_LINKS = 3
HEADERS = {'User-Agent': 'spin.clinic link preview (+https://spin.clinic/o-nas)'}

IMAGE_PROMPT = ('Opisz rzeczowo po polsku, co przedstawia ten obraz dołączony do wpisu polityka: kogo lub co widać, '
                'jaki tekst jest na grafice (przepisz go dosłownie), czy to zrzut ekranu, wykres, zdjęcie, mem. '
                'Nie oceniaj i nie zgaduj tożsamości osób, których nie podpisano. 2–4 zdania.')


def _final_url(url: str) -> str:
    """Rozwija przekierowania (t.co) bez pobierania treści — najwyżej 4 kroki."""
    current = url
    for _ in range(4):
        try:
            response = requests.head(current, allow_redirects=False, timeout=(3, 6), headers=HEADERS)
        except requests.RequestException:
            return current
        location = response.headers.get('Location')
        if response.status_code in (301, 302, 303, 307, 308) and location:
            current = requests.compat.urljoin(current, location)
            continue
        return current
    return current


def _meta(html: str, name: str) -> str:
    match = re.search(rf'<meta[^>]+(?:property|name)=["\']{name}["\'][^>]+content=["\']([^"\']+)', html, re.I) or \
        re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{name}["\']', html, re.I)
    return unescape(match.group(1)).strip() if match else ''


def link_preview(url: str) -> dict:
    """Adres docelowy, tytuł i opis strony (tylko początek dokumentu HTML — jak podgląd linku)."""
    final = _final_url(url)
    info = {'url': final, 'domain': (urlsplit(final).hostname or '').removeprefix('www.'), 'title': '', 'description': ''}
    if info['domain'] in ('x.com', 'twitter.com'):
        info['title'] = 'wpis lub zdjęcie na X'
        return info
    try:
        with requests.get(final, timeout=(3, 8), headers=HEADERS, stream=True) as response:
            if 'html' not in response.headers.get('Content-Type', ''):
                return info
            html = response.raw.read(300_000, decode_content=True).decode(response.encoding or 'utf-8', errors='replace')
    except requests.RequestException:
        return info
    title = _meta(html, 'og:title') or unescape((re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S) or [None, ''])[1]).strip()
    info.update(title=' '.join(title.split())[:200], description=' '.join(_meta(html, 'og:description').split())[:300])
    return info


def describe_image(url: str) -> str:
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        return ''
    try:
        image = requests.get(url, timeout=(3, 10), headers=HEADERS)
        image.raise_for_status()
        mime = image.headers.get('Content-Type', 'image/jpeg').split(';')[0]
        if not mime.startswith('image/') or len(image.content) > 8_000_000:
            return ''
        model = os.environ.get('CLINIC_GEMINI_MODEL', '').strip() or 'gemini-3.8-flash'
        body = {'contents': [{'parts': [{'inline_data': {'mime_type': mime, 'data': base64.b64encode(image.content).decode()}},
                                        {'text': IMAGE_PROMPT}]}],
                'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 600, 'mediaResolution': 'MEDIA_RESOLUTION_LOW',
                                     **clinic_ai.gemini_thinking('image')}}
        response = clinic_ai.gemini_post(model, body, timeout=(5, 60), key=key, task='image')
        response.raise_for_status()
        parts = ((response.json().get('candidates') or [{}])[0].get('content') or {}).get('parts', [])
        return ' '.join(''.join(part.get('text', '') for part in parts).split())[:800]
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return ''


def describe(text: str, media: list[dict]) -> str:
    """Tekst sekcji „Załączniki” dla modeli: opisy zdjęć i podglądy linków z posta."""
    lines = []
    photos = [item for item in media or [] if isinstance(item, dict) and item.get('type', 'photo') in ('photo', 'image')]
    for index, item in enumerate(photos[:MAX_IMAGES], 1):
        url = item.get('url') or item.get('preview_image_url') or ''
        seen = describe_image(url) if url else ''
        alt = f" Opis alternatywny autora: {item['alt_text']}." if item.get('alt_text') else ''
        lines.append(f"Zdjęcie {index}: {seen or 'bez opisu (nie udało się obejrzeć obrazu)'}.{alt}")
    for item in media or []:
        if isinstance(item, dict) and item.get('type') in ('video', 'animated_gif'):
            lines.append(f"Wideo/animacja: {item.get('alt_text') or 'bez opisu — treści nagrania nie oglądano'}.")
    for index, url in enumerate(LINK.findall(text or '')[:MAX_LINKS], 1):
        info = link_preview(url.rstrip('.,)'))
        if info['title'] == 'wpis lub zdjęcie na X':
            continue  # link do samego zdjęcia z posta — opisany wyżej
        lines.append(f"Link {index}: {info['domain'] or url} — {info['title'] or 'bez tytułu'}"
                     + (f" — {info['description']}" if info['description'] else ''))
    return '\n'.join(lines)
