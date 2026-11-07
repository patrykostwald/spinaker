"""Rekruter Konsylium: zawieszanie martwych członków, powroty, sito kandydatów, role i tryb próbny."""
from datetime import timedelta
from unittest.mock import Mock, patch
from types import SimpleNamespace
from io import StringIO

import pytest
from django.utils import timezone

from news import council_recruiter as recruiter
from news.clinic_ai import ClinicAIError
from news.clinic_models import CouncilRecruitment, CouncilSeat


@pytest.mark.django_db
def test_adjust_drops_suspended_and_adds_admitted_role():
    CouncilSeat.objects.create(provider='hf', model='dead', status='suspended')
    CouncilSeat.objects.create(provider='openrouter', model='new:free', origin='recruiter', roles=['członek', 'recenzent'])
    members = [('groq', 'a'), ('hf', 'dead')]
    assert recruiter.adjust('CLINIC_COUNCIL', members) == [('groq', 'a'), ('openrouter', 'new:free')]
    assert recruiter.adjust('CLINIC_COUNCIL_LINGUIST', members) == [('groq', 'a')]


@pytest.mark.django_db
def test_hard_errors_start_a_streak_soft_ones_do_not(monkeypatch):
    recruiter.record(('openrouter', 'm'), 'openrouter: http_429')
    assert CouncilSeat.objects.get().first_fail_at is None  # limit zapisany dla panelu, bez serii do zawieszenia
    recruiter.record(('openrouter', 'm'), 'openrouter: http_404')
    seat = CouncilSeat.objects.get()
    assert seat.first_fail_at and 'http_404' in seat.last_error
    recruiter.record(('openrouter', 'm'), None)
    seat.refresh_from_db()
    assert seat.first_fail_at is None and seat.last_ok_at


@pytest.mark.django_db
def test_health_suspends_after_three_days_and_returns_on_answer(monkeypatch):
    monkeypatch.setattr(recruiter, '_notify', lambda *a: True)
    old = timezone.now() - timedelta(days=4)
    CouncilSeat.objects.create(provider='hf', model='dead', first_fail_at=old, last_error='hf: http_404')
    CouncilSeat.objects.create(provider='hf', model='fresh', first_fail_at=timezone.now(), last_error='hf: http_404')
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: True)
    monkeypatch.setattr(recruiter, '_probe', lambda member: 'hf: http_404')
    changes = recruiter.health()
    assert [c['model'] for c in changes] == ['dead']
    assert CouncilSeat.objects.get(model='dead').status == 'suspended'
    assert CouncilSeat.objects.get(model='fresh').status == 'active'
    monkeypatch.setattr(recruiter, '_probe', lambda member: None)
    assert recruiter.health()[0]['decision'] == 'returned'
    assert CouncilSeat.objects.get(model='dead').status == 'active'
    assert list(CouncilRecruitment.objects.values_list('decision', flat=True).order_by('pk')) == ['suspended', 'returned']


@pytest.mark.django_db
def test_sieve_filters_small_and_tooling_models_and_prefers_polish(monkeypatch):
    monkeypatch.setattr('news.ekspert_ai.watched_models', lambda: set())
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: True)
    found = [{'provider': 'openrouter', 'model': 'meta-llama/llama-guard-4-12b:free', 'context': 128000},
             {'provider': 'openrouter', 'model': 'mistralai/mistral-7b-instruct:free', 'context': 32000},
             {'provider': 'openrouter', 'model': 'z-ai/glm-4.5-air-106b:free', 'context': 128000},
             {'provider': 'hf', 'model': 'speakleash/Bielik-7B-v4-Instruct:publicai', 'context': 32000},
             {'provider': 'openrouter', 'model': 'someone/mystery-70b:free', 'context': 128000}]
    names = [c['model'] for c in recruiter.sieve(found)]
    assert names == ['speakleash/Bielik-7B-v4-Instruct:publicai', 'z-ai/glm-4.5-air-106b:free']


