"""Pionowy film (1080×1920, ok. 30 s) z diagnozy — na Reels, TikTok i YouTube Shorts.

Sceny: wpis polityka (nasza grafika, nie zrzut z X) → diagnoza Dr. Spina → techniki z cytatami → terapia (co mówią
źródła) → źródła → spin.clinic. Klatki rysuje Pillow tą samą czcionką co karta na X (Montserrat, OFL), film składa
ffmpeg z paczki imageio-ffmpeg — bez instalowania czegokolwiek w systemie serwera. Bez muzyki (cicha ścieżka dźwiękowa,
bo część serwisów odrzuca filmy bez audio). Treść diagnozy przechodzi bez zmian — skracamy tylko długość.
"""
from __future__ import annotations

import os
import re
import subprocess
from urllib.parse import urlparse

from PIL import Image, ImageDraw

from news.x_card import ACCENT, BG, CARD, EMOJI, MUTED, SPIN, TEXT, _font, _wrap

W, H, FPS = 1080, 1920, 30
X0, X1 = 84, W - 84          # marginesy; dół i prawa krawędź są zasłonięte przyciskami TikToka i Reels
TOP, BOTTOM = 250, 1560
FADE = 0.45                   # wejście elementu (s)
CROSS = 0.35                  # przejście między scenami (s)
GOOD, WARN = (70, 200, 120), (245, 176, 65)
ASSESSMENT_COLORS = {'supported': GOOD, 'contradicted': SPIN, 'misleading': WARN, 'unverified': MUTED}


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', EMOJI.sub('', text or '')).strip()


