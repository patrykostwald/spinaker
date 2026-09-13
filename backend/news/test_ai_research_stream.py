import json
import uuid
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from django.core.cache import cache
from rest_framework.test import APIRequestFactory

from news.ai_research_stream import AIResearchStreamView, AIResearchSourcesView, stream_research
from news.models import AIResearchCall, Article, ArchiveJob, ImportState, Source
from news.test_ai_research import provider_result


@pytest.fixture
def setup(db, monkeypatch):
    cache.clear()
    session = Mock()
    session.enrich.return_value = {'articles': []}
    monkeypatch.setitem(sys.modules, 'news.research_metadata', SimpleNamespace(ResearchMetadataSession=Mock(return_value=session)))
    monkeypatch.setenv('DR_SPIN_RESEARCH_ENABLED', 'true')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret-never-live')
    monkeypatch.setenv('DR_SPIN_RESEARCH_MODEL', 'test-model')
    return Source.objects.create(name='Publisher', url='https://example.org', is_active=True)


def request(data=None, view=AIResearchStreamView):
    data = data or {'query': 'history', 'mode': 'context', 'request_id': str(uuid.uuid4())}
    return view.as_view()(APIRequestFactory().post('/api/ai/research/stream/', data, format='json'))


def events():
    result = provider_result()
    result.update(usage={'input_tokens': 50, 'output_tokens': 20}, model='test-model')
    item = dict(result['output'][0], id='ws_1', status='completed')
    return [{'type': 'response.web_search_call.searching', 'item_id': 'ws_1'},
            {'type': 'response.output_text.delta', 'delta': 'UNVERIFIED SECRET PROSE'},
            {'type': 'response.output_item.done', 'item': item},
            {'type': 'response.completed', 'response': result}]


def provider(monkeypatch, data=None, error=None):
    class Stream:
        status_code = 200
        closed = False
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
        def iter_lines(self, **kwargs):
            for item in data if data is not None else events():
                yield ('data: ' + json.dumps(item)).encode()
                yield b''
            if error:
                raise error
    stream = Stream()
    post = Mock(return_value=stream)
    monkeypatch.setattr('news.ai_research_stream.requests.post', post)
    return post, stream


def test_true_stream_progress_precedes_result_and_no_raw_prose(setup, monkeypatch):
    post, transport = provider(monkeypatch)
    response = request()
    iterator = iter(response.streaming_content)
    first = next(iterator).decode()
    assert 'event: progress' in first
    assert 'result' not in first
    rest = b''.join(iterator).decode()
    assert 'event: sources' in rest and 'event: result' in rest and 'event: done' in rest
    assert 'UNVERIFIED SECRET PROSE' not in rest
    assert post.call_args.kwargs['json']['stream'] is True
    assert post.call_args.kwargs['json']['max_tool_calls'] == 4
    assert transport.closed
    assert Article.objects.count() == 0
    assert ArchiveJob.objects.get().url == 'https://example.org/a'
    audit = AIResearchCall.objects.get()
    assert (audit.input_tokens, audit.output_tokens, audit.web_search_calls) == (50, 20, 1)
    assert audit.status == 'completed'


def test_retry_uuid_cannot_buy_second_call_and_shares_budget(setup, monkeypatch):
    post, _ = provider(monkeypatch)
    data = {'query': 'private topic', 'mode': 'context', 'request_id': str(uuid.uuid4())}
    response = request(data)
    b''.join(response.streaming_content)
    assert request(data).status_code == 409
    assert post.call_count == 1
    assert ImportState.objects.get(name='web-ai-daily-budget').cursor['attempts'] == 1
    assert 'private topic' not in repr(list(ImportState.objects.values()))
    assert 'test-secret' not in repr(list(AIResearchCall.objects.values()))


def test_no_key_and_public_verify_never_reserve(setup, monkeypatch):
    post, _ = provider(monkeypatch)
    monkeypatch.delenv('OPENAI_API_KEY')
    assert request().status_code == 503
    assert request({'query': 'x', 'mode': 'verify'}).status_code == 403
    assert not ImportState.objects.exists()
    post.assert_not_called()


def test_disconnect_closes_transport_and_records_unknown_usage(setup, monkeypatch):
    _, transport = provider(monkeypatch)
    stream = stream_research('topic', 'context', {'example.org': setup})
    assert 'progress' in next(stream)
    stream.close()
    audit = AIResearchCall.objects.get()
    assert transport.closed and audit.status == 'disconnected'
    assert audit.input_tokens is None and audit.output_tokens is None
    assert audit.web_search_calls == 1


