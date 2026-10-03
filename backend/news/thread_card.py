"""Share cards from stored thread data only. No image downloads or AI calls."""
from io import BytesIO
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from PIL import Image, ImageDraw
from rest_framework.decorators import api_view
from news.community import public_threads, _counts, item_data
from news.features import threads_enabled
from news.clinic_card import _text

COLORS = {'positive': '#4ed18a', 'doubt': '#f2b441', 'negative': '#ff6b6b'}


def render_thread_card(thread, counts, story=False):
    width, height = (1080, 1920) if story else (1200, 630)
    image = Image.new('RGB', (width, height), '#141414')
    draw = ImageDraw.Draw(image)
    total, largest = sum(counts.values()), max(counts.values())
    winners = [key for key, value in counts.items() if value == largest]
    color = COLORS[winners[0]] if total >= 3 and len(winners) == 1 else '#555555'
    top, bottom = (280, height - 280) if story else (32, height - 48)
    draw.rounded_rectangle((32, top, width - 32, bottom), radius=16, outline=color, width=3)
    _text(draw, thread.title, (64, top + 32, width - 64, top + 148), size=38, lines=2, weight=700)
    _text(draw, 'Dr. Spin (AI)' if thread.diagnosis_id else f'@{thread.owner.username}',
          (64, top + 150, width - 64, top + 192), size=22, color='#a6a6a6')
    rows = [item_data(i) for i in thread.items.select_related('article__source', 'link')
            if not (i.link_id and i.link.hidden_at)][:2]
    for index, item in enumerate(rows):
        x = 64 if story else 64 + index * ((width - 144) // 2 + 16)
        y = top + 224 + (index * 360 if story else 0)
        box_width = width - 128 if story else (width - 144) // 2
        box_height = 320 if story else 218
        draw.rounded_rectangle((x, y, x + box_width, y + box_height), radius=8, outline='#555555', width=2)
        _text(draw, item['title'], (x + 20, y + 20, x + box_width - 20, y + 150), size=28, lines=3, weight=600)
        _text(draw, item.get('note') or item.get('body') or item.get('source_name') or item.get('domain', ''),
              (x + 20, y + 152, x + box_width - 20, y + box_height - 16), size=21, lines=4 if story else 1, color='#a6a6a6')
    _text(draw, 'spin.clinic', (64, bottom - 64, width - 64, bottom - 16), size=30, weight=700)
    for x, key in zip((72, width // 2, width - 72), COLORS):
        draw.rectangle((x - 24, bottom - 4, x + 24, bottom + 4), fill='#141414')
        stroke = COLORS[key] if total >= 3 else '#555555'
        if key == 'positive':
            draw.line([(x-12, bottom), (x-4, bottom+8), (x+14, bottom-12)], fill=stroke, width=3)
        elif key == 'negative':
            draw.line([(x-10,bottom-10), (x+10,bottom+10)], fill=stroke, width=3)
            draw.line([(x+10,bottom-10), (x-10,bottom+10)], fill=stroke, width=3)
        else:
            draw.arc((x-9,bottom-16,x+9,bottom+2), 180, 450, fill=stroke, width=3)
            draw.line([(x,bottom+2),(x,bottom+7)], fill=stroke, width=3)
            draw.ellipse((x-1,bottom+12,x+1,bottom+14), fill=stroke)
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


@api_view(['GET'])
def thread_card(request, thread_id):
    if not threads_enabled():
        raise Http404
    thread = get_object_or_404(public_threads().select_related('owner'), pk=thread_id)
    format = request.GET.get('layout', 'og')
    if format not in ('og', 'story'):
        return HttpResponse(status=400)
    response = HttpResponse(render_thread_card(thread, _counts([thread.pk])[thread.pk], format == 'story'), content_type='image/png')
    response['Cache-Control'] = 'no-store'
    return response
