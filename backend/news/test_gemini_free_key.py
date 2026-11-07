"""Zapasowy darmowy klucz Gemini (GEMINI_API_KEY_FREE): płatny pierwszy, darmowy gdy brak środków lub budżetu."""
import pytest

from news import clinic_ai
from news.clinic_ai import ClinicAIError


class Calls(list):
    plan: dict
    urls: list


class Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {'candidates': [], 'usageMetadata': {}}
        self.text = ''

    def json(self):
        return self._payload


@pytest.fixture
def calls(monkeypatch):
    sent = Calls()
    plan = {}
    sent.plan = plan
    sent.urls = []

    def fake_post(url, json=None, timeout=None, headers=None):
        key = headers['x-goog-api-key']
        sent.append(key)
        sent.urls.append(url)
        return Resp(plan.get(key, 200))
    monkeypatch.setattr(clinic_ai.requests, 'post', fake_post)
    monkeypatch.setattr(clinic_ai, 'record_gemini_spend', lambda task, payload: sent.append('koszt:' + task))
    monkeypatch.setattr(clinic_ai, 'gemini_spent_today', lambda: 0.0)
    monkeypatch.setenv('GEMINI_API_KEY', 'platny')
    monkeypatch.setenv('GEMINI_API_KEY_FREE', 'darmowy')
    monkeypatch.setenv('GEMINI_DAILY_BUDGET_USD', '5')
    return sent


def test_paid_key_first_and_cost_counted(calls):
    response = clinic_ai.gemini_post('m', {}, timeout=5, task='interview')
    assert response.status_code == 200
    assert calls == ['platny', 'koszt:interview']


@pytest.mark.parametrize('status', [402, 403, 429])
def test_free_key_used_when_paid_has_no_funds_and_no_cost_counted(calls, status):
    calls.plan['platny'] = status
    response = clinic_ai.gemini_post('m', {}, timeout=5)
    assert response.status_code == 200
    assert calls == ['platny', 'darmowy']  # bez wpisu kosztu


def test_free_key_used_when_paid_budget_exhausted(calls, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'gemini_spent_today', lambda: 9.0)
    response = clinic_ai.gemini_post('m', {}, timeout=5)
    assert response.status_code == 200 and calls == ['darmowy']


def test_budget_error_without_free_key(calls, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'gemini_spent_today', lambda: 9.0)
    monkeypatch.delenv('GEMINI_API_KEY_FREE')
    with pytest.raises(ClinicAIError) as error:
        clinic_ai.gemini_post('m', {}, timeout=5)
    assert error.value.code == 'gemini_daily_budget'


def test_other_errors_do_not_trigger_fallback(calls):
    calls.plan['platny'] = 500
    assert clinic_ai.gemini_post('m', {}, timeout=5).status_code == 500
    assert calls == ['platny']


def test_explicit_key_has_no_fallback(calls):
    calls.plan['moj'] = 402
    assert clinic_ai.gemini_post('m', {}, timeout=5, key='moj').status_code == 402
    assert calls == ['moj']


def test_both_keys_failing_returns_last_response(calls):
    calls.plan['platny'] = 402
    calls.plan['darmowy'] = 429
    assert clinic_ai.gemini_post('m', {}, timeout=5).status_code == 429
    assert calls == ['platny', 'darmowy']


def test_free_key_uses_its_own_model(calls, monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL_FREE', 'gemini-2.5-flash')
    calls.plan['platny'] = 402
    clinic_ai.gemini_post('gemini-3.8-flash', {}, timeout=5)
    assert calls.urls[0].endswith('/models/gemini-3.8-flash:generateContent')
    assert calls.urls[1].endswith('/models/gemini-2.5-flash:generateContent')
