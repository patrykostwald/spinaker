"""Kworum i stała miara Konsylium (6.10) - wyłącznie atrapy, bez sieci."""
import random
import statistics
from datetime import timedelta, timezone as dt_timezone

import pytest
import requests
from django.core.cache import cache
from django.utils import timezone

from news import clinic, clinic_ai, clinic_council as council, council_quorum as quorum, council_registry as registry
from news import council_rerun
from news.clinic_ai import ClinicAIError
from news.clinic_models import SpinDiagnosis

CORE = [m[1] for m in quorum.core_members()]  # gpt-oss, qwen, nemotron, gemini, bielik
EXTRA = ['mistral-small-latest', '@cf/meta/llama-3.3-70b-instruct-fp8-fast']


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for key in [*registry.KEYS.values(), 'CLINIC_COUNCIL', 'COUNCIL_CORE', 'COUNCIL_QUORUM_MIN', 'COUNCIL_CORE_MIN',
                'COUNCIL_STABLE_MEASURE', 'COUNCIL_CONTENT_RESERVE', 'COUNCIL_SIDE_SHARE', 'CLINIC_ESCALATE']:
        monkeypatch.delenv(key, raising=False)
    for key in registry.KEYS.values():
        monkeypatch.setenv(key, 'test-key')
    monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID', 'account')
    monkeypatch.setenv('PLLUM_API_URL', 'https://pllum.example/v1')

    def forbidden(*args, **kwargs):
        raise AssertionError('Prawdziwa sieć jest zabroniona w testach')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    yield
    cache.clear()


def rec(model, intensity=50, verdict='partial', status='odpowiedział', note=''):
    out = {'model': model, 'status': status, 'provider': 'x', 'company': model}
    if status == 'odpowiedział':
        out.update(verdict=verdict, intensity=intensity, techniques=[], claims=[], loaded_words=[])
    else:
        out['note'] = note
    return out


def core_tuples():
    return quorum.core_members()


# --- 1. kworum -----------------------------------------------------------------------------------------------------

def test_quorum_met_with_four_members_and_three_core():
    records = [rec(CORE[0]), rec(CORE[1]), rec(CORE[2]), rec(EXTRA[0])]
    state = quorum.check(records, core_tuples())
    assert state['met'] and state['members'] == 4 and state['core'] == 3


def test_quorum_not_met_like_5_10():
    """Skład z 5.10: gpt-oss bez odpowiedzi, Qwen i Bielik nieobecni - 4 odpowiedzi, ale tylko 2 z rdzenia."""
    records = [rec('openai/gpt-oss-20b', status='brak odpowiedzi', note='groq_daily_limit'),
               rec('nvidia/nemotron-3-super-120b-a12b', 50), rec('gemini-3.8-flash', 45),
               rec(EXTRA[0], 5, 'no_spin'), rec(EXTRA[1], 30)]
    state = quorum.check(records, core_tuples())
    assert not state['met'] and state['core'] == 2 and state['need_core'] == 3
    assert state['reason'] == 'council_quorum: odpowiedziało 4 z wymaganych 4, stałych 2 z wymaganych 3'
    too_few = quorum.check([rec(c) for c in CORE[:3]], core_tuples())
    assert not too_few['met'] and too_few['members'] == 3


def test_suspended_core_member_does_not_block_measure():
    core = core_tuples()[:2]  # pozostali stali członkowie zawieszeni/bez klucza
    assert quorum.check([rec(core[0][1]), rec(core[1][1]), rec(EXTRA[0]), rec(EXTRA[1])], core)['met']


def test_breaker_waits_until_reset_when_core_hit_limits():
    now = timezone.now()
    records = [rec('openai/gpt-oss-20b', status='brak odpowiedzi', note='groq_daily_limit'),
               rec('qwen/qwen3.8-27b', status='brak odpowiedzi', note='groq: http_429')]
    state = quorum.block(records, 'council_quorum: test', now)
    assert state['limits'] and state['until'] == quorum.next_reset(now).astimezone(dt_timezone.utc).isoformat()
    assert quorum.waiting()
    quorum.release('mechanik')
    assert quorum.waiting() is None
    state = quorum.block([rec('openai/gpt-oss-20b', status='brak odpowiedzi', note='Timeout')], 'x', now)
    assert not state['limits'] and state['until'] == (now + timedelta(hours=1)).astimezone(dt_timezone.utc).isoformat()


