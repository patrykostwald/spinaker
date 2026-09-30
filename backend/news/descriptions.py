"""Czyszczenie opisów kart, bez modyfikowania materiału źródłowego."""

import re


_URL = re.compile(
    r"(?<!\w)(?:https?://|www\.|(?:bit\.ly|youtu\.be|t\.co|tinyurl\.com|"
    r"cutt\.ly|ow\.ly|rb\.gy)/)[^\s<>\"\u201c\u201d)\]}]+",
    re.IGNORECASE,
)
_URL_MARKER = "\x00"
# Punktory wyznaczają granice formułek również w opisach bez nowych linii.
_BULLET = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2022\u25A0-\u25FF]"
    r"[\uFE0E\uFE0F\u200D]*"
)
_DECORATION = re.compile(r"([-_=*~|•])\1{2,}")
_PROMO = re.compile(
    r"^(?:subskrybuj\b|zapraszamy\s+(?:również\s+)?(?:tutaj|do|na)\b|"
    r"obserwuj\s+nas\b|dołącz\s+do\s+nas\b|wspieraj\s+nas\b|"
    r"(?:wesprzyj|wspieraj)\s+(?:nas\s+na\s+)?patronite\b|"
    r"kliknij\s+(?:w\s+)?dzwoneczek\b|polub\b|udostępnij\b|"
    r"więcej\s+na\b|czytaj\s+także\b|"
    r"(?:facebook|instagram|tiktok|twitter|x)\s*:)",
    re.IGNORECASE,
)
_LINK_LABEL = re.compile(r"^(?:portal|kanał)\b[^:]*:\s*\x00", re.IGNORECASE)
_TRAILING_HASHTAGS = re.compile(r"(?:\s*#\w+)+[\s,;.!|–—-]*$")
_EDGE_SEPARATORS = " \t:;|/–—-.,!()[]{}\x00"


def clean_description(text: str) -> str:
    """Usuń reklamy i linki; zachowaj merytoryczne zdania i ich interpunkcję."""
    # Zastępnik chroni kropki adresów przed podziałem na zdania i pozwala
    # rozpoznać etykiety portali, zanim zniknie sam link.
    text = _BULLET.sub("\n", text)
    text = _URL.sub(lambda match: _URL_MARKER + match[0][len(match[0].rstrip('.,;!?:')):], text)
    text = _DECORATION.sub("\n", text)
    text = _TRAILING_HASHTAGS.sub("", text)
    parts = re.split(r"\n|\r|(?<=[.!?])\s+|\s+[|]\s+", text)
    kept = []
    for part in parts:
        part = " ".join(part.split())
        candidate = part.lstrip(_EDGE_SEPARATORS)
        if not candidate.strip(_EDGE_SEPARATORS) or _PROMO.match(candidate) or _LINK_LABEL.match(candidate):
            continue
        if _URL_MARKER in part:
            # Nawiasy i separatory przy usuniętych linkach nie są treścią.
            part = re.sub(r"[([]\s*\x00\s*[)\]]", "", part)
            part = part.replace(_URL_MARKER, "")
            part = re.sub(r"\s+([,.;!?])", r"\1", part)
            part = part.strip(" \t:;|/–—-")
        else:
            part = part.strip()
        if part:
            kept.append(part)
    result = " ".join(" ".join(kept).split())
    return result if len(result) >= 25 else ""
