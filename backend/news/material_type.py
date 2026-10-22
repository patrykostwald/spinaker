"""Orientacyjny typ z metadanych wydawcy; bez I/O i analizy treści artykułu."""
import re
from collections.abc import Mapping
from urllib.parse import unquote, urlsplit


MATERIAL_LABELS = {'wywiad': 'wywiad', 'reportaz': 'reportaż', 'opinia': 'opinia',
                   'news': 'news', 'wzmianka': 'wzmianka', 'inne': 'inne'}
_PATTERNS = (
    ('wywiad', r'\b(?:wywiad|rozmowa z)\b'),
    ('reportaz', r'\breporta[żz]\b'),
    ('opinia', r'\b(?:felieton|opinie|opinia|komentarz)\b'),
)
_PATHS = {'wywiad': {'wywiad', 'wywiady', 'rozmowa', 'rozmowy'},
          'reportaz': {'reportaz', 'reportaż', 'reportaze', 'reportaże'},
          'opinia': {'felieton', 'felietony', 'opinie', 'opinia', 'komentarz', 'komentarze'}}


def classify_material_type(article):
    """Przyjmuje Article lub mapping. Kontekst dopasowania przekazuje wywołujący.

    Wzmianka wyłącznie w opisie ma pierwszeństwo; potem ścieżka URL, tytuł,
    tagi i opis. Nie wywodzimy udziału osoby z gatunku dziennikarskiego.
    """
    def get(key, default=''):
        return article.get(key, default) if isinstance(article, Mapping) else getattr(article, key, default)

    if get('automatic_match', False) and get('matched_in') == 'description':
        return 'wzmianka'
    try:
        segments = set(unquote(urlsplit(str(get('url') or '')).path).casefold().split('/'))
    except ValueError:
        segments = set()
    for kind, paths in _PATHS.items():
        if segments & paths:
            return kind
    tags = get('tags', [])
    if isinstance(tags, (list, tuple)):
        tags = ' '.join(t for t in tags if isinstance(t, str))
    elif not isinstance(tags, str):
        tags = ''
    for value in (get('title'), tags, get('description')):
        for kind, pattern in _PATTERNS:
            if re.search(pattern, str(value or '').casefold()):
                return kind
    return 'news' if get('title') or get('description') or get('url') else 'inne'