def test_next_reset_is_two_oclock_warsaw():
    from datetime import datetime
    now = datetime(2026, 10, 5, 23, 30, tzinfo=quorum.WARSAW)
    assert quorum.next_reset(now) == datetime(2026, 10, 6, 2, 0, tzinfo=quorum.WARSAW)
    assert quorum.next_reset(datetime(2026, 10, 6, 1, 0, tzinfo=quorum.WARSAW)).day == 6


@pytest.mark.django_db
def test_diagnosis_without_quorum_waits_in_queue_not_published(monkeypatch):
    from news.test_clinic import account, post
    row = SpinDiagnosis.objects.create(post=post(account()), status='queued', screen_score=90)
    records = [rec('openai/gpt-oss-20b', status='brak odpowiedzi', note='groq_daily_limit'),
               rec('nvidia/nemotron-3-super-120b-a12b'), rec('gemini-3.8-flash'), rec(EXTRA[0]), rec(EXTRA[1])]
    monkeypatch.setattr(council, 'consult', lambda *a: records)
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda context: council.diagnose(context, 'tekst'))
    clinic.diagnose(row)
    row.refresh_from_db()
    assert row.status == 'queued' and row.error.startswith('council_quorum')
    assert row.diagnosed_at is None and not row.verdict  # nie liczy się do dziennego limitu, nic się nie ukazało
    assert row.usage['quorum']['attempts'] == 1 and row.usage['council']['members'][0]['note'] == 'groq_daily_limit'
    assert quorum.waiting()
    assert clinic.quorum_waiting().count() == 1


@pytest.mark.django_db
def test_run_diagnoses_waits_without_asking_models(monkeypatch):
    from news.test_clinic import account, post
    SpinDiagnosis.objects.create(post=post(account()), status='queued', screen_score=90, error='council_quorum: 3/4')
    monkeypatch.setenv('CLINIC_AI_ENABLED', 'true')
    monkeypatch.setenv('CLINIC_PROVIDER', 'council')
    monkeypatch.setattr(clinic, 'local_now', lambda: timezone.localtime().replace(hour=12))
    monkeypatch.setattr(council, 'consult', lambda *a: pytest.fail('bez kworum nie pytamy modeli'))
    quorum.block([], 'council_quorum: test')
    result = clinic.run_diagnoses()
    assert result['status'] == 'quorum' and result['waiting'] == 1
    quorum.release()
    for member in quorum.core_members()[:3]:  # 3 z 5 stałych bez limitu - sprawdzenie przed zapytaniami też czeka
        cache.set(registry.limit_key(member), registry.daily_limit(member), 3600)
    assert clinic.run_diagnoses()['status'] == 'quorum'


@pytest.mark.django_db
def test_quorum_wait_expires_after_72h_with_reason():
    from news.test_clinic import account, post
    row = SpinDiagnosis.objects.create(post=post(account(), hours_ago=80), status='queued', error='council_quorum: 3/4')
    assert clinic.expire_quorum_waits() == 1
    row.refresh_from_db()
    assert row.status == 'failed' and row.error.startswith('council_quorum_expired')


def test_consult_fills_quorum_with_core_first(monkeypatch):
    asked = []

    def fake(member, *a, **kw):
        asked.append(member[1])
        if member[1] in ('openai/gpt-oss-20b',):
            raise ClinicAIError('groq_daily_limit')
        return {'verdict': 'partial', 'intensity': 50, 'techniques': [], 'claims': []}
    monkeypatch.setattr(council, 'ask', fake)
    rows = council.consult('tekst', '')
    assert quorum.check(rows)['met']
    answered_core = [r['model'] for r in rows if r['status'] == 'odpowiedział' and r['model'] in CORE]
    assert len(answered_core) >= 3


# --- 2. stała miara --------------------------------------------------------------------------------------------------

