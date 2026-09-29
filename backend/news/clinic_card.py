"""Publiczny obraz diagnozy odpowiadający karcie w serwisie."""
import hashlib
import io
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from django.conf import settings
from PIL import Image, ImageDraw, ImageOps

from news.techniques import FAMILY_LABELS
from news.x_card import _font, EMOJI

VERSION = 'v4'
COLORS = {'spin': '#ff6b6b', 'partial': '#f2b441', 'no_spin': '#4ed18a', 'unclear': '#a6a6a6'}
MUTED, ACCENT = '#a6a6a6', '#4a9eff'
FAMILIES = {'dane': '#7ea6d8', 'przedstawienie': '#d2a86a', 'spor': '#b58ad8'}
MAX_BYTES = 5 * 1024 * 1024


def _atomic_write(path, payload):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _decode(payload):
    with Image.open(io.BytesIO(payload)) as source:
        if source.width * source.height > 20_000_000:
            raise ValueError('Image too large')
        return ImageOps.exif_transpose(source).convert('RGB')


def fetch_image(url):
    """Tylko HTTPS CDN X; bez przekierowań, z cache sukcesów i godziną cache błędów."""
    try:
        parsed = urlsplit(url or '')
        if (parsed.scheme != 'https' or parsed.hostname not in {'pbs.twimg.com', 'abs.twimg.com'}
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            return None
    except ValueError:
        return None
    directory = Path(settings.MEDIA_ROOT) / 'clinic_cards' / 'media'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256(url.encode()).hexdigest() + '.img')
    failed = path.with_suffix('.failed')
    if path.exists():
        try:
            return _decode(path.read_bytes())
        except (OSError, ValueError, Image.DecompressionBombError):
            path.unlink(missing_ok=True)
    if failed.exists() and time.time() - failed.stat().st_mtime < 3600:
        return None
    try:
        started = time.monotonic()
        with requests.get(url, stream=True, timeout=5, allow_redirects=False) as response:
            if response.status_code != 200 or int(response.headers.get('Content-Length', 0)) > MAX_BYTES:
                raise ValueError('Invalid response')
            payload = bytearray()
            for chunk in response.iter_content(64 * 1024):
                payload.extend(chunk)
                if len(payload) > MAX_BYTES or time.monotonic() - started > 5:
                    raise ValueError('Download limit')
        result = _decode(payload)
        _atomic_write(path, payload)
        failed.unlink(missing_ok=True)
        return result
    except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError):
        failed.touch()
        return None


