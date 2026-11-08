"""Sprawozdania finansowe partii i komitetów z pkw.gov.pl (6.11.2026): spis dokumentów z wyszukiwaniem po nazwie i streszczeniem uchwał.

Spis to dokumenty z pkw.gov.pl (tytuł, adres PDF). Dla uchwał PKW o sprawozdaniach partii, które mają warstwę tekstową, dołączamy
streszczenie odczytane z tekstu (decyzja, rok, łączne przychody, składki i darowizny zbiorczo, wpływy na Fundusz Wyborczy; scraper.
public_record_parsers.pkw_report). Skanów formularzy (sprawozdania komitetów) NIE czytamy (zasada: bez OCR), a nazwisk darczyńców,
numerów rachunków i adresów nie zapisujemy; ten widok zawsze odsyła do oryginału. Data publikacji to czas wgrania pliku na stronę PKW
z prefiksu nazwy pliku (sekundy Unix), nie data sprawozdania; data uchwały jest osobno w streszczeniu.
"""
import re
from datetime import datetime, timezone

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

PER_PAGE = 20
PAGE_MAX = 50
CACHE_KEY = 'przeszlosc:pkw:spis:v2'
CACHE_TTL = 600
KINDS = {'partia': 'Partia polityczna (ewidencja)', 'komitet': 'Komitet wyborczy', 'zalacznik': 'Załącznik do sprawozdania', 'inne': 'Inny dokument'}
NOTE = ('Spis dokumentów z pkw.gov.pl. Przy uchwałach PKW o sprawozdaniach partii pokazujemy kwoty odczytane z tekstu uchwały (z cytatem); '
        'skanów formularzy komitetów nie czytamy (bez OCR), więc tam otwórz oryginał. Nie zapisujemy nazwisk darczyńców ani numerów rachunków. '
        'Data publikacji to czas wgrania pliku na stronę PKW, nie data sprawozdania.')
REASONS = {'skan_bez_warstwy_tekstowej': 'skan formularza bez warstwy tekstowej (nie stosujemy OCR)',
           'nie_jest_uchwala_o_sprawozdaniu': 'dokument nie jest uchwałą o sprawozdaniu partii',
           'invalid_or_large_pdf': 'plik zbyt duży albo uszkodzony', 'pdf_requires_manual_review': 'plik wymaga ręcznego przeglądu'}
AMOUNT_LABELS = {'income_total': 'Przychody ogółem', 'individuals_total': 'Wpłaty osób fizycznych (zbiorczo)', 'membership_fees': 'w tym składki członkowskie',
                 'donations_cash': 'w tym darowizny pieniężne', 'non_cash_value': 'Wartości niepieniężne', 'election_fund_inflow': 'Wpływy na Fundusz Wyborczy'}


def _published(url):
    match = re.search(r'/uploaded_files/(\d{10})_', url or '')
    if not match:
        return None
    try:
        return datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


def _kind(title):
    low = (title or '').casefold()
    if '(ewp' in low:
        return 'partia'
    if 'załącznik' in low[:40] or 'zalacznik' in low[:40]:
        return 'zalacznik'          # „9) Załącznik nr 9 Komitet Wyborczy…” to załącznik, nie komitet
    if low.lstrip().startswith(('komitet', 'kw ', 'kww ')) or 'komitet wyborczy' in low:
        return 'komitet'
    return 'inne'


def _report(data):
    """Streszczenie z uchwały (tylko pola jawne i kwoty z cytatem) albo powód braku odczytu; None, gdy PDF jeszcze nie był czytany."""
    if not data:
        return None
    if not data.get('readable'):
        return {'readable': False, 'reason': REASONS.get(data.get('reason'), data.get('reason') or 'brak odczytu')}
    return {'readable': True, 'resolution': data.get('resolution'), 'resolution_date': data.get('resolution_date'), 'year': data.get('report_year'),
            'name': data.get('name'), 'decision': data.get('decision'), 'with_irregularity': bool(data.get('with_irregularity')),
            'amounts': [{'key': k, 'label': AMOUNT_LABELS[k], 'value': v, 'currency': data.get('currency') or 'PLN', 'quote': (data.get('evidence') or {}).get(k, '')}
                        for k, v in (data.get('amounts') or {}).items() if k in AMOUNT_LABELS]}


