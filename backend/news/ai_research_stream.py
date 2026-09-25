"""Responses SSE: only tool provenance is public before citation validation.

Protocol: https://developers.openai.com/api/docs/guides/streaming-responses
No provider retry: an interrupted call can have incurred usage.
"""
import hashlib
import json
import os
import re
import time
import uuid

import requests
from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from news.ai_research import (AIResearchView, RULES, ResearchError, archive_result,
                              audit_usage, reserve_attempt, validate_result)
from news.external_search import allowed_sources, match_source
from news.models import AIResearchCall, ImportState
from scraper.queue import enqueue_requested_url
from scraper.utils import safe_url
from news.schema import json_view


class DuplicateRequest(APIException):
    status_code = 409
    default_detail = 'To wyszukiwanie zostało już przyjęte. Nie uruchomiono drugiego płatnego wywołania.'


def sse(event, data):
    return 'event: ' + event + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n'


def provider_events(response, deadline):
    """Bound cumulative bytes, individual lines and wall time, including ignored deltas."""
    size, lines = 0, []
    for raw in response.iter_lines(chunk_size=1024):
        size += len(raw) + 1
        if size > 1048576 or len(raw) > 524288 or time.monotonic() > deadline:
            raise ResearchError()
        line = raw.decode('utf-8')
        if not line:
            if lines:
                body = '\n'.join(lines)
                lines = []
                if body != '[DONE]':
                    event = json.loads(body)
                    if not isinstance(event, dict):
                        raise ResearchError()
                    yield event
            continue
        if line.startswith('data:'):
            lines.append(line[5:].lstrip(' '))


def discovered_sources(item, sources, seen):
    references = []
    for candidate in item.get('action', {}).get('sources', []):
        url = safe_url(candidate.get('url'))
        publisher = match_source(url, sources) if url else None
        if not publisher or len(url) > 1024 or url in seen or len(seen) >= 30:
            continue
        seen.add(url)
        enqueue_requested_url(url, publisher)
        # Tool sources establish a URL, not publication metadata.
        references.append({'url': url, 'source_name': publisher.name,
                           'title': url, 'published_date': None, 'status': 'discovered'})
    return references


def stream_research(query, mode, sources):
    requested_model = os.environ['DR_SPIN_RESEARCH_MODEL']
    model = requested_model if re.fullmatch(r'[A-Za-z0-9._:-]{1,120}', requested_model) and not requested_model.startswith('sk-') else 'invalid-model-setting'
    audit = AIResearchCall.objects.create(mode=mode, model=model)
    payload = {'model': requested_model, 'store': False, 'stream': True,
               'max_output_tokens': 4000, 'max_tool_calls': 4, 'instructions': RULES,
               'tools': [{'type': 'web_search', 'filters': {'allowed_domains': sorted(sources)},
                          'search_context_size': 'low'}],
               'tool_choice': 'required', 'include': ['web_search_call.action.sources'],
               'input': json.dumps({'mode': mode, 'topic_or_statement': query}, ensure_ascii=False)}
    seen, calls = set(), set()
    complete = False
    try:
        deadline = time.monotonic() + 100
        with requests.post('https://api.openai.com/v1/responses', json=payload,
                           headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']},
                           timeout=(5, 15), allow_redirects=False, stream=True) as response:
            audit.http_status = response.status_code
            if response.status_code != 200:
                audit.status = 'http_error'
                raise ResearchError()
            for event in provider_events(response, deadline):
                kind = event.get('type', '')
                if kind in {'response.web_search_call.in_progress', 'response.web_search_call.searching',
                            'response.web_search_call.completed'}:
                    item_id = event.get('item_id')
                    if isinstance(item_id, str) and len(item_id) <= 200:
                        calls.add(item_id)
                        yield sse('progress', {'stage': kind.rsplit('.', 1)[-1], 'item_id': item_id})
                elif kind == 'response.output_item.done':
                    item = event.get('item', {})
                    if item.get('type') == 'web_search_call':
                        if isinstance(item.get('id'), str):
                            calls.add(item['id'])
                        refs = discovered_sources(item, allowed_sources(), seen)
                        if refs:
                            yield sse('sources', {'sources': refs})
                elif kind in {'response.completed', 'response.incomplete', 'response.failed'}:
                    result = event.get('response', {})
                    audit_usage(audit, result)
                    # A source can be disabled while the request is in flight.
                    current_sources = allowed_sources()
                    validated = validate_result(result, current_sources)
                    validated['sections'] = [section for section in validated['sections'] if section['citations']]
                    final = archive_result(validated, mode, current_sources)
                    audit.status = 'completed'
                    complete = True
                    yield sse('result', final)
                    break
                elif kind == 'error':
                    raise ResearchError()
            if not complete:
                raise ResearchError()
        # The web process only queues URLs and reads metadata already stored.
        # Publisher fetching runs in the existing scheduler with its host gates.
        try:
            from news.research_metadata import ResearchMetadataSession
            session = ResearchMetadataSession(current_sources, max_urls=15, deadline_seconds=20)
            metadata = session.enrich([reference['url'] for reference in final['sources']][:15])
            yield sse('metadata', {'articles': metadata['articles']})
        except Exception:
            # The validated research is still useful; the durable queue can finish
            # later. Never retransmit exception text, URLs remain refreshable.
            yield sse('metadata', {'articles': []})
    except GeneratorExit:
        if not complete:
            audit.status = 'disconnected'
        raise
    except requests.RequestException:
        audit.status = 'transport_error'
        yield sse('error', {'status': 'unavailable', 'detail': 'Przerwano połączenie z wyszukiwaniem AI. Wyniki bazy pozostają dostępne.'})
    except (ResearchError, ValueError, TypeError, AttributeError, KeyError):
        if audit.status == 'started':
            audit.status = 'invalid_response'
        yield sse('error', {'status': 'unavailable', 'detail': 'Nie uzyskano kompletnego wyniku z poprawnymi odnośnikami. Wyniki bazy pozostają dostępne.'})
    finally:
        if audit.web_search_calls is None and calls:
            audit.web_search_calls = len(calls)
        audit.finished_at = timezone.now()
        audit.save(update_fields=['finished_at', 'response_model', 'status', 'provider_status',
                                  'http_status', 'input_tokens', 'output_tokens', 'web_search_calls'])
    yield sse('done', {'status': 'completed' if complete else 'error'})


