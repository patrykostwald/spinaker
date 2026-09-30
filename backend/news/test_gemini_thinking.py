from types import SimpleNamespace

from news import clinic_ai


def test_each_task_gets_its_thinking_level(monkeypatch):
    monkeypatch.delenv('GEMINI_THINKING_CHECK', raising=False)
    assert clinic_ai.gemini_thinking('check') == {'thinkingConfig': {'thinkingLevel': 'medium'}}
    assert clinic_ai.gemini_thinking('transcript') == {'thinkingConfig': {'thinkingLevel': 'minimal'}}
    monkeypatch.setenv('GEMINI_THINKING_CHECK', 'default')
    assert clinic_ai.gemini_thinking('check') == {}


def test_rejected_thinking_level_is_retried_without_it(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    sent = []

    def post(url, json, timeout, headers):
        sent.append(json['generationConfig'])
        if 'thinkingConfig' in json['generationConfig']:
            return SimpleNamespace(status_code=400, text='Unknown field thinking_level')
        return SimpleNamespace(status_code=200, text='{}')

    monkeypatch.setattr(clinic_ai.requests, 'post', post)
    response = clinic_ai.gemini_post('m', {'generationConfig': {'temperature': 0, **clinic_ai.gemini_thinking('image')}}, timeout=1)
    assert response.status_code == 200 and len(sent) == 2 and 'thinkingConfig' not in sent[1]


def test_thinking_tokens_are_counted_as_output():
    assert clinic_ai.gemini_output_tokens({'candidatesTokenCount': 300, 'thoughtsTokenCount': 4200}) == 4500


import pytest
from io import StringIO
from django.core.management import call_command


@pytest.mark.django_db
def test_gemini_costs_command_runs():
    out = StringIO()
    call_command('gemini_costs', '--days', '3', stdout=out)
    assert 'RAZEM' in out.getvalue()