def catalogue():
    """Wszystkie dokumenty (kilkaset): [{title, kind, published, url, report}]: najpierw z odczytanymi kwotami, potem od najnowszych; cache 10 min."""
    rows = cache.get(CACHE_KEY)
    if rows is None:
        from news.public_records_models import PublicRecord
        reports = {k: d for k, d in PublicRecord.objects.filter(source='pkw', kind='financial_report').values_list('external_id', 'data')}
        rows = []
        for key, title, url in PublicRecord.objects.filter(source='pkw', kind='financial_document').values_list('external_id', 'title', 'source_url'):
            when = _published(url)
            rows.append({'title': (title or '').strip()[:300], 'kind': _kind(title), 'published': when.isoformat() if when else None, 'url': url,
                         'report': _report(reports.get(key))})
        # Najpierw odczytane uchwały, w nich najpierw te z kwotami (najcenniejsze dla czytelnika), potem od najnowszych plików.
        rows.sort(key=lambda r: (bool(r['report'] and r['report'].get('readable')), bool(r['report'] and r['report'].get('amounts')), r['published'] or '', r['title']), reverse=True)
        cache.set(CACHE_KEY, rows, CACHE_TTL)
    return rows


def search(query='', kind='', with_data=False):
    words = [w.casefold() for w in re.split(r'\s+', (query or '').strip()) if w]
    out = []
    for r in catalogue():
        if kind and r['kind'] != kind:
            continue
        if with_data and not (r['report'] and r['report'].get('readable')):
            continue
        low = r['title'].casefold()
        if all(w in low for w in words):
            out.append(r)
    return out


@api_view(['GET'])
@permission_classes([AllowAny])
def pkw_view(request):
    """GET /api/przeszlosc/pkw/?q=<fragment nazwy>&rodzaj=partia|komitet|zalacznik|inne&z_danymi=1&strona=1&na_strone=20"""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    query = (request.query_params.get('q') or '').strip()[:120]
    kind = (request.query_params.get('rodzaj') or '').strip()
    if kind and kind not in KINDS:
        return Response({'detail': 'Rodzaj: partia, komitet, zalacznik albo inne.'}, status=400)
    try:
        page = max(1, int(request.query_params.get('strona') or 1))
        per_page = max(1, min(PAGE_MAX, int(request.query_params.get('na_strone') or PER_PAGE)))
    except ValueError:
        return Response({'detail': 'Strona i liczba na stronę to liczby.'}, status=400)
    everything = catalogue()
    with_data = (request.query_params.get('z_danymi') or '') in ('1', 'true')
    found = search(query, kind, with_data)
    pages = max(1, -(-len(found) // per_page))
    page = min(page, pages)
    counts = {k: sum(1 for r in everything if r['kind'] == k) for k in KINDS}
    response = Response({'query': query, 'filter': {'rodzaj': kind or None, 'z_danymi': with_data}, 'total': len(found), 'all': len(everything),
                         'with_data': sum(1 for r in everything if r['report'] and r['report'].get('readable')), 'page': page, 'pages': pages,
                         'per_page': per_page, 'kinds': [{'key': k, 'label': KINDS[k], 'count': counts[k]} for k in KINDS if counts[k]],
                         'results': found[(page - 1) * per_page: page * per_page], 'note': NOTE,
                         'source': {'label': 'Państwowa Komisja Wyborcza, finansowanie polityki', 'url': 'https://pkw.gov.pl/finansowanie-polityki/'}})
    response['Cache-Control'] = 'public, max-age=300'
    return response
