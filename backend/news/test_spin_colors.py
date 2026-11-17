"""Skala i jej użycie w kartach oraz animowanych kafelkach, bez sieci."""
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from news.spin_colors import strength_bar, strength_color, tabular_score


@pytest.mark.parametrize('value, expected', [
    (0, (63, 158, 110)), (40, (74, 134, 212)), (50, (74, 134, 212)), (66, (149, 109, 143)),
    (70, (224, 84, 74)), (100, (184, 48, 42)), (-10, (63, 158, 110)), (110, (184, 48, 42)),
])
def test_strength_color(value, expected):
    assert strength_color(value) == expected


@pytest.mark.parametrize('value', [0, 1, 15, 50, 90, 100])
def test_bar_is_slice_of_full_scale(value):
    image = Image.new('RGB', (221, 31))
    strength_bar(ImageDraw.Draw(image), (10, 5, 210, 25), value)
    for x in range(201):
        expected = strength_color(x / 2) if value and x <= 2 * value else (38, 38, 38)
        assert image.getpixel((10 + x, 15)) == expected


@pytest.mark.parametrize('progress', [0, .25, .5, 1])
def test_video_strength_animation_uses_current_value(progress):
    from news import social_video as video
    with patch.object(ImageDraw.ImageDraw, 'text', autospec=True) as text:
        image = video._strength_tile(90)(progress)
    number = next(call for call in text.call_args_list if call.kwargs['font'].size == 120)
    assert number.args[2] == str(round(90 * progress))
    assert number.kwargs['fill'] == strength_color(round(90 * progress))
    x = video.TILE_PAD + 20
    expected = strength_color(20 / (video.TILE_W - 2 * video.TILE_PAD) * 100) if progress else video.SURF3
    assert image.convert('RGB').getpixel((x, 397)) == expected


def test_council_has_no_tracks_and_has_verdict_dots():
    from news import social_video as video
    info = {'agreement': '1/3', 'votes': [
        {'model': 'GPT', 'intensity': 7, 'verdict': 'no_spin'},
        {'model': 'Claude', 'intensity': 50, 'verdict': 'partial'},
        {'model': 'Gemini', 'intensity': 100, 'verdict': 'spin'},
    ]}
    with patch.object(video, '_track', side_effect=AssertionError('Pasek głosu')), \
            patch.object(video, 'tabular_score', wraps=tabular_score) as score:
        image = video._council_tile(info)(1).convert('RGB')
    assert len({call.args[1] for call in score.call_args_list}) == 1
    x = video.TILE_W - video.TILE_PAD - 7
    assert [image.getpixel((x, y)) for y in (338, 390, 442)] == [
        (78, 209, 138), (242, 180, 65), (255, 107, 107)]


def test_score_uses_equal_digit_cells_without_raqm():
    from news.x_card import _font
    draw = ImageDraw.Draw(Image.new('RGB', (200, 50)))
    with patch.object(draw, 'text') as text:
        tabular_score(draw, 180, 10, 101, _font(30, 700), '#ffffff')
    positions = [call.args[0][0] for call in text.call_args_list]
    assert positions[0] - positions[1] == positions[1] - positions[2]


def test_renderers_share_traffic_light_order_and_claim_colors():
    from news import clinic_card, social_video
    from news.spin_colors import CLAIM_COLORS, FAMILY_COLORS
    from news.techniques import FAMILY_LABELS
    assert list(FAMILY_LABELS) == ['spor', 'przedstawienie', 'dane', 'inne']
    assert list(clinic_card.FAMILIES.items()) == list(FAMILY_COLORS.items())
    assert social_video.FAMILIES == [(key, label, FAMILY_COLORS[key]) for key, label in FAMILY_LABELS.items()]
    assert {key: color for key, color, _ in social_video.CLAIM_KINDS if key != 'opinion'} == CLAIM_COLORS


def test_video_four_families_fit_below_caption():
    from news import social_video as video
    info = video.presentation({'techniques': [{'name': name} for name in
                              ['Atak na osobę', 'Straszenie', 'Wybiórcze dane', 'Inne']]})
    original = ImageDraw.ImageDraw.text
    bounds = []
    def record(draw, xy, text, **kwargs):
        if text in {'techniki', 'Spór', 'Emocje', 'Dane', 'Inne'}:
            bounds.append(draw.textbbox(xy, text, font=kwargs['font'], anchor=kwargs['anchor']))
        return original(draw, xy, text, **kwargs)
    with patch.object(ImageDraw.ImageDraw, 'text', record):
        video._techniques_tile(info)(1)
    assert len(bounds) == 5
    assert all(upper[3] < lower[1] for upper, lower in zip(bounds, bounds[1:]))