def test_timeout_emits_error_done_and_does_not_invent_zero_usage(setup, monkeypatch):
    provider(monkeypatch, data=[], error=requests.Timeout())
    text = b''.join(request().streaming_content).decode()
    assert 'event: error' in text and 'event: done' in text and 'event: result' not in text
    audit = AIResearchCall.objects.get()
    assert audit.status == 'transport_error' and audit.web_search_calls is None


def test_unallowed_tool_url_and_invalid_citation_not_emitted(setup, monkeypatch):
    result = provider_result('https://evil.example/a')
    provider(monkeypatch, data=[{'type': 'response.output_item.done', 'item': result['output'][0]},
                                {'type': 'response.completed', 'response': result}])
    text = b''.join(request().streaming_content).decode()
    assert 'evil.example' not in text and 'event: error' in text
    assert not ArchiveJob.objects.exists()


def test_metadata_refresh_read_only_bounded_disabled_sources_hidden(setup, monkeypatch):
    post, _ = provider(monkeypatch)
    response = request({'urls': ['https://example.org/a']}, AIResearchSourcesView)
    assert response.status_code == 200 and response.data['sources'][0]['published_date'] is None
    assert not ImportState.objects.exists() and not ArchiveJob.objects.exists()
    setup.is_active = False
    setup.save()
    assert request({'urls': ['https://example.org/a']}, AIResearchSourcesView).data == {'articles': [], 'sources': []}
    assert request({'urls': ['https://example.org/a'] * 31}, AIResearchSourcesView).status_code == 400
    post.assert_not_called()


def test_inflight_exclusion_hides_newly_discovered_source(setup, monkeypatch):
    provider(monkeypatch)
    response = request()
    iterator = iter(response.streaming_content)
    next(iterator)
    setup.is_active = False
    setup.save()
    text = b''.join(iterator).decode()
    assert 'example.org' not in text and 'event: result' not in text
    assert not ArchiveJob.objects.exists()


def test_disconnect_after_result_skips_enrichment(setup, monkeypatch):
    _, transport = provider(monkeypatch)
    stream = stream_research('topic', 'context', {'example.org': setup})
    for item in stream:
        if 'event: result' in item:
            break
    stream.close()
    sys.modules['news.research_metadata'].ResearchMetadataSession.assert_not_called()
    assert transport.closed
    assert AIResearchCall.objects.get().status == 'completed'


def test_metadata_after_result_with_bounds_and_provider_closed(setup, monkeypatch):
    _, transport = provider(monkeypatch)
    helper = sys.modules['news.research_metadata'].ResearchMetadataSession
    def enrich(urls):
        assert transport.closed and len(urls) <= 15
        return {'articles': [{'id': 123, 'title': 'Publisher metadata'}]}
    helper.return_value.enrich.side_effect = enrich
    text = b''.join(request().streaming_content).decode()
    assert text.index('event: result') < text.index('event: metadata') < text.index('event: done')
    assert 'Publisher metadata' in text
    assert helper.call_args.kwargs == {'max_urls': 15, 'deadline_seconds': 20}


def test_metadata_error_preserves_validated_research(setup, monkeypatch):
    provider(monkeypatch)
    sys.modules['news.research_metadata'].ResearchMetadataSession.side_effect = RuntimeError('private error')
    text = b''.join(request().streaming_content).decode()
    assert 'event: result' in text and 'event: done' in text and 'private error' not in text
    assert AIResearchCall.objects.get().status == 'completed'


def test_registered_api_route_stream_and_readonly_refresh(setup, monkeypatch):
    from rest_framework.test import APIClient
    post, _ = provider(monkeypatch)
    client = APIClient()
    response = client.post('/api/ai/research/stream/',
        {'query': 'history', 'mode': 'context', 'request_id': str(uuid.uuid4())}, format='json')
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/event-stream')
    assert response['X-Accel-Buffering'] == 'no'
    text = b''.join(response.streaming_content).decode()
    assert text.count('event: result') == 1 and text.count('event: done') == 1
    refresh = client.post('/api/ai/research/sources/', {'urls': ['https://example.org/a']}, format='json')
    assert refresh.status_code == 200 and refresh.data['sources'][0]['status'] == 'discovered'
    assert post.call_count == 1
