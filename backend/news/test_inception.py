"""Inception (Mercury 2.5) - kształt zapytania, strażnik darmowej puli (stop przy 90%), zapas bez klucza, pierwszeństwo
w zadaniach pobocznych, brak udziału w diagnozach bez Rekrutera. Bez sieci: requests.post/get podmienione."""
import json

import pytest
import requests
from django.core.cache import cache

from news import agents_common, clinic_ai, clinic_council, council_recruiter, inception, mechanik, odbior_spinu, raport_petli
from news import council_registry as registry
from news.clinic_models import CouncilSeat

pytestmark = pytest.mark.django_db
ENV = ('INCEPTION_API_KEY', 'INCEPTION_MODEL', 'INCEPTION_FREE_TOKENS', 'INCEPTION_STOP_SHARE', 'INCEPTION_DAILY_TOKENS',
       'INCEPTION_MONTHLY_TOKENS', 'INCEPTION_ALLOW_PAID', 'INCEPTION_NO_TRAINING', 'INCEPTION_API_URL', 'INCEPTION_RETRIES',
       'INCEPTION_REASONING_EFFORT', 'CLINIC_COUNCIL', 'GROQ_API_KEY', 'NIM_API_KEY', 'CLINIC_TRIAGE_MODEL', 'CLINIC_TRIAGE_ENABLED')


class Response:
    def __init__(self, status=200, data=None, text='', headers=None):
        self.status_code, self._data, self.text, self.headers = status, data, text, headers or {}

    def json(self):
        if self._data is None:
            raise ValueError('no json')
        return self._data


