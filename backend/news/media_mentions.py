"""Bounded metadata matches, never editorial evidence or persisted references."""
import hashlib
import re
import unicodedata

from django.core.cache import cache
from django.db.models import Q

from news.models import Article
from news.political_models import PublicFigure

# Śledczy R1, P0-4: nie przeglądamy już 2000 najnowszych artykułów. Kandydatów wybiera zapytanie po formach nazwiska
# (cała baza), a ten limit chroni tylko przed lawiną trafień w samym nazwisku (najnowsze pierwsze).
CANDIDATE_LIMIT = 5000
MENTION_LIMIT = 100
CACHE_SECONDS = 600
MIN_SURNAME_LENGTH = 4
# Samo nazwisko (bez imienia) tylko dla nazwisk jednoznacznych w rejestrze i dość długich.
MIN_SURNAME_ONLY_LENGTH = 4
# Poniżej tej długości samo nazwisko musi być pisane z wielkiej litery (Tusk, nie „tusk”).
SHORT_SURNAME_LENGTH = 6
# Funkcje i słowa poprzedzające nazwisko, które nie czynią z niego innej osoby („Premier Tusk”, „Afera Obajtka”).
FUNCTION_WORDS = frozenset({
    'premier', 'premiera', 'premierowi', 'premierem', 'wicepremier', 'wicepremiera', 'minister', 'ministra',
    'prezes', 'prezesa', 'prezesowi', 'prezesem', 'poseł', 'posła', 'posłowi', 'posłem', 'posłanka', 'posłanki',
    'europoseł', 'europosła', 'senator', 'senatora', 'prezydent', 'prezydenta', 'marszałek', 'marszałka',
    'lider', 'lidera', 'szef', 'szefa', 'szefowi', 'szefem', 'afera', 'afery', 'aferze', 'sprawa', 'sprawy',
    'rząd', 'rządu', 'pupil', 'pupila', 'wojewoda', 'burmistrz', 'radny', 'kandydat', 'kandydata', 'sędzia',
})


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
    'daniel': ('daniela', 'danielowi', 'danielem'),
    'michał': ('michała', 'michałowi', 'michałem'),
    'piotr': ('piotra', 'piotrowi', 'piotrem'),
    'paweł': ('pawła', 'pawłowi', 'pawłem'),
    'marcin': ('marcina', 'marcinowi', 'marcinem'),
    'tomasz': ('tomasza', 'tomaszowi', 'tomaszem'),
    'adam': ('adama', 'adamowi', 'adamem'),
    'rafał': ('rafała', 'rafałowi', 'rafałem'),
    'sławomir': ('sławomira', 'sławomirowi', 'sławomirem'),
    'katarzyna': ('katarzyny', 'katarzynie', 'katarzynę', 'katarzyną'),
}


def surname_forms(surname):
    """Mianownik i odmienione formy nazwiska; wyłącznie jawne końcówki, bez zgadywania."""
    forms = {surname}
    if surname.endswith(('ski', 'cki', 'dzki')):
        forms.update(surname[:-1] + ending for ending in ('iego', 'iemu', 'im'))
    elif surname.endswith(('ska', 'cka', 'dzka')):
        forms.update(surname[:-1] + ending for ending in ('iej', 'ą'))
    elif not surname.endswith(('a', 'o', 'e', 'i', 'y')):
        forms.update(surname + ending for ending in ('a', 'owi', 'em', 'iem', 'u'))
        if surname.endswith('ek'):  # Obajtek -> Obajtka, Obajtkowi, Obajtkiem
            stem = surname[:-2] + 'k'
            forms.update(stem + ending for ending in ('a', 'owi', 'iem', 'u'))
    return forms


def name_pattern(name):
    parts = normalize_name(name).split()
    if len(parts) < 2 or len(parts[-1].replace('-', '')) < MIN_SURNAME_LENGTH:
        return None
    if any(not re.fullmatch(r'[^\W\d_]+(?:-[^\W\d_]+)*', p) for p in parts):
        return None
    surnames = surname_forms(parts[-1])
    patterns = []
    for part in parts[:-1]:
        patterns.append('(?:' + '|'.join(re.escape(v) for v in (part, *GIVEN_NAMES.get(part, ()))) + ')')
    patterns.append('(?:' + '|'.join(re.escape(v) for v in sorted(surnames)) + ')')
    # A hyphen is part of a name: Kowalski must not match Kowalski-Nowak.
    return re.compile(r'(?<![\w-])' + r'\s+'.join(patterns) + r'(?![\w-])', re.IGNORECASE)


def surname_only_pattern(name):
    """Samo nazwisko: tylko mianownik i jawne formy; poprzedni wyraz sprawdza surname_only_hit."""
    parts = normalize_name(name).split()
    if len(parts) < 2 or len(parts[-1].replace('-', '')) < MIN_SURNAME_ONLY_LENGTH:
        return None
    if not re.fullmatch(r'[^\W\d_]+', parts[-1]):
        return None
    forms = '|'.join(re.escape(v) for v in sorted(surname_forms(parts[-1])))
    return re.compile(r'(?<![\w-])(?:' + forms + r')(?![\w-])', re.IGNORECASE)