def test_roles_need_majority_and_exam_support():
    candidate = {'polish': False}
    exam = {'polish': True, 'agreement': 0.8, 'mae': 11, 'consistency': {'passed': True}}
    votes = [{'admit': True, 'roles': ['członek', 'recenzent', 'przewodniczący']},
             {'admit': True, 'roles': ['członek', 'recenzent', 'przewodniczący']}, {'admit': False, 'roles': []}]
    assert recruiter.roles_for(candidate, exam, votes) == ['członek', 'recenzent']


@pytest.mark.django_db
def test_trial_mode_only_recommends(monkeypatch):
    monkeypatch.delenv('COUNCIL_RECRUITER_AUTO', raising=False)
    monkeypatch.setattr(recruiter, '_notify', lambda *a: True)
    candidate = {'provider': 'openrouter', 'model': 'z-ai/glm-4.5:free', 'company': 'Zhipu AI', 'context': 128000,
                 'polish': False, 'new_company': True, 'billions': None}
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [candidate])
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [object()] * 5)
    monkeypatch.setattr(recruiter, '_probe', lambda member: None)
    monkeypatch.setattr(recruiter, 'examine', lambda member, items: {
        'items': 5, 'answered': 5, 'agreement': 0.8, 'mae': 8, 'techniques_avg': 2, 'polish': True, 'passed': True, 'answers': []})
    monkeypatch.setattr(recruiter, 'vote', lambda c, e: [{'model': 'a', 'admit': True, 'roles': ['członek'], 'reason': 'ok'},
                                                         {'model': 'b', 'admit': True, 'roles': ['członek'], 'reason': 'ok'}])
    monkeypatch.setattr(recruiter, 'accept_charter', lambda member: {'accepts': True, 'statement': 'Przyjmuję.'})
    result = recruiter.recruit()
    assert result['decision'] == 'would_admit'
    assert not CouncilSeat.objects.exists()
    monkeypatch.setenv('COUNCIL_RECRUITER_AUTO', 'true')
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [{**candidate, 'model': 'z-ai/glm-5:free'}])
    assert recruiter.recruit()['decision'] == 'admitted'
    assert CouncilSeat.objects.get(model='z-ai/glm-5:free').roles == ['członek']


@pytest.mark.django_db
def test_failed_exam_is_rejected_without_votes(monkeypatch):
    monkeypatch.setattr(recruiter, '_notify', lambda *a: True)
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [{'provider': 'nim', 'model': 'x/y-70b', 'company': 'Meta', 'context': 0,
                                                            'polish': False, 'new_company': False, 'billions': 70}])
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [object()] * 5)
    monkeypatch.setattr(recruiter, '_probe', lambda member: None)
    monkeypatch.setattr(recruiter, 'examine', lambda member, items: {
        'items': 5, 'answered': 2, 'agreement': 0.2, 'mae': 40, 'techniques_avg': 0, 'polish': None, 'passed': False, 'answers': []})
    with patch.object(recruiter, 'vote', side_effect=AssertionError('no vote on failed exam')):
        assert recruiter.recruit()['decision'] == 'would_reject'


@pytest.mark.django_db
def test_run_examines_several_candidates_per_night(monkeypatch):
    monkeypatch.setenv('COUNCIL_RECRUITER_PER_NIGHT', '3')
    monkeypatch.setattr(recruiter, 'health', lambda: [])
    calls = iter([{'status': 'ok', 'model': 'a'}, {'status': 'ok', 'model': 'b'}, {'status': 'no_candidates'}, {'status': 'ok'}])
    monkeypatch.setattr(recruiter, 'recruit', lambda dry_run=False, **kwargs: next(calls))
    assert [r.get('model') for r in recruiter.run()['recruitment']] == ['a', 'b', None]


@pytest.mark.django_db
def test_exam_items_query_runs_on_real_models():
    # Wcześniej filtr po nieistniejącym polu „council” wywracał Rekrutera na produkcji (testy mockowały exam_items).
    assert recruiter.exam_items() == []