BIASES = {'openai/gpt-oss-20b': -1.0, 'qwen/qwen3.8-27b': 2.5, 'nvidia/nemotron-3-super-120b-a12b': 3.0,
          'gemini-3.8-flash': -2.5, 'speakleash/Bielik-11B-v3.0-Instruct:publicai': -5.0, EXTRA[0]: 0.0, EXTRA[1]: 2.5}


def opinions(scores, verdict='partial'):
    return [rec(model, score, verdict) for model, score in scores.items()]


@pytest.mark.parametrize('seed', range(25))
def test_full_core_scores_are_identical_with_stable_measure(seed):
    """Przy pełnym rdzeniu (z dodatkami albo bez) stała miara nie zmienia ani jednego wyniku - historia porównywalna."""
    rnd = random.Random(seed)
    models = CORE + rnd.sample(EXTRA, rnd.randint(0, 2))
    ops = opinions({m: rnd.randint(0, 100) for m in models}, rnd.choice(['partial', 'spin', 'no_spin']))
    biases = {m: rnd.uniform(-15, 15) for m in models}
    plain = council.combine(ops)
    stable = council.combine(ops, {'core': CORE, 'biases': biases})
    assert stable['intensity'] == plain['intensity'] and stable['verdict'] == plain['verdict']
    assert stable['measure']['shift'] == 0


def test_missing_core_member_shifts_by_composition_bias():
    full = {'openai/gpt-oss-20b': 49, 'qwen/qwen3.8-27b': 52.5, 'nvidia/nemotron-3-super-120b-a12b': 53,
            'gemini-3.8-flash': 47.5, 'speakleash/Bielik-11B-v3.0-Instruct:publicai': 45}
    present = {k: v for k, v in full.items() if 'Bielik' not in k and 'gpt-oss' not in k}  # bez dwóch surowszych
    ops = opinions({k: int(round(v)) for k, v in present.items()})
    raw = council.combine(ops)
    stable = council.combine(ops, {'core': CORE, 'biases': BIASES})
    expected = quorum.offset(list(present), CORE, BIASES)
    assert expected > 0 and stable['measure']['shift'] == expected
    assert stable["intensity"] == int(statistics.median([int(round(v)) for v in present.values()]) - expected)
    assert stable['intensity'] < raw['intensity']  # łagodniejszy skład nie zawyża wyniku


def test_same_measure_for_both_camps_mirrored():
    """Lustrzane dane: ten sam skład i te same oceny dla wpisu koalicji i opozycji - identyczny wynik i kworum."""
    ops = opinions({CORE[0]: 60, CORE[2]: 70, CORE[3]: 55, EXTRA[0]: 40})
    measure = {'core': CORE, 'biases': BIASES}
    coalition = council.combine([{**o, 'camp': 'coalition'} for o in ops], measure)
    opposition = council.combine([{**o, 'camp': 'opposition'} for o in ops], measure)
    assert coalition == opposition
    assert quorum.check(ops, core_tuples()) == quorum.check(list(reversed(ops)), core_tuples())


def test_bias_estimate_is_stable_and_recovers_full_council():
    """Typowa surowość odtwarzana z historii (szum ±10) i korekta zbliża wynik niepełnego składu do pełnego."""
    rnd = random.Random(7)
    true = {'openai/gpt-oss-20b': -1, 'qwen/qwen3.8-27b': 5, 'nvidia/nemotron-3-super-120b-a12b': 7,
            'gemini-3.8-flash': -3, 'speakleash/Bielik-11B-v3.0-Instruct:publicai': -9, EXTRA[0]: 0}
    history = []
    for _ in range(120):
        truth = rnd.randint(20, 80)
        history.append([rec(m, max(0, min(100, int(truth + b + rnd.gauss(0, 5))))) for m, b in true.items()])
    first, second = quorum.biases_from(history[:60]), quorum.biases_from(history[60:])
    for model in true:
        assert abs(first[model] - second[model]) <= 4  # stabilne między oknami
    raw_err = fixed_err = 0
    for records in history[-40:]:
        full = statistics.median(r['intensity'] for r in records)
        part = [r for r in records if r['model'] not in ('speakleash/Bielik-11B-v3.0-Instruct:publicai', 'openai/gpt-oss-20b')]
        raw_err += abs(statistics.median(r['intensity'] for r in part) - full)
        fixed, _ = quorum.stable_intensity(statistics.median(r['intensity'] for r in part), [r['model'] for r in part], CORE, first)
        fixed_err += abs(fixed - full)
    assert fixed_err < raw_err