def ok(content, tokens=1234, model='mercury-2.5'):
    return Response(200, {'model': model, 'choices': [{'message': {'content': json.dumps(content)}}],
                          'usage': {'prompt_tokens': 1000, 'completion_tokens': 234, 'total_tokens': tokens}})


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for name in ENV:
        monkeypatch.delenv(name, raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError('Prawdziwa sieć jest zabroniona w testach')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(inception, '_sleep', lambda seconds: None)
    yield
    cache.clear()


@pytest.fixture
def calls(monkeypatch):
    """Kolejka odpowiedzi dla requests.post w module inception; zapisuje każde zapytanie."""
    sent, queue = [], []

    def post(url, json=None, headers=None, timeout=None, allow_redirects=True):
        sent.append({'url': url, 'json': json, 'headers': headers})
        return queue.pop(0)
    monkeypatch.setattr(inception.requests, 'post', post)
    return sent, queue


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv('INCEPTION_API_KEY', 'inc-test')


# --- 1. dostawca -----------------------------------------------------------------------------------------------------

def test_request_shape_and_token_count(keyed, calls):
    sent, queue = calls
    queue.append(ok({'score': 80, 'reason': 'Konkretne twierdzenie.'}))
    data, model = inception.chat('System.', 'Wpis posła.', clinic_ai.SCREEN_SCHEMA, max_tokens=800)
    assert data == {'score': 80, 'reason': 'Konkretne twierdzenie.'} and model == 'mercury-2.5'
    request = sent[0]
    assert request['url'] == 'https://api.inceptionlabs.ai/v1/chat/completions'
    assert request['headers']['Authorization'] == 'Bearer inc-test'
    body = request['json']
    assert body['model'] == 'mercury-2.5' and body['max_completion_tokens'] == 800 and 'max_tokens' not in body
    assert body['reasoning_effort'] == 'low' and body['temperature'] == 0
    assert body['response_format'] == {'type': 'json_object'}
    assert 'Schemat:' in body['messages'][0]['content']
    assert [m['role'] for m in body['messages']] == ['system', 'user'] and body['messages'][1]['content'] == 'Wpis posła.'
    info = inception.usage()
    assert info['today'] == info['month'] == info['total'] == 1234 and info['calls_today'] == 1


def test_model_setting_and_custom_effort(keyed, calls, monkeypatch):
    sent, queue = calls
    monkeypatch.setenv('INCEPTION_MODEL', 'mercury-3')
    monkeypatch.setenv('INCEPTION_REASONING_EFFORT', 'instant')
    queue.append(ok({'ok': True}, model='mercury-3'))
    inception.chat('s', 'u', None)
    assert sent[0]['json']['model'] == 'mercury-3' and sent[0]['json']['reasoning_effort'] == 'instant'
    assert 'response_format' not in sent[0]['json']


def test_retries_429_then_succeeds(keyed, calls):
    sent, queue = calls
    queue.extend([Response(429, text='rate_limit_reached', headers={'Retry-After': '1'}), Response(503), ok({'ok': True})])
    assert inception.chat('s', 'u', None)[0] == {'ok': True}
    assert len(sent) == 3


def test_retries_exhausted_raise_error_without_halting(keyed, calls):
    sent, queue = calls
    queue.extend([Response(429, text='rate_limit_reached')] * 3)
    with pytest.raises(inception.InceptionError) as error:
        inception.chat('s', 'u', None)
    assert error.value.code == 'inception: http_429' and len(sent) == 3
    assert inception.usage()['halted'] is None and inception.ready()


def test_402_halts_until_key_changes(keyed, calls, monkeypatch):
    sent, queue = calls
    queue.append(Response(402, text='{"error": {"code": "account_error"}}'))
    with pytest.raises(inception.InceptionError):
        inception.chat('s', 'u', None)
    assert inception.refusal() == 'inception_halted'
    with pytest.raises(inception.InceptionError) as error:
        inception.chat('s', 'u', None)
    assert error.value.code == 'inception_halted' and len(sent) == 1  # drugie zapytanie nie wyszło
    monkeypatch.setenv('INCEPTION_API_KEY', 'nowy-klucz')
    assert inception.refusal() == ''


# --- 2. darmowa pula ------------------------------------------------------------------------------------------------

def test_free_token_guard_stops_at_90_percent(keyed, calls, monkeypatch):
    sent, queue = calls
    monkeypatch.setenv('INCEPTION_FREE_TOKENS', '100000')
    inception.record(89_000)
    assert inception.ready(500)
    assert inception.refusal(2_000) == 'inception_free_budget'  # 89k + 2k > 90k (90% ze 100k)
    inception.record(1_000)
    with pytest.raises(inception.InceptionError) as error:
        inception.chat('s', 'u', None, max_tokens=100)
    assert error.value.code == 'inception_free_budget' and sent == []
    assert inception.usage()['free_left'] == 0
    monkeypatch.setenv('INCEPTION_ALLOW_PAID', 'true')  # tylko świadoma decyzja właściciela
    assert inception.refusal(100) == ''


def test_daily_and_monthly_ceilings(keyed, monkeypatch):
    monkeypatch.setenv('INCEPTION_DAILY_TOKENS', '10000')
    monkeypatch.setenv('INCEPTION_MONTHLY_TOKENS', '20000')
    inception.record(9_500)
    assert inception.refusal(1_000) == 'inception_daily_limit'
    monkeypatch.setenv('INCEPTION_DAILY_TOKENS', '100000')
    inception.record(10_000)
    assert inception.refusal(1_000) == 'inception_monthly_limit'


def test_missing_usage_counts_the_estimate(keyed, calls):
    sent, queue = calls
    queue.append(Response(200, {'choices': [{'message': {'content': '{"ok": true}'}}]}))
    inception.chat('abc', 'def', None, max_tokens=100)
    assert inception.usage()['total'] == inception.estimate('abc', 'def', 100)


# --- 3. zapas bez klucza i pierwszeństwo w zadaniach pobocznych -------------------------------------------------------

def test_no_key_falls_back_to_current_chain(calls, monkeypatch):
    sent, _ = calls
    monkeypatch.setattr(clinic_ai, '_screen_groq', lambda text: {'score': 55, 'reason': 'r', 'provider': 'groq', 'model': 'g'})
    result = clinic_ai.screen('Wpis')
    assert result['provider'] == 'groq' and sent == []
    assert inception.side_json('s', 'u', {}) is None
    assert agents_common.inception_member() is None


def test_screening_prefers_inception(keyed, calls, monkeypatch):
    sent, queue = calls
    queue.append(ok({'score': 77, 'reason': 'Liczby bez źródła.'}))
    monkeypatch.setattr(clinic_ai, '_screen_groq', lambda text: pytest.fail('Konsylium nie może przesiewać, gdy jest Inception'))
    result = clinic_ai.screen('Rząd podniósł podatki o 300%!')
    assert result == {'score': 77, 'reason': 'Liczby bez źródła.', 'provider': 'inception', 'model': 'mercury-2.5'}


def test_screening_falls_back_when_free_pool_used(keyed, calls, monkeypatch):
    sent, _ = calls
    monkeypatch.setenv('INCEPTION_FREE_TOKENS', '1000')
    inception.record(900)
    monkeypatch.setattr(clinic_ai, '_screen_groq', lambda text: {'score': 40, 'reason': 'r', 'provider': 'groq', 'model': 'g'})
    assert clinic_ai.screen('Wpis')['provider'] == 'groq' and sent == []


def test_screening_falls_back_on_provider_error(keyed, calls, monkeypatch):
    sent, queue = calls
    queue.append(Response(500))
    queue.extend([Response(500)] * 2)
    monkeypatch.setattr(clinic_ai, '_screen_groq', lambda text: {'score': 40, 'reason': 'r', 'provider': 'groq', 'model': 'g'})
    assert clinic_ai.screen('Wpis')['provider'] == 'groq'


def test_agent_loops_prefer_inception(keyed, calls, monkeypatch):
    sent, queue = calls
    queue.append(ok({'title': 'Pomysł'}))
    monkeypatch.setattr(clinic_council, 'ask', lambda *a, **k: pytest.fail('limity Konsylium zostają dla diagnoz'))
    answer, member = agents_common.ask_any('Zaproponuj.', {'x': 1}, {'type': 'object'}, force=True)
    assert answer == {'title': 'Pomysł'} and member == ('inception', 'mercury-2.5')
    assert agents_common.POLICY.split('\n')[0] in sent[0]['json']['messages'][0]['content']
    assert agents_common.members(1, force=True) == [('inception', 'mercury-2.5')]


def test_agent_loops_fall_back_to_council_when_inception_fails(keyed, calls, monkeypatch):
    sent, queue = calls
    queue.extend([Response(500)] * 3)
    monkeypatch.setenv('GROQ_API_KEY', 'g')
    monkeypatch.setenv('CLINIC_COUNCIL', 'groq:openai/gpt-oss-20b')
    monkeypatch.setattr(clinic_council, 'ask', lambda member, *a, **k: {'title': 'z Konsylium'})
    answer, member = agents_common.ask_any('Zaproponuj.', {}, {'type': 'object'}, force=True)
    assert answer == {'title': 'z Konsylium'} and member == ('groq', 'openai/gpt-oss-20b')


def test_reception_uses_inception_only_without_training(keyed, calls, monkeypatch):
    sent, queue = calls
    monkeypatch.setattr(odbior_spinu, '_members', lambda: [])
    monkeypatch.setattr('news.dyrygent.allowed', lambda *a: True)
    with pytest.raises(agents_common.WindowClosed):  # odpowiedzi osób prywatnych: bez potwierdzenia opt-out ani słowa do Inception
        odbior_spinu.ask({'wpis': 'x', 'odpowiedzi': []})
    assert sent == [] and not odbior_spinu.model_ready()
    monkeypatch.setenv('INCEPTION_NO_TRAINING', 'true')
    queue.append(ok({'odpowiedzi': [{'i': 1, 'stance': 'zgoda', 'tone': 'pozytywny', 'asks_source': False}]}))
    answer, model = odbior_spinu.ask({'wpis': 'x', 'odpowiedzi': [{'i': 1, 'text': 'Racja'}]})
    assert model == 'mercury-2.5' and answer['odpowiedzi'][0]['stance'] == 'zgoda'
    assert odbior_spinu.model_ready()


# --- 4. Konsylium: tylko przez Rekrutera ----------------------------------------------------------------------------

def test_never_in_council_unless_recruited(keyed):
    members = clinic_council._members('CLINIC_COUNCIL', clinic_council.DEFAULT_COUNCIL)
    assert all(m[0] != 'inception' for m in members)
    for name, default in (('CLINIC_COUNCIL_CHAIR', clinic_council.CHAIR), ('CLINIC_COUNCIL_LINGUIST', clinic_council.LINGUIST),
                          ('CLINIC_COUNCIL_REVIEWER', clinic_council.REVIEWER)):
        assert all(m[0] != 'inception' for m in clinic_council._members(name, default))
    CouncilSeat.objects.create(provider='inception', model='mercury-2.5', company='Inception Labs', origin='recruiter',
                               roles=['członek'], status='active')
    assert ('inception', 'mercury-2.5') in clinic_council._members('CLINIC_COUNCIL', clinic_council.DEFAULT_COUNCIL)


def test_recruiter_lists_inception_as_candidate(keyed, monkeypatch):
    def fake_get(url, **kwargs):
        if 'inceptionlabs' in url:
            assert kwargs['headers']['Authorization'] == 'Bearer inc-test'
            return {'data': [{'id': 'mercury-2.5'}, {'id': 'mercury-edit-2'}, {'id': 'mercury-voice'}]}
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(council_recruiter, '_get', fake_get)
    found = council_recruiter.discover()
    assert found == [{'provider': 'inception', 'model': 'mercury-2.5', 'context': 0}]
    candidates = council_recruiter.sieve(found)
    assert candidates[0]['model'] == 'mercury-2.5' and candidates[0]['company'] == 'Inception Labs'
    assert candidates[0]['new_company'] and candidates[0]['watched']
    assert registry.metadata(('inception', 'mercury-2.5'))['company'] == 'Inception Labs'


def test_council_ask_routes_through_free_pool_guard(keyed, calls, monkeypatch):
    sent, queue = calls
    monkeypatch.setenv('INCEPTION_FREE_TOKENS', '1000')
    inception.record(900)
    with pytest.raises(clinic_ai.ClinicAIError) as error:  # egzamin Rekrutera też nie przekroczy puli
        clinic_council._ask(('inception', 'mercury-2.5'), 's', 'u', {'type': 'object'})
    assert error.value.code == 'inception_free_budget' and sent == []


# --- 5. Mechanik i Raport pętli ---------------------------------------------------------------------------------------

def test_mechanik_health_check_and_successor(keyed, monkeypatch):
    def get(url, **kwargs):
        assert url == 'https://api.inceptionlabs.ai/v1/models'
        return Response(200, {'data': [{'id': 'mercury-2.6'}, {'id': 'mercury-edit-2'}]})
    monkeypatch.setattr(inception.requests, 'get', get)
    result = mechanik.step()
    assert result['inception']['replaced'] and result['inception']['model'] == 'mercury-2.6'
    assert inception.model() == 'mercury-2.6'
    monkeypatch.setattr(inception.requests, 'get', lambda url, **k: Response(200, {'data': [{'id': 'mercury-2.6'}]}))
    assert inception.health()['ok']


def test_mechanik_skips_inception_without_key():
    assert 'inception' not in mechanik.step()


def test_loop_report_cost_line(keyed, monkeypatch):
    monkeypatch.setenv('INCEPTION_FREE_TOKENS', '100000000')
    inception.record(1_500_000)
    line = next(l for l in raport_petli._koszty(None) if l.startswith('Inception'))
    assert 'dziś 1,50 mln tokenów' in line and 'zostało darmowych 88,50 mln' in line and 'działa' in line


def test_loop_report_without_key():
    assert any('brak klucza INCEPTION_API_KEY' in l for l in raport_petli._koszty(None))
