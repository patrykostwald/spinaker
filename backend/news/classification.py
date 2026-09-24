"""Narrow publisher-declared genre rules; never infer sponsorship from topic."""
from urllib.parse import urlsplit
from django.utils.html import strip_tags


GENRES = {'InterviewNewsArticle': 'interview', 'ReportageNewsArticle': 'reportage',
          'VideoObject': 'video', 'PodcastEpisode': 'podcast'}
GENRE_LABELS = {'wywiad': 'interview', 'interview': 'interview', 'reportaż': 'reportage',
                'reportage': 'reportage', 'film': 'video', 'video': 'video',
                'podcast': 'podcast'}


def normalize_publisher_tags(values):
    """Publisher-supplied tags only. Bound, strip markup and deduplicate."""
    if isinstance(values, str):
        values = values.split(',')
    if not isinstance(values, (tuple, list)):
        return []
    result, seen = [], set()
    for value in values:
        if isinstance(value, dict):
            value = value.get('term') or value.get('name') or ''
        if not isinstance(value, str):
            continue
        tag = ' '.join(strip_tags(value).split())[:80]
        if tag and tag.casefold() not in seen:
            result.append(tag)
            seen.add(tag.casefold())
        if len(result) == 12:
            break
    return result


def declared_category(types, genre):
    """Exact genre declarations, never title words or topical RSS categories."""
    types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
    values = {GENRES[t] for t in types if isinstance(t, str) and t in GENRES}
    genres = [genre] if isinstance(genre, str) else genre if isinstance(genre, list) else []
    values.update(GENRE_LABELS[g.strip().casefold()] for g in genres
                  if isinstance(g, str) and g.strip().casefold() in GENRE_LABELS)
    return next(iter(values)) if len(values) == 1 else ''


def publisher_category(url, fallback):
    try:
        parsed = urlsplit(url)
    except ValueError:
        return fallback, ''
    if ((parsed.hostname or '').removeprefix('www.') == 'ddwloclawek.pl'
            and parsed.path.startswith('/pl/701_artykuly-sponsorowane/')
            and parsed.path.endswith('.html')):
        return 'sponsored', ('Kategoria na podstawie działu wydawcy: '
            'https://ddwloclawek.pl/pl/701_artykuly-sponsorowane/ '
            '(reguła zweryfikowana 2026-09-09).')
    return fallback, ''