@json_view("Research AI — strumień (SSE)", tags=["redakcja"])
class AIResearchStreamView(AIResearchView):
    def reserve(self, request):
        try:
            request_id = str(uuid.UUID(str(request.data.get('request_id', ''))))
        except (ValueError, TypeError, AttributeError):
            raise serializers.ValidationError({'request_id': 'Podaj identyfikator UUID wyszukiwania.'})
        # Opaque durable tombstone only: no prompt, output, key or user identity persisted.
        name = 'ai-stream-' + hashlib.sha256(request_id.encode()).hexdigest()
        with transaction.atomic():
            _, created = ImportState.objects.get_or_create(name=name)
            if not created:
                raise DuplicateRequest()
            if not reserve_attempt():
                ImportState.objects.filter(name=name).delete()
                return False
        return True

    def execute(self, query, mode, sources):
        response = StreamingHttpResponse(stream_research(query, mode, sources), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-store'
        response['X-Accel-Buffering'] = 'no'
        return response


class ResearchSourcesInput(serializers.Serializer):
    urls = serializers.ListField(child=serializers.URLField(max_length=1024), max_length=30, allow_empty=False)


class SourcesAnonThrottle(AnonRateThrottle):
    scope = "ai_sources_anon"
    rate = "240/hour"


class SourcesUserThrottle(UserRateThrottle):
    scope = "ai_sources_user"
    rate = "480/hour"


@json_view("Research AI — źródła", tags=["redakcja"])
class AIResearchSourcesView(AIResearchView):
    """Read-only publisher metadata refresh. No provider or daily budget reservation."""
    throttle_classes = [SourcesAnonThrottle, SourcesUserThrottle]

    def post(self, request):
        serializer = ResearchSourcesInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        sources = allowed_sources()
        refs = []
        for url in dict.fromkeys(serializer.validated_data['urls']):
            publisher = match_source(url, sources) if safe_url(url) else None
            if publisher:
                refs.append({'url': url, 'source_name': publisher.name, 'title': url,
                             'published_date': None, 'status': 'discovered'})
        result = archive_result({'sections': [], 'sources': refs}, 'context', sources, enqueue=False, limit=30)
        return Response({'articles': [a for group in result['archive_timeline'].values() for a in group],
                         'sources': result['sources']})
