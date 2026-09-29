"""Publiczny obraz diagnozy; cache zależy od wersji i wszystkich danych obrazu."""
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from news.techniques import FAMILY_LABELS
from news.x_card import _font, EMOJI

VERSION = 'v1'
COLORS = {'spin': '#ff6b6b', 'partial': '#f2b441', 'no_spin': '#4ed18a', 'unclear': '#a6a6a6'}
MUTED, ACCENT = '#a6a6a6', '#4a9eff'


def render(data):
    image = Image.new('RGB', (1200, 675), '#000000')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 1176, 651), radius=24, fill='#0f0f0f')

    def text(value, x, y, width, size=22, lines=1, color='#ffffff', weight=500):
        font = _font(size, weight)
        words = EMOJI.sub('', str(value or '')).split()
        output, line = [], ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=font) <= width:
                line = candidate
            else:
                if line:
                    output.append(line)
                # Nawet pojedynczy długi adres nie może wyjść poza kolumnę.
                line = word if draw.textlength(word, font=font) <= width else '…'
        if line:
            output.append(line)
        if len(output) > lines:
            output = output[:lines]
            while output[-1] and draw.textlength(output[-1] + '…', font=font) > width:
                output[-1] = ' '.join(output[-1].split()[:-1])
            output[-1] += '…'
        for index, value in enumerate(output):
            draw.text((x, y + index * (size + 9)), value, font=font, fill=color)

    scan, author = data['scan'], data['author']
    party = (author.get('party') or {}).get('short')
    text(author['name'] + (f', {party}' if party else ''), 52, 48, 690, 30, weight=700)
    date = str(data['post']['published_at'])[:10]
    text(f"{data['camp_label']} · {date}", 52, 94, 640, 19, color=MUTED)
    color = COLORS.get(data['verdict'], MUTED)
    text(data['verdict_label'], 820, 46, 320, 23, color=color, weight=700)
    text(f"{data['intensity']}/100", 820, 80, 320, 43, weight=700)
    draw.rounded_rectangle((820, 140, 1148, 150), radius=5, fill='#303030')
    if data['intensity']:
        draw.rectangle((820, 140, 820 + 328 * min(100, data['intensity']) / 100, 150), fill=color)
    draw.line((52, 173, 1148, 173), fill='#303030', width=2)
    text('WPIS', 52, 193, 590, 16, color=MUTED, weight=700)
    text('„' + data['post']['text'] + '”', 52, 223, 595, 25, 4)
    text('SYNTEZA', 52, 378, 590, 16, color=ACCENT, weight=700)
    text((scan['synthesis'] or {}).get('lead') or 'Synteza w przygotowaniu.', 52, 411, 595, 23, 4)
    maximum = max(1, *scan['families'].values())
    for index, family in enumerate(('fakty', 'emocje', 'zagrania')):
        y, count = 200 + index * 61, scan['families'][family]
        text(FAMILY_LABELS[family], 706, y, 365, 20)
        text(count, 1100, y, 48, 20, color=ACCENT, weight=700)
        draw.rectangle((706, y + 32, 1148, y + 40), fill='#303030')
        if count:
            draw.rectangle((706, y + 32, 706 + 442 * count / maximum, y + 40), fill=ACCENT)
    claims = scan['claims']
    text(f"Twierdzenia: {claims['checked']} sprawdzonych · źródła: {scan['sources']}", 706, 388, 442, 17)
    x = 706
    draw.rectangle((x, 420, 1148, 432), fill='#303030')
    for key, verdict in (('supported', 'no_spin'), ('misleading', 'partial'), ('contradicted', 'spin')):
        width = 442 * claims[key] / max(1, claims['checked'])
        if width:
            draw.rectangle((x, 420, x + width, 432), fill=COLORS[verdict])
        x += width
    text(f"Potw. {claims['supported']}  /  mylące {claims['misleading']}  /  sprzeczne {claims['contradicted']}",
         706, 443, 442, 15, color=MUTED)
    council = scan['council']
    text('Konsylium · zgodność ' + (council['agreement'] or '—'), 706, 477, 442, 19)
    for index, vote in enumerate(council['votes'][:4]):
        x = 706 + index * 112
        draw.ellipse((x, 513, x + 12, 525), fill=COLORS.get(vote['verdict'], MUTED))
        text(vote['model'], x, 531, 105, 12, color=MUTED)
    for index, item in enumerate(scan['techniques'][:4]):
        x = 52 + index * 278
        draw.rounded_rectangle((x, 574, x + 266, 610), radius=12, outline='#303030')
        text(item['name'], x + 10, 582, 246, 14, color=ACCENT)
    text(f"spin.clinic/klinika/{data['id']} · Diagnoza AI · ta sama miara dla obu stron", 52, 626, 1096, 16, color=MUTED)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def cached_card(data):
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:24]
    directory = Path(settings.MEDIA_ROOT) / 'clinic_cards'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"diagnosis-{data['id']}-{VERSION}-{digest}.png"
    if not path.exists():
        payload = render(data)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as stream:
                temporary = stream.name
                stream.write(payload)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return path