@pytest.mark.django_db
def test_provider_outage_defers_instead_of_rejecting(monkeypatch):
    # 429/402 na każdym wpisie to awaria dostawcy, nie ocena modelu: bez głosowania, kandydat wraca po 3 dniach.
    monkeypatch.setattr(recruiter, '_notify', lambda *a: True)
    candidate = {'provider': 'groq', 'model': 'openai/gpt-oss-120b', 'company': 'OpenAI', 'context': 0,
                 'polish': False, 'new_company': False, 'billions': 120}
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [candidate])
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [object()] * 5)
    monkeypatch.setattr(recruiter, '_probe', lambda member: None)
    monkeypatch.setattr(recruiter, 'examine', lambda member, items: {
        'items': 5, 'answered': 0, 'hard_error': False, 'agreement': 0, 'mae': 100, 'techniques_avg': 0, 'polish': None,
        'passed': False, 'answers': [{'note': 'http_429', 'verdict': None}]})
    with patch.object(recruiter, 'vote', side_effect=AssertionError('no vote on outage')):
        assert recruiter.recruit()['decision'] == 'deferred'
    assert ('groq', 'openai/gpt-oss-120b') in recruiter.blocked()
    CouncilRecruitment.objects.update(created_at=timezone.now() - timedelta(days=4))
    assert ('groq', 'openai/gpt-oss-120b') not in recruiter.blocked()


@pytest.mark.django_db
def test_old_rejection_with_zero_answers_is_retried_but_404_stays_blocked():
    old = timezone.now() - timedelta(days=4)
    CouncilRecruitment.objects.create(provider='hf', model='a/b-70b', decision='would_reject', created_at=old,
                                      exam={'answered': 0, 'items': 5})
    CouncilRecruitment.objects.create(provider='nim', model='meta/llama2-70b', decision='would_reject', created_at=old,
                                      exam={'answered': 0, 'items': 5, 'hard_error': True})
    CouncilRecruitment.objects.create(provider='nim', model='c/d-70b', decision='would_reject', created_at=old,
                                      exam={'answered': 5, 'items': 5})
    assert recruiter.blocked() == {('nim', 'meta/llama2-70b'), ('nim', 'c/d-70b')}


def test_sieve_skips_outdated_models_and_second_routes(monkeypatch):
    monkeypatch.setattr(recruiter, 'skipped_providers', lambda: [])
    monkeypatch.setattr('news.ekspert_ai.watched_models', lambda: set())
    monkeypatch.setattr(recruiter, 'blocked', lambda: set())
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: True)
    with patch('news.clinic_council._members', return_value=[('groq', 'openai/gpt-oss-120b')]), \
            patch('news.clinic_models.CouncilSeat.objects') as seats:
        seats.all.return_value = []
        found = [{'provider': 'nim', 'model': 'meta/llama2-70b', 'context': 32000},
                 {'provider': 'hf', 'model': 'openai/gpt-oss-120b:novita', 'context': 128000},
                 {'provider': 'nim', 'model': 'meta/llama-3.3-70b-instruct', 'context': 128000},
                 {'provider': 'hf', 'model': 'meta-llama/Llama-3.3-70B-Instruct:groq', 'context': 128000}]
        names = [c['model'] for c in recruiter.sieve(found)]
    assert names == ['meta/llama-3.3-70b-instruct']


def test_new_catalog_companies_are_known():
    from news import council_registry as registry
    for model, company in (('thinkingmachines/inkling:free', 'Thinking Machines Lab'), ('inclusionai/ling-3.0-flash-sante:free', 'Inclusion AI (Ant Group)')):
        assert registry.metadata(('openrouter', model))['company'] == company


@pytest.mark.django_db
def test_sieve_examines_models_watched_by_ai_expert_first(monkeypatch):
    """Ekspert AI zmienia tylko kolejność egzaminów; filtry i egzamin bez zmian (właściciel 5.10)."""
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: True)
    monkeypatch.setattr(recruiter, 'blocked', lambda: set())
    found = [{'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-671b:free', 'context': 128000},
             {'provider': 'openrouter', 'model': 'z-ai/glm-4.5-air-106b:free', 'context': 128000}]
    monkeypatch.setattr('news.ekspert_ai.watched_models', lambda: set())
    assert recruiter.sieve(found)[0]['model'] == 'deepseek/deepseek-v4-671b:free'  # bez eksperta: większy pierwszy
    monkeypatch.setattr('news.ekspert_ai.watched_models', lambda: {'glm-4.5-air'})
    assert [c['model'] for c in recruiter.sieve(found)] == ['z-ai/glm-4.5-air-106b:free', 'deepseek/deepseek-v4-671b:free']


