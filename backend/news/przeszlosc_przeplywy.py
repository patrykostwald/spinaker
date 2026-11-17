"""Przepływy pieniędzy v1 (sprint 23.10): skąd do kogo płyną pieniądze publiczne - tabela i dane do wykresu sankey.

Każda pozycja to jedna para płatnik -> odbiorca z datą, kwotą i źródłem (rekord, z którego pochodzi). Te same zasady co
drzewo przepływu (drzewo_pieniedzy.py): wyłącznie po identyfikatorach (NIP, KRS, REGON), nigdy po nazwie; kwoty nierealne
(amount_suspect) zostają w tabeli, ale poza sumami i wykresem; waluty osobno.

Podmiot:
- zamówienia TED, w których podmiot jest wykonawcą: zamawiający -> podmiot;
- zamówienia TED, w których podmiot jest zamawiającym (jawny NIP zamawiającego): podmiot -> wykonawca (osoba fizyczna
  prowadząca działalność bez nazwy - LEGAL);
- ogłoszenia BZP podmiotu jako zamawiającego: tylko w tabeli, BZP nie podaje wykonawcy ani kwoty;
- dotacje UE z FTS (Komisja Europejska -> podmiot), dotacje NIW-CRSO (NIW -> podmiot), 1,5% podatku (podatnicy -> OPP).
Osoba: przepływy podmiotów z potwierdzoną funkcją w KRS, domyślnie tylko z okresu funkcji (?cala_historia=1 - wszystkie,
z oznaczeniem „poza okresem funkcji”). To kontekst, nie dowód: osoba nie jest płatnikiem ani odbiorcą.
"""
import re
from collections import defaultdict

from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from news import drzewo_pieniedzy as money
from news import krs
from news import opp_podatek as opp

VERSION = 'v1'
MAX_ROWS = 500
SANKEY_SIDE = 8   # tylu największych płatników i odbiorców na wykresie; reszta jako „pozostali”
NOTE = ('Pieniądze publiczne według rekordów źródłowych, łączone tylko po NIP, KRS i REGON. Kwoty zamówień z ogłoszeń TED '
        '(wartość całego ogłoszenia, nie umowy), dotacje z FTS i NIW-CRSO, 1,5% z wykazu MF. Kwoty do weryfikacji są w tabeli, '
        'ale poza sumami i wykresem; tak samo wartość ogłoszenia z kilkoma wykonawcami (nie wiemy, ile przypadło każdemu). Ta sama miara dla wszystkich, bez oceny.')
PERSON_NOTE = ('Przepływy podmiotów, w których osoba ma potwierdzoną funkcję w KRS, z okresu tej funkcji. Osoba nie jest '
               'płatnikiem ani odbiorcą; funkcja w podmiocie to kontekst, nie dowód.')
KIND = {'ted_in': 'zamówienie (wykonawca)', 'ted_out': 'zamówienie (zamawiający)', 'bzp': 'ogłoszenie BZP (zamawiający)',
        'fts': 'dotacja UE', 'niw': 'dotacja krajowa', 'mf_opp': '1,5% podatku'}
FUNDERS = {'fts': 'Komisja Europejska (budżet UE)', 'niw': 'NIW-CRSO (Narodowy Instytut Wolności)',
           'mf_opp': 'Podatnicy PIT (1,5% podatku, przez urzędy skarbowe)'}


def _party(label, nip='', url=''):
    return {'label': (label or 'nie podano w źródle')[:300], 'nip': nip or '', 'url': url or ''}


def _org_party(org):
    return _party(org.name, org.nip, f'/przeszlosc/spolka/{org.krs_number}')


def _known(nips):
    """NIP -> adres podmiotu w naszej bazie (żeby kontrahent prowadził do swojego profilu)."""
    from news.political_models import RegisteredOrganisation
    nips = {n for n in nips if n}
    if not nips:
        return {}
    return {o.nip: (o.name, f'/przeszlosc/spolka/{o.krs_number}')
            for o in RegisteredOrganisation.objects.filter(nip__in=nips, archived=False)}


def _source(key, url):
    meta = money.SOURCES.get(key) or {}
    if not meta and key == 'fts':
        meta = {'label': 'Financial Transparency System (Komisja Europejska)', 'license': 'CC BY 4.0'}
    return {'key': key, 'label': meta.get('label', key.upper()), 'license': meta.get('license', ''), 'url': url}


