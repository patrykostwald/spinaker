"""PCSS w Konsylium (21.10): bliźniak Qwen za Groq i kandydat dla Rekrutera. Wyłącznie atrapy sieci."""
from unittest.mock import Mock

import pytest
import requests
from django.core.cache import cache

from news import clinic_council as council, council_quorum as quorum, council_recruiter as recruiter, council_registry as registry
from news.clinic_ai import ClinicAIError

GROQ_QWEN = ('groq', 'qwen/qwen3.8-27b')
OPINION = {'verdict': 'partial', 'intensity': 50, 'techniques': [], 'claims': []}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for key in [*registry.KEYS.values(), 'COUNCIL_TWINS', 'COUNCIL_PCSS_CANDIDATES', 'CLINIC_COUNCIL']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('Prawdziwa sieć jest zabroniona w testach')))
    yield
    cache.clear()


def keys(monkeypatch, *services):
    for service in services:
        monkeypatch.setenv(registry.KEYS[service], 'test')


def test_twin_off_by_default(monkeypatch):
    keys(monkeypatch, 'groq', 'pcss')
    assert registry.twin(GROQ_QWEN) is None
    monkeypatch.setenv('COUNCIL_TWINS', 'true')
    assert registry.twin(GROQ_QWEN) == ('pcss', 'Qwen3.8-27B')
    assert registry.twin(('groq', 'openai/gpt-oss-20b')) is None


def test_twin_answers_for_groq_and_keeps_seat(monkeypatch):
    keys(monkeypatch, 'groq', 'pcss')
    monkeypatch.setenv('COUNCIL_TWINS', 'true')
    asked = []
    def fake(member, *a, **kw):
        asked.append(member)
        if member[0] == 'groq':
            raise ClinicAIError('groq_daily_limit')
        return OPINION
    monkeypatch.setattr(council, 'ask', fake)
    row = council._opinion(GROQ_QWEN, 'tekst', '')
    assert asked == [GROQ_QWEN, ('pcss', 'Qwen3.8-27B')]
    assert row['status'] == 'odpowiedział' and row['model'] == 'qwen/qwen3.8-27b'  # to samo miejsce w kworum
    assert row['provider'] == 'pcss' and row['served_by'] == 'pcss:Qwen3.8-27B' and row['twin_of'] == 'groq:qwen/qwen3.8-27b'
    assert quorum.check([row], core=[GROQ_QWEN], size=1)['core'] == 1


def test_no_twin_when_disabled_or_content_reserve(monkeypatch):
    keys(monkeypatch, 'groq', 'pcss')
    monkeypatch.setattr(council, 'ask', Mock(side_effect=ClinicAIError('groq_daily_limit')))
    assert council._opinion(GROQ_QWEN, 'tekst', '')['status'] == 'brak odpowiedzi'
    assert council.ask.call_count == 1
    monkeypatch.setenv('COUNCIL_TWINS', 'true')
    monkeypatch.setattr(council, 'ask', Mock(side_effect=ClinicAIError('groq_content_reserve')))
    assert council._opinion(GROQ_QWEN, 'tekst', '')['status'] == 'brak odpowiedzi'
    assert council.ask.call_count == 1  # odmowa z rezerwy na treść to polityka, nie awaria - bez bliźniaka


def test_groq_at_limit_stays_available_through_twin(monkeypatch):
    keys(monkeypatch, 'groq', 'pcss')
    cache.set(registry.limit_key(GROQ_QWEN), registry.daily_limit(GROQ_QWEN))
    assert not registry.available(GROQ_QWEN)
    monkeypatch.setenv('COUNCIL_TWINS', 'true')
    assert registry.available(GROQ_QWEN)


def test_pcss_request_shape(monkeypatch):
    keys(monkeypatch, 'pcss')
    post = Mock(return_value=Mock(status_code=200, json=lambda: {'choices': [{'message': {'content': '{"verdict": "spin"}'}}]}))
    monkeypatch.setattr(council.requests, 'post', post)
    assert council._ask(('pcss', 'gpt-oss_120b'), 'system', 'user', {}, 4000) == {'verdict': 'spin'}
    assert post.call_args.args[0] == 'https://llm.hpc.psnc.pl/v1/chat/completions'
    body = post.call_args.kwargs['json']
    assert body['response_format'] == {'type': 'json_object'} and body['reasoning_effort'] == 'low'
    council._ask(('pcss', 'Qwen3.8-27B'), 'system', 'user', {}, 4000)
    assert post.call_args.kwargs['json']['chat_template_kwargs'] == {'enable_thinking': False}
    assert registry.metadata(('pcss', 'gpt-oss_120b'))['company'] == 'OpenAI'


def test_recruiter_finds_only_listed_pcss_models(monkeypatch):
    keys(monkeypatch, 'pcss')
    catalog = {'data': [{'id': 'gpt-oss_120b'}, {'id': 'Mistral-Small-3.2:24b'}, {'id': 'whisper-large-v3-turbo:0.8b', 'mode': 'audio_transcription'}]}
    monkeypatch.setattr(recruiter, '_get', lambda url, **kw: catalog if 'psnc' in url else {'data': []})
    monkeypatch.setattr('news.zwiadowca_rozwiazan.recruiter_candidates', lambda: [])
    found = [f for f in recruiter.discover() if f['provider'] == 'pcss']
    assert [f['model'] for f in found] == ['gpt-oss_120b']
