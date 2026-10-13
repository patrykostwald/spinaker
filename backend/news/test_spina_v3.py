"""Spina v3: ciąg przyczyn przekazu (walidator, bramki, zatwierdzanie, flagi), siła spinu dnia, lista głosowań, powiązania osoby.
Bez sieci i bez modeli: odpowiedzi modeli podstawione."""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from news import causal_chain
from news.clinic_models import CausalChain, CausalChainEvent, ClinicDailyMessage, SpinDiagnosis
from news.models import Ballot
from news.test_clinic import account, post
from news.test_przeszlosc_osoba import mp, voting

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 12)
TEXT_A = 'Ministerstwo Finansów opublikowało projekt 12 października: https://www.gov.pl/web/finanse/projekt-vat'
TEXT_B = 'Podatek wzrośnie o 5 proc. „To koniec ulg dla rodzin” - piszemy jasno.'
TEXT_C = 'Rząd znowu oszukuje obywateli, kłamstwo za kłamstwem.'


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def make_message(texts=(TEXT_A, TEXT_B, TEXT_C), camp='government'):
    acc = account(camp=camp, handle='ministerstwo', user_id='501')
    posts = [post(acc, post_id=str(9100 + i), text=t, hours_ago=2 + i) for i, t in enumerate(texts)]
    message = ClinicDailyMessage.objects.create(day=DAY, camp=camp, status='approved', message='Przekaz dnia.', thesis='Teza')
    message.posts.add(*posts)
    return message, posts


def good_steps(message):
    first = message.posts.get(text=TEXT_A)
    return [
        {'kind': 'fakt', 'text': 'Ministerstwo opublikowało projekt zmian 12 października.', 'source_id': f'w{first.pk}l1',
         'source': {'name': 'Wymyślone Ministerstwo', 'url': 'https://zle.example/x', 'date': '2020-01-01'}},
        {'kind': 'interpretacja', 'text': 'Wpisy przedstawiają projekt jako przesądzony.'},
        {'kind': 'spin', 'text': 'Pojawia się straszenie skutkami dla rodzin.', 'technique': 'straszenie'},
        {'kind': 'wniosek', 'text': 'Odbiorca dostaje obraz decyzji, której jeszcze nie ma.'},
    ]


def staff(name='ordynator', decide=True):
    """Personel; decide=True nadaje uprawnienie news.can_decide_causalchain (recenzja Codex 2)."""
    from django.contrib.auth.models import Permission
    user = get_user_model().objects.create_user(name, password='x', is_staff=True)
    if decide:
        user.user_permissions.add(Permission.objects.get(codename='can_decide_causalchain'))
    return get_user_model().objects.get(pk=user.pk)


def test_chain_decisions_require_permission():
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    client = APIClient()
    client.force_authenticate(staff('bez_prawa', decide=False))
    response = client.post(f'/api/staff/clinic/messages/{message.pk}/causal-chain/review/', {'decision': 'approve'}, format='json')
    assert response.status_code == 403
    with pytest.raises(CommandError):
        call_command('lancuch_przekazu', 'zatwierdz', str(chain.pk), '--kto', 'bez_prawa')
    chain.refresh_from_db()
    assert chain.status == 'pending_review'


def fake_ask(steps, review=('publish', [])):
    def ask(prompt, data, schema, exclude=()):
        if 'steps' in schema.get('properties', {}):
            return {'steps': steps}, ('groq', 'llama-test')
        return {'decision': review[0], 'critical': list(review[1]), 'reason': 'ok'}, ('nim', 'recenzent')
    return ask


# --- walidator ---------------------------------------------------------------------------------------------------------

def test_fact_source_comes_from_materials_not_from_model():
    message, posts = make_message()
    items = causal_chain.materials(message)
    steps, gates = causal_chain.validate_steps(good_steps(message), items)
    fact = steps[0]
    assert fact['kind'] == 'fakt'
    assert fact['source']['url'] == 'https://www.gov.pl/web/finanse/projekt-vat'
    assert fact['source']['date'] == timezone.localtime(posts[0].published_at).date().isoformat()
    assert 'Wymyślone' not in fact['source']['name'] and 'gov.pl' in fact['source']['name']
    assert steps[2]['technique'] == 'Straszenie'
    assert gates['walidator']['status'] == 'pass' and gates['walidator']['steps_out'] == 4


