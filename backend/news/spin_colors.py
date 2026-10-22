"""Wspólna paleta ciemnych grafik Pillow i skala siły spinu."""
from PIL import Image, ImageDraw

# Skala siły spinu (właściciel 2.10): przygaszona; niebieski do 62, czerwień od 70, krwista przy 100.
STRENGTH_STOPS = ((0, (63, 158, 110)), (40, (74, 134, 212)), (62, (74, 134, 212)), (70, (224, 84, 74)), (100, (184, 48, 42)))
FAMILY_COLORS = {'spor': '#ff6b6b', 'przedstawienie': '#f2c94c', 'dane': '#4ed18a', 'inne': '#8b9097'}
CLAIM_COLORS = {'supported': '#4ed18a', 'misleading': '#f2b441',
                'contradicted': '#ff6b6b', 'unverified': '#8b9097'}
VERDICT_COLORS = {'spin': '#ff6b6b', 'partial': '#f2b441', 'no_spin': '#4ed18a', 'unclear': '#8b9097'}


def strength_color(value):
    """Interpolacja RGB po stopach skali 0-100, z ograniczeniem do jej końców."""
    value = max(0, min(100, value or 0))
    for (x0, c0), (x1, c1) in zip(STRENGTH_STOPS, STRENGTH_STOPS[1:]):
        if value <= x1:
            fraction = (value - x0) / (x1 - x0) if x1 > x0 else 1
            return tuple(round(a + (b - a) * fraction) for a, b in zip(c0, c1))
    return STRENGTH_STOPS[-1][1]


def strength_bar(draw, box, value, track='#262626'):
    """Lewy wycinek pełnej skali: kolor zależy od toru, nie od długości wypełnienia."""
    left, top, right, bottom = map(round, box)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return
    draw.rounded_rectangle((left, top, right, bottom), radius=height / 2, fill=track)
    filled = round(width * max(0, min(100, value or 0)) / 100)
    if filled <= 0:
        return
    mask = Image.new('L', (filled + 1, height + 1))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, filled, height), radius=height / 2, fill=255)
    for x in range(filled + 1):
        bounds = mask.crop((x, 0, x + 1, height + 1)).getbbox()
        if bounds:
            draw.line((left + x, top + bounds[1], left + x, top + bounds[3] - 1),
                      fill=strength_color(x / width * 100))


def tabular_score(draw, right, top, value, font, fill):
    """Stałe komórki cyfr i prawa krawędź, także bez biblioteki libraqm."""
    step = max(draw.textlength(digit, font=font) for digit in '0123456789')
    for index, digit in enumerate(reversed(str(value))):
        draw.text((right - (index + .5) * step, top), digit, font=font, fill=fill, anchor='mt')
