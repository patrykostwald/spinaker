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


def _display(name: str) -> str:
    return ' '.join(part.capitalize() if part.isupper() and len(part) > 1 else part for part in (name or '').split())


def build(data: dict, account: bool = False) -> list[str]:
    """Jeden wpis: ocena w skali spinu, sedno diagnozy, techniki, terapia — źródła, link do pełnej diagnozy.

    account=False — wersja do skopiowania dla czytelnika: z @autorem i linkiem do wpisu (X pokaże cytat).
    account=True — wpis konta spin.clinic: BEZ oznaczenia i bez linku do polityka (żadnych powiadomień, które kończą
    się blokadą) — wpis polityka idzie jako obrazek (news/x_card.py). Wolne miejsce wypełnia sedno diagnozy."""
    author = data.get('author') or {}
    party = (author.get('party') or {}).get('short', '')
    intensity = data.get('intensity', 0)
    if account:
        who = _display(author.get('name', '')) + (f' ({party})' if party else '')
        head = f'{who} — wpis oceniony przez Dr. Spina (AI) na {intensity}/100 w skali spinu.'
        tail_link = ''
    else:
        head = f"Dr. Spin (AI) ocenia wpis @{author.get('handle', '')} na {intensity}/100 w skali spinu."
        tail_link = (data.get('post') or {}).get('url', '')
    synthesis = data.get('x_thread') or []
    lead = synthesis[0] if synthesis else (data.get('headline') or '')
    names = list(dict.fromkeys(_technique_name(t.get('name', '')) for t in data.get('techniques') or [] if t.get('name')))
    urls = list(dict.fromkeys(source['url'] for claim in data.get('claims') or [] for source in (claim.get('sources') or [])[:1]
                              if source.get('url')))
    full = f'Pełna diagnoza: {diagnosis_url(data["id"])}'

    def compose(technique_count: int, source_count: int, lead_text: str = '') -> str:
        parts = [head]
        if lead_text:
            parts.append(lead_text)
        if technique_count:
            parts.append('Techniki: ' + ', '.join(names[:technique_count]) + '.')
        if source_count:
            parts.append('W ramach terapii Dr. Spin zaleca źródła: ' + ' '.join(urls[:source_count]))
        parts.append(full)
        if tail_link:
            parts.append(tail_link)
        return ' '.join(parts)

    # Kolejność prób: najpierw 2–3 techniki i 1–2 źródła, potem mniej; wolne miejsce — sedno diagnozy.
    preferences = [(3, 2), (2, 2), (3, 1), (2, 1), (1, 2), (1, 1), (3, 0), (2, 0), (1, 0), (0, 1), (0, 0)]
    for techniques, sources in preferences:
        if techniques > len(names) or sources > len(urls):
            continue
        base = compose(techniques, sources)
        if weight(base) > LIMIT:
            continue
        room = LIMIT - weight(base) - 1
        if lead and room >= 50:
            return [compose(techniques, sources, shorten(lead, room))]
        return [base]
    return [shorten(compose(1 if names else 0, 0), LIMIT)]