def test_fact_matched_by_post_url_and_unsourced_fact_degraded():
    message, posts = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message)
    raw[0] = {'kind': 'fakt', 'text': 'Ministerstwo opublikowało projekt.', 'source_url': posts[0].url.replace('x.com', 'twitter.com')}
    raw.insert(1, {'kind': 'fakt', 'text': 'Projekt poparł premier.', 'source': {'name': 'TVN', 'url': 'https://tvn.example/a'}})
    steps, gates = causal_chain.validate_steps(raw, items)
    assert steps[0]['source']['url'] == posts[0].url
    assert steps[1] == {'kind': 'interpretacja', 'text': 'Projekt poparł premier.', 'degraded': True}
    assert gates['fact_checker']['status'] == 'fixed' and gates['walidator']['degraded'] == 1


@pytest.mark.parametrize('text,gate', [
    ('Podatek wzrośnie o 23 proc. dla wszystkich.', 'fact_checker'),              # liczba spoza materiałów
    ('Wpisy mówią: „to koniec świata dla nas”.', 'fact_checker'),               # cytat spoza materiałów
    ('Minister jest złodziejem i to widać.', 'prawnik'),                         # zarzut, który nie padł
    ('Autorzy celowo wprowadzają w błąd.', 'prawnik'),                           # intencja
    ('Spin działa świetnie!', 'jezykoznawca'),                                   # wykrzyknik
    ('a' * 161, 'jezykoznawca'),                                                 # za długi
])
def test_rejected_step_rules(text, gate):
    message, _ = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message) + [{'kind': 'interpretacja', 'text': text}]
    steps, gates = causal_chain.validate_steps(raw, items)
    assert len(steps) == 4 and all(s['text'] != text for s in steps)
    assert gates[gate]['status'] == 'fixed' and gates[gate]['issues'][0]['action'] == 'usunięty'


def test_numbers_quotes_and_accusations_present_in_materials_are_allowed():
    message, _ = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message)
    raw[1] = {'kind': 'interpretacja', 'text': 'Wpisy mówią o 5 proc. i „to koniec ulg dla rodzin”.'}
    raw[3] = {'kind': 'wniosek', 'text': 'Zarzut kłamstwa pada bez dowodu — odbiorca go powtarza.'}
    steps, _ = causal_chain.validate_steps(raw, items)
    assert len(steps) == 4
    assert steps[3]['text'] == 'Zarzut kłamstwa pada bez dowodu - odbiorca go powtarza.'  # tylko krótki myślnik


def test_chain_needs_three_steps_and_a_sourced_fact():
    message, _ = make_message()
    items = causal_chain.materials(message)
    with pytest.raises(causal_chain.InvalidChain):
        causal_chain.validate_steps(good_steps(message)[:2], items)
    no_fact = [{'kind': 'interpretacja', 'text': 'Jeden.'}, {'kind': 'spin', 'text': 'Dwa.'}, {'kind': 'wniosek', 'text': 'Trzy.'}]
    with pytest.raises(causal_chain.InvalidChain) as error:
        causal_chain.validate_steps(no_fact, items)
    assert error.value.gates['walidator']['status'] == 'fail'


def test_more_than_five_steps_keeps_conclusion():
    message, _ = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message)
    raw = raw[:3] + [{'kind': 'interpretacja', 'text': f'Dodatkowy krok {n}.'} for n in (5, 12)] + raw[3:]
    steps, _ = causal_chain.validate_steps(raw, items)
    assert len(steps) == 5 and steps[-1]['kind'] == 'wniosek'


# --- generowanie, przegląd, decyzja --------------------------------------------------------------------------------------

def test_generate_pending_with_log_and_review_pass():
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)))
    assert chain.status == 'pending_review' and chain.prompt_version == causal_chain.PROMPT_VERSION
    assert chain.model_name == 'groq:llama-test' and chain.gates['przeglad']['status'] == 'pass'
    assert [r['role'] for r in chain.gates['przeglad']['roles']] == ['facts', 'law', 'linguist']
    assert list(chain.events.values_list('event', flat=True)) == ['generated', 'reviewed']


def test_generate_invalid_is_failed_and_never_public(settings):
    settings.CAUSAL_CHAIN_ENABLED = True
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask([{'kind': 'wniosek', 'text': 'Sam wniosek.'}]))
    assert chain.status == 'failed' and chain.events.get().event == 'failed'
    with pytest.raises(causal_chain.ChainError):
        causal_chain.approve(chain, staff())


