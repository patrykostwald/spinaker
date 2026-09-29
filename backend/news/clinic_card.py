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

VERSION = 'v2'
COLORS = {'spin': '#ff6b6b', 'partial': '#f2b441', 'no_spin': '#4ed18a', 'unclear': '#a6a6a6'}
MUTED, ACCENT = '#a6a6a6', '#4a9eff'


def render(data):
    image = Image.new('RGB', (1200, 675), '#000000')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 1176, 651), radius=24, fill='#0f0f0f')

    def text(value, x, y, width, size=22, lines=1, color='#ffffff', weight=500):
        font = _font(size, weight)
        words = EMOJI.sub('', str(value if value is not None else '')).split()
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
    text(f"Ocena AI: {data['intensity']}/100", 820, 90, 320, 27, weight=700)
    draw.rounded_rectangle((820, 140, 1148, 150), radius=5, fill='#303030')
    if data['intensity']:
        draw.rectangle((820, 140, 820 + 328 * min(100, data['intensity']) / 100, 150), fill=color)
    version = str(scan.get('diagnosed_at') or '')[:10]
    if len(version) == 10:
        version = '.'.join(reversed(version.split('-')))
    scope = scan['scope']
    scope_text = 'analiza ' + ('tekstu i obrazu' if scope['image'] else 'tekstu')
    if 'film' in scope['not_analyzed']:
        scope_text += '; film nieanalizowany'
    text(f'diagnoza {version} · {scope_text}', 52, 139, 750, 17, color=MUTED)
    draw.line((52, 173, 1148, 173), fill='#303030', width=2)
    text('WPIS', 52, 193, 590, 16, color=MUTED, weight=700)
    text('„' + data['post']['text'] + '”', 52, 223, 595, 25, 4)
    text('SYNTEZA', 52, 378, 590, 16, color=ACCENT, weight=700)
    text((scan['synthesis'] or {}).get('lead') or 'Synteza w przygotowaniu.', 52, 411, 595, 23, 4)
    text('TYPY TECHNIK', 706, 190, 442, 16, color=MUTED)
    for index, (family, values) in enumerate(scan['families'].items()):
        y = 219 + index * 36
        text(FAMILY_LABELS[family], 706, y, 370, 20)
        text(values['technique_types'], 1100, y, 48, 20, color=ACCENT, weight=700)
    claims = scan['claims']
    text(f"Twierdzenia: {claims['checked']} sprawdzonych · domeny: {scan['sources']}", 706, 379, 442, 17)
    parts = [f"{claims[key]} {label}" for key, label in
             (('supported', 'potwierdzone'), ('misleading', 'mylące'), ('contradicted', 'sprzeczne'), ('opinions', 'opinie'))
             if claims[key]]
    text(' · '.join(parts) or 'Brak sprawdzonych twierdzeń.', 706, 410, 442, 18, 2)
    council = scan['council']
    agreement = (council['verdict_agreement'] or '').replace('/', ' z ')
    scores = council['range']
    label = f"Werdykt: {agreement} modeli zgodne" if agreement else 'Brak danych konsylium'
    if scores:
        label += f" · oceny {scores[0]}–{scores[1]}"
    text(label, 706, 481, 442, 19, 2)
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
