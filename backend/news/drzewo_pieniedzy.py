"""Drzewo przepływu pieniędzy (właściciel 6.10, obiecane publicznie), wersja 1: z danych, które już zbieramy, bez sieci.

Spółka albo fundacja z KRS (RegisteredOrganisation) -> gałęzie:
- zamówienia publiczne: ogłoszenia TED, w których podmiot jest wykonawcą (identyfikator wykonawcy), i ogłoszenia BZP,
  w których podmiot jest zamawiającym (NIP zamawiającego);
- dotacje UE: wiersze FTS (budżet UE zarządzany przez KE) po numerze VAT beneficjenta;
- osoby z funkcjami w KRS: potwierdzone relacje PublicFigureOrganisationRelation z odnośnikiem do profilu przeszłość.today.

Łączenie wyłącznie po identyfikatorach (NIP, KRS, REGON) - LEGAL w pracownia_osint.py: nigdy po samej nazwie. Rekordy,
które zbieracz dopasował tylko po nazwie (Kohesio, FTS bez VAT), są pokazywane osobno jako „niepowiązane” i nie wchodzą
do sum. Ta sama miara dla wszystkich: bez filtra politycznego i bez oceny; kwoty z ogłoszeń, nie z umów.
Każdy węzeł ma źródło z licencją jak inne bloki przeszłość.today.
"""
import re
from collections import defaultdict
from functools import reduce
from operator import or_

from news import krs
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

SOURCES = {
    'krs': {'key': 'krs', 'label': 'Krajowy Rejestr Sądowy (api-krs.ms.gov.pl)', 'license': 'dane publiczne rejestru',
            'url': 'https://api-krs.ms.gov.pl/'},
    'ted': {'key': 'ted', 'label': 'TED - Tenders Electronic Daily (Urząd Publikacji UE)',
            'license': 'ponowne wykorzystanie dozwolone (decyzja KE 2011/833/UE)', 'url': 'https://ted.europa.eu/'},
    'bzp': {'key': 'bzp', 'label': 'Biuletyn Zamówień Publicznych (ezamowienia.gov.pl)', 'license': 'informacja publiczna',
            'url': 'https://ezamowienia.gov.pl/'},
}
NOTE = ('Powiązania tylko po identyfikatorach (NIP, KRS, REGON), tą samą miarą dla wszystkich: bez oceny i bez filtra politycznego. '
        'Kwoty z ogłoszeń, nie z umów. Funkcje w KRS to kontekst osoby, nie dowód winy.')
UNLINKED_REASON = 'zgodność nazwy, bez identyfikatora'
ROLE = {'ted': 'wykonawca', 'bzp': 'zamawiający'}
PER_BRANCH = 60


def digits(value):
    return re.sub(r'\D', '', str(value or ''))


def identifiers(org):
    """{'NIP': ..., 'KRS': ..., 'REGON': ...} - tylko wypełnione; wartości to same cyfry."""
    return {k: v for k, v in (('NIP', digits(org.nip)), ('KRS', digits(org.krs_number)), ('REGON', digits(org.regon))) if v}


def matched_by(value, ids):
    """Nazwa identyfikatora, gdy wartość z rekordu (np. „PL5260250995”, „KRS 0000012345”) to dokładnie jeden z naszych."""
    d = digits(value)
    return next((k for k, v in ids.items() if d and d == v), None) if d else None


def variants(value):
    """Zapisy tego samego identyfikatora w rejestrach: same cyfry (także po „PL”) i NIP z kreskami (526-025-09-95, 526-02-50-995)."""
    d = digits(value)
    out = [d] if d else []
    if len(d) == 10:
        out += [f'{d[:3]}-{d[3:6]}-{d[6:8]}-{d[8:]}', f'{d[:3]}-{d[3:5]}-{d[5:7]}-{d[7:]}']
    return out


def _records(source, kind, key, needles):
    """Wstępny wybór po tekście pola JSON (działa na SQLite i Postgres); dopasowanie rozstrzyga matched_by na cyfrach."""
    from news.public_records_models import PublicRecord
    needles = [v for n in needles for v in variants(n)]
    if not needles:
        return PublicRecord.objects.none()
    q = reduce(or_, (Q(**{f'data__{key}__icontains': n}) for n in needles))
    return PublicRecord.objects.filter(q, source=source, kind=kind).order_by(F('date').desc(nulls_last=True), '-pk')


