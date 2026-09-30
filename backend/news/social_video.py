"""Pionowy film (1080×1920, ok. 20 s) z diagnozy — na Reels, TikTok i YouTube Shorts.

Sceny (tempo pod krótkie formaty): siła spinu z licznikiem → wpis polityka (nasza grafika, nie zrzut z X) → panel danych
jak na stronie (siła spinu, Konsylium AI, twierdzenia, techniki — z rosnącymi paskami) → diagnoza → techniki z cytatami
→ spin.clinic. Kolory i układ panelu są te same co na karcie skanera (SpinSummary.tsx): czarne tło, siła na niebiesko,
rodziny technik w swoich kolorach, obóz rządzący niebieski, opozycja czerwona w paski. Klatki rysuje Pillow czcionką
Montserrat (OFL), film składa ffmpeg z paczki imageio-ffmpeg. Bez muzyki (cicha ścieżka dźwiękowa, bo część serwisów
odrzuca filmy bez audio). Treść diagnozy przechodzi bez zmian — skracamy tylko długość; tekst syntezy pokazujemy tylko
wtedy, gdy wszystkie twierdzenia są sprawdzone ze źródłami.
"""
from __future__ import annotations

import os
import re
import subprocess

from PIL import Image, ImageDraw

from news.x_card import EMOJI, _font, _wrap

W, H, FPS = 1080, 1920, 30
X0, X1 = 72, W - 72           # marginesy; dół i prawa krawędź są zasłonięte przyciskami TikToka i Reels
TOP, BOTTOM = 240, 1580
FADE = 0.28                   # wejście elementu (s)
SLIDE = 36                    # wjazd elementu z dołu (px)
CROSS = 0.22                  # przejście między scenami (s)

# Paleta strony (kit.css, motyw ciemny)
BG, SURF, SURF2, SURF3, LINE = (0, 0, 0), (15, 15, 15), (23, 23, 23), (38, 38, 38), (52, 52, 52)
TEXT, TEXT2, TEXT3 = (255, 255, 255), (179, 179, 179), (140, 140, 140)
ACCENT, GOV, OPP, OPP_DARK = (74, 158, 255), (91, 155, 255), (255, 107, 107), (201, 74, 74)
POSITIVE, WARNING, NEGATIVE = (78, 209, 138), (242, 180, 65), (255, 107, 107)
FAMILIES = [('dane', 'Dane i wnioskowanie', (85, 180, 255)), ('przedstawienie', 'Emocje i przedstawienie', (245, 165, 74)),
            ('spor', 'Spór i odpowiedzialność', (181, 138, 216)), ('inne', 'Inne', TEXT3)]
FAMILY_COLOR = {key: color for key, _, color in FAMILIES}
CLAIM_KINDS = [('supported', POSITIVE, 'potwierdzone'), ('misleading', WARNING, 'mylące'), ('contradicted', NEGATIVE, 'sprzeczne'),
               ('unverified', TEXT3, 'niezweryfikowane'), ('opinion', None, 'opinie')]


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', EMOJI.sub('', text or '')).strip()


def _ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


