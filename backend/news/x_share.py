"""Diagnoza Dr. Spina jako JEDEN wpis na X — ten sam dla czytelników („Kopiuj”) i dla konta spin.clinic.

Ocena w skali spinu, techniki, terapia (źródła z linkami), link do pełnej diagnozy, a na końcu link do wpisu polityka —
X pokaże go jako cytowany wpis. Mieści się w 280 znakach ważonych (X liczy każdy link jako 23 znaki).
"""
from __future__ import annotations

import os
import re

LIMIT = 280
URL_WEIGHT = 23
URL = re.compile(r'https?://\S+')


def weight(text: str) -> int:
    return len(URL.sub('x' * URL_WEIGHT, text))


def shorten(text: str, budget: int) -> str:
    """Skraca całymi zdaniami, a gdy się nie da — całymi słowami, z wielokropkiem."""
    text = ' '.join(text.split())
    if weight(text) <= budget:
        return text
    sentences = re.findall(r'[^.!?]+[.!?]+', text)
    kept = ''
    for sentence in sentences:
        candidate = (kept + ' ' + sentence.strip()).strip()
        if weight(candidate) > budget:
            break
        kept = candidate
    if len(kept) > len(text) / 3:
        return kept
    words, result = text.split(), ''
    for word in words:
        candidate = f'{result} {word}'.strip()
        if weight(candidate + '…') > budget:
            break
        result = candidate
    return result.rstrip(',;:—–-') + '…'


def diagnosis_url(diagnosis_id: int) -> str:
    return f"https://{os.environ.get('SPIN_DOMAIN', 'spin.clinic')}/klinika/{diagnosis_id}"


def _technique_name(name: str) -> str:
    """„Sekurytyzacja / straszenie” → „sekurytyzacja”; „Etykietowanie (zarzut bez konkretu)” → „etykietowanie”."""
    name = re.split(r'\s*[/(]', name or '')[0].strip()
    return name[:1].lower() + name[1:]


def build(data: dict) -> list[str]:
    """Jeden wpis (decyzja właściciela 28.09): ocena w skali spinu, techniki, terapia — źródła, link do pełnej diagnozy
    i na końcu link do wpisu polityka (X pokaże go jako cytowany wpis). Gdy się nie mieści — mniej źródeł, potem technik."""
    handle = (data.get('author') or {}).get('handle', '')
    post_url = (data.get('post') or {}).get('url', '')
    head = (f"Dr. Spin (AI) ocenia wpis @{handle} na {data.get('intensity', 0)}/100 w skali spinu "
            f"({str(data.get('verdict_label', '')).lower()}).")
    names = list(dict.fromkeys(_technique_name(t.get('name', '')) for t in data.get('techniques') or [] if t.get('name')))
    urls = list(dict.fromkeys(source['url'] for claim in data.get('claims') or [] for source in (claim.get('sources') or [])[:1]
                              if source.get('url')))
    full = f'Pełna diagnoza: {diagnosis_url(data["id"])}'

    def compose(technique_count: int, source_count: int) -> str:
        parts = [head]
        if technique_count:
            parts.append('Techniki: ' + ', '.join(names[:technique_count]) + '.')
        if source_count:
            parts.append('W ramach terapii Dr. Spin zaleca źródła: ' + ' '.join(urls[:source_count]))
        parts.append(full)
        if post_url:
            parts.append(post_url)
        return ' '.join(parts)

    # Kolejność prób: najpierw 2–3 techniki i 1–2 źródła, potem mniej.
    preferences = [(3, 2), (2, 2), (3, 1), (2, 1), (1, 2), (1, 1), (3, 0), (2, 0), (1, 0), (0, 1), (0, 0)]
    for techniques, sources in preferences:
        if techniques > len(names) or sources > len(urls):
            continue
        text = compose(techniques, sources)
        if weight(text) <= LIMIT:
            return [text]
    return [shorten(compose(1 if names else 0, 0), LIMIT)]
