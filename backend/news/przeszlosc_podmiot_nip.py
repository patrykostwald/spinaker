"""Podmiot po NIP bez wpisu z KRS (6.11.2026, wniosek 1 rundy person 2): gminy, jednostki budżetowe i inne podmioty spoza rejestru.

Pokazujemy to, co mamy w danych i da się powiązać WYŁĄCZNIE po numerze NIP (te same zasady i te same funkcje co drzewo spółki):
ogłoszenia BZP (podmiot jako zamawiający), TED (podmiot jako wykonawca) i dotacje UE z FTS (po VAT). Nic o osobach, żadnych nazw
„po zgodności”: nazwa i miejscowość pochodzą z ogłoszeń BZP tego samego NIP-u. Brak danych znaczy „brak w naszych danych”.
"""
import re
from collections import Counter

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

LIMIT = 50
WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
NOTE_NO_KRS = ('Ten podmiot nie ma u nas wpisu z KRS (np. gmina, jednostka budżetowa albo podmiot spoza rejestru przedsiębiorców). '
               'Pokazujemy ogłoszenia i dotacje powiązane wyłącznie po numerze NIP.')
NOTE_EMPTY = ('Brak w naszych danych: nie mamy ogłoszeń BZP ani TED, ani dotacji z FTS powiązanych z tym NIP-em. '
              'To nie znaczy, że ich nie ma: BZP zbieramy od września 2025, TED od października 2025, FTS po numerze VAT.')


def valid_nip(value):
    """10 cyfr z poprawną sumą kontrolną (wagi 6,5,7,2,3,4,5,6,7, modulo 11)."""
    d = re.sub(r'\D', '', str(value or ''))
    if len(d) != 10:
        return None
    total = sum(int(c) * w for c, w in zip(d[:9], WEIGHTS)) % 11
    return d if total != 10 and total == int(d[9]) else None


def _identity(nip):
    """Nazwa i miejscowość z ogłoszeń BZP tego NIP-u (najczęstsze wartości); pusto, gdy nie ma ogłoszeń."""
    from news.drzewo_pieniedzy import _records, matched_by
    names, cities, provinces = Counter(), Counter(), Counter()
    for r in _records('bzp', 'notice', 'organizationNationalId', [nip])[:200]:
        if not matched_by(r.data.get('organizationNationalId'), {'NIP': nip}):
            continue
        for counter, key in ((names, 'organizationName'), (cities, 'organizationCity'), (provinces, 'organizationProvince')):
            value = str(r.data.get(key) or '').strip()
            if value:
                counter[value] += 1
    top = lambda c: c.most_common(1)[0][0] if c else ''   # noqa: E731
    return {'name': top(names), 'city': top(cities), 'province': top(provinces)}


def build(nip):
    from news.drzewo_pieniedzy import _sums, contracts, grants
    from news.political_models import RegisteredOrganisation
    org = RegisteredOrganisation.objects.filter(nip=nip, archived=False).order_by('pk').first()
    if org is not None:
        return {'nip': nip, 'status': 'krs', 'name': org.name, 'krs_number': org.krs_number, 'url': f'/przeszlosc/spolka/{org.krs_number}',
                'note': 'Ten podmiot ma wpis z KRS: pełne drzewo zamówień, dotacji i osób jest na jego stronie.'}
    ids = {'NIP': nip}
    c, g = contracts(None, ids), grants(None, ids)
    identity = _identity(nip)
    if not c and not g:
        return {'nip': nip, 'status': 'empty', 'name': '', 'city': '', 'province': '', 'note': NOTE_EMPTY,
                'contracts': {'count': 0, 'sums': [], 'results': []}, 'grants': {'count': 0, 'sums': [], 'results': []}}
    return {'nip': nip, 'status': 'found', **identity, 'note': NOTE_NO_KRS,
            'contracts': {'count': len(c), 'sums': _sums(c), 'suspect_count': sum(1 for x in c if x.get('amount_suspect')), 'results': c[:LIMIT]},
            'grants': {'count': len(g), 'sums': _sums(g), 'results': g[:LIMIT]},
            'sources': [{'key': 'bzp', 'label': 'Biuletyn Zamówień Publicznych (ezamowienia.gov.pl)', 'url': 'https://ezamowienia.gov.pl/'},
                        {'key': 'ted', 'label': 'TED (Tenders Electronic Daily, UE)', 'url': 'https://ted.europa.eu/'},
                        {'key': 'fts', 'label': 'Financial Transparency System (Komisja Europejska)', 'url': 'https://ec.europa.eu/budget/fts/'}],
            'rules': 'Łączymy wyłącznie po numerze NIP (dla FTS po numerze VAT). Kwoty z ogłoszeń, nie z umów; pozycje oznaczone jako wątpliwe nie wchodzą do sum.'}


def has_data(nip):
    """Szybkie pytanie dla wyszukiwarki: czy widok „po NIP” ma cokolwiek do pokazania."""
    from news.drzewo_pieniedzy import _records, matched_by
    for source, kind, key in (('bzp', 'notice', 'organizationNationalId'), ('fts', 'eu_grant', 'vat')):
        if any(matched_by(r.data.get(key), {'NIP': nip}) for r in _records(source, kind, key, [nip])[:20]):
            return True
    return False


@api_view(['GET'])
@permission_classes([AllowAny])
def podmiot_view(request, nip):
    """GET /api/przeszlosc/podmiot/<NIP>/ - zamówienia i dotacje podmiotu bez KRS (po samym NIP)."""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    valid = valid_nip(nip)
    if valid is None:
        return Response({'detail': 'To nie jest poprawny numer NIP (10 cyfr z sumą kontrolną).'}, status=400)
    response = Response(build(valid))
    response['Cache-Control'] = 'public, max-age=300'
    return response