def bought(org):
    """TED: podmiot jako zamawiający (jawny NIP zamawiającego z ogłoszenia) -> wykonawcy."""
    nip = money.digits(org.nip)
    if len(nip) != 10:
        return []
    out = []
    for r in money._records('ted', 'notice', 'buyer_nip', [nip]):
        data = r.data or {}
        if money.buyer_nip(data) != nip:
            continue
        winners = [w for w in data.get('winners') or [] if isinstance(w, dict)]
        named = [w for w in winners if not w.get('osoba_fizyczna')]
        private = len(winners) - len(named)
        if len(winners) == 1:
            w = winners[0]
            to = _party('osoba fizyczna prowadząca działalność' if w.get('osoba_fizyczna') else w.get('name'),
                        '' if w.get('osoba_fizyczna') else money.digits(w.get('id')) if len(money.digits(w.get('id'))) == 10 else '')
        elif winners:
            names = [str(w.get('name') or '') for w in named[:3]] + (['osoba fizyczna'] * min(private, 1))
            to = _party(f'{len(winners)} wykonawców: ' + '; '.join(n for n in names if n))
        else:
            to = _party('wykonawca nie podany w ogłoszeniu')
        out.append({'id': f'ted:{r.pk}:out', 'kind': 'ted_out', 'date': r.date.isoformat() if r.date else None,
                    'from': _org_party(org), 'to': to, 'amount': money._amount(data.get('value')),
                    'currency': data.get('currency') or '', 'title': (r.title or '')[:300],
                    'source': _source('ted', r.source_url), 'matched_by': 'NIP', 'record': f'ted:{r.pk}'})
    return money.mark_suspect(out)


def org_flows(org):
    """Wszystkie przepływy jednego podmiotu (bez limitu; widok tnie do MAX_ROWS)."""
    ids = money.identifiers(org)
    me = _org_party(org)
    rows = []
    found = money.contracts(org, ids)
    from news.public_records_models import PublicRecord
    ted_pks = [int(x['id'].split(':')[1]) for x in found if x['source'] == 'ted']
    winners = {pk: len((data or {}).get('winners') or []) for pk, data in PublicRecord.objects.filter(pk__in=ted_pks).values_list('pk', 'data')}
    for x in found:
        base = {'date': x['date'], 'title': x['title'], 'source': _source(x['source'], x['url']), 'matched_by': x['matched_by'],
                'record': x['id'], 'amount_suspect': x.get('amount_suspect', False)}
        if x['source'] == 'ted':
            # Śledczy R3 P0-11: przy kilku wykonawcach kwota to wartość całego ogłoszenia, nie część podmiotu - poza sumami i wykresem
            shared = winners.get(int(x['id'].split(':')[1]), 1) > 1
            rows.append({**base, 'id': f"{x['id']}:in", 'kind': 'ted_in', 'from': _party(x['party']), 'to': me,
                         'amount': x['amount'], 'currency': x['currency'], 'amount_shared': shared})
        else:
            rows.append({**base, 'id': x['id'], 'kind': 'bzp', 'from': me, 'to': _party('wykonawca: BZP go nie podaje'),
                         'amount': None, 'currency': ''})
    rows += bought(org)
    for x in money.grants(org, ids):
        rows.append({'id': x['id'], 'kind': x['source'], 'date': x['date'] or (str(x['year']) if x.get('year') else None),
                     'from': _party(FUNDERS[x['source']]), 'to': me, 'amount': x['amount'], 'currency': x['currency'],
                     'title': x['title'] or x.get('programme', ''), 'source': _source(x['source'], x['url']),
                     'matched_by': x['matched_by'], 'record': x['id'], 'amount_suspect': x.get('amount_suspect', False),
                     **({'attribution': x['attribution']} if x.get('attribution') else {})})
    for x in money.opp_tax(org, ids):
        rows.append({'id': x['id'], 'kind': 'mf_opp', 'date': str(x['payment_year'] or x['tax_year'] or '') or None,
                     'from': _party(FUNDERS['mf_opp']), 'to': me, 'amount': x['amount'], 'currency': 'PLN',
                     'title': f"1,5% podatku za rok {x['tax_year']}, wpłata w {x['payment_year']}",
                     'source': {'key': 'mf_opp', 'label': money.SOURCES['mf_opp']['label'], 'license': money.SOURCES['mf_opp']['license'],
                                'url': x['url']}, 'matched_by': 'KRS', 'record': x['id'], 'amount_suspect': False,
                     'attribution': x['attribution']})
    for r in rows:
        r.setdefault('amount_suspect', False)
        r.setdefault('amount_shared', False)
    known = _known([p['nip'] for r in rows for p in (r['from'], r['to'])])
    for r in rows:
        for side in ('from', 'to'):
            hit = known.get(r[side]['nip'])
            if hit and not r[side]['url']:
                r[side]['url'] = hit[1]
    return rows


