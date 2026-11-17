"""Tolerancyjne wyciąganie obiektu JSON z odpowiedzi modelu (pilotaż 13.10: inception_invalid_json).

Obsługuje: blok ```json ... ```, tekst przed i po obiekcie, <think>...</think>, przecinki przed } i ], cudzysłowy
typograficzne wokół kluczy. Zwraca dict albo zgłasza ValueError('invalid_json'). Bez eval i bez wykonywania kodu.
"""
from __future__ import annotations

import json
import re

FENCE = re.compile(r'```(?:json|JSON)?\s*(.*?)```', re.S)
TRAILING_COMMA = re.compile(r',\s*([}\]])')


def _candidates(text: str):
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
    for block in FENCE.findall(text):
        yield block.strip()
    yield text
    start = text.find('{')
    if start != -1:
        depth, in_string, escaped = 0, False, False
        for i, ch in enumerate(text[start:], start):  # pierwszy zbalansowany obiekt
            if in_string:
                escaped = (ch == '\\' and not escaped)
                if ch == '"' and not escaped:
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    yield text[start:i + 1]
                    break
        end = text.rfind('}')
        if end > start:
            yield text[start:end + 1]


def loads(text) -> dict:
    if isinstance(text, dict):
        return text
    for candidate in _candidates(str(text or '')):
        for variant in (candidate, TRAILING_COMMA.sub(r'\1', candidate),
                        TRAILING_COMMA.sub(r'\1', candidate.replace('„', '"').replace('”', '"'))):
            try:
                result = json.loads(variant, strict=False)
            except ValueError:
                continue
            if isinstance(result, dict):
                return result
    raise ValueError('invalid_json')
