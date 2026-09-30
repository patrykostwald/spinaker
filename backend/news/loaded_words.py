"""Heurystyczny słownik emocji; trafienie nie przesądza o manipulacji."""
import re

KINDS = {
    'strach': 'Strach i zagrożenie', 'gniew': 'Gniew i oburzenie',
    'pogarda': 'Pogarda i wyśmiewanie', 'duma': 'Duma i wspólnota',
    'litość': 'Współczucie i krzywda',
}
# Rdzenie kończą się na granicy słowa; alternacje obejmują oboczności odmiany.
ROOTS = {
    'strach': ('katastrof', 'zagroż', 'tragedi', 'dramat', 'zapaś[ćc]', 'chaos',
               'zniszcz', 'upad(?:ek|k|ł|a)', 'przeraż', 'groz', 'terror', 'panik',
               'niebezpiecz', 'zagład', 'apokalips', 'koszmar', 'ruin', 'śmier[ćct]',
               'śmierteln', 'krwaw', 'wojn', 'inwazj', 'agresj', 'paraliż',
               'bankruc', 'kataklizm', 'spustosz', 'zastrasz'),
    'gniew': ('skandal', 'hańb', 'zdrad', 'oszuk', 'okłam', 'kłam', 'złodziej',
              'bezczel', 'oburz', 'wściek', 'nikczemn', 'podłoś', 'podł[yae]',
              'haniebn', 'szant[aą]ż', 'korupcj', 'korupcyjn', 'łapów', 'grabież',
              'rabun', 'zagrabi', 'bezpraw', 'naduży', 'oszust', 'drań', 'szubraw',
              'sprzeniewierz', 'niegodziw'),
    'pogarda': ('nieudoln', 'ośmiesz', 'kompromitac', 'kompromituj', 'żałos',
                'dyletant', 'amator', 'idiot', 'głup', 'debil', 'pajac', 'błaz[enń]',
                'śmieszn', 'kpina', 'kpin[ęyą]', 'kpi[ćł]', 'pogard', 'miernot',
                'niekompeten', 'tchórz', 'hipokry', 'marionet', 'popychad',
                'nieudacz', 'pośmiew', 'zacofan', 'prymityw', 'poraż'),
    'duma': ('bohater', 'patriot', 'suweren', 'godnoś', 'godno[śs]ci', 'zwycięstw',
             'zwycięż', 'dum[anyąę]', 'dumn', 'wspólnot', 'solidarnoś', 'solidarności',
             'niezłomn', 'niepokonan', 'hero', 'waleczn', 'odważ', 'męstw',
             'chwał', 'chwalebn', 'triumf', 'niepodległ', 'ojczyzn', 'honor',
             'dzieln', 'poświęceń', 'poświęceni', 'braterstw'),
    'litość': ('krzywd', 'ofiar', 'cierpi', 'cierpie', 'cierpiał', 'bezbronn',
               'skrzywdz', 'poszkodowan', 'pokrzywdzon', 'nieszczęś', 'nieszczę[śs]ci',
               'bied', 'ubóstw', 'głod', 'głód', 'osieroc', 'sierot', 'opuszczon',
               'samotn', 'bezsiln', 'bezradn', 'rozpacz', 'łez', 'łzy', 'udręcz',
               'poniewieran', 'prześladow', 'wykluczon'),
}
PHRASES = {'litość': (r'odebran\w*\s+dzieci\w*', r'odebrano\s+\w+\s+dzieci',
                       r'odbier\w*\s+dzieci\w*')}
# Wyjątki obejmują tylko lokalny zwrot, nie cały wpis.
EXCEPTIONS = (
    r'\bdramat\w*\s+(?:teatraln\w*|literack\w*|filmow\w*|romantyczn\w*|antyczn\w*)',
    r'\b(?:gatunek\s+literacki|gatunek|film|sztuka)\s*[:–-]?\s*dramat\w*',
    r'\bofiar\w*\s+(?:pieniężn\w*|na\s+(?:tacę|kościół|cele\s+charytatywne))',
    r'\b(?:złoży\w*|składa\w*)\s+ofiar\w*\s+na\s+\w+',
)
PATTERNS = {kind: re.compile(r'(?<!\w)(?:' + '|'.join(
    [root + r'[^\W\d_]*' for root in roots] + list(PHRASES.get(kind, ()))) + r')(?!\w)', re.I)
    for kind, roots in ROOTS.items()}
LOADED_PROMPT = ('\nOpcjonalne loaded_words: najwyżej 8 dokładnych słów lub zwrotów z wpisu, '
                 'które zamiast informować mają wzbudzić emocję, z polami word i kind. '
                 'kind: strach, gniew, pogarda, duma lub litość; stosuj tę samą miarę dla obu stron.')
LOADED_SCHEMA = {'type': 'array', 'maxItems': 8, 'items': {'type': 'object',
    'properties': {'word': {'type': 'string'}, 'kind': {'type': 'string', 'enum': list(KINDS)}},
    'required': ['word', 'kind']}}


def loaded_words(text):
    excluded = [m.span() for pattern in EXCEPTIONS for m in re.finditer(pattern, text or '', re.I)]
    hits = sorted((m.start(), m.end(), kind) for kind, pattern in PATTERNS.items()
                  for m in pattern.finditer(text or ''))
    result, seen = [], set()
    for start, end, kind in hits:
        word = text[start:end]
        if word.casefold() in seen or any(a <= start and end <= b for a, b in excluded):
            continue
        seen.add(word.casefold())
        result.append({'word': word, 'kind': kind})
    return result


def validate_loaded_words(text, items):
    """Przywraca pisownię z wpisu, odrzuca obce cytaty i scala powtórzenia."""
    result, seen = [], set()
    dictionary = {item['word'].casefold(): item['kind'] for item in loaded_words(text)}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get('word'), str):
            continue
        word = item['word'].strip()
        if not word:
            continue
        match = re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text, re.I)
        kind = item.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            kind = dictionary.get(word.casefold())
        if not match or not kind or word.casefold() in seen:
            continue
        seen.add(word.casefold())
        result.append((match.start(), {'word': match.group(), 'kind': kind}))
    return [item for _, item in sorted(result, key=lambda hit: hit[0])][:8]


def loaded_data(text, items=None):
    words = validate_loaded_words(text, items)
    source = 'model' if words else 'słownik'
    words = words or loaded_words(text)
    return {'count': len(words), 'words': words[:8],
            'by_kind': {kind: sum(w['kind'] == kind for w in words) for kind in KINDS},
            'source': source}
