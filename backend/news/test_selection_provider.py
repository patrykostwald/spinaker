import json

import pytest
import responses

from news.selection_provider import (MistralEUSelectionProvider,
                                     OpenAIResponsesSelectionProvider,
                                     SelectionProviderError)


def provider():
    return OpenAIResponsesSelectionProvider(api_key='secret-test-key', model='test-model', instructions='test')


@responses.activate
def test_selects_only_supplied_ids_without_retrying():
    responses.post('https://api.openai.com/v1/responses', json={
        'status': 'completed',
        'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'article_ids': [2, 1]})}
        ]}],
    })
    assert provider().select('topic', [{'id': 1}, {'id': 2}]) == [2, 1]
    assert len(responses.calls) == 1


@responses.activate
def test_rejects_foreign_ids_and_redacts_key_from_repr():
    responses.post('https://api.openai.com/v1/responses', json={
        'status': 'completed',
        'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'article_ids': [999]})}
        ]}],
    })
    current = provider()
    assert 'secret-test-key' not in repr(current)
    with pytest.raises(SelectionProviderError):
        current.select('topic', [{'id': 1}])
    assert len(responses.calls) == 1


@responses.activate
def test_mistral_eu_uses_structured_output_and_supplied_ids_only():
    responses.post(MistralEUSelectionProvider.endpoint, json={
        'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'article_ids': [2]})}}],
        'model': 'mistral-small-2603',
    })
    current = MistralEUSelectionProvider(
        api_key='mistral-secret-test-key', model='mistral-small-2603', instructions='test')
    assert current.select('topic', [{'id': 1}, {'id': 2}]) == [2]
    sent = json.loads(responses.calls[0].request.body)
    assert sent['temperature'] == 0
    assert sent['response_format']['type'] == 'json_schema'
    assert 'mistral-secret-test-key' not in repr(current)
    assert len(responses.calls) == 1


@responses.activate
def test_mistral_rejects_foreign_id_without_retry():
    responses.post(MistralEUSelectionProvider.endpoint, json={
        'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'article_ids': [999]})}}],
    })
    current = MistralEUSelectionProvider(api_key='key', model='model', instructions='test')
    with pytest.raises(SelectionProviderError):
        current.select('topic', [{'id': 1}])
    assert len(responses.calls) == 1
