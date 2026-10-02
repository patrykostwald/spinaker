"""Wspólna paleta ciemnych grafik Pillow i skala siły spinu."""
from PIL import Image, ImageDraw

STRENGTH_STOPS = ((78, 209, 138), (74, 158, 255), (255, 107, 107))
FAMILY_COLORS = {'spor': '#ff6b6b', 'przedstawienie': '#f2c94c', 'dane': '#4ed18a', 'inne': '#8b9097'}
CLAIM_COLORS = {'supported': '#4ed18a', 'misleading': '#f2b441',
                'contradicted': '#ff6b6b', 'unverified': '#8b9097'}
VERDICT_COLORS = {'spin': '#ff6b6b', 'partial': '#f2b441', 'no_spin': '#4ed18a', 'unclear': '#8b9097'}


def strength_color(value):
    """Interpolacja RGB skali 0-100, z ograniczeniem do jej końców."""
    value = max(0, min(100, value or 0))
    index = 0 if value <= 50 else 1
    fraction = (value - 50 * index) / 50
    return tuple(round(a + (b - a) * fraction)
                 for a, b in zip(STRENGTH_STOPS[index], STRENGTH_STOPS[index + 1]))


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