def test_bias_needs_enough_samples_and_is_clipped():
    rows = [[rec(CORE[0], 90), rec(CORE[1], 10), rec(CORE[2], 10)] for _ in range(quorum.BIAS_MIN_SAMPLES - 1)]
    assert quorum.biases_from(rows) == {}
    rows.append(rows[0])
    assert quorum.biases_from(rows)[CORE[0]] == quorum.BIAS_CLIP


# --- 3. rezerwa limitów dla treści -----------------------------------------------------------------------------------

def test_side_jobs_cannot_use_content_reserve():
    member = ('groq', 'openai/gpt-oss-20b')
    limit, side = registry.daily_limit(member), registry.side_limit(member)
    cache.set(registry.limit_key(member), side, 3600)
    assert not registry.reserve(member)  # zadanie poboczne: odmowa
    assert cache.get(registry.limit_key(member)) == side  # odmowa nie zużywa limitu
    assert registry.content_reserved(member)
    with registry.for_content():
        assert registry.reserve(member)  # diagnoza sięga do rezerwy
        assert not registry.content_reserved(member)
    assert side < limit


def test_screening_on_council_model_stops_early_and_falls_back(monkeypatch):
    member = ('groq', 'openai/gpt-oss-20b')
    assert registry.reserve_side(member)
    cache.set(registry.limit_key(member), int(registry.daily_limit(member) * 0.25), 3600)
    assert not registry.reserve_side(member)
    assert registry.reserve_side(('groq', 'llama-3.1-8b-instant'))  # model spoza Konsylium - bez ograniczeń
    monkeypatch.setenv('CLINIC_TRIAGE_MODEL', 'openai/gpt-oss-20b')
    assert clinic_ai._screen_groq('tekst') is None  # strażnik oddaje wpis do NIM, nie zabiera głosów Konsylium


def test_content_reserve_refusal_is_not_a_member_failure(monkeypatch):
    member = ('groq', 'openai/gpt-oss-20b')
    cache.set(registry.limit_key(member), registry.side_limit(member), 3600)
    recorded = []
    monkeypatch.setattr('news.council_recruiter.record', lambda *a: recorded.append(a))
    monkeypatch.setattr('news.council_health.record', lambda *a: recorded.append(a))
    with pytest.raises(ClinicAIError) as error:
        council.ask(member, 's', 'u', {})
    assert error.value.code == 'groq_content_reserve' and recorded == []


# --- 4. powtórka -----------------------------------------------------------------------------------------------------

def full_result(intensity=62, verdict='spin'):
    members = [rec(m, intensity) for m in CORE]
    return {'verdict': verdict, 'intensity': intensity, 'headline': 'Nowy nagłówek', 'summary': 'Nowe.', 'analysis': 'Nowa.',
            'limitations': '', 'techniques': [], 'claims': [], 'plain': {}, 'lab': {}, 'loaded_words': [],
            'usage': {'model': 'konsylium: pełny', 'council': {'members': members}}}


@pytest.fixture
def broken_row(db):
    from news.test_clinic import account, post
    members = [rec('nvidia/nemotron-3-super-120b-a12b', 30), rec('gemini-3.8-flash', 25), rec(EXTRA[0], 5, 'no_spin')]
    return SpinDiagnosis.objects.create(
        post=post(account()), status='approved', provider='anthropic', verdict='partial', intensity=30, headline='Stary',
        summary='Stare.', limitations='', diagnosed_at=timezone.now() - timedelta(hours=5), reviewed_at=timezone.now(),
        usage={'model': 'konsylium: niepełny', 'council': {'members': members}, 'videos': []})


@pytest.fixture
def rerun_ready(monkeypatch):
    monkeypatch.setattr(clinic_ai, 'enabled', lambda: True)
    monkeypatch.setattr(clinic, 'budget_left', lambda: 5.0)
    monkeypatch.setattr(clinic, 'ensure_x_thread', lambda *a, **k: False)
    monkeypatch.setattr(quorum, 'possible', lambda: {'met': True, 'reason': ''})


