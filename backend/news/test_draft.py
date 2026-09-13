import json
from datetime import timedelta

import pytest
import responses
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from news.draft import EditorialDraftView
from news.models import Article, Source, Thread

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def config(monkeypatch):
    cache.clear()
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-not-real')
    monkeypatch.setenv('DR_SPIN_MODEL', 'test-model')
    yield
    cache.clear()


@pytest.fixture
def records():
    source = Source.objects.create(name='Publisher', url='https://example.test')
    return [Article.objects.create(source=source, title=f'Event {i}', url=f'https://example.test/{i}',
            published_date=timezone.now() - timedelta(days=i) if i < 2 else None) for i in range(3)]


def call(records, staff=True, data=None):
    request = APIRequestFactory().post('/api/editor/draft/', data or {'topic': 'Temat', 'article_ids': [a.pk for a in records]}, format='json')
    user, _ = get_user_model().objects.get_or_create(username='editor', defaults={'is_staff': staff})
    force_authenticate(request, user=user)
    return EditorialDraftView.as_view()(request)


def reply(ids, **extra):
    return {'status': 'completed', 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps({'article_ids': ids})}]}], **extra}


@responses.activate
def test_permissions_and_disabled_never_pay(records, monkeypatch):
    assert call(records, staff=False).status_code == 403
    user = get_user_model().objects.get(username='editor')
    user.is_staff = True
    user.save()
    monkeypatch.delenv('OPENAI_API_KEY')
    assert call(records).data['status'] == 'disabled'
    assert not responses.calls


@responses.activate
def test_chronological_draft_preserves_sources_and_never_publishes(records):
    responses.post('https://api.openai.com/v1/responses', json=reply([a.pk for a in records]))
    result = call(records)
    assert result.status_code == 200
    assert result.data['article_ids'] == [records[1].pk, records[0].pk, records[2].pk]
    assert result.data['undated_article_ids'] == [records[2].pk]
    assert result.data['requires_review'] and result.data['basis'] == 'stored_metadata'
    assert Thread.objects.count() == 0 and Article.objects.count() == 3
    sent = json.loads(responses.calls[0].request.body)
    assert sent['store'] is False and sent['max_output_tokens'] == 1200
    assert 'tools' not in sent
    assert 'description' not in json.loads(sent['input'])['candidates'][0]


@pytest.mark.parametrize('ids', [[99999], [True], [1, 1], list(range(1, 17))])
@responses.activate
def test_rejects_invented_duplicate_or_oversize_model_output(records, ids):
    responses.post('https://api.openai.com/v1/responses', json=reply(ids))
    assert call(records).status_code == 502
    assert Thread.objects.count() == 0


@responses.activate
def test_provider_failure_is_not_retried_or_exposed(records):
    responses.post('https://api.openai.com/v1/responses', status=429, json={'secret': 'sensitive provider detail'})
    result = call(records)
    assert result.status_code == 502 and 'secret' not in str(result.data)
    assert len(responses.calls) == 1


@responses.activate
def test_invalid_candidates_and_paid_throttle(records):
    assert call(records, data={'topic': 'A', 'article_ids': [999999]}).status_code == 400
    assert call(records, data={'topic': 'A', 'article_ids': [records[0].pk] * 61}).status_code == 400
    cache.set('editorial-draft-inflight', True, 90)
    assert call(records).status_code == 429
    assert not responses.calls


@responses.activate
def test_incomplete_model_result_rejected(records):
    responses.post('https://api.openai.com/v1/responses', json=reply([records[0].pk], status='incomplete'))
    assert call(records).status_code == 502

@responses.activate
def test_daily_budget_survives_cache_clear(records, monkeypatch):
    monkeypatch.setenv('DR_SPIN_DAILY_CALL_LIMIT', '1')
    responses.post('https://api.openai.com/v1/responses', json=reply([records[0].pk]))
    assert call(records).status_code == 200
    cache.clear()
    result = call(records)
    assert result.status_code == 429 and result.data['status'] == 'budget_exhausted'
    assert len(responses.calls) == 1