def _wrap(draw, value, font, width):
    words = EMOJI.sub('', str(value if value is not None else '')).split()
    lines, line = [], ''
    for word in words:
        if draw.textlength(word, font=font) > width:
            word = '…'
        candidate = f'{line} {word}'.strip()
        if draw.textlength(candidate, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + ([line] if line else [])


def _text(draw, value, box, size=22, minimum=None, lines=1, color='#ffffff', weight=500, tight=False):
    """Każde pole ma twarde granice, z zapasem na wychylenia glifów Montserrat."""
    x, y, right, bottom = box
    x, right = x + 2, right - 2
    for selected in range(size, (minimum or size) - 1, -1):
        font = _font(selected, weight)
        output = _wrap(draw, value, font, right - x)
        step = selected + 8
        limit = min(lines, int((bottom - y) // step))
        if tight:
            limit = min(lines, len(output), max(0, int((bottom - y) // step) + 1))
            while limit and y + (limit - 1) * step + draw.textbbox((0, 0), output[limit - 1], font=font, anchor='lt')[3] > bottom:
                limit -= 1
        if len(output) <= limit:
            break
    if limit < 1:
        return y
    if len(output) > limit:
        output = output[:limit]
        words = output[-1].split()
        while words and draw.textlength(' '.join(words) + '…', font=font) > right - x:
            words.pop()
        output[-1] = ' '.join(words) + '…'
    for line in output:
        draw.text((x, y), line, font=font, fill=color, anchor='lt')
        y += step
    return y - step + draw.textbbox((0, 0), output[-1], font=font, anchor='lt')[3] if tight and output else y


def _paste(image, source, box, radius=18):
    x, y, right, bottom = box
    size = (right - x, bottom - y)
    crop = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(.5, 0))
    mask = Image.new('L', size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    image.paste(crop, (x, y), mask)


def _date(value):
    value = str(value or '')[:10]
    return '.'.join(reversed(value.split('-'))) if len(value) == 10 else value


def plural_pl(n, singular, plural, genitive):
    if n == 1:
        return singular
    return plural if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else genitive


def _first_sentence(value):
    # Nie traktuj wielokropka jako zakończenia pełnego zdania.
    value = str(value or '').replace('…', '').replace('...', '').strip()
    match = re.search(r'^.*?[.!?](?=\s|$)', value)
    return match.group(0) if match else ''


def render(data):
    image = Image.new('RGB', (1600, 900), '#0b0b0b')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, 1560, 834), radius=28, fill='#171717')
    # Szerokości treści: 532 + 40 + 868; wspólny dół kolumn na y=802.
    left, right, end = 80, 652, 1520
    scan, author, post = data['scan'], data['author'], data['post']
    def text(value, box, **kwargs):
        return _text(draw, value, box, **kwargs)
    avatar = fetch_image(author.get('avatar_url'))
    if avatar is not None:
        _paste(image, avatar, (left, 76, left + 56, 132), 28)
    else:
        draw.ellipse((left, 76, left + 56, 132), fill='#303030')
        initials = ''.join(p[0] for p in author.get('name', '').split()[:2]).upper()
        text(initials, (left + 9, 92, left + 49, 124), size=20, minimum=14, weight=700)
    party = (author.get('party') or {}).get('short')
    text(author.get('name', '') + (f', {party}' if party else ''), (152, 77, 612, 106), size=22, minimum=17, weight=700)
    text(f"{_date(post.get('published_at'))} · Wpis na X", (152, 110, 612, 140), size=18, color=MUTED)
    scope = scan.get('scope') or {}
    label = 'Analiza: tekst' + (' i obraz' if scope.get('image') else '')
    if 'film' in scope.get('not_analyzed', []):
        label += ' · film nieanalizowany'
    draw.rounded_rectangle((left, 154, 612, 193), radius=10, fill='#222222')
    text(label, (left + 12, 163, 600, 190), size=17, minimum=14, color=MUTED, weight=600)
    deleted = post.get('available') is False or bool(post.get('deleted_at') or post.get('unavailable_at'))
    media = post.get('media') or []
    attachment = fetch_image(media[0].get('url')) if media and not deleted else None
    if deleted:
        text('Wpis usunięty przez autora', (left, 218, 612, 802), size=25, lines=3, color=MUTED)
    else:
        bottom = text(post.get('text', ''), (left, 214, 612, 582 if attachment is not None else 802), size=23, lines=100, tight=True)
        if attachment is not None:
            _paste(image, attachment, (left, bottom + 20, 612, 802))
    color = COLORS.get(data.get('verdict'), MUTED)
    verdict = data.get('verdict_label') or ''
    badge_end = right + int(draw.textlength(verdict, font=_font(16, 700)) + 29)
    draw.rounded_rectangle((right, 76, badge_end, 107), radius=15, outline=color, width=2)
    text(verdict, (right + 12, 82, badge_end - 12, 106), size=16, color=color, weight=700)
    text('OCENA KONSYLIUM AI', (badge_end + 12, 84, 1130, 109), size=15, weight=700, color='#8c8c8c')
    text(f"#SPIN-{data['id']} · diagnoza {_date(scan.get('diagnosed_at'))}", (1140, 84, end, 109), size=15, minimum=12, color='#8c8c8c')
    synthesis = scan.get('synthesis') or {}
    lead_bottom = text(synthesis.get('lead') or data.get('headline'), (right, 130, end, 247), size=31, minimum=27, lines=3, weight=700, tight=True)
    points = synthesis.get('points') or []
    reason = points[0] if points else _first_sentence(data.get('summary'))
    # Mierz uzasadnienie przed rysowaniem; nigdy nie dopisuj wielokropka.
    reason_top = lead_bottom + 14
    reason_size = 17
    reason_lines = _wrap(draw, reason, _font(reason_size), end - right - 4)
    reason_bottom = text(reason, (right, reason_top, end, reason_top + len(reason_lines) * 25), size=reason_size, lines=len(reason_lines), color=MUTED, tight=True)
    top = reason_bottom + 24
    edges = [right, right + 195, right + 405, right + 673, end]
    council, claims = scan.get('council') or {}, scan.get('claims') or {}
    families = scan.get('families') or {}
    counts = {family: families.get(family, {}).get('technique_types', 0) for family in FAMILIES}
    total = sum(v.get('technique_types', 0) for v in families.values())
    numbers = [str(data.get('intensity', 0)), council.get('verdict_agreement') or '—', claims.get('checked', 0), total]
    labels = ['Nasilenie spinu\n(ocena AI)', 'Zgodność\nwerdyktu', 'Sprawdzone\ntwierdzenia', 'Typy\ntechnik']
    details = [(key, label, shade) for key, label, shade in [('supported', 'potwierdzone', '#4ed18a'), ('contradicted', 'sprzeczne ze źródłami', '#ff6b6b'), ('misleading', 'mylące', '#f2b441'), ('unverified', 'niesprawdzone', MUTED)] if claims.get(key)]
    detail_top = top + 130
    opinions = claims.get('opinions', 0)
    opinion_label = f"Osobno: {opinions} {plural_pl(opinions, 'opinia', 'opinie', 'opinii')}"
    detail_height = sum(len(_wrap(draw, f"{claims[key]} {label}", _font(20), 211)) * 28 for key, label, _ in details)
    votes = []
    for vote in council.get('votes') or []:
        name = vote.get('model') or '?'
        name = next((label for key, label in [('gpt', 'GPT'), ('qwen', 'Qwen'), ('gemini', 'Gemini')] if key in name.lower()), name)
        votes.append(f"{name} {vote.get('intensity') if vote.get('intensity') is not None else '—'}")
    vote_label = ' · '.join(votes) or 'Brak danych'
    scores = council.get('range')
    range_label = f'rozrzut ocen {scores[0]}–{scores[1]}' if scores else 'Brak ocen modeli'
    vote_height = (min(3, len(_wrap(draw, vote_label, _font(20), 170))) + len(_wrap(draw, range_label, _font(20), 170))) * 28 + 8
    panel_bottom = detail_top + max(vote_height, detail_height + 8 + len(_wrap(draw, opinion_label, _font(20), 228)) * 28) + 16
    draw.rounded_rectangle((right, top, end, panel_bottom), radius=22, fill='#0f0f0f')
    for edge in edges[1:-1]:
        draw.line((edge, top, edge, panel_bottom), fill='#262626')
    for index in range(4):
        x, cell_end = edges[index] + 18, edges[index + 1] - 18
        text(numbers[index], (x, top + 16, cell_end, top + 74), size=44, minimum=30, weight=700, color=ACCENT if index == 0 else '#ffffff')
        if index == 0:
            offset = draw.textlength(str(numbers[0]), font=_font(44, 700))
            text('/100', (x + offset + 2, top + 38, cell_end, top + 74), size=19, color=MUTED)
        for j, line in enumerate(labels[index].split('\n')):
            text(line, (x, top + 78 + j * 26, cell_end, top + 105 + j * 26), size=18, color=MUTED)
    x = right + 20
    draw.rounded_rectangle((x, detail_top, x + 155, detail_top + 5), radius=2, fill='#262626')
    score = max(0, min(100, data.get('intensity') or 0))
    if score:
        draw.rectangle((x, detail_top, x + 155 * score / 100, detail_top + 5), fill=ACCENT)
    x = edges[1] + 18
    y = text(vote_label, (x, detail_top, edges[2] - 18, panel_bottom), size=20, lines=3)
    text(range_label, (x, y + 8, edges[2] - 18, panel_bottom), size=20, lines=2, color='#8c8c8c')
    x, y = edges[2] + 18, detail_top
    for key, label, shade in details:
        draw.ellipse((x, y + 5, x + 9, y + 14), fill=shade)
        y = text(f"{claims[key]} {label}", (x + 17, y, edges[3] - 18, panel_bottom), size=20, lines=2)
    text(opinion_label, (x, y + 8, edges[3] - 18, panel_bottom), size=20, lines=2, color='#8c8c8c')
    x = edges[3] + 18
    text(f"w {sum(bool(v) for v in counts.values())} z 3 rodzin", (x, detail_top, end - 18, panel_bottom), size=20, lines=2)
    table_top = panel_bottom + 24
    text('RODZINA TECHNIK', (right, table_top, 932, table_top + 27), size=15, weight=700, color='#8c8c8c')
    text('TECHNIKI W ANALIZOWANYM MATERIALE', (952, table_top, 1460, table_top + 27), size=14, weight=700, color='#8c8c8c')
    text('TYPY', (1475, table_top, end, table_top + 27), size=14, color='#8c8c8c')
    for index, (family, shade) in enumerate(FAMILIES.items()):
        y = table_top + 34 + index * 42
        draw.line((right, y, end, y), fill='#262626')
        draw.rounded_rectangle((right, y + 17, right + 9, y + 26), radius=2, fill=shade)
        text(FAMILY_LABELS[family], (right + 22, y + 12, 936, y + 40), size=17, minimum=15, weight=700)
        names = [t['name'] for t in scan.get('techniques', []) if t.get('family') == family]
        text(' · '.join(names) or 'Nie wskazano', (952, y + 12, 1455, y + 40), size=17, minimum=14, color='#ffffff' if names else '#8c8c8c')
        text(counts[family], (1480, y + 12, end, y + 40), size=18, weight=700)
    text(f"spin.clinic/klinika/{data['id']}", (38, 858, 560, 890), size=18, color=MUTED)
    footer = 'Diagnoza AI · rządzący i opozycja według tych samych zasad'
    footer_x = 1560 - draw.textlength(footer, font=_font(18))
    text(footer, (footer_x - 2, 858, 1562, 890), size=18, color=MUTED)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def cached_card(data):
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:24]
    directory = Path(settings.MEDIA_ROOT) / 'clinic_cards'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"diagnosis-{data['id']}-{VERSION}-{digest}.png"
    if not path.exists():
        _atomic_write(path, render(data))
    return path
