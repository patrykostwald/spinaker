"""Provider-neutral editorial selection contract and OpenAI transport."""
from __future__ import annotations

import json
import time
from typing import Protocol

import requests


class SelectionProviderError(Exception):
    """A provider failed or returned an invalid selection."""


class SelectionProvider(Protocol):
    def select(self, topic: str, candidates: list[dict]) -> list[int]: ...


class OpenAIResponsesSelectionProvider:
    """One bounded, non-retried Responses request returning candidate IDs only."""

    __slots__ = ('_api_key', 'model', 'instructions')

    def __init__(self, *, api_key: str, model: str, instructions: str):
        self._api_key = api_key
        self.model = model
        self.instructions = instructions

    def __repr__(self) -> str:
        return f'{type(self).__name__}(model={self.model!r}, api_key=<redacted>)'

    def select(self, topic: str, candidates: list[dict]) -> list[int]:
        allowed_ids = {candidate['id'] for candidate in candidates}
        payload = {
            'model': self.model,
            'store': False,
            'max_output_tokens': 1200,
            'instructions': self.instructions,
            'input': json.dumps({'topic': topic, 'candidates': candidates}, ensure_ascii=False),
            'text': {'format': {'type': 'json_schema', 'name': 'context_selection', 'strict': True,
                'schema': {'type': 'object', 'additionalProperties': False, 'required': ['article_ids'],
                           'properties': {'article_ids': {'type': 'array', 'maxItems': 15,
                               'items': {'type': 'integer', 'enum': sorted(allowed_ids)}}}}}},
        }
        deadline = time.monotonic() + 60
        try:
            with requests.post(
                'https://api.openai.com/v1/responses',
                headers={'Authorization': f'Bearer {self._api_key}'},
                json=payload,
                timeout=(5, 45),
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code != 200:
                    raise SelectionProviderError()
                raw = bytearray()
                for chunk in response.iter_content(8192):
                    raw.extend(chunk)
                    if len(raw) > 131072 or time.monotonic() > deadline:
                        raise SelectionProviderError()
                result = json.loads(raw)
            if result.get('status') != 'completed':
                raise SelectionProviderError()
            fragments = [content.get('text', '') for item in result.get('output', [])
                         if item.get('type') == 'message' for content in item.get('content', [])
                         if content.get('type') == 'output_text']
            selected = json.loads(''.join(fragments))
            if not isinstance(selected, dict) or set(selected) != {'article_ids'}:
                raise SelectionProviderError()
            ids = selected['article_ids']
            if (not isinstance(ids, list) or len(ids) > 15 or
                    any(type(pk) is not int or pk not in allowed_ids for pk in ids) or
                    len(set(ids)) != len(ids)):
                raise SelectionProviderError()
            return ids
        except SelectionProviderError:
            raise
        except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise SelectionProviderError() from exc
