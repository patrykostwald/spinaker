"""Obrazek z wpisem polityka do wpisu konta spin.clinic na X — zamiast oznaczania autora (@) i cytowania jego wpisu.

Oznaczenie i cytat wysyłają politykowi powiadomienie przy każdej diagnozie (prosta droga do blokady konta). Obrazek
pokazuje to samo — autora, datę i treść wpisu — bez powiadomień. Styl jak w serwisie; czcionka Montserrat (OFL).
"""
from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]')
FONT = Path(__file__).resolve().parent / 'assets' / 'fonts' / 'Montserrat[wght].ttf'
WIDTH, HEIGHT, PAD = 1200, 675, 64
BG, CARD, TEXT, MUTED, ACCENT, SPIN = (7, 9, 13), (18, 22, 30), (255, 255, 255), (174, 182, 194), (74, 158, 255), (255, 90, 90)


def _font(size: int, weight: int = 500) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT), size)
    try:
        font.set_variation_by_axes([weight])
    except (OSError, ValueError, AttributeError):
        pass
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int) -> list[str]:
    """Zawija tekst do szerokości w pikselach; ostatnia linia z wielokropkiem, gdy się nie mieści."""
    lines: list[str] = []
    for paragraph in (text or '').split('\n'):
        words, line = paragraph.split(), ''
        for word in words:
            candidate = f'{line} {word}'.strip()
            if draw.textlength(candidate, font=font) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    lines = [line for line in lines if line is not None]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + '…', font=font) > width:
            lines[-1] = lines[-1].rsplit(' ', 1)[0]
        lines[-1] += '…'
    return lines


def render(*, name: str, handle: str, party: str, published: str, text: str, intensity: int, verdict_label: str) -> bytes:
    image = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((PAD - 24, PAD - 24, WIDTH - PAD + 24, HEIGHT - PAD + 24), radius=36, fill=CARD)
    # nagłówek: inicjały, imię i nazwisko, @konto · partia · data
    initials = ''.join(part[0] for part in name.split()[:2]).upper()
    draw.ellipse((PAD, PAD, PAD + 72, PAD + 72), fill=(42, 48, 59))
    draw.text((PAD + 36, PAD + 36), initials, font=_font(28, 700), fill=MUTED, anchor='mm')
    draw.text((PAD + 96, PAD + 6), name, font=_font(32, 700), fill=TEXT)
    meta = ' · '.join(part for part in [f'@{handle}' if handle else '', party, published] if part)
    draw.text((PAD + 96, PAD + 46), meta, font=_font(22, 500), fill=MUTED)
    # treść wpisu — tyle linii, ile mieści się nad stopką; bez emoji (czcionka ich nie ma) i bez pustych akapitów
    footer_y = HEIGHT - PAD - 30
    body_font = _font(30, 500)
    clean = EMOJI.sub('', text or '')
    clean = re.sub(r'\n\s*\n+', '\n', clean).strip()
    y = PAD + 110
    lines = _wrap(draw, clean, body_font, WIDTH - 2 * PAD, max(1, (footer_y - 28 - y) // 40))
    for line in lines:
        draw.text((PAD, y), line, font=body_font, fill=TEXT)
        y += 40
    # stopka: ocena Dr. Spina i źródło obrazka
    tag = f'{verdict_label} · {intensity}/100'
    tag_font = _font(22, 700)
    tag_width = draw.textlength(tag, font=tag_font) + 28
    draw.rounded_rectangle((PAD, footer_y - 6, PAD + tag_width, footer_y + 32), radius=19, outline=SPIN, width=2)
    draw.text((PAD + 14, footer_y + 13), tag, font=tag_font, fill=SPIN, anchor='lm')
    draw.text((WIDTH - PAD, footer_y + 13), 'Wpis z X · diagnoza: spin.clinic', font=_font(22, 600), fill=ACCENT, anchor='rm')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def fields(diagnosis) -> dict:
    """Autor, konto, partia, data i treść wpisu — wspólne dla karty na X i filmu (news/social_video.py)."""
    from news.clinic import CAMP_LABELS, figures_by_account, party_data
    post = diagnosis.post
    figure = figures_by_account([post.account_id]).get(post.account_id)
    party = (party_data(figure) or {}).get('short', '') if figure else ''
    name = figure.canonical_name if figure else (post.author_data or {}).get('name') or post.account.display_name
    name = ' '.join(part.capitalize() if part.isupper() and len(part) > 1 else part for part in name.split())
    published = post.published_at.strftime('%d.%m.%Y, %H:%M') if post.published_at else ''
    return {'name': name, 'handle': post.account.handle, 'party': party or CAMP_LABELS.get(post.camp_at_collection, ''),
            'published': published, 'text': post.text, 'intensity': diagnosis.intensity,
            'verdict_label': diagnosis.get_verdict_display()}


def for_diagnosis(diagnosis) -> bytes:
    return render(**fields(diagnosis))
