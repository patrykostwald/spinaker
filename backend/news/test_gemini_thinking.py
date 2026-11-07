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


def test_spend_counter_adds_thinking_and_searches(settings):
    from django.core.cache import cache
    from django.utils import timezone
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    payload = {'usageMetadata': {'promptTokenCount': 1_000_000, 'candidatesTokenCount': 0, 'thoughtsTokenCount': 1_000_000},
               'candidates': [{'groundingMetadata': {'webSearchQueries': ['a', 'b']}}]}
    clinic_ai.record_gemini_spend('check', payload)
    row = cache.get(clinic_ai.GEMINI_SPEND_KEY.format(day=timezone.localdate().isoformat(), task='check'))
    assert row['calls'] == 1 and row['searches'] == 2 and row['thinking'] == 1_000_000
    assert abs(row['usd'] - (0.5 + 3.0 + 2 * clinic_ai.GEMINI_SEARCH_USD)) < 1e-9


def test_daily_budget_stops_paid_calls(settings, monkeypatch):
    from django.core.cache import cache
    from django.utils import timezone
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    monkeypatch.setenv('GEMINI_DAILY_BUDGET_USD', '1')
    cache.set(clinic_ai.GEMINI_SPEND_KEY.format(day=timezone.localdate().isoformat(), task='council'), {'calls': 9, 'usd': 1.2, 'searches': 0, 'thinking': 0})
    monkeypatch.setattr(clinic_ai.requests, 'post', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no paid call over budget')))
    with pytest.raises(clinic_ai.ClinicAIError, match='gemini_daily_budget'):
        clinic_ai.gemini_post('m', {'generationConfig': {}}, timeout=1)