def _candidate(provider='hf', model='test/model-70b'):
    return {'provider': provider, 'model': model, 'company': 'Meta', 'context': 32000,
            'polish': False, 'new_company': True, 'billions': 70}


def _failure(provider='hf', age=timedelta(), code='http_402'):
    return CouncilRecruitment.objects.create(
        kind='candidate', provider=provider, model=f'model-{CouncilRecruitment.objects.count()}',
        decision='deferred', created_at=timezone.now() - age, reason=code,
        exam={'answered': 0, 'items': 8, 'answers': [{'note': code}]})


@pytest.mark.django_db
@pytest.mark.parametrize(('count', 'days'), [(2, 1), (3, 2), (4, 4), (5, 7)])
def test_provider_breaker_backoff_and_expiry(monkeypatch, count, days):
    now = timezone.now()
    monkeypatch.setattr(recruiter.timezone, 'now', lambda: now)
    for index in range(count):
        _failure(age=timedelta(minutes=index))
    outage, = recruiter.skipped_providers()
    assert outage['provider'] == 'hf'
    assert outage['days'] == days
    assert outage['failures'] == count
    assert '402' in outage['reason']
    monkeypatch.setattr(recruiter.timezone, 'now', lambda: now + timedelta(days=days))
    assert recruiter.skipped_providers() == []


@pytest.mark.django_db
def test_provider_breaker_assessed_exam_resets_failures():
    _failure(age=timedelta(hours=2))
    _failure(age=timedelta(hours=1))
    CouncilRecruitment.objects.create(provider='hf', model='assessed', decision='would_reject',
                                      exam={'answered': 6, 'passed': False})
    assert recruiter.skipped_providers() == []


@pytest.mark.django_db
def test_provider_breaker_filters_supplier_not_model(monkeypatch):
    _failure()
    _failure()
    monkeypatch.setattr('news.clinic_council._members', lambda *a: [])
    monkeypatch.setattr('news.ekspert_ai.watched_models', lambda: set())
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: True)
    found = [_candidate('hf', 'meta/llama-3.3-70b-instruct'),
             _candidate('nim', 'meta/llama-3.3-70b-instruct')]
    assert [c['provider'] for c in recruiter.sieve(found)] == ['nim']


@pytest.mark.django_db
@pytest.mark.parametrize('code', ['http_402', 'http_400', 'http_503', 'ReadTimeout'])
def test_failed_probe_skips_exam_votes_and_charter(monkeypatch, code):
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [_candidate()])
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [object()] * 8)
    probe = Mock(return_value=code)
    monkeypatch.setattr(recruiter, '_probe', probe)
    for name in ('examine', 'vote', 'accept_charter'):
        monkeypatch.setattr(recruiter, name, Mock(side_effect=AssertionError(name)))
    assert recruiter.recruit()['decision'] == 'deferred'
    probe.assert_called_once_with(('hf', 'test/model-70b'))
    entry = CouncilRecruitment.objects.get()
    assert code in entry.reason
    assert entry.exam['probe'] is True


@pytest.mark.django_db
@pytest.mark.parametrize('budget', ['1', '3'])
def test_run_moves_to_another_supplier_after_failed_probe(monkeypatch, budget):
    monkeypatch.setenv('COUNCIL_RECRUITER_PER_NIGHT', budget)
    monkeypatch.setattr(recruiter, 'health', lambda: [])
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    candidates = [_candidate('hf', 'first'), _candidate('hf', 'second'), _candidate('nim', 'third')]
    monkeypatch.setattr(recruiter, 'sieve', lambda found: candidates)
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [object()] * 8)
    probe = Mock(return_value='http_402')
    monkeypatch.setattr(recruiter, '_probe', probe)
    monkeypatch.setattr(recruiter, 'examine', Mock(side_effect=AssertionError('no exam')))
    result = recruiter.run()
    assert [c.args[0] for c in probe.call_args_list] == [('hf', 'first'), ('nim', 'third')]
    assert {p['provider'] for p in result['skipped_providers']} == {'hf', 'nim'}


