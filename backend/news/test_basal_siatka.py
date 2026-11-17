from types import SimpleNamespace

import pytest

from news import basal_siatka, clinic, clinic_ai
from news.clinic_models import SpinDiagnosis
from news.test_clinic import account, post


def answer(p):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
        'model': 'basal-2.0-4.5B', 'answers': {'decyzja': {'choice': 'rada' if p >= .5 else 'pusc', 'confidence': max(p, 1 - p),
                                                            'probabilities': {'rada': p, 'pusc': 1 - p}}}})


def test_off_without_url(monkeypatch):
    monkeypatch.delenv('BASAL_URL', raising=False)
    monkeypatch.setattr(basal_siatka.requests, 'post', lambda *a, **k: pytest.fail('bez BASAL_URL nie ma zapytań'))
    assert basal_siatka.opinion('Wygnajcie ich wszystkich.') is None


def test_opinion_and_threshold(monkeypatch):
    monkeypatch.setenv('BASAL_URL', 'http://127.0.0.1:8000/')
    sent = {}
    monkeypatch.setattr(basal_siatka.requests, 'post', lambda url, **k: sent.update(url=url, **k) or answer(.95))
    result = basal_siatka.opinion('Wygnajcie ich wszystkich.')
    assert sent['url'] == 'http://127.0.0.1:8000/v1/systemone' and sent['json']['state'] == 'Wygnajcie ich wszystkich.'
    assert result['p_rada'] == .95 and result['would_escalate'] and result['mode'] == 'shadow'
    monkeypatch.setenv('BASAL_ESCALATE_THRESHOLD', '0.97')
    assert not basal_siatka.opinion('Wygnajcie ich wszystkich.')['would_escalate']


def test_failure_never_raises(monkeypatch):
    monkeypatch.setenv('BASAL_URL', 'http://127.0.0.1:8000')
    def boom(*a, **k):
        raise ConnectionError('down')
    monkeypatch.setattr(basal_siatka.requests, 'post', boom)
    assert basal_siatka.opinion('tekst') is None


@pytest.mark.django_db
def test_shadow_mode_keeps_guard_status(monkeypatch):
    monkeypatch.setenv('BASAL_URL', 'http://127.0.0.1:8000')
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 20, 'reason': 'hasło', 'provider': 'groq', 'model': 'm'})
    monkeypatch.setattr(basal_siatka.requests, 'post', lambda *a, **k: answer(.96))
    row = clinic.screen_post(post(account(), text='Wygnajcie najeźdźców.'))
    row.refresh_from_db()
    assert row.status == 'not_applicable' and row.screen_score == 20
    assert row.triage['reason'] == 'hasło' and row.triage['basal']['would_escalate']
    summary = basal_siatka.shadow_summary()
    assert summary['rejected'] == 1 and summary['would_escalate'] == 1 and summary['examples'][0]['guard'] == 20


@pytest.mark.django_db
def test_guard_works_when_basal_down(monkeypatch):
    monkeypatch.setenv('BASAL_URL', 'http://127.0.0.1:8000')
    monkeypatch.setattr(clinic_ai, 'screen', lambda text: {'score': 90, 'reason': 'r', 'provider': 'groq', 'model': 'm'})
    monkeypatch.setattr(basal_siatka.requests, 'post', lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    row = clinic.screen_post(post(account(), text='Rząd podniósł podatki o 50 procent.'))
    assert row.status == 'queued' and 'basal' not in row.triage and SpinDiagnosis.objects.count() == 1