def linguist_only_ask(steps):
    """Uwagi krytyczne tylko w roli Językoznawcy (polecenie przeglądu zawiera nazwę roli)."""
    def ask(prompt, data, schema, exclude=()):
        if 'steps' in schema.get('properties', {}):
            return {'steps': steps}, ('groq', 'llama-test')
        if 'Językoznawca' in prompt:
            return {'decision': 'revise', 'critical': ['Szyk zdania w kroku 2.'], 'reason': 'język'}, ('nim', 'recenzent')
        return {'decision': 'publish', 'critical': [], 'reason': 'ok'}, ('nim', 'recenzent')
    return ask


def test_review_block_hard_for_facts_and_law():
    """Recenzja Fable (poprawka 7): uwagi krytyczne fact-checkera albo prawnika = bez override, nowe wygenerowanie."""
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message), review=('revise', ['Brak podstawy dla kroku 2.'])))
    with pytest.raises(causal_chain.ChainError) as error:
        causal_chain.approve(chain, staff(), 'Uzasadnienie.', override=True)
    assert error.value.code == 'blocked_hard'


def test_review_block_requires_override_with_note():
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=linguist_only_ask(good_steps(message)))
    assert chain.gates['przeglad']['status'] == 'blocked'
    user = staff()
    with pytest.raises(causal_chain.ChainError) as error:
        causal_chain.approve(chain, user)
    assert error.value.code == 'blocked'
    chain = causal_chain.approve(chain, user, 'Krok 2 to interpretacja, oznaczona.', override=True)
    assert chain.status == 'approved' and chain.approved_by == user
    assert chain.events.filter(event='approved', details__override=True).exists()


def test_generate_does_not_overwrite_human_decision_and_stops_in_silence(settings):
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    causal_chain.approve(chain, staff())
    again = causal_chain.generate(message, ask=fake_ask([]))
    assert again.status == 'approved' and len(again.steps) == 4
    settings.ELECTION_SILENCE = True
    assert causal_chain.generate(message, ask=fake_ask(good_steps(message)), force=True) is None


# --- API przekazu --------------------------------------------------------------------------------------------------------

def day_url():
    return f'/api/clinic/messages/{DAY.isoformat()}/'


def test_flags_off_response_unchanged():
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    causal_chain.approve(chain, staff())
    data = APIClient().get(day_url()).json()['government']
    assert 'causal_chain' not in data and 'spin_strength' not in data
    listing = APIClient().get('/api/clinic/messages/').json()['results'][0]['government']
    assert 'causal_chain' not in listing


def test_chain_public_only_after_approval_and_not_in_silence(settings):
    settings.CAUSAL_CHAIN_ENABLED = True
    message, _ = make_message()
    assert APIClient().get(day_url()).json()['government']['causal_chain'] is None
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    assert APIClient().get(day_url()).json()['government']['causal_chain'] is None  # do zatwierdzenia
    causal_chain.approve(chain, staff())
    public = APIClient().get(day_url()).json()['government']['causal_chain']
    assert public['ai_generated'] is True and public['approved_at'] and public['model'] == 'groq:llama-test'
    assert [s['kind'] for s in public['steps']] == ['fakt', 'interpretacja', 'spin', 'wniosek']
    assert set(public['steps'][0]) == {'kind', 'text', 'source'} and set(public['steps'][0]['source']) == {'name', 'url', 'date'}
    assert 'source_id' not in str(public)
    settings.ELECTION_SILENCE = True
    assert APIClient().get(day_url()).json()['government']['causal_chain'] is None


def test_changed_message_hides_approved_chain_until_regenerated(settings):
    settings.CAUSAL_CHAIN_ENABLED = True
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    causal_chain.approve(chain, staff())
    assert APIClient().get(day_url()).json()['government']['causal_chain'] is not None
    message.message = 'Przekaz odświeżony po południu.'
    message.save()
    assert APIClient().get(day_url()).json()['government']['causal_chain'] is None
    again = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    assert again.pk == chain.pk and again.status == 'pending_review' and again.approved_at is None


