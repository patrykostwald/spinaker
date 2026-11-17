import pytest

from news import mechanik
from news.clinic_models import CouncilSeat

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'x')


def test_renamed_model_gets_successor(monkeypatch):
    CouncilSeat.objects.create(provider='groq', model='groq/compound', last_error='groq: http_404')
    monkeypatch.setattr(mechanik, 'provider_models', lambda s: {'compound-beta', 'llama-3.3-70b-versatile'})
    monkeypatch.setattr(mechanik, 'probe', lambda s, m: (m == 'compound-beta', ''))
    result = mechanik.step()
    assert result['results'] == [('groq/compound', 'zamiennik compound-beta')]
    assert mechanik.alias('groq', 'groq/compound') == 'compound-beta'
    seat = CouncilSeat.objects.get()
    assert seat.status == 'active' and seat.last_error == ''


def test_listed_model_restored_and_402_left_alone(monkeypatch):
    CouncilSeat.objects.create(provider='groq', model='openai/gpt-oss-120b', status='suspended', last_error='groq: http_404')
    CouncilSeat.objects.create(provider='groq', model='qwen/qwen3-32b', last_error='groq: http_402')
    monkeypatch.setattr(mechanik, 'provider_models', lambda s: {'openai/gpt-oss-120b'})
    monkeypatch.setattr(mechanik, 'probe', lambda s, m: (True, ''))
    assert mechanik.step()['results'] == [('openai/gpt-oss-120b', 'przywrócony')]
    assert CouncilSeat.objects.get(model='openai/gpt-oss-120b').status == 'active'
    assert CouncilSeat.objects.get(model='qwen/qwen3-32b').last_error == 'groq: http_402'


def test_successor_family_match():
    listed = {'llama-4-maverick-17b-128e-instruct', 'meta-llama/llama-3.3-70b-instruct', 'gemma2-9b-it'}
    assert mechanik.successor('groq', 'llama-3.3-70b-versatile', {'llama-3.3-70b-specdec', 'gemma2-9b-it'}) == 'llama-3.3-70b-specdec'
    assert mechanik.successor('groq', 'mixtral-8x7b-32768', listed) is None