def _diagnoses(count=30):
    return [SimpleNamespace(pk=i, verdict='no_spin' if i % 5 == 0 else 'spin',
                            intensity=0 if i % 5 == 0 else 80,
                            post=SimpleNamespace(text=f'post {i}', camp_at_collection='government' if i % 2 else 'opposition'))
            for i in range(1, count + 1)]


def test_exam_selection_layers_shared_core_and_rotation(monkeypatch):
    rows = _diagnoses()
    query = Mock()
    query.filter.return_value.select_related.return_value.order_by.return_value = rows
    monkeypatch.setattr('news.clinic.published_diagnoses', lambda: query)
    monkeypatch.setenv('COUNCIL_EXAM_SIZE', '8')
    exams = [recruiter.exam_items(name) for name in ('alpha', 'beta', 'gamma', 'delta')]
    for items in exams:
        assert len(items) == len({d.pk for d in items}) == 8
        assert sum(d.post.camp_at_collection == 'government' for d in items) >= 3
        assert sum(d.post.camp_at_collection == 'opposition' for d in items) >= 3
        assert any(d.verdict == 'no_spin' for d in items)
        assert any(d.intensity >= 70 for d in items)
        assert items[:5] == exams[0][:5]
    assert len({tuple(d.pk for d in items[5:]) for items in exams}) > 1
    assert recruiter.exam_items('alpha') == exams[0]


@pytest.mark.parametrize(('repeat_verdict', 'repeat_intensity', 'consistent'),
                         [('spin', 95, True), ('spin', 96, False), ('no_spin', 70, False)])
def test_exam_consistency_bias_and_roles(monkeypatch, repeat_verdict, repeat_intensity, consistent):
    monkeypatch.setenv('COUNCIL_EXAM_ANSWERED', '0.75')
    monkeypatch.setenv('COUNCIL_EXAM_AGREEMENT', '0.6')
    monkeypatch.setenv('COUNCIL_EXAM_MAE', '20')
    items = _diagnoses(8)
    for item in items:
        item.verdict, item.intensity = 'spin', 60
    opinions = [{'status': 'odpowiedział', 'verdict': 'spin', 'intensity': 70, 'claims': ['Tekst po polsku.']}
                for _ in items]
    opinions.append({'status': 'odpowiedział', 'verdict': repeat_verdict, 'intensity': repeat_intensity})
    opinion = Mock(side_effect=opinions)
    monkeypatch.setattr('news.clinic_council._opinion', opinion)
    monkeypatch.setattr('news.clinic_ai.looks_polish', lambda text: True)
    monkeypatch.setattr(recruiter, '_exam_prompt', lambda d: str(d.pk))
    exam = recruiter.examine(('nim', 'candidate'), items)
    assert opinion.call_count == 9
    assert opinion.call_args_list[0].args == opinion.call_args_list[-1].args
    assert exam['answered'] == exam['items'] == len(exam['answers']) == 8
    assert exam['bias'] == exam['mae'] == 10
    assert exam['passed'] is True
    assert exam['consistency']['passed'] is consistent
    votes = [{'admit': True, 'roles': ['recenzent', 'przewodniczący']} for _ in range(2)]
    roles = recruiter.roles_for(_candidate(), exam, votes)
    assert ('recenzent' in roles) is consistent
    assert ('przewodniczący' in roles) is consistent
    assert 'członek' in roles


