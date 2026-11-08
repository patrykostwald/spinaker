from types import SimpleNamespace

import pytest

from news.material_type import classify_material_type


@pytest.mark.parametrize('metadata,expected', [
    ({'title': 'WYWIAD: Łódź się zmienia'}, 'wywiad'),
    ({'title': 'Rozmowa z Anną Żółkiewską'}, 'wywiad'),
    ({'title': 'Reportaż znad Wisły'}, 'reportaz'),
    ({'title': 'Felieton: co dalej?'}, 'opinia'),
    ({'title': 'Komentarz do zmian'}, 'opinia'),
    ({'title': 'Wiadomości z Łodzi'}, 'news'),
    ({'url': 'https://media.test/wywiad/123'}, 'wywiad'),
    ({'url': 'https://media.test/rozmowa/123'}, 'wywiad'),
    ({'url': 'https://media.test/reportaz/123'}, 'reportaz'),
    ({'url': 'https://media.test/felieton/123'}, 'opinia'),
    ({'url': 'https://media.test/opinie/123'}, 'opinia'),
    ({'url': 'https://media.test/komentarz/123'}, 'opinia'),
    ({'url': 'https://media.test/reporta%C5%BC/123'}, 'reportaz'),
    ({'tags': ['Polska', 'Reportaż']}, 'reportaz'),
    ({'description': 'Nasz wywiad z gościem.'}, 'wywiad'),
    ({'title': 'Aktualności', 'automatic_match': True, 'matched_in': 'description'}, 'wzmianka'),
    ({'title': 'Wywiad', 'automatic_match': True, 'matched_in': 'description'}, 'wzmianka'),
    ({'title': 'Aktualności', 'automatic_match': True, 'matched_in': 'title'}, 'news'),
    ({'title': 'Wywiadowca wraca', 'tags': [None, {}]}, 'news'),
    ({'title': 'Aktualności', 'url': 'https://wywiad.test/news?a=/wywiad/'}, 'news'),
    ({}, 'inne'),
])
def test_metadata(metadata, expected):
    assert classify_material_type(metadata) == expected
    assert classify_material_type(SimpleNamespace(**metadata)) == expected
