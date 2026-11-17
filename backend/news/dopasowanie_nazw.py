"""Dopasowanie podmiotu po nazwie z drugim, niezależnym danym (zasada właściciela 6.11.2026, docs/PRZESZLOSC_ZRODLA_DANYCH.md).

Klasy (od najpewniejszej):
- 'nazwa_i_siedziba': nazwa identyczna po normalizacji (z formą prawną) i zgodna siedziba (miejscowość, kod pocztowy albo
  województwo), dokładnie jeden kandydat; pokazujemy jako „dopasowanie po nazwie i siedzibie”, bez wliczania do sum;
- 'nazwa': sama nazwa, dokładnie jeden kandydat (przy znanej, a sprzecznej siedzibie `conflict` = True): „niepowiązane”;
- brak wyniku: zero kandydatów albo dwóch i więcej (niejednoznaczne), nic nie łączymy.
Nigdy nie łączymy po osobach (reprezentanci to dane osób). Wynik to wskazówka, nie identyfikator: do sum wchodzą tylko NIP i KRS.
"""
import re
import unicodedata

LEGAL_FORMS = (
    (r'spolka z ograniczona odpowiedzialnoscia|sp\.? ?z ?o\.? ?o\.?', 'spzoo'),
    (r'spolka akcyjna|s\.? ?a\.?', 'sa'),
    (r'spolka komandytowo-akcyjna|s\.? ?k\.? ?a\.?', 'ska'),
    (r'spolka komandytowa|sp\.? ?k\.?', 'spk'),
    (r'spolka jawna|sp\.? ?j\.?', 'spj'),
)
_FOLD = str.maketrans({'ł': 'l', 'Ł': 'L'})


def fold(text):
    """Małe litery bez polskich znaków i interpunkcji (ł obsłużone osobno: NFD jej nie rozkłada)."""
    text = unicodedata.normalize('NFKD', str(text or '').translate(_FOLD))
    text = ''.join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r'\s+', ' ', re.sub(r'[„”"\'`]', '', text)).strip()


def normalize_name(name):
    """Nazwa do porównania: bez znaków diakrytycznych, cudzysłowów i różnic zapisu form prawnych („sp. z o.o.” = „spółka z ograniczoną
    odpowiedzialnością”); skróty są tokenami, więc „Orlen SA” różni się od „Orlen sp. z o.o.”."""
    text = fold(name)
    for pattern, token in LEGAL_FORMS:
        text = re.sub(rf'(?<![a-z0-9])(?:{pattern})(?![a-z0-9])', f' {token} ', text)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', text)).strip()


def same_place(seat, asked):
    """True/False, gdy da się porównać (obie strony znają dane), None, gdy brak danych do porównania."""
    pairs = [(fold(seat.get(k)), fold(asked.get(k))) for k in ('city', 'postal_code', 'voivodeship') if seat.get(k) and asked.get(k)]
    if not pairs:
        return None
    return any(a == b for a, b in pairs)


def choose(candidates, name, city='', postal_code='', voivodeship=''):
    """candidates: [{'name','city','postal_code','voivodeship', ...}] -> (klasa, kandydat, konflikt) albo (None, None, False).
    Najpierw ci o tej samej nazwie; siedziba zawęża, ale nie unieważnia (miejsce realizacji bywa inne niż siedziba)."""
    wanted = normalize_name(name)
    if not wanted:
        return None, None, False
    named = [c for c in candidates if normalize_name(c.get('name')) == wanted]
    asked = {'city': city, 'postal_code': postal_code, 'voivodeship': voivodeship}
    if not named:
        return None, None, False
    if any(asked.values()):
        agreeing = [c for c in named if same_place(c, asked) is True]
        if len(agreeing) == 1:
            return 'nazwa_i_siedziba', agreeing[0], False
        if len(agreeing) > 1:
            return None, None, False
    if len(named) == 1:
        conflict = any(asked.values()) and same_place(named[0], asked) is False
        return 'nazwa', named[0], bool(conflict)
    return None, None, False


def match_own(name, city='', postal_code='', voivodeship=''):
    """Dopasowanie do podmiotów, które już mamy (RegisteredOrganisation, bez wyszukiwania w sieci). Zwraca słownik albo None."""
    from news.political_models import RegisteredOrganisation
    wanted = normalize_name(name)
    if len(wanted) < 4:
        return None
    first = wanted.split(' ')[0]
    pool = [o for o in RegisteredOrganisation.objects.filter(archived=False, name__icontains=first[:6]) if normalize_name(o.name) == wanted]
    # nazwy w bazie bywają zapisane z innymi znakami (ł, ó): gdy filtr po początku nic nie dał, przeglądamy całość raz
    if not pool:
        pool = [o for o in RegisteredOrganisation.objects.filter(archived=False) if normalize_name(o.name) == wanted]
    candidates = [{'name': o.name, 'city': o.seat_city, 'postal_code': o.seat_postal_code, 'voivodeship': o.seat_voivodeship, 'org': o}
                  for o in pool]
    kind, hit, conflict = choose(candidates, name, city, postal_code, voivodeship)
    if kind is None:
        return None
    org = hit['org']
    return {'class': kind, 'conflict': conflict, 'organisation_id': org.pk, 'krs_number': org.krs_number, 'nip': org.nip, 'name': org.name}