def test_staff_review_endpoint():
    message, _ = make_message()
    causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    url = f'/api/staff/clinic/messages/{message.pk}/causal-chain/review/'
    client = APIClient()
    assert client.post(url, {'decision': 'approve'}, format='json').status_code in (401, 403)
    client.force_authenticate(staff())
    response = client.post(url, {'decision': 'approve', 'note': 'Sprawdzone.'}, format='json')
    assert response.status_code == 200 and response.json()['status'] == 'approved' and response['Cache-Control'] == 'no-store'
    assert client.post(url, {'decision': 'approve'}, format='json').status_code == 409
    assert client.post(url, {'decision': 'reject', 'note': 'Jednak nie.'}, format='json').json()['status'] == 'rejected'
    assert client.post(f'/api/staff/clinic/messages/{message.pk + 99}/causal-chain/review/', {'decision': 'approve'},
                       format='json').status_code == 404


def test_staff_review_locked_in_silence(settings):
    message, _ = make_message()
    causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    settings.ELECTION_SILENCE = True
    client = APIClient()
    client.force_authenticate(staff())
    response = client.post(f'/api/staff/clinic/messages/{message.pk}/causal-chain/review/', {'decision': 'approve'}, format='json')
    assert response.status_code == 423 and response.json()['code'] == 'silence'


def test_command_approve_and_reject():
    message, _ = make_message()
    chain = causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    staff('dyzurny')
    with pytest.raises(CommandError):
        call_command('lancuch_przekazu', 'odrzuc', str(chain.pk), '--kto', 'dyzurny')  # bez uzasadnienia
    with pytest.raises(CommandError):
        call_command('lancuch_przekazu', 'zatwierdz', str(chain.pk), '--kto', 'nieznany')
    call_command('lancuch_przekazu', 'zatwierdz', str(chain.pk), '--kto', 'dyzurny', '--uwaga', 'OK')
    chain.refresh_from_db()
    assert chain.status == 'approved' and chain.approved_by.username == 'dyzurny'
    assert CausalChainEvent.objects.filter(chain=chain, event='approved', actor__username='dyzurny').exists()


# --- siła spinu dnia -----------------------------------------------------------------------------------------------------

def diagnose(p, intensity, verdict='spin', status='approved'):
    return SpinDiagnosis.objects.create(post=p, status=status, verdict=verdict, intensity=intensity)


def test_spin_strength_median_minimum_and_exclusions(settings):
    settings.PRZEKAZ_SPIN_STRENGTH_ENABLED = True
    message, posts = make_message(texts=('a jeden', 'b dwa', 'c trzy', 'd cztery', 'e pięć'))
    diagnose(posts[0], 20)
    diagnose(posts[1], 90, verdict='unclear')        # nie da się ocenić - poza miarą
    diagnose(posts[2], 60, status='pending_review')  # niezatwierdzona - poza miarą
    assert APIClient().get(day_url()).json()['government']['spin_strength'] is None
    diagnose(posts[3], 61, verdict='no_spin')
    diagnose(posts[4], 30, verdict='partial')
    strength = APIClient().get(day_url()).json()['government']['spin_strength']
    assert strength['value'] == 30 and strength['n'] == 3 and 'Mediana' in strength['method']


def test_median_rounding():
    assert causal_chain.median_strength([10, 20]) is None
    assert causal_chain.median_strength([10, 20, 30, 41]) == 25
    assert causal_chain.median_strength([10, 20, 31, 40]) == 26  # 25,5 w górę


# --- przeszłość: lista głosowań ------------------------------------------------------------------------------------------

@pytest.fixture
def przeszlosc(monkeypatch, settings):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    settings.PRZESZLOSC_VOTES_LIST_ENABLED = True
    settings.PRZESZLOSC_NETWORK_ENABLED = True


def votings():
    a = voting(1, [(1, 'Anna A', 'KO', 'YES'), (2, 'Bartek B', 'PiS', 'NO'), (3, 'Celina C', 'KO', 'YES')])
    a.counts = {'yes': 240, 'no': 200, 'abstain': 1, 'notParticipating': 19, 'majorityType': 'SIMPLE_MAJORITY', 'majorityVotes': 201}
    a.save()
    b = voting(2, [(1, 'Anna A', 'KO', 'NO'), (2, 'Bartek B', 'PiS', 'YES')])
    b.counts = {'yes': 100, 'no': 300, 'majorityType': 'SIMPLE_MAJORITY', 'majorityVotes': 301}
    b.article.title = 'Głosowanie 2: ustawa o lasach'
    b.article.save()
    b.save()
    c = voting(3, [(2, 'Bartek B', 'PiS', 'VOTE_VALID')])
    c.kind, c.counts = 'ON_LIST', {}
    c.save()
    return a, b, c