def known_given_name(word):
    word = word.casefold()
    return word in GIVEN_NAMES or any(word in forms for forms in GIVEN_NAMES.values())


def is_shouting(text):
    """Tytuł pisany wersalikami: wielkość liter nie odróżnia imienia od funkcji."""
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 6 and sum(c.isupper() for c in letters) / len(letters) > 0.8


def surname_only_hit(pattern, text):
    """Wyraz z wielkiej litery tuż przed nazwiskiem (np. „Adrian Obajtek”) oznacza inną osobę: pomijamy.

    Wyjątki: funkcja lub słowo z FUNCTION_WORDS („Premier Tusk”); w tytule wersalikami odrzucamy
    akceptujemy tylko funkcję lub krótki przyimek. Krótkie nazwisko musi zaczynać się wielką literą.
    """
    shouting = is_shouting(text)
    for found in pattern.finditer(text):
        if len(found.group()) < SHORT_SURNAME_LENGTH and not found.group()[0].isupper():
            continue
        before = re.search(r'([^\W\d_][\w-]*)\s+$', text[max(0, found.start() - 40):found.start()])
        if not before:
            return True
        word = before.group(1)
        if word.casefold() in FUNCTION_WORDS:
            return True
        if shouting:
            if len(word) <= 3 and not known_given_name(word):  # przyimek: „Z TUSKIEM”
                return True
        elif not word[0].isupper():
            return True
    return False


def unique_surname(figure, normalized):
    """Nazwisko występuje w rejestrze tylko u tej osoby (z aliasami scalonymi do niej)."""
    surname = normalized.split()[-1]
    others = [n for n in PublicFigure.objects.filter(merged_into__isnull=True, canonical_name__iendswith=surname)
              .exclude(pk=figure.pk).values_list('canonical_name', flat=True)
              if normalize_name(n).split()[-1:] == [surname]]
    return not others


def matched_field(pattern, article, surname_pattern=None):
    """(pole, pewność): pełne imię i nazwisko = wysoka, samo jednoznaczne nazwisko = średnia."""
    for field in ('title', 'description'):
        text = unicodedata.normalize('NFC', article.get(field) or '')
        if pattern and pattern.search(text):
            return field, 'high'
    if surname_pattern:
        for field in ('title', 'description'):
            if surname_only_hit(surname_pattern, unicodedata.normalize('NFC', article.get(field) or '')):
                return field, 'medium'
    return None


def snippet_of(pattern, surname_pattern, row, width=70):
    """Krótki fragment pola, w którym znaleziono nazwisko (cytat do weryfikacji, nie cały tekst)."""
    text = unicodedata.normalize('NFC', row.get(row['matched_in']) or '')
    found = (pattern.search(text) if pattern else None) or (surname_pattern.search(text) if surname_pattern else None)
    if not found:
        return ''
    start, end = max(0, found.start() - width), min(len(text), found.end() + width)
    return ('…' if start else '') + ' '.join(text[start:end].split()) + ('…' if end < len(text) else '')


def candidate_filter(surname):
    """Wstępny wybór w bazie po formach nazwiska (bez pierwszej litery: wielkość liter polskich znaków)."""
    query = Q()
    for form in surname_forms(surname):
        needle = form[1:] if len(form) > 3 else form
        query |= Q(title__icontains=needle) | Q(description__icontains=needle)
    return query


def mentions_data(figure):
    """Do 100 odnośników z całej bazy artykułów (wybór po formach nazwiska), cache 10 minut.

    Pewność: high = pełne imię i nazwisko, medium = samo nazwisko jednoznaczne w rejestrze.
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
    surname_pattern = surname_only_pattern(figure.canonical_name) if unique_surname(figure, normalized) else None
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]
    key = f'media-mentions:v2:{figure.pk}:{digest}:{int(bool(surname_pattern))}'
    matches = cache.get(key)
    if matches is None:
        # Kandydaci z bazy po nazwisku (najnowsi pierwsi); dopiero regex rozstrzyga o dopasowaniu.
        candidates = list(Article.objects.filter(candidate_filter(normalized.split()[-1]), published_date__isnull=False)
                          .order_by('-published_date').values(
                              'pk', 'title', 'description', 'url', 'tags', 'category',
                              'published_date', 'source_id')[:CANDIDATE_LIMIT])
        matches = []
        for article in candidates:
            hit = matched_field(pattern, article, surname_pattern)
            if hit:
                matches.append({**article, 'matched_in': hit[0], 'confidence': hit[1]})
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
            'matched_in': row['matched_in'], 'confidence': row['confidence'], 'material_type': material_type,
            'snippet': snippet_of(pattern, surname_pattern, row),
            'match_method': 'name_only',  # po samym nazwisku w tytule lub opisie; nie jest to identyfikator
            'kind_label': MATERIAL_LABELS[material_type],
        })
        if len(results) >= MENTION_LIMIT:
            break
    from news.article_changes import attach_change_flags
    attach_change_flags(results)
    return {'results': results}
