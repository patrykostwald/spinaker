import json
from io import StringIO

import pytest
from django.core.management import call_command


pytestmark = pytest.mark.django_db


def test_provider_preflight_is_read_only_and_hides_secret(monkeypatch):
    monkeypatch.setenv('NIM_API_KEY', 'secret-value')
    monkeypatch.setenv('NIM_EMBEDDING_MODEL', 'embed')
    monkeypatch.setenv('NIM_EMBEDDING_URL', 'https://nim.example/embed')
    monkeypatch.setenv('NIM_RERANK_MODEL', 'rerank')
    monkeypatch.setenv('NIM_RERANK_URL', 'https://nim.example/rerank')
    monkeypatch.setenv('NIM_ENABLED', 'false')
    output = StringIO()
    call_command('ai_provider_preflight', stdout=output)
    data = json.loads(output.getvalue())
    assert data['nim']['ready_for_controlled_pilot'] is True
    assert data['nim']['enabled'] is False
    assert data['network_calls_made'] == 0
    assert 'secret-value' not in output.getvalue()
