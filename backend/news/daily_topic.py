"""A transparent, bounded media-attention signal, not a truth/importance verdict."""
from collections import Counter, defaultdict
from datetime import timedelta
import re
import unicodedata
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from news.portal import visible_articles, top_sources, TOP_TEN, STOP
from news.topics import TOPICS

MAX_RECORDS = 30000
MAX_CANDIDATES = 600
GENERIC = set(STOP) | {alias for _, aliases in TOPICS.values() for alias in aliases} | {
    'informacje', 'wydarzenia', 'artykuł', 'artykuły', 'wywiad', 'reportaż', 'opinia', 'opinie',
    'wideo', 'video', 'film', 'reklama', 'sponsorowane', 'najnowsze', 'aktualności', 'wiadomości',
    'ogród', 'ogrod', 'dom', 'region', 'lokalne', 'regionalne', 'regiony', 'wiadomości lokalne',
    'miasto', 'powiat', 'samorząd', 'styl życia', 'lifestyle', 'strona kobiet', 'porady',
    'turystyka', 'religia', 'nieruchomości', 'piłka nożna', 'sporty', 'rozrywka', 'handel',
    'praca', 'edukacja', 'historia', 'podróże', 'prawo', 'bezpieczeństwo', 'społeczeństwo',
    'prezydent', 'premier', 'minister', 'ministerstwo', 'rząd', 'rządu', 'sejm', 'senat',
    'policja', 'policji', 'komunikat', 'wyniki', 'wynik', 'szef', 'sąd', 'nowe informacje',
    'konflikty zbrojne', 'globalne interesy', 'prawo drogowe', 'onet', 'rano', 'pilne',
}


def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', str(value)).casefold().split()).strip('# ')


def headline_names(title):
    """Conservative literal candidates when RSS only declares a broad section.

    Capitalized names inside a headline, and adjacent capitalized name pairs,
    are search candidates only. They are never written into publisher tags.
    """
    tokens = list(re.finditer(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", title, re.UNICODE))
    for index, token in enumerate(tokens):
        value = token.group()
        if not value[0].isupper() or normalized(value) in GENERIC:
            continue
        if index > 0 and (len(value) >= 4 or value.isupper() and len(value) >= 3):
            yield value
        if index + 1 < len(tokens):
            following = tokens[index + 1]
            if (following.group()[0].isupper() and normalized(following.group()) not in GENERIC
                    and title[token.end():following.start()].isspace()):
                yield title[token.start():following.end()]


def rank_topics(rows, now):
    """Candidates come literally from publisher tags/headlines; match metadata.

    One publisher cannot win by posting hundreds of near-identical stories.
    We require three sources and three distinct headlines, and cap its tie score.
    """
    candidates = defaultdict(set)
    labels = {}
    records = []
    lower_words, capital_words = Counter(), Counter()
    for row in rows:
        for word in re.findall(r'[^\W\d_]+', row['title'], re.UNICODE):
            (capital_words if word[0].isupper() else lower_words)[normalized(word)] += 1
    for row in rows:
        tags = [normalized(tag) for tag in row['tags'] if isinstance(tag, str)] if isinstance(row['tags'], list) else []
        title = normalized(row['title'])
        records.append((row['source_id'], title, ' '.join(tags), row['published_date']))
        declared = row['tags'] if isinstance(row['tags'], list) else []
        names = [name for name in headline_names(row['title'])
                 if all(capital_words[word] > lower_words[word] for word in normalized(name).split())]
        for raw in [*declared, *names]:
            if not isinstance(raw, str): continue
            term = normalized(raw)
            if not 3 <= len(term) <= 70 or term in GENERIC or term.isdigit() or len(term.split()) > 5 or '://' in term:
                continue
            candidates[term].add(row['source_id'])
            labels.setdefault(term, ' '.join(raw.split()).strip('# '))
    ranked = []
    # A prolific publisher cannot crowd out other candidates before scoring.
    for term in sorted(candidates, key=lambda term: (-len(candidates[term]), term))[:MAX_CANDIDATES]:
        words = [re.compile(r'(?<!\w)' + re.escape(word) + r'(?!\w)') for word in term.split()]
        sources = defaultdict(set)
        recent_sources = set()
        matching = 0
        for source, title, tags, published in records:
            if not all(word.search(title) or word.search(tags) for word in words): continue
            sources[source].add(re.sub(r'\W+', ' ', title).strip())
            matching += 1
            if published >= now - timedelta(hours=6): recent_sources.add(source)
        distinct_headlines = set().union(*sources.values()) if sources else set()
        if len(sources) < 3 or len(distinct_headlines) < 3: continue
        # Diversity first; recent breadth and capped volume break ties.
        score = (len(sources), len(recent_sources), sum(min(5, len(titles)) for titles in sources.values()))
        ranked.append((score, term, {'query':term, 'label':labels[term], 'source_count':len(sources),
            'article_count':matching, 'distinct_headlines':len(distinct_headlines)}))
    ranked.sort(key=lambda value: (tuple(-part for part in value[0]), value[1]))
    return ranked[0][2] if ranked else None


@api_view(['GET'])
def topic_of_day(request):
    sources = top_sources()
    source_ids = [source.pk for source in sources]
    # Changing the selected/visible sources takes effect without waiting for TTL.
    key = 'portal-topic-of-day:v2:' + ','.join(map(str, source_ids))
    cached = cache.get(key)
    if cached is not None: return Response(cached)
    now = timezone.now()
    rows = list(visible_articles().filter(source_id__in=source_ids,
        published_date__gte=now-timedelta(hours=24), published_date__lte=now)
        .exclude(category__in=['advertisement','sponsored','voting','legislation','parliamentary_print','document'])
        .order_by('-published_date','-pk').values('source_id','title','tags','published_date')[:MAX_RECORDS+1])
    truncated = len(rows) > MAX_RECORDS
    rows = rows[:MAX_RECORDS]
    selected = rank_topics(rows, now)
    covered_ids = {row['source_id'] for row in rows}
    payload = {'query':None,'label':None,'source_count':0,'article_count':0,**(selected or {}),
        'mode':'automatic' if selected else 'unavailable', 'window_hours':24,'checked_at':now.isoformat(),
        'records_considered':len(rows),'limited_window_sample':truncated,
        'selection_pool':'top10', 'query_match':'words', 'expected_source_count':len(TOP_TEN),
        'covered_source_count':len(covered_ids),
        'sources':[{'id':source.pk,'name':source.name,'url':source.url,
            'has_recent_materials':source.pk in covered_ids} for source in sources],
        'method':'Temat z tytułów i oznaczeń publikacji TOP10. Wybór według liczby źródeł podejmujących temat w ostatnich 24 godzinach, następnie obecności w ostatnich 6 godzinach i ograniczonej liczby publikacji na źródło.',
        'note':'Automatyczny wybór ze zgromadzonych publikacji TOP10; redakcje nie musiały same oznaczyć go jako temat dnia. Nie jest to ocena prawdziwości ani pełności internetu. Pasek obejmuje dostępną historię ze wszystkich źródeł w naszej bazie.'}
    cache.set(key,payload,300)
    return Response(payload)