@pytest.mark.django_db
def test_weekly_summary_and_command_notify(monkeypatch):
    from django.core.management import call_command
    _failure()
    _failure()
    _failure('inception', code='http_400')
    _failure('nim', code='ReadTimeout')
    _failure('obsolete', age=timedelta(days=8))
    summary = recruiter.weekly_summary()
    assert 'Hugging Face (hf): deferred: 2' in summary
    assert 'doładuj konto albo wyłącz dostawcę' in summary
    assert 'Inception' in summary and 'schematu JSON' in summary
    assert 'NVIDIA' in summary and 'status dostawcy' in summary
    assert 'Dostawcy pomijani:' in summary
    assert 'obsolete' not in summary
    notify = Mock(return_value=True)
    monkeypatch.setattr(recruiter, '_notify', notify)
    monkeypatch.setattr(recruiter, 'run', Mock(side_effect=AssertionError('summary only')))
    output = StringIO()
    call_command('council_recruiter', '--podsumowanie', stdout=output)
    assert summary in output.getvalue()
    notify.assert_called_once_with('podsumowanie tygodnia', summary)
    notify.reset_mock()
    call_command('council_recruiter', '--podsumowanie', '--dry-run', stdout=StringIO())
    notify.assert_not_called()


@pytest.mark.parametrize('configured', [True, False])
def test_discover_mistral_and_cloudflare_chat_only(monkeypatch, configured):
    monkeypatch.setattr(recruiter.registry, 'configured', lambda member: configured)
    monkeypatch.setattr(recruiter.registry, 'credentials', lambda service: 'fake' if service in ('mistral', 'cloudflare') else '')
    monkeypatch.setattr(recruiter.registry, 'endpoint', lambda service: 'https://catalog.invalid/ai/v1/chat/completions')
    monkeypatch.setattr('news.zwiadowca_rozwiazan.recruiter_candidates', lambda: [])
    def catalog(url, **kwargs):
        if 'mistral' in url:
            return {'data': [{'id': 'mistral-large-latest', 'capabilities': {'completion_chat': True}},
                             {'id': 'mistral-embed', 'capabilities': {'completion_chat': False}}]}
        if 'catalog.invalid' in url:
            return {'result': [{'name': '@cf/meta/llama-3.3-70b-instruct-fp8-fast', 'task': {'name': 'Text Generation'}},
                               {'name': '@cf/embedding', 'task': {'name': 'Text Embeddings'}},
                               {'name': '@hf/chat', 'task': {'name': 'Text Generation'}}]}
        return {'data': []}
    get = Mock(side_effect=catalog)
    monkeypatch.setattr(recruiter, '_get', get)
    found = recruiter.discover()
    if configured:
        assert {(c['provider'], c['model']) for c in found} == {
            ('mistral', 'mistral-large-latest'), ('cloudflare', '@cf/meta/llama-3.3-70b-instruct-fp8-fast')}
    else:
        assert found == []
        assert not any('mistral' in c.args[0] or 'catalog.invalid' in c.args[0] for c in get.call_args_list)


def test_exam_selection_uses_available_three_five_split(monkeypatch):
    rows = _diagnoses(8)
    for index, row in enumerate(rows):
        row.post.camp_at_collection = 'government' if index < 3 else 'opposition'
    query = Mock()
    query.filter.return_value.select_related.return_value.order_by.return_value = rows
    monkeypatch.setattr('news.clinic.published_diagnoses', lambda: query)
    monkeypatch.setenv('COUNCIL_EXAM_SIZE', '8')
    items = recruiter.exam_items('candidate')
    assert len(items) == 8
    assert sum(d.post.camp_at_collection == 'government' for d in items) == 3


def test_vote_describes_signed_bias(monkeypatch):
    monkeypatch.setattr('news.clinic_council._members', lambda *a: [('nim', 'voter')])
    monkeypatch.setattr(recruiter.registry, 'select_members', lambda members, **kwargs: members)
    ask = Mock(return_value={'admit': False, 'roles': [], 'reason': 'test'})
    monkeypatch.setattr('news.clinic_council.ask', ask)
    recruiter.vote(_candidate(), {'answered': 8, 'items': 8, 'agreement': 1, 'mae': 10,
                                 'bias': -10, 'techniques_avg': 1, 'polish': True,
                                 'passed': True, 'consistency': {'passed': True}})
    summary = ask.call_args.args[2]
    assert 'bias' in summary and '-10' in summary and 'łagodniejszy' in summary


