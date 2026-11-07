"""Pełne zdania syntezy diagnozy w jednym lub dwóch wpisach na X."""
from __future__ import annotations

import os
import re
import unicodedata

LIMIT = 280
URL_WEIGHT = 23
URL = re.compile(r'https?://\S+')


def weight(text: str) -> int:
    text = unicodedata.normalize('NFC', URL.sub('x' * URL_WEIGHT, text))
    return sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x200D
               or 0x2010 <= ord(c) <= 0x201F or 0x2032 <= ord(c) <= 0x2037 else 2 for c in text)


def shorten(text: str, budget: int) -> str:
    """Wybiera wyłącznie pełne zdania mieszczące się w limicie."""
    text = ' '.join(text.split())
    if not text or '…' in text or '...' in text:
        return ''
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])', text)
    kept = []
    for sentence in sentences:
        if not sentence.endswith(('.', '”', '»')):
            break
        if weight(' '.join([*kept, sentence])) > budget:
            break
        kept.append(sentence)
    return ' '.join(kept)


def diagnosis_url(diagnosis_id: int) -> str:
    return f"https://{os.environ.get('SPIN_DOMAIN', 'spin.clinic')}/klinika/{diagnosis_id}"


def _technique_name(name: str) -> str:
    """„Sekurytyzacja / straszenie” → „sekurytyzacja”; „Etykietowanie (zarzut bez konkretu)” → „etykietowanie”."""
    name = re.split(r'\s*[/(]', name or '')[0].strip()
    return name[:1].lower() + name[1:]


def heading(data: dict) -> str:
    from news.names import display_name
    author = data.get('author') or {}
    party = (author.get('party') or {}).get('short', '')
    who = display_name(author.get('name', '')) + (f', {party}' if party else '')
    return f"Dr. Spin (AI) · {who} · {data.get('verdict_label') or 'Spin'} {data.get('intensity', 0)}/100"


def build(data: dict, account: bool = False) -> list[str]:
    """Dwa wpisy konta lub jeden do skopiowania; brak syntezy oznacza brak publikacji."""
    from news.social_content import checked_claims
    synthesis = list(data.get('x_thread') or [])
    plain = data.get('plain') or {}
    gist = plain.get('gist') if isinstance(plain, dict) else None
    if isinstance(gist, str) and gist.strip():
        synthesis = [gist, *synthesis[1:]]
    from news.clinic_council import UNCHECKED, is_tool_failure
    if any(re.search(r'[!?@#\U0001F000-\U0001FAFF\u2600-\u27bf]', text) or URL.search(text) for text in synthesis):
        return []
    if any(is_tool_failure(text) or UNCHECKED in text or 'nie do sprawdzenia' in text.lower()
           or 'niezweryfikowan' in text.lower() for text in synthesis):
        return []
    if len(synthesis) < (1 if not account and gist else 2):
        return []
    head = heading(data)
    full = f'Pełna diagnoza ze źródłami: {diagnosis_url(data["id"])}'
    names = list(dict.fromkeys(_technique_name(t['name']) for t in data.get('techniques') or [] if t.get('name')))
    # Bez powtórzeń: technika nazwana już w zdaniu głównym nie wraca w linii „Techniki:” (właściciel 2.10.2026:
    # „etykietowanie przeciwnika i atak na osobę” stało w obu miejscach). Gdy wszystkie są w zdaniu – bez tej linii.
    said = synthesis[0].casefold()
    names = [name for name in names if name.casefold() not in said]
    first = ''
    for count in range(min(3, len(names)), 0 if names else -1, -1):
        technique = 'Techniki: ' + ', '.join(names[:count]) + '.' if count else ''
        parts = [head] + ([technique] if technique else []) + ([] if account else [full])
        # Sekcje rozdzielone pustą linią (decyzja właściciela 1.10.2026).
        lead = shorten(synthesis[0], LIMIT - weight('\n\n'.join(parts)) - 2)
        if lead:
            first = '\n\n'.join([head, lead] + ([technique] if technique else []) + ([] if account else [full]))
            break
    if not first:
        return []
    if not account:
        return [first]
    point = shorten(synthesis[1], LIMIT - weight(full) - 2)
    if not point:
        return []
    second = point + '\n\n' + full
    claims = checked_claims(data.get('claims'))
    # Przy kilku twierdzeniach dobieramy źródło nazwane w punkcie, zamiast przypisywać mu losowy link.
    sources = [source for claim in claims for source in claim.get('sources', [])
               if source.get('url', '').startswith(('http://', 'https://'))]
    matching = [source for source in sources if source.get('title')
                and source['title'].casefold() in point.casefold()]
    if sources and (len(claims) == 1 or len(matching) == 1):
        source = (matching[0] if len(matching) == 1 else sources[0])['url']
        extra = '\n\nŹródło: ' + source
        if source and weight(second + extra) <= LIMIT:
            second += extra
    return [first, second]