def person_flows(figure, whole_history=False):
    from news.political_models import PublicFigureOrganisationRelation
    from news.przeszlosc_przeplyw import in_tenure
    windows = defaultdict(list)
    orgs = {}
    rels = (PublicFigureOrganisationRelation.objects.filter(public_figure=figure, verification_status='confirmed', organisation__archived=False)
            .select_related('organisation'))
    for rel in rels:
        orgs[rel.organisation_id] = rel.organisation
        windows[rel.organisation_id].append((rel.since, rel.until))
    rows, outside = [], 0
    for pk, org in orgs.items():
        via = {'name': org.name, 'url': f'/przeszlosc/spolka/{org.krs_number}'}
        for r in org_flows(org):
            day = _day(r['date'])
            inside = in_tenure(day, windows[pk]) if day else in_tenure(None, windows[pk])
            if not inside:
                outside += 1
                if not whole_history:
                    continue
                r['outside_tenure'] = True
            rows.append({**r, 'id': f"{r['id']}@{pk}", 'via': via})
    return rows, outside, list(orgs.values())


def _day(value):
    from datetime import date
    text = str(value or '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return date.fromisoformat(text)
    if re.fullmatch(r'\d{4}', text):
        return date(int(text), 12, 31)  # sam rok (FTS, 1,5%): koniec roku
    return None


CONTRACT_KINDS = ('ted_in', 'ted_out', 'bzp')


def sums(rows):
    totals = defaultdict(float)
    counts = defaultdict(int)
    for r in rows:
        if r.get('amount') is not None and not r.get('amount_suspect') and not r.get('amount_shared'):
            totals[r['currency'] or 'PLN'] += r['amount']
            counts[r['currency'] or 'PLN'] += 1
    return [{'currency': c, 'total': round(v, 2), 'count': counts[c]} for c, v in sorted(totals.items(), key=lambda x: -x[1])]


def sankey(rows, currency=None):
    """Płatnicy po lewej, odbiorcy po prawej, wstęgi proporcjonalne do sumy kwot jednej waluty (domyślnie najczęstszej)."""
    counted = [r for r in rows if r.get('amount') and not r.get('amount_suspect') and not r.get('amount_shared')]
    if not counted:
        return {'currency': None, 'nodes': [], 'links': [], 'other_currencies': []}
    by_currency = defaultdict(int)
    for r in counted:
        by_currency[r['currency'] or 'PLN'] += 1
    currency = currency or max(by_currency, key=lambda c: by_currency[c])
    pairs = defaultdict(float)
    for r in counted:
        if (r['currency'] or 'PLN') == currency:
            pairs[(r['from']['label'], r['to']['label'])] += r['amount']

    def top(side):
        total = defaultdict(float)
        for (a, b), v in pairs.items():
            total[a if side == 0 else b] += v
        return {k for k, _ in sorted(total.items(), key=lambda x: -x[1])[:SANKEY_SIDE]}
    left, right = top(0), top(1)
    links = defaultdict(float)
    for (a, b), v in pairs.items():
        links[(a if a in left else 'pozostali płatnicy', b if b in right else 'pozostali odbiorcy')] += v
    nodes, index = [], {}
    for side, names in ((0, sorted({a for a, _ in links})), (1, sorted({b for _, b in links}))):
        for name in names:
            index[(side, name)] = len(nodes)
            nodes.append({'id': len(nodes), 'label': name, 'side': 'from' if side == 0 else 'to',
                          'total': round(sum(v for (a, b), v in links.items() if (a if side == 0 else b) == name), 2)})
    return {'currency': currency, 'nodes': nodes,
            'links': [{'source': index[(0, a)], 'target': index[(1, b)], 'value': round(v, 2)}
                      for (a, b), v in sorted(links.items(), key=lambda x: -x[1])],
            'other_currencies': sorted(c for c in by_currency if c != currency)}


def payload(rows, subject, note, extra=None):
    rows = sorted(rows, key=lambda r: (r['date'] or ''), reverse=True)
    counted_in = [r for r in rows if r['to'].get('url') == subject.get('url')]
    counted_out = [r for r in rows if r['from'].get('url') == subject.get('url')]
    kinds = defaultdict(int)
    for r in rows:
        kinds[r['kind']] += 1
    used = {}
    for r in rows:
        used.setdefault(r['source']['key'], {k: v for k, v in r['source'].items() if k != 'url'})
    return {'subject': subject, 'count': len(rows), 'truncated': len(rows) > MAX_ROWS, 'results': rows[:MAX_ROWS],
            # Śledczy R3 P0-11: wartość wygranych zamówień (z ogłoszeń, nie zapłata) osobno od dotacji i 1,5% - nie jedna „suma wpływów”
            'sums': {'all': sums(rows), 'in': sums(counted_in), 'out': sums(counted_out),
                     'in_contracts': sums([r for r in counted_in if r['kind'] in CONTRACT_KINDS]),
                     'in_grants': sums([r for r in counted_in if r['kind'] not in CONTRACT_KINDS])},
            'suspect_count': sum(1 for r in rows if r.get('amount_suspect')),
            'shared_count': sum(1 for r in rows if r.get('amount_shared')),
            'kinds': [{'kind': k, 'label': KIND[k], 'count': n} for k, n in sorted(kinds.items(), key=lambda x: -x[1])],
            'sankey': sankey(rows), 'sources': list(used.values()), 'note': note, 'version': VERSION,
            'generated_at': timezone.now().isoformat(timespec='minutes'), **(extra or {})}


def for_org(org):
    subject = {'kind': 'organisation', 'name': org.name, 'krs_number': org.krs_number, 'nip': org.nip,
               'url': f'/przeszlosc/spolka/{org.krs_number}', 'identifiers_missing': not org.nip,
               'register_url': krs.official_register_url(org.official_register_url)}
    return payload(org_flows(org), subject, NOTE)


def for_person(figure, whole_history=False):
    from news.przeszlosc_osoba import display_name, slug
    rows, outside, orgs = person_flows(figure, whole_history)
    subject = {'kind': 'person', 'name': display_name(figure.canonical_name), 'url': f'/przeszlosc/osoba/{slug(figure)}',
               'organisations': [{'name': o.name, 'url': f'/przeszlosc/spolka/{o.krs_number}', 'nip_missing': not o.nip} for o in orgs]}
    out = payload(rows, subject, NOTE + ' ' + PERSON_NOTE, {'outside_tenure': outside, 'whole_history': whole_history})
    # osoba nie jest stroną: wpływy i wydatki liczymy względem jej podmiotów
    urls = {o['url'] for o in subject['organisations']}
    out['sums']['in'] = sums([r for r in rows if r['to'].get('url') in urls])
    out['sums']['out'] = sums([r for r in rows if r['from'].get('url') in urls])
    incoming = [r for r in rows if r['to'].get('url') in urls]
    out['sums']['in_contracts'] = sums([r for r in incoming if r['kind'] in CONTRACT_KINDS])
    out['sums']['in_grants'] = sums([r for r in incoming if r['kind'] not in CONTRACT_KINDS])
    if not orgs:
        out['empty_reason'] = ('Brak potwierdzonych funkcji w KRS: bez nich nie łączymy pieniędzy z osobą. '
                               'Funkcje sprawdzamy w kolejce KRS (agent i zespół).')
    return out


@api_view(['GET'])
@permission_classes([AllowAny])
def flows_view(request, ident):
    """GET /api/przeszlosc/przeplywy/<osoba:slug|spolka:KRS|NIP>/ - tabela przepływów i dane do sankey."""
    from news import przeszlosc_osoba as person
    from news.przeszlosc import enabled
    from news.przeszlosc_dostep import has, locked
    from news.przeplyw_cache import revision
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    whole = request.query_params.get('cala_historia', '0')
    if whole not in ('0', '1'):
        return Response({'detail': 'cala_historia: 0 albo 1.'}, status=400)
    prefix, _, value = str(ident).partition(':')
    obj = person.resolve(value) if prefix == 'osoba' else money.resolve(value) if prefix == 'spolka' else None
    if obj is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej lub podmiotu w naszych danych.'}, status=404)
    if not has('money_trail', request):
        return locked('money_trail')
    key = f'przeszlosc:przeplywy:{VERSION}:{revision()}:{prefix}:{obj.pk}:{whole}'
    data = cache.get(key)
    if data is None:
        data = for_person(obj, whole == '1') if prefix == 'osoba' else for_org(obj)
        cache.set(key, data, 6 * 3600)
    return Response(data)
