"""Bounded metadata matches, never editorial evidence or persisted references."""
import hashlib
import re
import unicodedata

from django.core.cache import cache

from news.models import Article
from news.political_models import PublicFigure

CANDIDATE_LIMIT = 2000
MENTION_LIMIT = 100
CACHE_SECONDS = 600
MIN_SURNAME_LENGTH = 5


def normalize_name(value):
    return ' '.join(unicodedata.normalize('NFC', value or '').casefold().split())


# Explicit forms deliberately prefer omissions over unrelated names.
GIVEN_NAMES = {
    'jan': ('jana', 'janowi', 'janem'),
    'andrzej': ('andrzeja', 'andrzejowi', 'andrzejem'),
    'donald': ('donalda', 'donaldowi', 'donaldem'),
    'mateusz': ('mateusza', 'mateuszowi', 'mateuszem'),
    'jarosław': ('jarosława', 'jarosławowi', 'jarosławem'),
    'krzysztof': ('krzysztofa', 'krzysztofowi', 'krzysztofem'),
    'łukasz': ('łukasza', 'łukaszowi', 'łukaszem'),
    'anna': ('anny', 'annie', 'annę', 'anną'),
    'maria': ('marii', 'marię', 'marią'),
    'katarzyna': ('katarzyny', 'katarzynie', 'katarzynę', 'katarzyną'),
}


def name_pattern(name):
    parts = normalize_name(name).split()
    if len(parts) < 2 or len(parts[-1].replace('-', '')) < MIN_SURNAME_LENGTH:
        return None
    if any(not re.fullmatch(r'[^\W\d_]+(?:-[^\W\d_]+)*', p) for p in parts):
        return None
    surname = parts[-1]
    surnames = {surname}
    if surname.endswith(('ski', 'cki', 'dzki')):
        surnames.update(surname[:-1] + ending for ending in ('iego', 'iemu', 'im'))
    elif surname.endswith(('ska', 'cka', 'dzka')):
        surnames.update(surname[:-1] + ending for ending in ('iej', 'ą'))
    patterns = []
    for part in parts[:-1]:
        patterns.append('(?:' + '|'.join(re.escape(v) for v in (part, *GIVEN_NAMES.get(part, ()))) + ')')
    patterns.append('(?:' + '|'.join(re.escape(v) for v in sorted(surnames)) + ')')
    # A hyphen is part of a name: Kowalski must not match Kowalski-Nowak.
    return re.compile(r'(?<![\w-])' + r'\s+'.join(patterns) + r'(?![\w-])', re.IGNORECASE)


def matched_field(pattern, article):
    for field in ('title', 'description'):
        if pattern.search(unicodedata.normalize('NFC', article.get(field) or '')):
            return field
    return None


def mentions_data(figure):
    """At most 100 links from the latest 2000 dated records, cached for 10 minutes.

    Registry ambiguity and editorial exclusions are checked even for cache hits.
    Archived independent identities still block homonyms; merged aliases do not.
    """
    empty = {'results': []}
    if figure.archived or figure.merged_into_id:
        return empty
    pattern = name_pattern(figure.canonical_name)
    if pattern is None:
        return empty
    normalized = normalize_name(figure.canonical_name)
    same_names = sum(normalize_name(name) == normalized for name in
                     PublicFigure.objects.filter(merged_into__isnull=True).values_list('canonical_name', flat=True))
    if same_names != 1:
        return empty
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]
    key = f'media-mentions:v1:{figure.pk}:{digest}'
    matches = cache.get(key)
    if matches is None:
        # No textual/source filter before this LIMIT: index walk has a hard bound.
        candidates = list(Article.objects.filter(published_date__isnull=False)
                          .order_by('-published_date').values(
                              'pk', 'title', 'description', 'url', 'tags', 'category',
                              'published_date', 'source_id')[:CANDIDATE_LIMIT])
        matches = []
        for article in candidates:
            field = matched_field(pattern, article)
            if field:
                matches.append({**article, 'matched_in': field})
        cache.set(key, matches, CACHE_SECONDS)
    ids = [row['pk'] for row in matches]
    excluded = set(figure.article_references.filter(
        verification_status__in=('confirmed', 'rejected'), article_id__in=ids,
    ).values_list('article_id', flat=True))
    # Recheck source visibility and deletion instead of trusting stale metadata.
    live = dict(Article.objects.filter(pk__in=ids, source__is_active=True).values_list('pk', 'source__name'))
    from news.material_type import MATERIAL_LABELS, classify_material_type
    results = []
    for row in matches:
        if row['pk'] in excluded or row['pk'] not in live:
            continue
        material_type = classify_material_type({**row, 'automatic_match': True})
        results.append({
            'id': row['pk'], 'title': row['title'], 'url': row['url'],
            'source': live[row['pk']], 'published_date': row['published_date'],
            'category': row['category'], 'automatic_match': True,
            'matched_in': row['matched_in'], 'material_type': material_type,
            'kind_label': MATERIAL_LABELS[material_type],
        })
        if len(results) >= MENTION_LIMIT:
            break
    return {'results': results}