def _amount(value):
    try:
        return round(float(value), 2) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


# Walidacja kwot (Śledczy R1, P0-1): jedno ogłoszenie TED z kwotą bilionową (błąd źródła lub parsera) zepsułoby
# sumę spółki. Rekord podejrzany zostaje na liście z flagą, ale nie wchodzi do sum.
SUSPECT_ABSOLUTE = 5_000_000_000
SUSPECT_RELATIVE_FLOOR = 1_000_000_000
SUSPECT_RELATIVE_FACTOR = 100
SUSPECT_MIN_SAMPLE = 5


def amount_suspect(amount):
    """Bezwzględna bramka kwoty: ponad 5 mld w jednej walucie to prawie na pewno błąd, nie zamówienie."""
    return amount is not None and amount > SUSPECT_ABSOLUTE


def mark_suspect(rows):
    """Ustawia amount_suspect: powyżej progu bezwzględnego albo (od 1 mld) ponad 100x mediany pozostałych kwot waluty."""
    by_currency = defaultdict(list)
    for r in rows:
        if r.get('amount') is not None and r['amount'] > 0:
            by_currency[r.get('currency') or 'PLN'].append(r['amount'])
    medians = {}
    for currency, values in by_currency.items():
        if len(values) >= SUSPECT_MIN_SAMPLE:
            ordered = sorted(values)
            medians[currency] = ordered[len(ordered) // 2]
    for r in rows:
        amount = r.get('amount')
        median = medians.get(r.get('currency') or 'PLN')
        r['amount_suspect'] = bool(amount_suspect(amount) or (
            amount is not None and median and amount >= SUSPECT_RELATIVE_FLOOR
            and amount > SUSPECT_RELATIVE_FACTOR * median))
    return rows


def _sums(rows):
    totals = defaultdict(float)
    for r in rows:
        if r.get('amount') is not None and not r.get('amount_suspect'):
            totals[r.get('currency') or 'PLN'] += r['amount']
    return [{'currency': c, 'total': round(v, 2)} for c, v in sorted(totals.items(), key=lambda x: -x[1])]


def contracts(org, ids):
    """TED: podmiot jako wykonawca (identyfikator wykonawcy). BZP: podmiot jako zamawiający (NIP zamawiającego)."""
    out = []
    for r in _records('ted', 'notice', 'winners', list(ids.values())):
        hit = next((matched_by(w.get('id'), ids) for w in r.data.get('winners') or [] if matched_by(w.get('id'), ids)), None)
        if hit:
            out.append({'id': f'ted:{r.pk}', 'source': 'ted', 'role': ROLE['ted'], 'title': (r.title or '')[:300],
                        'party': '; '.join(r.data.get('buyer') or [])[:300], 'amount': _amount(r.data.get('value')),
                        'currency': r.data.get('currency') or '', 'date': r.date.isoformat() if r.date else None,
                        'kind': r.data.get('notice_type', ''), 'url': r.source_url, 'matched_by': hit})
    nip = ids.get('NIP')
    if nip:
        for r in _records('bzp', 'notice', 'organizationNationalId', [nip]):
            hit = matched_by(r.data.get('organizationNationalId'), {'NIP': nip})
            if hit:
                out.append({'id': f'bzp:{r.pk}', 'source': 'bzp', 'role': ROLE['bzp'], 'title': (r.title or '')[:300],
                            'party': str(r.data.get('organizationName') or '')[:300], 'amount': None, 'currency': '',
                            'date': r.date.isoformat() if r.date else None, 'kind': str(r.data.get('noticeType') or ''),
                            'url': r.source_url, 'matched_by': hit})
    out.sort(key=lambda x: (x['date'] or ''), reverse=True)
    return mark_suspect(out)


def grants(org, ids):
    """FTS: beneficjent z Polski po numerze VAT (PL + NIP)."""
    nip = ids.get('NIP')
    out = []
    for r in _records('fts', 'eu_grant', 'vat', [nip] if nip else []):
        hit = matched_by(r.data.get('vat'), {'NIP': nip})
        if hit:
            out.append({'id': f'fts:{r.pk}', 'source': 'fts', 'title': (r.data.get('subject') or r.title or '')[:300],
                        'programme': str(r.data.get('programme') or '')[:200], 'amount': _amount(r.data.get('amount')),
                        'currency': 'EUR', 'date': r.date.isoformat() if r.date else None, 'year': r.data.get('year'),
                        'url': r.source_url, 'matched_by': hit})
    return mark_suspect(out)


def unlinked(org, linked_pks):
    """Rekordy dopasowane przez zbieracz tylko po nazwie (Kohesio, FTS bez VAT): pokazane, ale nie liczone."""
    from news.public_records_models import PublicRecord
    rows = (PublicRecord.objects.filter(kind__in=('eu_project', 'eu_grant'), data__organisation_id=org.pk)
            .exclude(pk__in=linked_pks).order_by(F('date').desc(nulls_last=True), '-pk')[:PER_BRANCH])
    return [{'id': f'{r.source}:{r.pk}', 'source': r.source, 'title': (r.data.get('project') or r.data.get('subject') or r.title or '')[:300],
             'amount': _amount(r.data.get('eu_budget') if r.kind == 'eu_project' else r.data.get('amount')), 'currency': 'EUR',
             'date': r.date.isoformat() if r.date else None, 'url': r.source_url, 'reason': UNLINKED_REASON} for r in rows]


def people(org):
    """Osoby publiczne z potwierdzoną funkcją w podmiocie; odnośnik do profilu przeszłość.today."""
    from news.political_models import PublicFigureOrganisationRelation
    from news.przeszlosc_osoba import slug
    rows = (PublicFigureOrganisationRelation.objects.filter(organisation=org, verification_status='confirmed', public_figure__archived=False)
            .select_related('public_figure').order_by('relation_status', 'public_figure__canonical_name'))
    out = []
    for r in rows:
        f = r.public_figure
        out.append({'id': f'figure:{f.pk}', 'figure_id': f.pk, 'name': f.canonical_name, 'slug': slug(f), 'profile_url': f'/przeszlosc/osoba/{slug(f)}',
                    'role': r.organ or r.public_role, 'function': r.public_role, 'status': r.relation_status,
                    'since': r.since.isoformat() if r.since else None, 'until': r.until.isoformat() if r.until else None,
                    'method': r.verification_method, 'url': r.evidence_url})
    return out


def organisation(org):
    return {'id': org.pk, 'name': org.name, 'krs_number': org.krs_number, 'nip': org.nip, 'regon': org.regon, 'kind': org.kind,
            'legal_form': org.legal_form, 'sector': org.sector, 'url': krs.official_register_url(org.official_register_url), 'extra_url': krs.extra_register_url(org.krs_number),
            'source': SOURCES['krs']}


def branches(org):
    ids = identifiers(org)
    c, g, p = contracts(org, ids), grants(org, ids), people(org)
    linked = [int(x['id'].split(':')[1]) for x in c + g]
    u = unlinked(org, linked)
    return {'contracts': {'count': len(c), 'sums': _sums(c), 'suspect_count': sum(1 for x in c if x['amount_suspect']),
                          'results': c[:PER_BRANCH]},
            'grants': {'count': len(g), 'sums': _sums(g), 'suspect_count': sum(1 for x in g if x['amount_suspect']),
                       'results': g[:PER_BRANCH]},
            'people': {'count': len(p), 'results': p[:PER_BRANCH]},
            'unlinked': {'count': len(u), 'results': u}}


def tree(org):
    """Węzły i krawędzie dla widoku drzewa + gałęzie z sumami, źródła z licencjami, zasady."""
    from scraper.nowe_zrodla import LICENSES
    b = branches(org)
    root = f'org:{org.pk}'
    nodes = [{'id': root, 'kind': 'organisation', 'label': org.name[:160], 'sub': f'KRS {org.krs_number}', 'url': krs.official_register_url(org.official_register_url)}]
    edges = []
    for x in b['contracts']['results']:
        nodes.append({'id': x['id'], 'kind': 'contract', 'label': x['title'], 'sub': x['party'], 'date': x['date'], 'amount': x['amount'],
                      'amount_suspect': x['amount_suspect'], 'currency': x['currency'], 'url': x['url'], 'source': x['source']})
        edges.append({'source': root, 'target': x['id'], 'label': x['role']})
    for x in b['grants']['results']:
        nodes.append({'id': x['id'], 'kind': 'grant', 'label': x['title'], 'sub': x['programme'], 'date': x['date'], 'amount': x['amount'],
                      'amount_suspect': x['amount_suspect'], 'currency': 'EUR', 'url': x['url'], 'source': 'fts'})
        edges.append({'source': root, 'target': x['id'], 'label': 'dotacja UE'})
    for x in b['people']['results']:
        nodes.append({'id': x['id'], 'kind': 'person', 'label': x['name'], 'sub': x['role'], 'slug': x['slug'], 'url': x['profile_url'], 'source': 'krs'})
        edges.append({'source': root, 'target': x['id'], 'label': 'funkcja w KRS', 'since': x['since'], 'until': x['until']})
    used = {'krs'} | {x['source'] for x in b['contracts']['results']} | ({'fts'} if b['grants']['results'] else set()) \
        | {x['source'] for x in b['unlinked']['results']}
    sources = [{'key': k, **(SOURCES.get(k) or LICENSES[k])} for k in sorted(used)]
    ids = identifiers(org)
    return {'organisation': organisation(org), 'identifiers': ids, 'identifiers_missing': 'NIP' not in ids,
            'nodes': nodes, 'edges': edges, **b, 'sources': sources, 'note': NOTE, 'unlinked_reason': UNLINKED_REASON,
            'generated_at': timezone.now().isoformat(timespec='minutes')}


def person_companies(figure):
    """Blok „Pieniądze powiązanych spółek” w profilu osoby: jej podmioty z KRS z sumami gałęzi; każdy otwiera drzewo."""
    from news.political_models import PublicFigureOrganisationRelation
    rows = (PublicFigureOrganisationRelation.objects.filter(public_figure=figure, verification_status='confirmed', organisation__archived=False)
            .select_related('organisation').order_by('relation_status', 'organisation__name'))
    seen, out = set(), []
    for r in rows:
        org = r.organisation
        if org.pk in seen:
            continue
        seen.add(org.pk)
        b = branches(org)
        out.append({'id': org.pk, 'name': org.name, 'krs_number': org.krs_number, 'nip': org.nip, 'role': r.organ or r.public_role,
                    'status': r.relation_status, 'url': f'/przeszlosc/spolka/{org.krs_number}', 'identifiers_missing': not org.nip,
                    'contracts': {'count': b['contracts']['count'], 'sums': b['contracts']['sums'],
                                  'suspect_count': b['contracts']['suspect_count']},
                    'grants': {'count': b['grants']['count'], 'sums': b['grants']['sums'],
                               'suspect_count': b['grants']['suspect_count']},
                    'people': b['people']['count'], 'unlinked': b['unlinked']['count']})
    return {'results': out, 'note': NOTE}


def resolve(ident):
    """Adres: 10 cyfr = numer KRS; inaczej id podmiotu w naszej bazie. Podmioty zarchiwizowane nie są pokazywane."""
    from news.political_models import RegisteredOrganisation
    value = str(ident or '').strip()
    if not value.isdigit():
        return None
    q = Q(krs_number=value) if len(value) == 10 else Q(pk=int(value))
    return RegisteredOrganisation.objects.filter(q, archived=False).first()


@api_view(['GET'])
@permission_classes([AllowAny])
def company_view(request, ident):
    """GET /api/przeszlosc/spolka/<KRS albo id>/ - drzewo przepływu pieniędzy jednego podmiotu."""
    from django.core.cache import cache
    from django.db import connection
    from news.przeszlosc import enabled
    from news.przeszlosc_dostep import access, has, locked
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    org = resolve(ident)
    if org is None:
        return Response({'detail': 'Nie ma takiego podmiotu w naszym rejestrze KRS.'}, status=404)
    if not has('money_trail', request):
        return locked('money_trail')
    key = f'przeszlosc:spolka:{org.pk}'
    data = cache.get(key) if connection.vendor == 'postgresql' else None
    if data is None:
        data = tree(org)
        if connection.vendor == 'postgresql':
            cache.set(key, data, 900)
    return Response({**data, 'access': access(request)})
