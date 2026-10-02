from unittest.mock import patch

import pytest

from news import agents_common as common
from news import seba
from news.agent_models import AgentNote, SebaReview
from news.clinic_ai import ClinicAIError

pytestmark = pytest.mark.django_db
MEMBER = ('mistral', 'mistral-large-latest')


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv('SEBA_ENABLED', 'true')
    monkeypatch.setenv('SEBA_DAILY_CALLS', '20')
    with patch('news.seba.choose', return_value=MEMBER), \
         patch('requests.post', side_effect=AssertionError('No live models')):
        yield


def idea(**scores):
    return AgentNote.objects.create(agent='strateg', kind='idea', title='Pomysł', body='Plan',
        scores={'author': {'provider': 'groq', 'model': 'qwen', 'company': 'Alibaba'}, **scores})


def verdict(score, word):
    return {'score': score, 'verdict': word, 'reason': 'Bo tak', **{k: 'Opis' for k in seba.DIMENSIONS}}


def test_new_idea_is_hidden_until_seba_passes():
    note = idea()
    assert not seba.can_show(note)
    with patch.object(common, 'ask', return_value=verdict(8, 'przepuść')):
        assert seba.process(note.seba_review.pk) == 'passed'
    assert seba.can_show(note)
    assert AgentNote.objects.get(pk=note.pk).critiques[-1]['role'] == 'Seba'


def test_two_rounds_then_rejected():
    note = idea()
    job = note.seba_review
    with patch.object(common, 'agent_window', return_value=True), \
         patch.object(common, 'ask', side_effect=[verdict(3, 'popraw'), {'title': 'Lepszy', 'body': 'Lepszy plan'},
                                                  verdict(4, 'odrzuć')]):
        assert seba.process(job.pk) == 'queued' or SebaReview.objects.get(pk=job.pk).phase == 'revision'
        seba.process(job.pk)
        assert seba.process(job.pk) == 'rejected'
    job.refresh_from_db()
    assert job.rounds == 2 and not seba.can_show(note)


def test_daily_limit_queues_instead_of_error(monkeypatch):
    monkeypatch.setenv('SEBA_DAILY_CALLS', '0')
    note = idea()
    with patch.object(common, 'ask') as ask:
        assert seba.process(note.seba_review.pk) == 'queued'
        ask.assert_not_called()
    assert 'limit' in SebaReview.objects.get(pk=note.seba_review.pk).last_error


def test_rate_limit_429_queues():
    note = idea()
    with patch.object(common, 'ask', side_effect=ClinicAIError('groq_429')):
        assert seba.process(note.seba_review.pk) == 'queued'
    assert SebaReview.objects.get(pk=note.seba_review.pk).status == 'queued'


def test_charter_violation_never_passes():
    note = idea(violations=['stronniczość'])
    with patch.object(common, 'ask', return_value=verdict(10, 'przepuść')):
        assert seba.process(note.seba_review.pk) == 'rejected'
