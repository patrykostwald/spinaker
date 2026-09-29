"""Wspólny słownik kategorii technik, promptów i walidacji diagnoz."""
import re
import unicodedata


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ł', 'l'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(
        char for char in value if not unicodedata.combining(char))).split())


# Kolejność rozstrzyga niejednoznaczności: szczegółowe techniki przed ogólnymi.
RULES = (
    ('Straszenie', r'strasz|strach|leku|katastrof'),
    ('Przypisywanie sobie zasług', r'zaslug|przypisanie wysilku'),
    ('Przypisywanie intencji', r'intencj|motywow|czytanie w mysl'),
    ('Atak na osobę', r'atak.*osob|ad hominem|personaln|dyskredyt'),
    ('Fałszywa alternatywa', r'alternatyw|dychotom|falszywy dylemat|zero jedynkow'),
    # przeinaczenie cudzego stanowiska przed ogólnym „przeinaczeniem”
    ('Słomiany człowiek', r'slomian|chochol|straw man|przeinaczenie (stanowiska|cudzej)'),
    ('Fałszywa analogia i skojarzenie', r'analogi|skojarzen|amalgamat|zestawienie|laczenie'),
    ('Przeinaczenie faktów', r'jako fakt|statusu faktu|przeinacz|przesuniecie kategorii|niedopasowan'),
    ('Sugestia i niedopowiedzenie', r'sugest|nieostr|nieokreslon|presupozyc|pytanie retoryczne|zakladanie zgody'),
    ('Fałszywa przyczynowość', r'przyczyn|korelac'),
    ('Liczba bez punktu odniesienia', r'(liczb|procent|kwot).*bez.*(odnies|porown|kontekst|zrodl)'),
    ('Wybiórcze dane', r'wybior|selektywn|cherry pick'),
    ('Pominięcie kontekstu', r'kontekst|przemilcz|pominie'),
    ('Nadmierne uogólnienie', r'uogol|generaliz|zawlaszczenie kategorii'),
    ('Etykietowanie', r'etykiet|stygmat|demoniz'),
    ('My kontra oni', r'my (kontra|i|przeciw) oni|polaryzac|podzial.*(my|oni)'),
    ('Zmiana tematu', r'zmiana tematu|odwr.*uwag|whatabout|a u was'),
    ('Odwołanie do autorytetu', r'autorytet|eksperc'),
    ('Teza bez dowodu', r'bez dowod|nieudowod|goloslown|ukryte zaloz|insynuac|dowod.*(nie pokaz|niepokaz)|teza.*dowod'
                        r'|skok wnioskow|bez pokrycia|niefalsyfikowal|samopotwierdz|kontrfaktyczn'),
    ('Przesada', r'przesad|hiperbol|wyolbrzym|wniosek.*przeslank|dramatyzac'),
    ('Apel do emocji', r'emocj'),
)
CANONICAL_TECHNIQUES = tuple(name for name, _ in RULES) + ('Inne',)

FAMILIES = {
    'fakty': ('Liczba bez punktu odniesienia', 'Wybiórcze dane', 'Pominięcie kontekstu',
              'Przeinaczenie faktów', 'Teza bez dowodu', 'Fałszywa przyczynowość',
              'Nadmierne uogólnienie', 'Fałszywa analogia i skojarzenie'),
    'emocje': ('Apel do emocji', 'Straszenie', 'Przesada', 'Etykietowanie', 'My kontra oni',
               'Sugestia i niedopowiedzenie'),
    'zagrania': ('Atak na osobę', 'Przypisywanie intencji', 'Słomiany człowiek', 'Fałszywa alternatywa',
                 'Zmiana tematu', 'Odwołanie do autorytetu', 'Przypisywanie sobie zasług'),
    'inne': ('Inne',),
}
FAMILY_LABELS = {'fakty': 'Fakty i liczby', 'emocje': 'Emocje i ramy',
                 'zagrania': 'Zagrania wobec innych', 'inne': 'Inne'}
