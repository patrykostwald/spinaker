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
from news.x_card import _font, EMOJI, glue_short

VERSION = 'v6'
FORMATS = {'diagnoza', 'skrot'}
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
    words = glue_short(EMOJI.sub('', str(value if value is not None else '')).split())
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



def _short_reason(draw, primary, fallback, width):
    candidates = [str(primary or '').strip(), _first_sentence(primary), _first_sentence(fallback)]
    for candidate in candidates:
        if candidate and candidate[-1] in '.!?' and len(_wrap(draw, candidate, _font(17), width)) <= 2:
            return candidate
    return ''


def _scope_label(scan):
    scope = scan.get('scope') or {}
    label = 'Analiza: tekst' + (' i obraz' if scope.get('image') else '')
    if 'film' in scope.get('not_analyzed', []):
        label += ' · film nieanalizowany'
    return label


def _deleted(post):
    return post.get('available') is False or bool(post.get('deleted_at') or post.get('unavailable_at'))


def _quote(data):
    if _deleted(data['post']):
        return ''
    techniques = data['scan'].get('techniques') or []
    value = (techniques[0].get('quote') if techniques else '') or data['post'].get('text', '')
    words = value.split()
    # Krótki cytat rozwiń wyłącznie o autentyczny kontekst wpisu.
    post_text = ' '.join(data['post'].get('text', '').split())
    quote_text = ' '.join(words)
    if len(words) < 12 and quote_text and quote_text in post_text:
        start = post_text.index(quote_text)
        words = post_text[start:].split()
        if len(words) < 12:
            words = post_text.split()[-25:]
    return ' '.join(words[:25]) + ('…' if len(words) > 25 else '')


