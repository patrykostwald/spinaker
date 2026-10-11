"""Słownik skrótów i odmian tematów przeszłość.today w jednym miejscu (Śledczy 11.10: CPK i Turów miały 0 głosowań).

SKROTY: skrót → pełne nazwy w odmianach; wyszukiwanie łapie skrót i każdą z nich (dokładny zapis, bez szumu).
ODMIANY: rdzeń nazwy własnej → wszystkie formy fleksyjne, także te, których wspólny początek wyrazu nie obejmuje
(Turów / Turowa / Turowie / Turowem, ale też Turowie przy nazwie z „ó”). Obie tabele działają tak samo dla każdego tematu.
"""

SKROTY = {
    'cpk': ['Centralny Port Komunikacyjny', 'Centralnego Portu Komunikacyjnego', 'Centralnemu Portowi Komunikacyjnemu',
            'Centralnym Portem Komunikacyjnym', 'Centralnym Porcie Komunikacyjnym', 'Port Polska', 'Portu Polska', 'Portem Polska',
            'Portowi Polska', 'Porcie Polska'],
    'kpo': ['Krajowy Plan Odbudowy', 'Krajowego Planu Odbudowy'], 'krrit': ['Krajowa Rada Radiofonii', 'Krajowej Rady Radiofonii'],
    'nfz': ['Narodowy Fundusz Zdrowia', 'Narodowego Funduszu Zdrowia'], 'zus': ['Zakład Ubezpieczeń Społecznych', 'Zakładu Ubezpieczeń Społecznych'],
    'oze': ['odnawialnych źródeł', 'odnawialne źródła'],
    'vat': ['podatek od towarów i usług', 'podatku od towarów i usług', 'podatkiem od towarów i usług'],
    'pit': ['podatek dochodowy od osób fizycznych', 'podatku dochodowym od osób fizycznych', 'podatku dochodowego od osób fizycznych'],
    'cit': ['podatek dochodowy od osób prawnych', 'podatku dochodowym od osób prawnych', 'podatku dochodowego od osób prawnych'],
    'mon': ['Ministerstwo Obrony Narodowej', 'Ministra Obrony Narodowej', 'obronie Ojczyzny', 'obrony narodowej'],
    'nato': ['Sojuszu Północnoatlantyckiego', 'Traktatu Północnoatlantyckiego'],
    'cpn': ['paliw', 'stacjach paliw', 'cen paliw', 'Ceny Paliw Niżej'],
    'rcb': ['Rządowe Centrum Bezpieczeństwa', 'Rządowego Centrum Bezpieczeństwa', 'zarządzaniu kryzysowym'],
    'ue': ['Unii Europejskiej', 'Unia Europejska'], 'krs': ['Krajowy Rejestr Sądowy', 'Krajowego Rejestru Sądowego'],
    'tk': ['Trybunał Konstytucyjny', 'Trybunału Konstytucyjnego'], 'sn': ['Sąd Najwyższy', 'Sądu Najwyższego'],
    'pkp': ['Polskie Koleje Państwowe', 'kolei'], 'lpg': ['gazu płynnego', 'autogazu'],
}

# Klucz: słowo zapytania małymi literami (także bez polskich znaków); wartość: formy do dopasowania obok rdzenia.
ODMIANY = {
    'turów': ['Turów', 'Turowa', 'Turowie', 'Turowem', 'Turowowi', 'Turowska', 'Turowskiej', 'Turowskiego'],
    'turow': ['Turów', 'Turowa', 'Turowie', 'Turowem', 'Turowowi', 'Turowska', 'Turowskiej', 'Turowskiego'],
    'turowa': ['Turów', 'Turowa', 'Turowie', 'Turowem', 'Turowowi'],
    'turowie': ['Turów', 'Turowa', 'Turowie', 'Turowem', 'Turowowi'],
    'turowem': ['Turów', 'Turowa', 'Turowie', 'Turowem', 'Turowowi'],
}


def formy(term):
    """Dodatkowe formy dla słowa zapytania (skrót → pełne nazwy, nazwa własna → odmiany); puste, gdy słownik nic nie wie."""
    key = term.lower().strip()
    return list(SKROTY.get(key, [])) + list(ODMIANY.get(key, []))
