"""Rekruter Konsylium: zawieszanie martwych członków, powroty, sito kandydatów, role i tryb próbny."""
from datetime import timedelta
from unittest.mock import patch

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
    exam = {'polish': True, 'agreement': 0.8, 'mae': 11}
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
    monkeypatch.setattr(recruiter, 'exam_items', lambda: [])
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
    monkeypatch.setattr(recruiter, 'exam_items', lambda: [])
    monkeypatch.setattr(recruiter, 'examine', lambda member, items: {
        'items': 5, 'answered': 2, 'agreement': 0.2, 'mae': 40, 'techniques_avg': 0, 'polish': None, 'passed': False, 'answers': []})
    with patch.object(recruiter, 'vote', side_effect=AssertionError('no vote on failed exam')):
        assert recruiter.recruit()['decision'] == 'would_reject'


@pytest.mark.django_db
def test_run_examines_several_candidates_per_night(monkeypatch):
    monkeypatch.setenv('COUNCIL_RECRUITER_PER_NIGHT', '3')
    monkeypatch.setattr(recruiter, 'health', lambda: [])
    calls = iter([{'status': 'ok', 'model': 'a'}, {'status': 'ok', 'model': 'b'}, {'status': 'no_candidates'}, {'status': 'ok'}])
    monkeypatch.setattr(recruiter, 'recruit', lambda dry_run=False: next(calls))
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
    monkeypatch.setattr(recruiter, 'exam_items', lambda: [])
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
