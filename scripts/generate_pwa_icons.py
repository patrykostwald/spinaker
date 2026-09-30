"""Render the simple app/icon.svg geometry with Pillow, no extra dependencies."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
source = ET.parse(ROOT / 'frontend-spin/app/icon.svg').getroot()
width = float(source.attrib['viewBox'].split()[2])
target = ROOT / 'frontend-spin/public/app'
target.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    for maskable in (False, True):
        scale = size * 4 / width * (0.72 if maskable else 1)
        offset = size * 4 * (0.14 if maskable else 0)
        image = Image.new('RGB', (size * 4, size * 4), source[0].attrib['fill'])
        draw = ImageDraw.Draw(image)
        def p(value):
            return float(value) * scale + offset
        for element in source:
            attrs = element.attrib
            tag = element.tag.split('}')[-1]
            if tag == 'rect':
                draw.rounded_rectangle((p(0), p(0), p(attrs['width']), p(attrs['height'])),
                                       radius=float(attrs.get('rx', 0)) * scale, fill=attrs['fill'])
            elif tag == 'circle':
                x, y, radius = float(attrs['cx']), float(attrs['cy']), float(attrs['r'])
                draw.ellipse((p(x-radius), p(y-radius), p(x+radius), p(y+radius)), fill=attrs['fill'])
            elif tag == 'path':
                match = re.fullmatch(r'M([\d.]+) ([\d.]+)h([\d.]+)', attrs['d'])
                if not match:
                    raise ValueError('Unsupported SVG path; update renderer for the new icon.')
                x, y, length = map(float, match.groups())
                draw.line((p(x), p(y), p(x+length), p(y)), fill=attrs['stroke'],
                          width=round(float(attrs['stroke-width']) * scale))
            else:
                raise ValueError(f'Unsupported SVG element: {tag}')
        name = 'maskable' if maskable else 'icon'
        image.resize((size, size), Image.Resampling.LANCZOS).save(target / f'{name}-{size}.png')
