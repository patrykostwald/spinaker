"""Pre-filtr komentarza przed publikacją (PETLA 2.2 wiersz 8): komentarz 280 znaków to kanał doxxingu.

PESEL z poprawną sumą kontrolną: twarda blokada (400). Numer telefonu albo adres e-mail: miękka blokada
("komentarz czeka na sprawdzenie": przypięcie publikuje się, komentarz ma status 'held' do decyzji człowieka).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
DIGITS11 = re.compile(r'(?<!\d)(\d{11})(?!\d)')
PHONE = re.compile(r'(?<!\d)(?:\+?48[\s-]?)?(?:\d[\s-]?){9}(?!\d)')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', re.I)
POSTAL_ADDRESS = re.compile(r'\b(?:ul\.|ulica|al\.|aleja|os\.|osiedle)\s+\S+.{0,30}?\d+[a-z]?(?:\s*/\s*\d+)?\b', re.I)


def pesel_valid(value: str) -> bool:
    if not value or len(value) != 11 or not value.isdigit():
        return False
    control = sum(int(d) * w for d, w in zip(value[:10], PESEL_WEIGHTS)) % 10
    return (10 - control) % 10 == int(value[10])


@dataclass(frozen=True)
class CommentCheck:
    status: str     # 'ok' | 'held' | 'blocked' | 'empty'
    reason: str = ''


def check_comment(text: str, max_length: int = 280) -> CommentCheck:
    text = (text or '').strip()
    if not text:
        return CommentCheck('empty')
    if len(text) > max_length:
        return CommentCheck('blocked', f'Komentarz ma najwyżej {max_length} znaków.')
    for candidate in DIGITS11.findall(text):
        if pesel_valid(candidate):
            return CommentCheck('blocked', 'Komentarz zawiera numer PESEL. Nie publikujemy danych osób.')
    if EMAIL.search(text):
        return CommentCheck('held', 'Komentarz zawiera adres e-mail i czeka na sprawdzenie.')
    if PHONE.search(text):
        return CommentCheck('held', 'Komentarz zawiera numer telefonu i czeka na sprawdzenie.')
    if POSTAL_ADDRESS.search(text):
        return CommentCheck('held', 'Komentarz zawiera adres i czeka na sprawdzenie.')
    return CommentCheck('ok')