class Scene:
    """Tło sceny i elementy wchodzące kolejno. Element to gotowa warstwa albo funkcja postępu (0–1) → warstwa,
    np. rosnący pasek czy licznik; takie elementy dostają własny czas trwania animacji."""

    def __init__(self, duration: float):
        self.duration = duration
        self.base = Image.new('RGBA', (W, H), BG + (255,))
        self.layers: list[tuple[float, object, int, int, float]] = []

    def add(self, at: float, layer, x: int, y: int, animate: float = 0.0) -> None:
        self.layers.append((at, layer, x, y, animate))

    def settled(self) -> float:
        return max([at + max(FADE, animate) for at, _, _, _, animate in self.layers] + [0])

    def center(self) -> None:
        """Przesuwa całą treść na środek obszaru między nagłówkiem a strefą przycisków serwisu."""
        if not self.layers:
            return
        sizes = [(y, (layer(1.0) if callable(layer) else layer).height) for _, layer, _, y, _ in self.layers]
        top = min(y for y, _ in sizes)
        bottom = max(y + h for y, h in sizes)
        shift = max(TOP, (TOP + BOTTOM - (bottom - top)) // 2) - top
        self.layers = [(at, layer, x, y + shift, animate) for at, layer, x, y, animate in self.layers]

    def frame(self, t: float) -> Image.Image:
        frame = self.base.copy()
        for at, layer, x, y, animate in self.layers:
            if t < at:
                continue
            image = layer(_ease((t - at) / animate)) if callable(layer) else layer
            ease = _ease((t - at) / FADE)
            if ease < 1:
                faded = image.copy()
                faded.putalpha(faded.getchannel('A').point(lambda a, e=ease: int(a * e)))
                frame.alpha_composite(faded, (x, int(y + SLIDE * (1 - ease))))
            else:
                frame.alpha_composite(image, (x, y))
        return frame


# --- elementy -------------------------------------------------------------------------------

def _text_block(lines: list[str], size: int, weight: int, color, line_height: int, width: int = X1 - X0,
                spacing: float = 0) -> Image.Image:
    layer = Image.new('RGBA', (width, max(1, line_height * len(lines))), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(size, weight)
    for i, line in enumerate(lines):
        if spacing:
            x = 0
            for char in line:
                draw.text((x, i * line_height), char, font=font, fill=color)
                x += draw.textlength(char, font=font) + spacing
        else:
            draw.text((0, i * line_height), line, font=font, fill=color)
    return layer


def _wrapped(text: str, size: int, weight: int, color, max_lines: int, line_height: int | None = None,
             width: int = X1 - X0, sentences: bool = True) -> Image.Image:
    """Zawija tekst; zbyt długi skraca do pełnych zdań (sentences) albo — dla cytatów — wielokropkiem w słowie."""
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    from news.x_share import shorten
    clean = _clean(text)
    lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
    if sentences and lines and lines[-1].endswith('…') and shorten(clean, len(clean)):
        budget = len(' '.join(lines)) - 1
        clean = shorten(clean, budget)
        lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
        while lines and lines[-1].endswith('…') and budget > 0:
            budget -= 10
            clean = shorten(clean, budget)
            lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
    return _text_block(lines, size, weight, color, line_height or int(size * 1.3), width)


def _label(text: str, color=TEXT3, width: int = X1 - X0) -> Image.Image:
    return _text_block([text.upper()], 30, 800, color, 40, width, spacing=2.5)


def _pill(text: str, color, filled: bool = False) -> Image.Image:
    font = _font(36, 800)
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width = int(probe.textlength(text, font=font)) + 64
    layer = Image.new('RGBA', (width, 78), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if filled:
        draw.rounded_rectangle((0, 0, width - 1, 77), radius=39, fill=color)
        draw.text((width // 2, 39), text, font=font, fill=(4, 16, 31), anchor='mm')
    else:
        draw.rounded_rectangle((1, 1, width - 2, 76), radius=38, outline=color, width=4)
        draw.text((width // 2, 39), text, font=font, fill=color, anchor='mm')
    return layer


def _camp_chip(camp: str, label: str) -> Image.Image:
    """Obóz jak na stronie: rządzący — pełny niebieski, opozycja — czerwony w paski."""
    font = _font(30, 800)
    text = (label or ('Rządzący' if camp == 'government' else 'Opozycja')).upper()
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width = int(probe.textlength(text, font=font)) + 56 + len(text) * 3
    layer = Image.new('RGBA', (width, 60), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if camp == 'government':
        draw.rounded_rectangle((0, 0, width - 1, 59), radius=12, fill=GOV)
    else:
        stripes = Image.new('RGBA', (width, 60), OPP + (255,))
        sdraw = ImageDraw.Draw(stripes)
        for x in range(-60, width + 60, 18):
            sdraw.polygon([(x, 60), (x + 7, 60), (x + 67, 0), (x + 60, 0)], fill=OPP_DARK)
        mask = Image.new('L', (width, 60), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, 59), radius=12, fill=255)
        layer.paste(stripes, (0, 0), mask)
    x = 28
    for char in text:
        draw.text((x, 30), char, font=font, fill=(10, 10, 10), anchor='lm')
        x += draw.textlength(char, font=font) + 3
    return layer


def _panel(content: Image.Image, pad: int = 36, accent=None, width: int = X1 - X0) -> Image.Image:
    layer = Image.new('RGBA', (width, content.height + 2 * pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, layer.width - 1, layer.height - 1), radius=32, fill=SURF2 + (255,), outline=LINE, width=2)
    if accent:
        draw.rounded_rectangle((0, 0, 10, layer.height - 1), radius=5, fill=accent)
    layer.alpha_composite(content, (pad + (8 if accent else 0), pad))
    return layer


def _stack(parts: list[tuple[Image.Image, int]], width: int) -> Image.Image:
    """Elementy jeden pod drugim (obraz, odstęp po nim)."""
    height = sum(img.height + gap for img, gap in parts)
    layer = Image.new('RGBA', (width, max(1, height)), (0, 0, 0, 0))
    y = 0
    for img, gap in parts:
        layer.alpha_composite(img, (0, y))
        y += img.height + gap
    return layer


def _chrome(scene: Scene, step: str) -> None:
    """Stały nagłówek: marka i etap — widz od razu wie, że to diagnoza AI spin.clinic."""
    draw = ImageDraw.Draw(scene.base)
    brand = _font(50, 800)
    x = X0
    for part, color in (('spin', TEXT), ('.', ACCENT), ('clinic', TEXT)):
        draw.text((x, 110), part, font=brand, fill=color)
        x += draw.textlength(part, font=brand)
    draw.text((X1, 136), step.upper(), font=_font(28, 700), fill=TEXT3, anchor='rm')
    draw.line((X0, 196, X1, 196), fill=SURF3, width=2)


def _track(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], share: float, color) -> None:
    x0, y0, x1, y1 = box
    radius = (y1 - y0) // 2
    draw.rounded_rectangle(box, radius=radius, fill=SURF3)
    if share > 0:
        draw.rounded_rectangle((x0, y0, max(x0 + 2 * radius, int(x0 + (x1 - x0) * min(1.0, share))), y1), radius=radius, fill=color)


def _techniques_word(n: int) -> str:
    if n == 1:
        return 'technika'
    return 'techniki' if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else 'technik'


# --- dane z diagnozy (to samo liczenie co diagnosisPresentation.ts) ----------------------------

def presentation(data: dict) -> dict:
    scan = data.get('scan') or {}
    scanned = {t.get('category') or t.get('name'): t.get('family') for t in scan.get('techniques') or []}
    types, seen = [], set()
    for item in data.get('techniques') or scan.get('techniques') or []:
        key = (item.get('category') or item.get('name') or '').strip()
        if not key or key in seen:
            continue
        seen.add(key)
        family = item.get('family') or scanned.get(key) or 'inne'
        types.append({**item, 'type': key, 'family': family if family in FAMILY_COLOR else 'inne'})
    families = [(key, label, color, sum(1 for t in types if t['family'] == key)) for key, label, color in FAMILIES]
    families = [row for row in families if row[0] != 'inne' or row[3]]
    claims = [(key, color, label, sum(1 for c in data.get('claims') or [] if c.get('assessment') == key))
              for key, color, label in CLAIM_KINDS]
    checked = sum(count for key, _, _, count in claims if key in ('supported', 'misleading', 'contradicted'))
    council = scan.get('council') or {}
    votes = [v for v in council.get('votes') or [] if v.get('verdict') in ('spin', 'partial', 'no_spin', 'unclear')]
    if not votes:
        votes = [{'model': m.get('model', '').split('/')[-1], **m} for m in (data.get('council') or {}).get('members') or []
                 if m.get('verdict') in ('spin', 'partial', 'no_spin', 'unclear')]
    same = max([sum(1 for o in votes if o.get('verdict') == v.get('verdict')) for v in votes] + [0])
    return {'types': types, 'families': families, 'claims': claims, 'checked': checked, 'votes': votes,
            'agreement': f'{same}/{len(votes)}' if votes else '—'}


# --- kafelki panelu danych (jak .sc-scan-m na stronie) ---------------------------------------

TILE_W, TILE_H, TILE_PAD = (X1 - X0 - 24) // 2, 500, 34


def _tile(label: str, number: str, suffix: str, graphic, number_color=TEXT):
    """Etykieta → duża liczba → grafika na wspólnej dolnej linii. graphic(draw, box, p) rysuje część animowaną."""
    def draw_tile(p: float) -> Image.Image:
        layer = Image.new('RGBA', (TILE_W, TILE_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle((0, 0, TILE_W - 1, TILE_H - 1), radius=28, fill=SURF2, outline=LINE, width=2)
        x = TILE_PAD
        for char in label.upper():
            draw.text((x, TILE_PAD), char, font=_font(28, 800), fill=TEXT3)
            x += draw.textlength(char, font=_font(28, 800)) + 2
        shown = number(p) if callable(number) else number
        big = _font(120, 800)
        draw.text((TILE_PAD, TILE_PAD + 44), shown, font=big, fill=number_color)
        width = draw.textlength(shown, font=big)
        draw.text((TILE_PAD, TILE_PAD + 44 + 178), suffix, font=_font(30, 600), fill=TEXT3, anchor='ls')
        graphic(draw, (TILE_PAD, 270, TILE_W - TILE_PAD, TILE_H - TILE_PAD), p)
        return layer
    return draw_tile


def _strength_tile(value: int):
    value = max(0, min(100, value))

    def graphic(draw, box, p):
        x0, y0, x1, y1 = box
        _track(draw, (x0, y1 - 84, x1, y1 - 54), value / 100 * p, ACCENT)
        for i, tick in enumerate(('0', '50', '100')):
            anchor = ('ls', 'ms', 'rs')[i]
            draw.text(((x0, (x0 + x1) // 2, x1)[i], y1), tick, font=_font(30, 700), fill=TEXT3, anchor=anchor)
    return _tile('Siła spinu', lambda p: str(round(value * p)), '/100', graphic, ACCENT)


def _council_tile(info: dict):
    votes = info['votes'][:4]

    def graphic(draw, box, p):
        x0, y0, x1, y1 = box
        if not votes:
            draw.text((x0, y1), 'Brak danych o składzie', font=_font(24, 600), fill=TEXT3, anchor='ls')
            return
        row = 52
        top = y1 - row * len(votes) + 12
        for i, vote in enumerate(votes):
            y = top + i * row
            name = re.sub(r'\s+', ' ', str(vote.get('model', '')))[:13]
            draw.text((x0, y + 16), name, font=_font(27, 600), fill=TEXT2, anchor='lm')
            intensity = vote.get('intensity')
            _track(draw, (x0 + 200, y + 9, x1 - 60, y + 23), (intensity or 0) / 100 * p, ACCENT)
            draw.text((x1, y + 16), str(intensity if intensity is not None else '—'), font=_font(30, 800), fill=TEXT, anchor='rm')
    return _tile('Konsylium AI', info['agreement'], 'ten sam werdykt', graphic)


def _claims_tile(info: dict):
    squares = [(color, key) for key, color, _, count in info['claims'] for _ in range(count)]
    legend = [f'{count} {label}' for key, _, label, count in info['claims'] if count]

    def graphic(draw, box, p):
        x0, y0, x1, y1 = box
        size, gap = 40, 12
        per_row = max(1, (x1 - x0 + gap) // (size + gap))
        shown = squares[:per_row * 2][:max(0, round(len(squares) * p))] if squares else []
        rows = (min(len(squares), per_row * 2) + per_row - 1) // per_row
        top = y1 - 56 - rows * (size + gap)
        for i, (color, key) in enumerate(shown):
            x = x0 + (i % per_row) * (size + gap)
            y = top + (i // per_row) * (size + gap)
            if color is None:
                draw.rounded_rectangle((x, y, x + size, y + size), radius=6, outline=TEXT3, width=3)
            else:
                draw.rounded_rectangle((x, y, x + size, y + size), radius=6, fill=color)
        draw.text((x0, y1), ' · '.join(legend[:2]) or 'brak twierdzeń', font=_font(28, 600), fill=TEXT3, anchor='ls')
    return _tile('Twierdzenia', str(info['checked']), 'sprawdzone', graphic)


def _techniques_tile(info: dict):
    families = info['families']
    top_count = max([count for *_, count in families] + [1])

    def graphic(draw, box, p):
        x0, y0, x1, y1 = box
        row = 60
        top = y1 - row * len(families) + 16
        for i, (key, label, color, count) in enumerate(families):
            y = top + i * row
            draw.text((x0, y + 18), label.split(' ')[0], font=_font(30, 700), fill=color, anchor='lm')
            _track(draw, (x0 + 170, y + 10, x1 - 44, y + 26), count / top_count * p, color)
            draw.text((x1, y + 18), str(count), font=_font(32, 800), fill=TEXT, anchor='rm')
    count = len(info['types'])
    return _tile('Techniki', str(count), _techniques_word(count), graphic)


def _post_card(post: dict) -> Image.Image:
    """Wpis polityka w pionie, dużą czcionką (nasza grafika, nie zrzut z X): autor, konto · partia · data, treść."""
    inner = X1 - X0 - 88
    from news.names import display_name
    name = display_name(post.get('name', ''))
    initials = ''.join(part[0] for part in name.split()[:2]).upper()
    head = Image.new('RGBA', (inner, 104), (0, 0, 0, 0))
    draw = ImageDraw.Draw(head)
    draw.ellipse((0, 0, 96, 96), fill=SURF3)
    draw.text((48, 48), initials, font=_font(36, 700), fill=TEXT2, anchor='mm')
    draw.text((120, 4), name, font=_font(42, 800), fill=TEXT)
    meta = ' · '.join(part for part in [f"@{post['handle']}" if post.get('handle') else '', post.get('party', ''),
                                        post.get('published', '')] if part)
    draw.text((120, 58), meta, font=_font(28, 500), fill=TEXT3)
    text = re.sub(r'\n\s*\n+', '\n', EMOJI.sub('', post.get('text', ''))).strip()
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = _wrap(probe, text, _font(44, 500), inner, 11)
    body = _text_block(lines, 44, 500, TEXT, 60, inner)
    return _panel(_stack([(head, 36), (body, 0)], inner), pad=44)


# --- sceny ----------------------------------------------------------------------------------

def build_scenes(data: dict, post: dict) -> list[Scene]:
    from news.names import display_name
    from news.social_content import checked_claims
    scenes = []
    content = X1 - X0
    info = presentation(data)
    intensity = int(data.get('intensity') or 0)
    camp = data.get('camp') or ''

    # 0. Hak: kto, obóz i siła spinu z licznikiem
    s = Scene(2.6)
    _chrome(s, 'Diagnoza AI')
    s.add(0.0, _camp_chip(camp, data.get('camp_label', '')), X0, TOP)
    name = _wrapped(display_name(post.get('name', '')), 68, 800, TEXT, 2, 80)
    s.add(0.1, name, X0, TOP + 96)
    party = post.get('party', '') if (post.get('party') or '').lower() != (data.get('camp_label') or '').lower() else ''
    meta = ' · '.join(part for part in [party, f"@{post['handle']}" if post.get('handle') else ''] if part)
    y = TOP + 116 + name.height
    if meta:
        s.add(0.2, _wrapped(meta, 36, 600, TEXT2, 1), X0, y)
        y += 70
    s.add(0.35, _label('Siła spinu według Konsylium AI'), X0, y + 30)

    def counter(p: float) -> Image.Image:
        layer = Image.new('RGBA', (content, 300), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        shown = str(round(intensity * p))
        big = _font(230, 800)
        draw.text((0, 250), shown, font=big, fill=ACCENT, anchor='ls')
        draw.text((draw.textlength(shown, font=big) + 16, 250), '/100', font=_font(72, 700), fill=TEXT3, anchor='ls')
        _track(draw, (0, 276, content, 300), intensity / 100 * p, ACCENT)
        return layer
    s.add(0.35, counter, X0, y + 80, animate=1.3)
    s.add(1.1, _pill(f"{data.get('verdict_label') or 'Spin'} · zgodność {info['agreement']}", ACCENT), X0, y + 420)
    s.center()
    scenes.append(s)

    # 1. Wpis polityka
    s = Scene(3.6)
    _chrome(s, 'Badany wpis')
    s.add(0.0, _label('Wpis na X'), X0, TOP)
    s.add(0.15, _post_card(post), X0, TOP + 60)
    s.center()
    scenes.append(s)

    # 2. Panel danych — jak na karcie skanera
    s = Scene(4.8)
    _chrome(s, 'Wynik badania')
    s.add(0.0, _wrapped('Co zmierzyło Konsylium AI', 64, 800, TEXT, 2, 76), X0, TOP)
    tiles = [_strength_tile(intensity), _council_tile(info), _claims_tile(info), _techniques_tile(info)]
    for i, tile in enumerate(tiles):
        s.add(0.35 + 0.3 * i, tile, X0 + (i % 2) * (TILE_W + 24), TOP + 120 + (i // 2) * (TILE_H + 24), animate=1.0)
    s.center()
    scenes.append(s)

    # 3. Diagnoza — synteza tylko przy sprawdzonych twierdzeniach; inaczej same techniki (bez niesprawdzonych tez)
    safe = len(checked_claims(data.get('claims'))) == len(data.get('claims') or [])
    synthesis = (data.get('scan') or {}).get('synthesis') or {}
    lead = (synthesis.get('lead') or (data.get('x_thread') or [''])[0] or data.get('headline', '')) if safe else ''
    points = (synthesis.get('points') or [])[:2] if safe else []
    if not lead and info['types']:
        count = len(info['types'])
        lead = f'Konsylium AI wskazało {count} {_techniques_word(count)} perswazji.'
        points = [f"{t['type']}" + (f" – {t['explanation']}" if t.get('explanation') else '') for t in info['types'][:2]]
    if lead:
        s = Scene(2.6 + 1.2 * len(points))
        _chrome(s, 'Diagnoza')
        s.add(0.0, _label('Diagnoza Dr. Spina', ACCENT), X0, TOP)
        headline = _wrapped(lead, 64, 800, TEXT, 5, 80)
        s.add(0.15, headline, X0, TOP + 64)
        y = TOP + 120 + headline.height
        for i, point in enumerate(points):
            block = _wrapped(point, 40, 500, TEXT2, 4, 54, content - 44)
            layer = Image.new('RGBA', (content, block.height), (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse((0, 16, 20, 36), fill=ACCENT)
            layer.alpha_composite(block, (44, 0))
            s.add(0.8 + 1.1 * i, layer, X0, y)
            y += block.height + 36
        s.center()
        scenes.append(s)

    # 4. Techniki z cytatami (do trzech)
    techniques = [t for t in info['types'] if t.get('quote')][:3]
    if techniques:
        s = Scene(1.0 + 1.5 * len(techniques))
        _chrome(s, 'Techniki')
        s.add(0.0, _label('Techniki perswazji · cytaty'), X0, TOP)
        y = TOP + 64
        inner = content - 80
        for i, item in enumerate(techniques):
            color = FAMILY_COLOR.get(item['family'], TEXT3)
            parts = [(_wrapped(item.get('name') or item['type'], 44, 800, color, 2, 56, inner), 14),
                     (_wrapped(f"„{_clean(item['quote'])}”", 42, 600, TEXT, 4, 56, inner, sentences=False), 0)]
            panel = _panel(_stack(parts, inner), pad=32, accent=color)
            if y + panel.height > BOTTOM:
                break
            s.add(0.3 + 1.5 * i, panel, X0, y)
            y += panel.height + 24
        s.center()
        scenes.append(s)

    # 5. Zakończenie
    s = Scene(2.8)
    _chrome(s, 'spin.clinic')
    s.add(0.0, _wrapped('Pełna diagnoza ze źródłami:', 48, 700, TEXT2, 2, 62), X0, TOP)
    s.add(0.15, _wrapped(f"spin.clinic/klinika/{data.get('id', '')}", 62, 800, ACCENT, 2, 78), X0, TOP + 76)
    s.add(0.5, _wrapped('Ta sama miara dla rządu i opozycji.', 58, 800, TEXT, 2, 72), X0, TOP + 260)
    s.add(0.8, _wrapped('Bez reklam i bez pieniędzy partii. Działamy dzięki wpłatom czytelników.', 38, 500, TEXT2, 3, 52),
          X0, TOP + 440)
    s.add(1.1, _pill('Obserwuj spin.clinic', ACCENT, filled=True), X0, TOP + 600)
    s.center()
    scenes.append(s)
    return scenes


def _frames(scenes: list[Scene]):
    """Klatki RGB po kolei; nieruchome fragmenty sceny wysyłamy jako tę samą klatkę (bez rysowania na nowo)."""
    for index, scene in enumerate(scenes):
        total = int(round(scene.duration * FPS))
        settled = scene.settled()
        still = None
        following = scenes[index + 1].frame(0) if index + 1 < len(scenes) else None
        for n in range(total):
            t = n / FPS
            if t >= settled and still is not None:
                frame = still
            else:
                frame = scene.frame(t)
                if t >= settled:
                    still = frame
            remaining = scene.duration - t
            if following is not None and remaining < CROSS:
                # przejście: przenikanie do pierwszej klatki następnej sceny
                frame = Image.blend(frame, following, 1 - remaining / CROSS)
            yield frame.convert('RGB').tobytes()


def render(data: dict, post: dict, out_path: str) -> dict:
    """Zapisuje MP4 (H.264, 30 kl./s, cicha ścieżka AAC). Zwraca długość i rozmiar."""
    import imageio_ffmpeg
    scenes = build_scenes(data, post)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
               '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               '-c:a', 'aac', '-b:a', '64k', '-shortest', out_path]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for chunk in _frames(scenes):
            process.stdin.write(chunk)
        process.stdin.close()
    except BrokenPipeError:
        pass
    error = process.stderr.read().decode('utf-8', 'replace')
    if process.wait() != 0:
        raise RuntimeError(f'ffmpeg: {error[:300]}')
    return {'seconds': round(sum(s.duration for s in scenes), 1), 'bytes': os.path.getsize(out_path)}


def for_diagnosis(diagnosis, out_path: str) -> dict:
    from news.clinic import detail_data
    from news.x_card import fields
    return render(detail_data(diagnosis), fields(diagnosis), out_path)