def since():
    return timezone.now() - timedelta(days=2)


def test_rerun_dry_run_lists_without_calls(broken_row, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda c: pytest.fail('dry-run bez zapytań'))
    result = council_rerun.run(since(), dry_run=True)
    assert result['status'] == 'dry_run' and result['candidates'] == 1
    assert result['rows'][0]['reason'].startswith('council_quorum: odpowiedziało 3 z wymaganych 4')


def test_rerun_keeps_history_and_is_idempotent(broken_row, rerun_ready, monkeypatch):
    calls = []
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda c: calls.append(1) or full_result())
    result = council_rerun.run(since(), anytime=True)
    assert result['done'] == 1 and result['updated'] == 1
    row = SpinDiagnosis.objects.get(pk=broken_row.pk)
    assert (row.verdict, row.intensity, row.status) == ('spin', 62, 'approved')
    assert row.limitations.startswith(council_rerun.NOTE)
    previous = row.usage['history'][0]
    assert (previous['verdict'], previous['intensity'], previous['headline'], previous['members']) == ('partial', 30, 'Stary', 3)
    assert row.usage['rerun']['changed'] and row.usage['rerun']['previous'] == {'verdict': 'partial', 'intensity': 30}
    assert row.diagnosed_at == broken_row.diagnosed_at  # nie liczy się do dziennego limitu diagnoz
    assert clinic.detail_data(row)['revisions'][0]['intensity'] == 30
    again = council_rerun.run(since(), anytime=True)
    assert again['candidates'] == 0 and len(calls) == 1  # najwyżej raz na diagnozę
    count, last = council_rerun.done_since(since())
    assert count == 1 and last is not None


def test_rerun_same_score_has_no_note(broken_row, rerun_ready, monkeypatch):
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda c: full_result(30, 'partial'))
    assert council_rerun.run(since(), anytime=True)['same'] == 1
    row = SpinDiagnosis.objects.get(pk=broken_row.pk)
    assert council_rerun.NOTE not in row.limitations and not row.usage['rerun']['changed'] and row.usage['history']


def test_rerun_without_quorum_keeps_published_result(broken_row, rerun_ready, monkeypatch):
    def no_quorum(context):
        error = ClinicAIError('council_quorum: 3/4 członków, stałych 2/3')
        error.council = {'members': []}
        raise error
    monkeypatch.setattr(clinic_ai, 'diagnose', no_quorum)
    result = council_rerun.run(since(), anytime=True)
    assert result['waiting'] == 1 and result['done'] == 0
    row = SpinDiagnosis.objects.get(pk=broken_row.pk)
    assert (row.status, row.verdict, row.intensity) == ('approved', 'partial', 30) and 'history' not in row.usage
    assert row.usage['rerun_attempts']['count'] == 1
    assert len(council_rerun.candidates(since())) == 1  # spróbuje ponownie następnej nocy


def test_rerun_waits_for_quiet_hours(broken_row, rerun_ready, monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda c: pytest.fail('poza cichymi godzinami'))
    noon = datetime(2026, 10, 6, 12, 0, tzinfo=quorum.WARSAW)
    assert council_rerun.run(since(), now=noon)['status'] == 'deferred'
    assert council_rerun.quiet(datetime(2026, 10, 6, 2, 40, tzinfo=quorum.WARSAW))


def test_command_dry_run(broken_row):
    from io import StringIO
    from django.core.management import call_command
    out = StringIO()
    call_command('konsylium_powtorz', '--od', (timezone.now() - timedelta(days=1)).date().isoformat(), '--dry-run', stdout=out)
    assert '"candidates": 1' in out.getvalue()


def test_loop_report_has_quorum_contract(broken_row):
    from news import raport_petli
    c = raport_petli.BY_KEY['kworum']
    assert c['category'] == 'konsylium' and c['pending'] == 'quorum' and c['beats'] == ('konsylium-powtorz-night',)
    from news.test_clinic import account, post
    SpinDiagnosis.objects.create(post=post(account(handle='inny', user_id='202'), post_id='9002'), status='queued',
                                 error='council_quorum: 3/4', created_at=timezone.now() - timedelta(hours=13))
    assert raport_petli._pending(c, timezone.now()) == 1