def test_votes_list_off_by_default(monkeypatch):
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert APIClient().get('/api/przeszlosc/glosowania/').status_code == 404


def test_votes_list_filters_pagination_and_coverage(przeszlosc):
    a, b, c = votings()
    client = APIClient()
    data = client.get('/api/przeszlosc/glosowania/').json()
    assert [r['id'] for r in data['results']] == ['10/40/1', '10/40/2', '10/40/3']  # najnowsze pierwsze
    assert [r['outcome'] for r in data['results']] == ['przyjete', 'odrzucone', 'nieustalone']
    assert data['coverage']['complete'] is False and data['coverage']['total_votings'] == 3
    assert data['coverage']['terms'][0]['term'] == 10 and data['clubs'] == ['KO', 'PiS']
    assert 'club_votes' not in data['results'][0]
    ko = client.get('/api/przeszlosc/glosowania/?klub=KO').json()
    assert ko['total'] == 2 and ko['results'][0]['club_votes'] == {'club': 'KO', 'votes': {'za': 2}}
    assert client.get('/api/przeszlosc/glosowania/?wynik=odrzucone').json()['total'] == 1
    assert client.get('/api/przeszlosc/glosowania/?q=lasach').json()['results'][0]['id'] == '10/40/2'
    assert client.get('/api/przeszlosc/glosowania/?kadencja=9').json()['total'] == 0
    since = (timezone.localdate() - timedelta(days=2)).isoformat()
    assert client.get(f'/api/przeszlosc/glosowania/?od={since}').json()['total'] == 2
    page = client.get('/api/przeszlosc/glosowania/?na_strone=2&strona=2').json()
    assert page['pages'] == 2 and page['page'] == 2 and len(page['results']) == 1
    response = client.get('/api/przeszlosc/glosowania/')
    assert response['Cache-Control'] == 'public, max-age=300'


@pytest.mark.parametrize('query', ['kadencja=x', 'od=2026-13-01', 'od=2026-10-02&do=2026-10-01', 'wynik=moze', 'q=ab', 'strona=-1'])
def test_votes_list_bad_params(przeszlosc, query):
    assert APIClient().get(f'/api/przeszlosc/glosowania/?{query}').status_code == 400


def test_outcome_rules():
    from news.przeszlosc_v3 import outcome
    assert outcome({'yes': 231, 'majorityVotes': 231}) == 'przyjete'
    assert outcome({'yes': 230, 'majorityVotes': 231}) == 'odrzucone'
    assert outcome({'yes': 230, 'no': 1}) == 'nieustalone'


# --- przeszłość: powiązania osoby ----------------------------------------------------------------------------------------

def test_network_from_denominators(przeszlosc):
    anna, bartek = mp('Anna A', 1), mp('Bartek B', 2)
    for n in range(1, 4):
        voting(n, [(1, 'Anna A', 'KO', 'YES'), (2, 'Bartek B', 'PiS', 'YES'), (3, 'Celina C', 'KO', 'NO')])
    client = APIClient()
    data = client.get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/').json()
    assert data['person']['id'] == anna.pk
    assert data['nodes'][0] == {'id': f'figure:{anna.pk}', 'kind': 'osoba', 'label': 'Anna A', 'role': 'Poseł na Sejm RP', 'root': True}
    votes = [e for e in data['edges'] if e['kind'] == 'glosowania']
    assert {e['target'] for e in votes} >= {f'figure:{bartek.pk}'}
    assert any(e['weight'] == 100 and e['evidence'] for e in votes if e['target'] == f'figure:{bartek.pk}')
    assert data['coverage']['votes_available'] is True and 'nie dowód' in data['note']
    assert client.get('/api/przeszlosc/osoba/999999/powiazania/').status_code == 404


def test_network_off_and_locked(monkeypatch, settings):
    anna = mp('Anna A', 1)
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    assert APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/').status_code == 404
    settings.PRZESZLOSC_NETWORK_ENABLED = True
    monkeypatch.setattr('news.przeszlosc_dostep.has', lambda feature, request=None, email='': False)
    response = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/')
    assert response.status_code == 403 and response.json()['feature'] == 'denominators'


# --- recenzja Codex 13.10: poprawki ------------------------------------------------------------------------------------

