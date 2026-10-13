"""Pilotaż 13.10 (0 par przy 12 wywołaniach): tolerancyjny JSON, ponowna próba u innego dostawcy, powód dla każdego pytania
bez pary, równy podział budżetu między osoby i obozy, klucz cache bez spacji. Bez sieci i bez modeli."""
import warnings

import pytest
from django.core.cache import cache
from django.core.cache.backends.base import CacheKeyWarning

from news import pilotaz, position_pairs as pp
from news.json_tolerant import loads
from news.test_position_pairs import NEW, OLD, person

pytestmark = pytest.mark.django_db

CHANGE = {'relation': 'zmiana stanowiska', 'confidence': 90, 'explanation': 'Wcześniej zapowiedź bez podwyżki, teraz poparcie.',
          'quote_then': 'Nie podniesiemy podatku od nieruchomości', 'quote_now': 'Podatek od nieruchomości musi wzrosnąć'}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    cache.clear()
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    yield
    cache.clear()


# --- tolerancyjny JSON ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '{"relation": "to samo stanowisko", "confidence": 40}',
    '```json\n{"relation": "to samo stanowisko", "confidence": 40}\n```',
    'Oto ocena:\n{"relation": "to samo stanowisko", "confidence": 40}\nDziękuję.',
    '{"relation": "to samo stanowisko", "confidence": 40,}',
    '<think>rozważam</think>{"relation": "to samo stanowisko", "confidence": 40, "x": [1, 2,],}',
])
def test_tolerant_json_accepts_common_shapes(text):
    assert loads(text)['confidence'] == 40


@pytest.mark.parametrize('text', ['', 'brak oceny', '{"relation": "to samo stanowisko", "confid', '[1, 2]'])
def test_tolerant_json_rejects_garbage(text):
    with pytest.raises(ValueError):
        loads(text)


def test_inception_parser_uses_tolerant_fallback():
    from news import inception
    assert inception._json('```json\n{"a": 1, "b": [1,],}\n```') == {'a': 1, 'b': [1]}
    with pytest.raises(inception.InceptionError):
        inception._json('{"a": ')


# --- powody dla każdego pytania ---------------------------------------------------------------------------------------------

class Recorder:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, payload, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer, 'test:model'


def test_markdown_answer_creates_pair():
    figure, _, _ = person()
    import json
    ask = Recorder('```json\n' + json.dumps(CHANGE, ensure_ascii=False) + '\n```')
    result = pp.from_topic(figure, 'podatek od nieruchomości', ask=ask)
    assert result['created'] == 1 and result['reasons'] == [] and result['calls'] == 1


def test_invalid_json_retried_elsewhere_then_reported():
    figure, _, _ = person()
    ask = Recorder('{"relation": "zmiana stanowiska", "confid', 'Nie potrafię ocenić.')
    result = pp.from_topic(figure, 'podatek od nieruchomości', ask=ask, verbose=True)
    assert result['created'] == 0 and result['calls'] == 2
    assert ask.calls[1] == {'skip_inception': True}  # druga próba u innego dostawcy, krótsze pytanie
    reason = result['reasons'][0]
    assert reason['reason'] == 'invalid_json' and reason['a'].startswith('post:') and reason['raw'] == 'Nie potrafię ocenić.'


def test_retry_success_after_invalid_first_answer():
    figure, _, _ = person()
    ask = Recorder({'relation': 'zmiana stanowiska'}, CHANGE)  # pierwsza bez pewności = niepełna
    assert pp.from_topic(figure, 'podatek od nieruchomości', ask=ask)['created'] == 1


def test_no_pair_and_validator_reasons_recorded(settings):
    figure, _, _ = person()
    result = pp.from_topic(figure, 'podatek od nieruchomości', ask=Recorder({'relation': 'to samo stanowisko', 'confidence': 80}))
    assert result['reasons'][0]['reason'] == 'brak_pary' and 'to samo stanowisko' in result['reasons'][0]['detail']
    bad = {**CHANGE, 'quote_then': 'Tego zdania nie było we wpisie wcale'}
    other, _, _ = person('Bartek B', 2, 'bartek_b', '602')
    result = pp.from_topic(other, 'podatek od nieruchomości', ask=Recorder(bad))
    reason = result['reasons'][0]
    assert reason['reason'] == 'odrzucone_walidatorem' and reason['code'] == 'invalid' and 'cytat' in reason['detail']


def test_model_unavailable_and_no_material_are_reasons():
    from news.agents_common import WindowClosed
    figure, _, _ = person()
    result = pp.from_topic(figure, 'podatek od nieruchomości', ask=Recorder(WindowClosed('okno zamknięte')))
    assert result['reasons'][0]['reason'] == 'limit' and 'model niedostępny' in result['reasons'][0]['detail']
    result = pp.from_topic(figure, 'temat, którego nie ma', ask=Recorder())
    assert result['reasons'] == [{'osoba': figure.pk, 'temat': 'temat, którego nie ma', 'reason': 'brak_materialu',
                                  'detail': result['reasons'][0]['detail']}] and result['calls'] == 0


def test_verbose_raw_redacts_contacts():
    assert pp._redact('napisz: jan@example.com albo +48 600 100 200, ' + 'x' * 300) .startswith('napisz: [e-mail] albo [telefon]')
    assert len(pp._redact('y' * 500)) == 200


# --- równy podział budżetu ---------------------------------------------------------------------------------------------------

def test_budget_split_across_people_and_camps():
    from news.test_position_pairs import x_account_in
    from news.test_przeszlosc_osoba import mp, x_post
    for n, camp in enumerate(['government', 'government', 'opposition', 'opposition']):
        figure = mp(f'Osoba {n}', 10 + n)
        account = x_account_in(figure, f'osoba_{n}', str(700 + n), camp)
        x_post(account, f'{700 + n}1', OLD, days_ago=200)
        x_post(account, f'{700 + n}2', NEW, days_ago=2)
        x_post(account, f'{700 + n}3', 'Podatek od nieruchomości to temat gmin, rozmawiamy z samorządami od lat.', days_ago=100)
    ask = Recorder(*[{'relation': 'nie na temat', 'confidence': 70}] * 40)
    log = pilotaz.generate_from_topics(['podatek od nieruchomości'], ask=ask, max_calls=6, per_combo=2, seed='test')
    assert log['calls'] == 6 and set(log['camps']) == {'government', 'opposition'}
    assert abs(log['camps']['government'] - log['camps']['opposition']) <= 2  # pierwszy przebieg: po 2 na osobę, na zmianę
    first = [c for c in log['combos'] if c['przebieg'] == 1]
    assert all(c['calls'] <= 2 for c in first) and len({c['osoba'] for c in first}) == 3
    assert log['reasons_summary']['brak_pary'] == 6 and log['reasons_summary']['limit'] == 1


# --- klucz cache bez spacji ----------------------------------------------------------------------------------------------------

def test_cost_counter_key_has_no_spaces():
    from news import petle_koszty
    key = petle_koszty._key('llm', '2026-10-13', 'poza zadaniem')
    assert ' ' not in key and key == 'petle:llm:2026-10-13:poza_zadaniem'
    with warnings.catch_warnings():
        warnings.simplefilter('error', CacheKeyWarning)
        petle_koszty.count_call()  # „poza zadaniem” bez ostrzeżenia
    assert petle_koszty.count_call() == 2