def _draw_panel(draw, data, box):
    """Wspólny panel obu formatów; grafiki mają tę samą linię dołu."""
    left, top, right, bottom = box
    scale = min((right - left) / 868, (bottom - top) / 272)
    cell = (right - left) / 4
    scan = data['scan']
    council, claims = scan.get('council') or {}, scan.get('claims') or {}
    families = scan.get('families') or {}
    counts = [families.get(key, {}).get('technique_types', 0) for key in FAMILIES]
    total = sum(v.get('technique_types', 0) for v in families.values())
    draw.rounded_rectangle(box, radius=22 * scale, fill='#0f0f0f')
    def text(value, x, y, end, size=15, color=MUTED, weight=500):
        selected = round(size * scale)
        return _text(draw, value, (x, y, end, y + selected + 10), size=selected, color=color, weight=weight)
    def bar(x, y, width, fraction, color):
        height = 8 * scale
        draw.rounded_rectangle((x, y, x + width, y + height), radius=height / 2, fill='#262626')
        if fraction > 0:
            draw.rounded_rectangle((x, y, x + max(height, width * min(1, fraction)), y + height), radius=height / 2, fill=color)
    numbers = [data.get('intensity', 0), council.get('verdict_agreement') or '—', claims.get('checked', 0), total]
    suffixes = ['/100', 'zgodne', plural_pl(numbers[2], 'sprawdzone', 'sprawdzone', 'sprawdzonych'), plural_pl(total, 'typ', 'typy', 'typów')]
    for i, title in enumerate(['NASILENIE SPINU', 'KONSYLIUM AI', 'TWIERDZENIA', 'TECHNIKI']):
        edge = left + cell * i
        if i:
            draw.line((edge, top, edge, bottom), fill='#262626', width=1)
        x, end = edge + 20 * scale, edge + cell - 18 * scale
        text(title, x, top + 22 * scale, end, size=14, weight=700, color='#8c8c8c')
        number_size = round(44 * scale)
        text(numbers[i], x, top + 57 * scale, end, size=44, weight=700, color=ACCENT if i == 0 else '#ffffff')
        offset = draw.textlength(str(numbers[i]), font=_font(number_size, 700))
        text(suffixes[i], x + offset + 5 * scale, top + 80 * scale, end, size=15)
        # Obszar wykresów: 104 jednostki, wspólny dół nad marginesem.
        y = bottom - 126 * scale
        width = end - x
        if i == 0:
            bar(x, bottom - 53 * scale, width, max(0, (data.get('intensity') or 0)) / 100, ACCENT)
            for label, fraction in [('0', 0), ('50', .5), ('100', 1)]:
                label_width = draw.textlength(label, font=_font(round(13 * scale))) + 5
                tick_x = x + (width - label_width) * fraction
                text(label, tick_x, bottom - 32 * scale, end + 3, size=13)
        elif i == 1:
            votes = council.get('votes') or []
            for j, key in enumerate(['gpt', 'qwen', 'gemini']):
                vote = next((v for v in votes if key in str(v.get('model', '')).lower()), {})
                row_y = y + 14 * scale + j * 33 * scale
                text(['GPT', 'Qwen', 'Gemini'][j], x, row_y, x + width * .4, size=14)
                score = vote.get('intensity')
                bar(x + width * .41, row_y + 6 * scale, width * .28, max(0, score or 0) / 100, ACCENT)
                text(score if score is not None else '—', x + width * .73, row_y, end - 9 * scale, size=15, color='#ffffff', weight=700)
                dot_x = end - 4 * scale
                draw.ellipse((dot_x, row_y + 6 * scale, dot_x + 8 * scale, row_y + 14 * scale), fill=COLORS.get(vote.get('verdict'), MUTED))
        elif i == 2:
            # Pięć kategorii musi zmieścić się z czytelną legendą (minimum 18 px).
            y = bottom - 158 * scale
            entries = [(key, label, color) for key, label, color in [
                ('supported', 'potw.', '#4ed18a'), ('misleading', 'mylące', '#f2b441'),
                ('contradicted', 'sprzeczne', '#ff6b6b'), ('unverified', 'niespr.', MUTED),
                ('opinions', plural_pl(claims.get('opinions', 0), 'opinia', 'opinie', 'opinii'), '#8c8c8c')]
                if claims.get(key, 0)]
            units = sum(claims[key] for key, _, _ in entries)
            gap = 5 * scale
            opinion_gap = 10 * scale if claims.get('opinions') and len(entries) > 1 else 0
            # Przy licznych twierdzeniach zmniejsz kwadraty; legenda zawsze podaje pełne liczby.
            visible = min(units, 16)
            square = min(18 * scale, (width - max(0, visible - 1) * gap - opinion_gap) / max(1, visible))
            cursor, drawn = x, 0
            for key, _, shade in entries:
                if key == 'opinions':
                    cursor += opinion_gap
                for _ in range(min(claims[key], 16 - drawn)):
                    draw.rounded_rectangle((cursor, y, cursor + square, y + square), radius=min(3 * scale, square / 3),
                                           fill=None if key == 'opinions' else shade, outline=shade, width=2)
                    cursor += square + gap
                    drawn += 1
            for j, (key, label, shade) in enumerate(entries):
                row_y = y + 28 * scale + j * 24 * scale
                draw.rectangle((x, row_y + 4 * scale, x + 7 * scale, row_y + 11 * scale),
                               fill=None if key == 'opinions' else shade, outline=shade)
                text(f'{claims[key]} {label}', x + 13 * scale, row_y, end, size=max(18, 18 / scale), color='#ffffff')
        else:
            maximum = max(1, *counts)
            for j, (label, shade, count) in enumerate(zip(['Dane', 'Emocje', 'Spór'], FAMILIES.values(), counts)):
                row_y = y + 14 * scale + j * 33 * scale
                text(label, x, row_y, x + width * .45, size=14)
                bar(x + width * .47, row_y + 6 * scale, width * .32, count / maximum, shade)
                text(count, x + width * .86, row_y, end + 3, size=15, color='#ffffff', weight=700)
    return bottom


