import json
from pathlib import Path

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from news.techniques import CANONICAL_TECHNIQUES, SEMEVAL_2023, SEMEVAL_MAP


def test_semeval_catalog_and_frontend_match():
    catalog = [name for names in SEMEVAL_2023.values() for name in names]
    assert len(SEMEVAL_2023) == 6
    assert len(catalog) == len(set(catalog)) == 23
    assert set(SEMEVAL_MAP) == set(CANONICAL_TECHNIQUES)
    assert all(isinstance(names, list) and set(names) <= set(catalog) for names in SEMEVAL_MAP.values())
    assert sum(not names for names in SEMEVAL_MAP.values()) == 8
    assert SEMEVAL_MAP['Zmiana tematu'] == ['Red Herring', 'Whataboutism']
    assert SEMEVAL_MAP['Apel do emocji'] == ['Loaded Language', 'Appeal to Values']
    frontend = (Path(__file__).resolve().parents[2] / 'packages/ui/src/lib/semeval.ts').read_text(encoding='utf-8')
    assert json.loads(frontend.split(' = ', 1)[1].split(';', 1)[0]) == SEMEVAL_MAP
    missing = set(catalog) - {name for names in SEMEVAL_MAP.values() for name in names}
    assert missing == {'Appeal to Hypocrisy', 'Appeal to Popularity', 'Consequential Oversimplification',
                       'Slogans', 'Conversation Killer', 'Appeal to Time', 'Obfuscation/Vagueness/Confusion', 'Repetition'}
    assert set(json.loads(frontend.split('SEMEVAL_UNRECOGNIZED = ')[1].split(';')[0])) == missing


@pytest.mark.django_db
def test_stats_api_semeval(django_assert_num_queries):
    cache.clear()
    try:
        response = APIClient().get('/api/clinic/stats/')
        assert response.status_code == 200
        definitions = response.json()['technique_definitions']
        assert set(definitions) == set(CANONICAL_TECHNIQUES)
        for name in CANONICAL_TECHNIQUES:
            assert definitions[name]['semeval'] == SEMEVAL_MAP[name]
        with django_assert_num_queries(0):
            assert APIClient().get('/api/clinic/stats/').json()['technique_definitions'] == definitions
    finally:
        cache.clear()