def test_clinic_page_cache_keyed_by_flags_and_bypassed_in_silence(settings, monkeypatch):
    from news import clinic_api
    settings.CAUSAL_CHAIN_ENABLED = True
    monkeypatch.setattr(clinic_api, '_page_cache_active', lambda: True)
    calls = []
    monkeypatch.setattr('news.clinic.clinic_page_data', lambda window: calls.append(window) or {'n': len(calls)})
    client = APIClient()
    assert client.get('/api/clinic/').json() == {'n': 1}
    assert client.get('/api/clinic/').json() == {'n': 1}  # z cache
    assert cache.get(causal_chain.page_cache_key(7)) == {'n': 1} and causal_chain.page_cache_key(7) != 'clinic-page:7'
    settings.ELECTION_SILENCE = True
    assert client.get('/api/clinic/').json() == {'n': 2}  # cisza: zawsze świeże dane, bez cache
    settings.ELECTION_SILENCE = False
    settings.CAUSAL_CHAIN_ENABLED = False
    assert causal_chain.page_cache_key(7) == 'clinic-page:7'  # flagi wyłączone: klucz jak przed v3
    causal_chain._clear_page_cache()
    assert cache.get(causal_chain.page_cache_key(7, True, False)) is None


@pytest.mark.parametrize('quoted_text', [
    'Wpisy mówią: "to koniec świata dla nas".',
    'Wpisy mówią: “to koniec świata dla nas”.',
    'Wpisy mówią: «to koniec świata dla nas».',
    'Wpisy mówią: »to koniec świata dla nas«.',
    "Wpisy mówią: 'to koniec świata dla nas'.",
    'Wpisy mówią: ‚to koniec świata dla nas’.',
])
def test_quotes_outside_materials_in_any_quote_style(quoted_text):
    message, _ = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message) + [{'kind': 'interpretacja', 'text': quoted_text}]
    steps, gates = causal_chain.validate_steps(raw, items)
    assert len(steps) == 4 and gates['fact_checker']['issues'][0]['issue'] == 'cytat spoza materiałów'


def test_quote_from_materials_allowed_in_english_quotes():
    message, _ = make_message()
    items = causal_chain.materials(message)
    raw = good_steps(message) + [{'kind': 'interpretacja', 'text': 'Wpisy powtarzają “To koniec ulg dla rodzin”.'}]
    steps, _ = causal_chain.validate_steps(raw, items)
    assert len(steps) == 5


def test_message_list_queries_constant_with_v3_flags(settings):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    settings.CAUSAL_CHAIN_ENABLED = True
    settings.PRZEKAZ_SPIN_STRENGTH_ENABLED = True
    acc = account(camp='government', handle='konto_n', user_id='777')

    def add_days(start, n):
        for d in range(start, start + n):
            m = ClinicDailyMessage.objects.create(day=DAY - timedelta(days=d), camp='government', status='approved', message='P.')
            m.posts.add(post(acc, post_id=str(70000 + d), text=f'wpis {d}', hours_ago=24 * d + 1))

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert APIClient().get('/api/clinic/messages/').status_code == 200
        return len(ctx.captured_queries)

    add_days(0, 2)
    count()  # rozgrzanie pamięci przełączników (v3_flags: 1 zapytanie na 30 s)
    few = count()
    add_days(2, 6)
    assert count() == few


def test_network_vary_headers(monkeypatch, settings):
    from news.test_przeszlosc_osoba import mp
    monkeypatch.setenv('PRZESZLOSC_ENABLED', 'true')
    settings.PRZESZLOSC_NETWORK_ENABLED = True
    anna = mp('Anna A', 1)
    response = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/')
    assert response.status_code == 200 and {'Cookie', 'Authorization'} <= {v.strip() for v in response['Vary'].split(',')}
    monkeypatch.setattr('news.przeszlosc_dostep.has', lambda feature, request=None, email='': False)
    locked = APIClient().get(f'/api/przeszlosc/osoba/{anna.pk}/powiazania/')
    assert locked.status_code == 403 and 'Authorization' in locked['Vary'] and 'no-store' in locked['Cache-Control']


def test_staff_reject_requires_note():
    message, _ = make_message()
    causal_chain.generate(message, ask=fake_ask(good_steps(message)), with_review=False)
    client = APIClient()
    client.force_authenticate(staff())
    url = f'/api/staff/clinic/messages/{message.pk}/causal-chain/review/'
    assert client.post(url, {'decision': 'reject'}, format='json').status_code == 400
    assert client.post(url, {'decision': 'reject', 'note': '  '}, format='json').status_code == 400
    assert CausalChain.objects.get().status == 'pending_review'