def _render_short(data):
    image = Image.new('RGB', (1600, 900), '#0b0b0b')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, 1560, 834), radius=28, fill='#171717')
    scan, author, post = data['scan'], data['author'], data['post']
    _text(draw, 'spin.clinic · Dr. Spin', (78, 82, 475, 126), size=30, weight=700)
    draw.rounded_rectangle((487, 78, 655, 122), radius=22, fill='#142331')
    _text(draw, 'Analiza AI', (502, 89, 646, 120), size=22, color=ACCENT, weight=700)
    party = (author.get('party') or {}).get('short')
    meta = author.get('name', '') + (f', {party}' if party else '') + f" · {_date(post.get('published_at'))}"
    meta_width = draw.textlength(meta, font=_font(23)) + 5
    _text(draw, meta, (max(715, 1520 - meta_width), 89, 1520, 155), size=23, minimum=18, lines=2, color=MUTED)
    quote = _quote(data)
    if quote:
        draw.line((82, 212, 82, 435), fill='#555555', width=4)
        _text(draw, f'„{quote}”', (104, 214, 620, 453), size=29, minimum=24, lines=7, color=MUTED)
    elif _deleted(post):
        _text(draw, 'Wpis usunięty przez autora', (80, 214, 620, 420), size=27, lines=3, color=MUTED)
    lead = (scan.get('synthesis') or {}).get('lead') or data.get('headline')
    _text(draw, lead, (680, 202, 1518, 454), size=43, minimum=32, lines=6, weight=700)
    verdict = data.get('verdict_label') or ''
    shade = COLORS.get(data.get('verdict'), MUTED)
    badge_end = 100 + draw.textlength(verdict, font=_font(23, 700)) + 18
    draw.rounded_rectangle((80, 473, badge_end, 517), radius=22, outline=shade, width=2)
    _text(draw, verdict, (94, 484, badge_end - 10, 516), size=23, color=shade, weight=700)
    _draw_panel(draw, data, (80, 537, 1520, 809))
    _text(draw, _scope_label(scan), (40, 858, 780, 892), size=18, color=MUTED)
    footer = f"spin.clinic/klinika/{data['id']} · diagnoza {_date(scan.get('diagnosed_at'))}"
    footer_x = 1560 - draw.textlength(footer, font=_font(18))
    _text(draw, footer, (footer_x - 2, 858, 1562, 892), size=18, color=MUTED)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def render(data, card_format='diagnoza'):
    if card_format not in FORMATS:
        raise ValueError('Unknown card format')
    if card_format == 'skrot':
        return _render_short(data)
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
    deleted = _deleted(post)
    media = post.get('media') or []
    attachment = fetch_image(media[0].get('url')) if media and not deleted else None
    if deleted:
        text('Wpis usunięty przez autora', (left, 218, 612, 802), size=25, lines=3, color=MUTED)
    else:
        text_top = 214
        if attachment is not None:
            # Krótki wpis oddaje miejsce zdjęciu; długi zachowuje min. 220 px zdjęcia.
            line_count = len(_wrap(draw, post.get('text', ''), _font(23), 612 - left - 4))
            text_height = min(line_count, (802 - 214 - 220 - 16) // 31) * 31
            attachment_bottom = 802 - text_height - (16 if text_height else 0)
            _paste(image, attachment, (left, 214, 612, attachment_bottom))
            text_top = attachment_bottom + 16
        text(post.get('text', ''), (left, text_top, 612, 802), size=23, lines=100, tight=True)
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
    # Całe zdanie musi zmieścić się w najwyżej dwóch wierszach.
    reason_top = lead_bottom + 14
    reason = _short_reason(draw, reason, data.get('summary'), end - right - 4)
    reason_bottom = text(reason, (right, reason_top, end, reason_top + 50), size=17, lines=2, color=MUTED, tight=True) if reason else lead_bottom
    panel_top = reason_bottom + 16
    panel_bottom = _draw_panel(draw, data, (right, panel_top, end, panel_top + 272))
    families = scan.get('families') or {}
    counts = {family: families.get(family, {}).get('technique_types', 0) for family in FAMILIES}
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
    loaded = scan.get('loaded') or {}
    loaded_top = table_top + 170
    if loaded and loaded_top + 28 <= 802:
        label = f"Słowa nacechowane: {loaded['count']}"
        words = ' · '.join(item['word'] for item in loaded.get('words', []))
        text(label + (' · ' + words if words else ''), (right, loaded_top, end, loaded_top + 28), size=18, color=MUTED)
    text(f"spin.clinic/klinika/{data['id']}", (38, 858, 560, 890), size=18, color=MUTED)
    footer = 'Diagnoza AI · rządzący i opozycja według tych samych zasad'
    footer_x = 1560 - draw.textlength(footer, font=_font(18))
    text(footer, (footer_x - 2, 858, 1562, 890), size=18, color=MUTED)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def cached_card(data, card_format='diagnoza'):
    if card_format not in FORMATS:
        raise ValueError('Unknown card format')
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:24]
    directory = Path(settings.MEDIA_ROOT) / 'clinic_cards'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"diagnosis-{data['id']}-{VERSION}-{card_format}-{digest}.png"
    if not path.exists():
        _atomic_write(path, render(data, card_format))
    return path


def share_png(diagnosis, max_bytes: int = 950_000) -> bytes:
    """Karta diagnozy w nowym formacie (panel danych jak na stronie) do wpisów na X i Bluesky.
    Bluesky przyjmuje obrazy do ~1 MB, więc w razie potrzeby zmniejszamy paletę, a potem rozmiar."""
    from news import clinic
    figures = clinic.figures_by_account([diagnosis.post.account_id])
    payload = cached_card(clinic.card_data(diagnosis, figures), 'diagnoza').read_bytes()
    if len(payload) <= max_bytes:
        return payload
    image = Image.open(io.BytesIO(payload)).convert('RGB')
    for size in (image.size, (1200, 675)):
        candidate = image.resize(size, Image.LANCZOS) if size != image.size else image
        buffer = io.BytesIO()
        candidate.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(buffer, format='PNG', optimize=True)
        if buffer.tell() <= max_bytes:
            return buffer.getvalue()
    return buffer.getvalue()