FAMILY_DEFINITIONS = {
    'fakty': 'Dobór i przedstawianie faktów, liczb oraz związków między nimi.',
    'emocje': 'Wpływanie na odbiór przez emocje, język i ramy interpretacji.',
    'zagrania': 'Sposoby przedstawiania innych osób i prowadzenia sporu.',
    'inne': 'Techniki spoza trzech głównych rodzin.',
}


def technique_family(category):
    return next((family for family, categories in FAMILIES.items() if category in categories), 'inne')


DEFINITIONS = {
    'Straszenie': 'Budowanie lęku nieproporcjonalnego do przedstawionych faktów.',
    'Przypisywanie sobie zasług': 'Przedstawianie wspólnego lub cudzego osiągnięcia jako własnej zasługi.',
    'Przypisywanie intencji': 'Podawanie cudzych motywów jako faktu bez dowodu.',
    'Atak na osobę': 'Dyskredytowanie osoby zamiast odniesienia się do jej argumentu.',
    'Fałszywa alternatywa': 'Przedstawianie tylko dwóch możliwości mimo istnienia innych.',
    'Słomiany człowiek': 'Atakowanie zniekształconego stanowiska przeciwnika.',
    'Fałszywa analogia i skojarzenie': 'Łączenie zjawisk lub osób na podstawie nieuzasadnionego podobieństwa.',
    'Przeinaczenie faktów': 'Zniekształcanie faktów lub przedstawianie innego rodzaju informacji jako faktu.',
    'Sugestia i niedopowiedzenie': 'Sugerowanie wniosku przez niedopowiedzenie lub założenie ukryte w pytaniu.',
    'Fałszywa przyczynowość': 'Przedstawianie nieudowodnionego związku jako przyczyny i skutku.',
    'Liczba bez punktu odniesienia': 'Podawanie liczby bez porównania, okresu, źródła lub skali.',
    'Wybiórcze dane': 'Dobieranie danych z pominięciem niewygodnych wyników.',
    'Pominięcie kontekstu': 'Pomijanie okoliczności zmieniających znaczenie informacji.',
    'Nadmierne uogólnienie': 'Wyciąganie ogólnej reguły z niewystarczającej liczby przypadków.',
    'Etykietowanie': 'Zastępowanie opisu nacechowanym określeniem.',
    'My kontra oni': 'Budowanie podziału na własną grupę i wrogich obcych.',
    'Zmiana tematu': 'Odwracanie uwagi od omawianej kwestii.',
    'Odwołanie do autorytetu': 'Zastępowanie dowodu powołaniem się na autorytet.',
    'Teza bez dowodu': 'Przedstawianie twierdzenia bez uzasadniających je dowodów.',
    'Przesada': 'Wyolbrzymianie znaczenia faktu lub siły wynikającego z niego wniosku.',
    'Apel do emocji': 'Zastępowanie argumentacji wzbudzaniem emocji.',
    'Inne': 'Technika lub uwaga, której nie obejmuje żadna z pozostałych kategorii.',
}

CATEGORY_SCHEMA = {"type": "string", "enum": list(CANONICAL_TECHNIQUES)}
CATEGORY_PROMPT = (
    "\nKażda technika: category wybierz dokładnie z poniższej listy; name to krótka nazwa opisowa.\n"
    + "\n".join(f"- {name}: {DEFINITIONS[name]}" for name in CANONICAL_TECHNIQUES)
)


def technique_category(item):
    category = item.get("category")
    return category if category in CANONICAL_TECHNIQUES else canonical_technique(item.get("name", ""))


def categorize_techniques(items):
    return [{**item, "category": technique_category(item)} if isinstance(item, dict) else item
            for item in (items or [])]


def canonical_technique(name) -> str:
    text = normalized(name)
    for canonical, pattern in RULES:
        if text == normalized(canonical) or re.search(pattern, text):
            return canonical
    return 'Inne'


def technique_groups(techniques):
    return list(dict.fromkeys(technique_category(item)
                             for item in (techniques or []) if isinstance(item, dict)))
