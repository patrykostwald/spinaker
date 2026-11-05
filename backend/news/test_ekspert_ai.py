import json
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache

from news import ekspert_ai, thread_review
from news.agent_models import AgentNote

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 5, 3, 40, tzinfo=ZoneInfo('Europe/Warsaw'))
MEMBERS = [('groq', 'openai/gpt-oss-20b'), ('nim', 'nvidia/nemotron'), ('groq', 'qwen/qwen')]
URL = 'http://arxiv.org/abs/2610.00001'


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('news.council_registry.configured', return_value=True), \
         patch('news.clinic_council._members', return_value=MEMBERS), \
         patch('news.council_recruiter._notify', return_value=True), \
         patch('requests.post', side_effect=AssertionError('No live models')), \
         patch('requests.get', side_effect=AssertionError('No live sources')):
        yield
    cache.clear()


def finding():
    return AgentNote.objects.create(agent='pielgrzym', kind='finding', title='Wędrówka: kalibracja',
        body=json.dumps({'findings': [{'title': 'Kalibracja ocen LLM', 'url': URL, 'summary': 'Nowa metoda.'}]}))


def brief(model='new-model-70b', url=URL):
    return {'summary': 'Kalibracja ważna dla siły spinu.',
            'developments': [{'title': 'Kalibracja ocen LLM', 'why': 'Mniej skrajnych ocen.', 'source_url': url},
                             {'title': 'Zmyślony przełom', 'why': 'Bez źródła.', 'source_url': 'https://example.com/x'}],
            'model_watch': [{'model': model, 'why': 'Dobre wyniki.', 'source_url': url}],
            'method_risks': ['Modele dzielą te same błędy.']}


def test_brief_keeps_only_grounded_points_and_checker_can_remove():
    finding()
    check = {'ok': True, 'remove': ['NEW-MODEL-70B'], 'reason': 'Model bez potwierdzenia jakości.'}
    with patch('news.clinic_council.ask', side_effect=[brief(), check]) as ask:
        note = ekspert_ai.step(force=True)
    body = note.scores
    assert 'Co nowego:' in note.body and 'Kalibracja ocen LLM' in note.body
    assert note.agent == 'ekspert' and note.status == 'new'
    assert [d['title'] for d in body['developments']] == ['Kalibracja ocen LLM']  # bez źródła wypada
    assert body['model_watch'] == []  # drugi ekspert usunął
    assert len({call.args[0][0] + call.args[0][1] for call in ask.call_args_list}) == 2
    assert note.sources == [URL]


def test_checker_rejection_hides_brief_and_weekly_rhythm():
    finding()
    with patch('news.clinic_council.ask', side_effect=[brief(), {'ok': False, 'remove': [], 'reason': 'Przesada.'}]):
        note = ekspert_ai.step(force=True)
    assert note.status == 'rejected' and ekspert_ai.latest() is None
    with patch('news.clinic_council.ask', side_effect=[brief(), {'ok': True, 'remove': [], 'reason': 'Zgodne.'}]):
        good = ekspert_ai.step(force=True)
    with patch('news.clinic_council.ask') as ask:
        assert ekspert_ai.step() == good  # mniej niż 6 dni: bez nowych zapytań
        ask.assert_not_called()


def test_no_findings_means_no_model_call():
    with patch('news.clinic_council.ask') as ask, pytest.raises(ekspert_ai.common.WindowClosed):
        ekspert_ai.step(force=True)
    ask.assert_not_called()


def test_watched_models_and_reviewer_context():
    AgentNote.objects.create(agent='ekspert', kind='report', status='new', title='Stan', body='Stan', scores=brief())
    assert ekspert_ai.watched_models() == {'new-model-70b'}
    assert ekspert_ai.context_for({'title': 'Nowy model AI ocenia wpisy'})['summary'].startswith('Kalibracja')
    assert ekspert_ai.context_for({'title': 'Podatek od zysków paliwowych'}) is None


def test_review_payload_drops_duplicate_original_and_trims_evidence():
    texts = {'title': 'Tytuł', 'description': 'Opis'}
    data = {'texts': texts, 'original': dict(texts), 'evidence': ['x' * 5000] * 4, 'boxes': [{'body': 'y' * 4000}] * 4}
    fitted = thread_review.fit(data)
    assert 'original' not in fitted and fitted['texts'] == texts
    assert thread_review._size(fitted) <= thread_review.SAFE_SIZE