@pytest.mark.parametrize(('answered', 'passed'), [(5, False), (6, True)])
def test_exam_answer_gate_is_fraction_and_repeat_does_not_count(monkeypatch, answered, passed):
    items = _diagnoses(8)
    opinions = [{'status': 'odpowiedział', 'verdict': d.verdict, 'intensity': d.intensity}
                if i < answered else {'status': 'błąd', 'note': 'http_429'} for i, d in enumerate(items)]
    opinions.append(opinions[0])
    monkeypatch.setattr('news.clinic_council._opinion', Mock(side_effect=opinions))
    monkeypatch.setattr(recruiter, '_exam_prompt', lambda d: str(d.pk))
    monkeypatch.setenv('COUNCIL_EXAM_ANSWERED', '0.75')
    monkeypatch.setenv('COUNCIL_EXAM_AGREEMENT', '0.6')
    monkeypatch.setenv('COUNCIL_EXAM_MAE', '20')
    exam = recruiter.examine(('nim', 'candidate'), items)
    assert exam['answered'] == answered
    assert exam['passed'] is passed


@pytest.mark.parametrize(('value', 'expected'), [('1', 5), ('5', 5), ('12', 12), ('99', 12),
                                                ('invalid', 8), ('nan', 8)])
def test_exam_size_configuration_is_bounded(monkeypatch, value, expected):
    monkeypatch.setenv('COUNCIL_EXAM_SIZE', value)
    assert recruiter.exam_size() == expected


@pytest.mark.parametrize(('answered', 'agreement', 'mae', 'expected'), [
    ('0.1', '0.2', '90', {'answered': 0.75, 'agreement': 0.6, 'mae': 20}),
    ('0.9', '0.8', '10', {'answered': 0.9, 'agreement': 0.8, 'mae': 10}),
    ('nan', 'invalid', 'nan', {'answered': 0.75, 'agreement': 0.6, 'mae': 20}),
])
def test_exam_configuration_cannot_weaken_hard_gates(monkeypatch, answered, agreement, mae, expected):
    monkeypatch.setenv('COUNCIL_EXAM_ANSWERED', answered)
    monkeypatch.setenv('COUNCIL_EXAM_AGREEMENT', agreement)
    monkeypatch.setenv('COUNCIL_EXAM_MAE', mae)
    assert recruiter.exam_gates() == expected


def test_missing_repeat_answer_blocks_senior_roles(monkeypatch):
    items = _diagnoses(8)
    opinions = [{'status': 'odpowiedział', 'verdict': d.verdict, 'intensity': d.intensity}
                for d in items] + [{'status': 'błąd', 'note': 'http_503'}]
    monkeypatch.setattr('news.clinic_council._opinion', Mock(side_effect=opinions))
    monkeypatch.setattr(recruiter, '_exam_prompt', lambda d: str(d.pk))
    monkeypatch.setenv('COUNCIL_EXAM_ANSWERED', '0.75')
    monkeypatch.setenv('COUNCIL_EXAM_AGREEMENT', '0.6')
    monkeypatch.setenv('COUNCIL_EXAM_MAE', '20')
    exam = recruiter.examine(('nim', 'candidate'), items)
    assert exam['passed'] is True
    assert exam['consistency']['passed'] is False
    votes = [{'admit': True, 'roles': ['recenzent', 'przewodniczący']} for _ in range(2)]
    assert recruiter.roles_for(_candidate(), exam, votes) == ['członek']


@pytest.mark.django_db
def test_no_diagnoses_does_not_probe_or_record_provider_failure(monkeypatch):
    monkeypatch.setattr(recruiter, 'discover', lambda: [])
    monkeypatch.setattr(recruiter, 'sieve', lambda found: [_candidate()])
    monkeypatch.setattr(recruiter, 'exam_items', lambda *a: [])
    probe = Mock(side_effect=AssertionError('no probe without exam material'))
    monkeypatch.setattr(recruiter, '_probe', probe)
    assert recruiter.recruit()['status'] == 'insufficient_items'
    probe.assert_not_called()
    assert not CouncilRecruitment.objects.exists()
