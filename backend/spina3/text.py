"""Normalizacja tekstu do wyszukiwania: bez polskich znaków, małe litery ("zylka" = "żyłka")."""
from __future__ import annotations

import re
import unicodedata

PL = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')
TOKEN = re.compile(r'[a-z0-9]+')


def normalize(text: str) -> str:
    text = (text or '').translate(PL)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(TOKEN.findall(text.lower()))


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def short(value: str, limit: int) -> str:
    value = ' '.join(str(value or '').replace('—', '-').replace('–', '-').split())
    if len(value) <= limit:
        return value
    cut = value[:limit - 1].rsplit(' ', 1)[0]
    return cut + '…'
