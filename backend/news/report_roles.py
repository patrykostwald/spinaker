"""Only code-reviewed roles may participate. Material cannot supply instructions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    label: str
    competence: str
    instruction: str


ROLES = {
    'politics': Role('Politolog', 'Procesy polityczne', 'Sprawdź opis instytucji i procesów; nie przypisuj intencji.'),
    'statistics': Role('Statystyk', 'Metoda i liczby', 'Sprawdź mianowniki, dobór próby, braki, porównania i wnioski. Próba nie jest reprezentatywna.'),
    'law': Role('Prawnik', 'Prawo prasowe, dobra osobiste, RODO', 'Wskaż zarzuty bez dowodów, dane zbędne i cudze treści. Nie uznawaj recenzji za poradę prawną.'),
    'communication': Role('Komunikacja', 'Techniki manipulacji', 'Sprawdź techniki i odróżnienie faktów od naszej diagnozy.'),
    'facts': Role('Fact-checker', 'Śledzenie pochodzenia twierdzeń', 'Sprawdź KAŻDE zdanie wobec wskazanych fact_ids. Brak potwierdzenia jest uwagą krytyczną.'),
    'impartiality': Role('Bezstronność', 'Symetria kryteriów', 'Ta sama miara dla rządzących i opozycji, niezależnie od odbiorcy raportu.'),
    'energy': Role('Energetyka', 'Rynek energii i regulacje', 'Sprawdź jednostki, regulacje i zakres wniosków dotyczących energii. Nie uzupełniaj brakujących faktów.'),
    'economy': Role('Ekonomia', 'Finanse i gospodarka', 'Sprawdź wartości nominalne, realne, podstawę porównań i rozróżnienie korelacji od przyczynowości.'),
    'linguist': Role('Językoznawca', 'Polszczyzna i angielski', 'Oceń język wskazany w danych: profesjonalny, krótki, rzeczowy. Tylko krótkie myślniki. Nie zmieniaj tekstu; zgłoś poprawki.'),
    'council': Role('Konsylium', 'Ostateczna ocena raportu', 'Głosuj publish/revise/reject z uzasadnieniem. Sprawdź tekst, dane, metodę i recenzje. Nie publikujesz ani nie wysyłasz raportu.'),
}
CORE_ROLES = ('politics', 'statistics', 'law', 'communication', 'facts', 'impartiality')
EXTRA_ROLES = ('energy', 'economy')


def validate_roles(items):
    if not isinstance(items, list) or len(items) > 2:
        raise ValueError('Nieprawidłowa lista konsultacji.')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'role', 'reason'} or item['role'] not in EXTRA_ROLES
                or item['role'] in seen or not isinstance(item['reason'], str) or not item['reason'].strip()
                or len(item['reason']) > 400):
            raise ValueError('Konsultacja wymaga roli z rejestru i uzasadnienia.')
        seen.add(item['role'])
    return items
