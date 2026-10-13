"""Płatne zadania z wyszukiwarką: Claude zamiast Gemini (właściciel 13.10.2026), z możliwością powrotu do Gemini."""
import pytest

from news import clinic_ai, clinic_council as council
from news.clinic_ai import ClinicAIError


def keys(monkeypatch, anthropic=True, gemini=True, backend=''):
    for name, on in (('ANTHROPIC_API_KEY', anthropic), ('GEMINI_API_KEY', gemini)):
        if on:
            monkeypatch.setenv(name, 'test')
        else:
            monkeypatch.delenv(name, raising=False)
    if backend:
        monkeypatch.setenv('CLINIC_PAID_BACKEND', backend)
    else:
        monkeypatch.delenv('CLINIC_PAID_BACKEND', raising=False)
    monkeypatch.delenv('CLINIC_GEMINI_FALLBACK', raising=False)
    monkeypatch.delenv('CLINIC_ESCALATE', raising=False)


def test_backend_defaults_to_claude_when_key_exists(monkeypatch):
    keys(monkeypatch)
    assert clinic_ai.paid_backend() == 'claude' and clinic_ai.paid_ready()
    keys(monkeypatch, backend='gemini')
    assert clinic_ai.paid_backend() == 'gemini' and clinic_ai.paid_ready()
    keys(monkeypatch, anthropic=False)
    assert clinic_ai.paid_backend() == 'gemini'
    keys(monkeypatch, anthropic=False, gemini=False)
    assert not clinic_ai.paid_ready()


def test_call_paid_uses_claude_and_falls_back_only_on_missing_credit(monkeypatch):
    keys(monkeypatch)
    calls = []
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: calls.append('claude') or 'C')
    monkeypatch.setattr(clinic_ai, '_call_gemini', lambda *a, **k: calls.append('gemini') or 'G')
    assert clinic_ai._call_paid('s', 'u', {}, web_search=True) == 'C'
    assert calls == ['claude']

    def no_credit(*a, **k):
        raise ClinicAIError('api_400: Your credit balance is too low')
    monkeypatch.setattr(clinic_ai, '_call_claude', no_credit)
    assert clinic_ai._call_paid('s', 'u', {}, web_search=True) == 'G'

    def other(*a, **k):
        raise ClinicAIError('rate_limited')
    monkeypatch.setattr(clinic_ai, '_call_claude', other)
    with pytest.raises(ClinicAIError):
        clinic_ai._call_paid('s', 'u', {}, web_search=True)


def test_call_paid_gemini_when_forced(monkeypatch):
    keys(monkeypatch, backend='gemini')
    monkeypatch.setattr(clinic_ai, '_call_claude', lambda *a, **k: pytest.fail('Claude nie powinien być wołany'))
    monkeypatch.setattr(clinic_ai, '_call_gemini', lambda *a, **k: 'G')
    assert clinic_ai._call_paid('s', 'u', {}, web_search=True) == 'G'


def test_fact_check_prefers_claude_and_skips_gemini(monkeypatch):
    keys(monkeypatch)
    expected = ([{'claim': 'x', 'assessment': 'confirmed', 'explanation': '', 'sources': []}], {'model': 'claude'})
    monkeypatch.setattr(council, 'claude_check', lambda claims: expected)
    monkeypatch.setattr(clinic_ai, '_call_gemini', lambda *a, **k: pytest.fail('Gemini nie powinien być wołany'))
    assert council.check_claims(['x']) == expected


def test_fact_check_does_not_use_gemini_after_claude_failure_by_default(monkeypatch):
    keys(monkeypatch)
    monkeypatch.setattr(council, 'claude_check', lambda claims: None)
    monkeypatch.setattr(council, 'free_check', lambda claims: None)
    monkeypatch.setattr(clinic_ai, '_call_gemini', lambda *a, **k: pytest.fail('Gemini bez zgody'))
    rows, usage = council.check_claims(['x'])
    assert rows[0]['assessment'] == 'unverified' and usage == {}


def test_fact_check_gemini_fallback_only_with_consent(monkeypatch):
    keys(monkeypatch)
    monkeypatch.setenv('CLINIC_GEMINI_FALLBACK', 'true')
    monkeypatch.setattr(council, 'claude_check', lambda claims: None)
    called = []

    def gemini(*a, **k):
        called.append(1)
        raise ClinicAIError('gemini_402')
    monkeypatch.setattr(clinic_ai, '_call_gemini', gemini)
    monkeypatch.setattr(council, 'free_check', lambda claims: None)
    council.check_claims(['x'])
    assert called


def test_escalation_defaults_to_claude(monkeypatch):
    keys(monkeypatch)
    expected = ([], {'model': 'claude'})
    monkeypatch.setattr(council, 'claude_check', lambda claims: expected)
    monkeypatch.setattr(clinic_ai, '_call_gemini', lambda *a, **k: pytest.fail('Gemini nie powinien być wołany'))
    assert council.escalate_claims(['x']) == expected
    monkeypatch.setenv('CLINIC_ESCALATE', 'gemini')  # stara wartość z .env nie przywraca Gemini przy backendzie claude
    assert council.escalate_claims(['x']) == expected


def test_claude_can_be_council_member(monkeypatch):
    from news import council_registry as registry
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    member = ('claude', 'claude-haiku-5-5')
    assert registry.configured(member)
    assert registry.metadata(member)['company'] == 'Anthropic'