class Scene:
    """Tło sceny i elementy wchodzące kolejno (przezroczyste warstwy z pozycją i chwilą wejścia)."""

    def __init__(self, duration: float):
        self.duration = duration
        self.base = Image.new('RGBA', (W, H), BG + (255,))
        self.layers: list[tuple[float, Image.Image, int, int]] = []

    def add(self, at: float, layer: Image.Image, x: int, y: int) -> None:
        self.layers.append((at, layer, x, y))

    def center(self) -> None:
        """Przesuwa całą treść na środek obszaru między nagłówkiem a strefą przycisków serwisu."""
        if not self.layers:
            return
        top = min(y for _, _, _, y in self.layers)
        bottom = max(y + layer.height for _, layer, _, y in self.layers)
        shift = max(TOP, (TOP + BOTTOM - (bottom - top)) // 2) - top
        self.layers = [(at, layer, x, y + shift) for at, layer, x, y in self.layers]

    def frame(self, t: float) -> Image.Image:
        frame = self.base.copy()
        for at, layer, x, y in self.layers:
            if t < at:
                continue
            p = min(1.0, (t - at) / FADE)
            ease = 1 - (1 - p) ** 3
            if ease < 1:
                faded = layer.copy()
                faded.putalpha(faded.getchannel('A').point(lambda a, e=ease: int(a * e)))
                frame.alpha_composite(faded, (x, int(y + 48 * (1 - ease))))
            else:
                frame.alpha_composite(layer, (x, y))
        return frame


def _text_block(lines: list[str], size: int, weight: int, color, line_height: int, width: int = X1 - X0) -> Image.Image:
    layer = Image.new('RGBA', (width, max(1, line_height * len(lines))), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(size, weight)
    for i, line in enumerate(lines):
        draw.text((0, i * line_height), line, font=font, fill=color)
    return layer


def _wrapped(text: str, size: int, weight: int, color, max_lines: int, line_height: int | None = None,
             width: int = X1 - X0) -> Image.Image:
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    from news.x_share import shorten
    clean = _clean(text)
    lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
    if lines and lines[-1].endswith('…'):
        budget = len(' '.join(lines)) - 1
        clean = shorten(clean, budget)
        lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
        while lines and lines[-1].endswith('…') and budget > 0:
            budget -= 10
            clean = shorten(clean, budget)
            lines = _wrap(probe, clean, _font(size, weight), width, max_lines)
    return _text_block(lines, size, weight, color, line_height or int(size * 1.32), width)


def _label(text: str, color=ACCENT) -> Image.Image:
    return _text_block([text.upper()], 34, 800, color, 44)


def _pill(text: str, color) -> Image.Image:
    font = _font(38, 800)
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width = int(probe.textlength(text, font=font)) + 64
    layer = Image.new('RGBA', (width, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((1, 1, width - 2, 78), radius=39, outline=color, width=4)
    draw.text((width // 2, 40), text, font=font, fill=color, anchor='mm')
    return layer


def _panel(content: Image.Image, pad: int = 36) -> Image.Image:
    layer = Image.new('RGBA', (X1 - X0, content.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((0, 0, layer.width - 1, layer.height - 1), radius=36, fill=CARD + (255,))
    layer.alpha_composite(content, (pad, pad))
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
    brand = _font(48, 800)
    x = X0
    for part, color in (('spin', TEXT), ('.', ACCENT), ('clinic', TEXT)):
        draw.text((x, 118), part, font=brand, fill=color)
        x += draw.textlength(part, font=brand)
    draw.text((X1, 142), step, font=_font(30, 600), fill=MUTED, anchor='rm')
    draw.line((X0, 204, X1, 204), fill=(40, 46, 58), width=2)


def _intensity_bar(value: int) -> Image.Image:
    layer = Image.new('RGBA', (X1 - X0, 26), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, layer.width - 1, 25), radius=13, fill=(40, 46, 58))
    filled = max(26, int((layer.width - 1) * max(0, min(100, value)) / 100))
    draw.rounded_rectangle((0, 0, filled, 25), radius=13, fill=SPIN if value >= 50 else WARN)
    return layer


def _post_card(post: dict) -> Image.Image:
    """Wpis polityka w pionie, dużą czcionką (nasza grafika, nie zrzut z X): autor, konto · partia · data, treść."""
    inner = X1 - X0 - 88
    from news.names import display_name
    name = display_name(post.get('name', ''))
    initials = ''.join(part[0] for part in name.split()[:2]).upper()
    head = Image.new('RGBA', (inner, 104), (0, 0, 0, 0))
    draw = ImageDraw.Draw(head)
    draw.ellipse((0, 0, 96, 96), fill=(42, 48, 59))
    draw.text((48, 48), initials, font=_font(36, 700), fill=MUTED, anchor='mm')
    draw.text((120, 4), name, font=_font(42, 800), fill=TEXT)
    meta = ' · '.join(part for part in [f"@{post['handle']}" if post.get('handle') else '', post.get('party', ''),
                                        post.get('published', '')] if part)
    draw.text((120, 58), meta, font=_font(28, 500), fill=MUTED)
    text = re.sub(r'\n\s*\n+', '\n', EMOJI.sub('', post.get('text', ''))).strip()
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = _wrap(probe, text, _font(44, 500), inner, 13)
    body = _text_block(lines, 44, 500, TEXT, 60, inner)
    return _panel(_stack([(head, 36), (body, 0)], inner), pad=44)


def build_scenes(data: dict, post: dict) -> list[Scene]:
    scenes = []
    content = X1 - X0
    inner = content - 72

    from news.names import display_name
    from news.social_content import checked_claims
    s = Scene(2.0)
    _chrome(s, 'Diagnoza AI')
    s.add(-FADE, _wrapped(f"{data.get('verdict_label') or 'Spin'} {data.get('intensity', 0)}/100",
                          88, 800, SPIN, 2, 110), X0, TOP)
    s.add(-FADE, _wrapped(display_name(post.get('name', '')), 56, 800, TEXT, 2), X0, TOP + 250)
    if post.get('party'):
        s.add(-FADE, _wrapped(post['party'], 44, 600, MUTED, 2), X0, TOP + 420)
    s.center()
    scenes.append(s)

    # 1. Wpis polityka
    s = Scene(5.0)
    _chrome(s, 'Klinika spinu')
    s.add(0.0, _label('Wpis polityka z X'), X0, TOP)
    title = _wrapped('Analizowany wpis', 72, 800, TEXT, 3, 88)
    s.add(0.15, title, X0, TOP + 64)
    s.add(0.7, _post_card(post), X0, TOP + 110 + title.height)
    s.center()
    scenes.append(s)

    # 2. Diagnoza
    s = Scene(6.5)
    _chrome(s, '1 · Diagnoza')
    s.add(0.0, _label('Diagnoza Dr. Spina'), X0, TOP)
    s.add(0.3, _pill(f"{data.get('verdict_label') or 'Diagnoza'} · {int(data.get('intensity') or 0)}/100", SPIN), X0, TOP + 70)
    s.add(0.6, _intensity_bar(int(data.get('intensity') or 0)), X0, TOP + 180)
    safe_summary = len(checked_claims(data.get('claims'))) == len(data.get('claims') or [])
    synthesis = (data.get('x_thread') or []) if safe_summary else []
    headline = _wrapped(synthesis[0] if synthesis else data.get('headline', '') if safe_summary else '', 64, 800, TEXT, 6, 82)
    s.add(1.0, headline, X0, TOP + 256)
    s.add(1.8, _wrapped(' '.join(synthesis[1:2]) if synthesis else data.get('summary', '') if safe_summary else '', 44, 500, MUTED, 8, 60), X0, TOP + 300 + headline.height)
    s.center()
    scenes.append(s)

    # 3. Techniki (do trzech, kolejno)
    techniques = [t for t in (data.get('techniques') or []) if t.get('name')][:3]
    if techniques:
        s = Scene(2.4 + 2.8 * len(techniques))
        _chrome(s, '2 · Techniki')
        s.add(0.0, _label('Techniki perswazji'), X0, TOP)
        y = TOP + 76
        for i, item in enumerate(techniques):
            parts = [(_wrapped(item['name'], 46, 800, ACCENT, 2, 58, inner), 16)]
            if item.get('quote'):
                parts.append((_wrapped(f"„{_clean(item['quote'])}”", 40, 600, TEXT, 3, 54, inner), 14))
            if item.get('explanation'):
                parts.append((_wrapped(item['explanation'], 34, 500, MUTED, 3, 46, inner), 0))
            panel = _panel(_stack(parts, inner))
            if y + panel.height > BOTTOM:
                break
            s.add(0.4 + 2.8 * i, panel, X0, y)
            y += panel.height + 28
        s.center()
        scenes.append(s)

    # 4. Terapia — co mówią źródła o twierdzeniach
    claims = [c for c in checked_claims(data.get('claims')) if c.get('claim')][:2]
    if claims:
        s = Scene(2.6 + 3.2 * len(claims))
        _chrome(s, '3 · Terapia')
        s.add(0.0, _label('Terapia · co mówią źródła'), X0, TOP)
        y = TOP + 76
        for i, claim in enumerate(claims):
            color = ASSESSMENT_COLORS.get(claim.get('assessment'), MUTED)
            parts = [(_wrapped(claim['claim'], 42, 700, TEXT, 3, 56, inner), 18)]
            if claim.get('assessment_label'):
                parts.append((_text_block([claim['assessment_label'].upper()], 32, 800, color, 42, inner), 14))
            if claim.get('explanation'):
                parts.append((_wrapped(claim['explanation'], 36, 500, MUTED, 5, 48, inner), 0))
            panel = _panel(_stack(parts, inner))
            if y + panel.height > BOTTOM:
                break
            s.add(0.4 + 3.2 * i, panel, X0, y)
            y += panel.height + 28
        s.center()
        scenes.append(s)

        # 5. Źródła
        sources, seen = [], set()
        for claim in claims:
            for source in claim.get('sources') or []:
                host = urlparse(source.get('url', '')).netloc.removeprefix('www.')
                if host and host not in seen:
                    seen.add(host)
                    sources.append((host, source.get('title', '')))
        if sources:
            s = Scene(4.0)
            _chrome(s, '4 · Źródła')
            s.add(0.0, _label('Źródła'), X0, TOP)
            y = TOP + 84
            for i, (host, title) in enumerate(sources[:5]):
                block = _stack([(_text_block([host], 46, 800, TEXT, 58), 6),
                                (_wrapped(title, 34, 500, MUTED, 2, 46), 0)], content)
                s.add(0.3 + 0.35 * i, block, X0, y)
                y += block.height + 44
            s.center()
            scenes.append(s)

    # 6. Zakończenie
    s = Scene(4.0)
    _chrome(s, 'spin.clinic')
    s.add(0.0, _wrapped('Pełna diagnoza ze źródłami:', 50, 700, TEXT, 2, 64), X0, TOP)
    s.add(0.3, _wrapped(f"spin.clinic/klinika/{data.get('id', '')}", 60, 800, ACCENT, 2, 76), X0, TOP + 84)
    s.add(0.8, _wrapped('Rządzący i opozycja — ta sama miara.', 48, 700, TEXT, 2, 62), X0, TOP + 290)
    s.add(1.2, _wrapped('Bez reklam i bez pieniędzy partii. Działamy dzięki wpłatom czytelników.', 40, 500, MUTED, 3, 54),
          X0, TOP + 440)
    s.add(1.6, _pill('Obserwuj · Wspomóż projekt', ACCENT), X0, TOP + 640)
    s.center()
    scenes.append(s)
    return scenes


def _frames(scenes: list[Scene]):
    """Klatki RGB po kolei; nieruchome fragmenty sceny wysyłamy jako tę samą klatkę (bez rysowania na nowo)."""
    for index, scene in enumerate(scenes):
        total = int(round(scene.duration * FPS))
        settled = max([at + FADE for at, *_ in scene.layers] + [0])
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
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
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
