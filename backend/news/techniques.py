"""Deterministyczny słownik do odczytu; nie modyfikuje diagnoz AI."""
import re
import unicodedata


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ł', 'l'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(
        char for char in value if not unicodedata.combining(char))).split())


# Kolejność rozstrzyga niejednoznaczności: szczegółowe techniki przed ogólnymi.
RULES = (
    ('Straszenie', r'strasz|strach|leku|katastrof'),
    ('Przypisywanie intencji', r'intencj|motywow|czytanie w mysl'),
    ('Atak na osobę', r'atak.*osob|ad hominem|personaln|dyskredyt'),
    ('Fałszywa alternatywa', r'alternatyw|dychotom|falszywy dylemat'),
    ('Słomiany człowiek', r'slomian|chochol|straw man'),
    ('Fałszywa przyczynowość', r'przyczyn|korelac'),
    ('Liczba bez punktu odniesienia', r'(liczb|procent|kwot).*bez.*(odnies|porown|kontekst|zrodl)'),
    ('Wybiórcze dane', r'wybior|selektywn|cherry pick'),
    ('Pominięcie kontekstu', r'kontekst|przemilcz|pominie'),
    ('Nadmierne uogólnienie', r'uogol|generaliz|zawlaszczenie kategorii'),
    ('Etykietowanie', r'etykiet|stygmat|demoniz'),
    ('My kontra oni', r'my (kontra|i|przeciw) oni|polaryzac|podzial.*(my|oni)'),
    ('Zmiana tematu', r'zmiana tematu|odwr.*uwag|whatabout|a u was'),
    ('Odwołanie do autorytetu', r'autorytet|eksperc'),
    ('Teza bez dowodu', r'bez dowod|nieudowod|goloslown|ukryte zaloz|insynuac|dowod.*(nie pokaz|niepokaz)|teza.*dowod'),
    ('Przesada', r'przesad|hiperbol|wyolbrzym|wniosek.*przeslank'),
    ('Apel do emocji', r'emocj'),
)
CANONICAL_TECHNIQUES = tuple(name for name, _ in RULES) + ('Inne',)


def canonical_technique(name) -> str:
    text = normalized(name)
    for canonical, pattern in RULES:
        if text == normalized(canonical) or re.search(pattern, text):
            return canonical
    return 'Inne'


def technique_groups(techniques):
    return list(dict.fromkeys(canonical_technique(item.get('name', ''))
                             for item in (techniques or []) if isinstance(item, dict)))
