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
    assert not CouncilSeat.objects.exists()
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
