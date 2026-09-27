"""Diagnoza Dr. Spina jako krótki wątek na X — 2–3 wpisy, ten sam dla czytelników („Kopiuj”) i dla konta spin.clinic.

1/N — werdykt, siła i synteza diagnozy; na końcu link do wpisu polityka (X pokaże go jako cytowany wpis).
2/N — diagnoza: techniki perswazji zwięźle, w jednym wpisie.
3/N — terapia: źródła z linkami (tyle, ile zmieści limit) i link do pełnej diagnozy. Bez źródeł — tylko link.
Każdy wpis mieści się w 280 znakach ważonych (X liczy każdy link jako 23 znaki).
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


def build(data: dict) -> list[str]:
    """`data` — wynik clinic.detail_data (werdykt, autor, wpis, techniki, twierdzenia, synteza x_thread)."""
    synthesis = data.get('x_thread') or []
    lead = synthesis[0] if synthesis else data.get('headline', '')
    handle = (data.get('author') or {}).get('handle', '')
    post_url = (data.get('post') or {}).get('url', '')
    head = f"Dr. Spin (AI) o wpisie @{handle}: {str(data.get('verdict_label', '')).lower()}, siła {data.get('intensity', 0)}/100."

    techniques = data.get('techniques') or []
    if len(synthesis) > 1:
        diagnosis = 'Diagnoza: ' + ' '.join(synthesis[1:])
    elif techniques:
        diagnosis = 'Diagnoza — techniki: ' + '; '.join(f"{t.get('name', '')} („{t.get('quote', '')}”)" for t in techniques[:4]) + '.'
    else:
        diagnosis = ''

    full = diagnosis_url(data['id'])
    therapy_head = 'Terapia — Dr. Spin zaleca sprawdzić u źródła:'
    tail = f'Pełna diagnoza: {full}'
    lines = []
    for claim in data.get('claims') or []:
        for source in (claim.get('sources') or [])[:1]:
            title = shorten(source.get('title') or claim.get('claim', ''), 60)
            candidate = lines + [f"• {title} {source['url']}"]
            if weight('\n'.join([therapy_head, *candidate, tail])) + 6 <= LIMIT:
                lines = candidate
    therapy = '\n'.join([therapy_head, *lines, tail]) if lines else tail

    posts = [f"{head} {shorten(lead, LIMIT - 6 - weight(head) - 2 - (URL_WEIGHT + 1 if post_url else 0))}" + (f' {post_url}' if post_url else '')]
    if diagnosis:
        posts.append(shorten(diagnosis, LIMIT - 6))
    posts.append(therapy)
    total = len(posts)
    return [f'{index}/{total} {post}' for index, post in enumerate(posts, 1)]
