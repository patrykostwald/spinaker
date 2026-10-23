"""Głosowania według rodzaju (dopisek właściciela 23.10): Sejm (posiedzenia plenarne), komisje sejmowe, Senat, Parlament Europejski.

Filtr pokazuje rodzaje z liczbą pozycji; rodzaj bez danych dostaje opis „brak danych w źródle” z powodem. Nic nie zgadujemy:
- Sejm: głosowania imienne z api.sejm.gov.pl (ParliamentaryVoting, Ballot), osoba po oficjalnym identyfikatorze posła;
- komisje: api.sejm.gov.pl publikuje posiedzenia komisji, ale nie imienne głosowania [DP: do potwierdzenia w dokumentacji API];
  wyników komisji nie przypisujemy osobom;
- Senat: senat.gov.pl odpowiada naszemu serwerowi 403 (2.10.2026), zbieranie wyłączone (SENAT_METADATA_ENABLED) - brak danych;
- Parlament Europejski: głosowania imienne europosłów z Polski z HowTheyVote.eu (ODbL, na podstawie oficjalnych protokołów PE).
Zgodność z klubem tylko dla Sejmu (większość klubu za/przeciw/wstrzymał się, remis = brak większości, jak club_line);
w PE mamy głosy tylko europosłów z Polski, więc zgodności z grupą nie liczymy.
"""
from datetime import date

from django.core.cache import cache
from django.db.models import F
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

PER_PAGE = 20
KINDS = {
    'sejm': {'label': 'Sejm - posiedzenia plenarne', 'source': 'Kancelaria Sejmu (api.sejm.gov.pl)', 'url': 'https://api.sejm.gov.pl/'},
    'komisje': {'label': 'Komisje sejmowe', 'source': 'Kancelaria Sejmu (api.sejm.gov.pl)', 'url': 'https://api.sejm.gov.pl/',
                'note': 'Brak danych w źródle: API Sejmu publikuje posiedzenia komisji, nie imienne głosowania. '
                        'Wyników komisji nie przypisujemy osobom.'},
    'senat': {'label': 'Senat', 'source': 'Kancelaria Senatu (senat.gov.pl)', 'url': 'https://www.senat.gov.pl/',
              'note': 'Brak danych: serwis senat.gov.pl nie odpowiada naszemu serwerowi, więc głosowań Senatu jeszcze nie zbieramy.'},
    'pe': {'label': 'Parlament Europejski', 'source': 'HowTheyVote.eu (ODbL 1.0) na podstawie oficjalnych protokołów PE',
           'url': 'https://howtheyvote.eu/'},
}
OUTCOMES = {'przyjete', 'odrzucone', 'nieustalone'}
EP_RESULT = {'ADOPTED': 'przyjete', 'REJECTED': 'odrzucone'}
CLUB = {'zgodnie': True, 'inaczej': False}


def params(query):
    """Walidacja; ValueError z komunikatem dla 400."""
    out = {'rodzaj': (query.get('rodzaj') or 'sejm').strip(), 'wynik': (query.get('wynik') or '').strip() or None,
           'klub': (query.get('zgodnosc') or '').strip() or None, 'kadencja': None, 'od': None, 'do': None, 'strona': 1}
    if out['rodzaj'] not in KINDS:
        raise ValueError('Rodzaj: sejm, komisje, senat albo pe.')
    if out['wynik'] and out['wynik'] not in OUTCOMES:
        raise ValueError('Wynik: przyjete, odrzucone albo nieustalone.')
    if out['klub'] and out['klub'] not in CLUB:
        raise ValueError('Zgodność z klubem: zgodnie albo inaczej.')
    for key in ('kadencja', 'strona'):
        value = query.get(key)
        if value not in (None, ''):
            if not str(value).isdigit():
                raise ValueError(f'Parametr {key} musi być liczbą.')
            out[key] = max(1, int(value)) if key == 'strona' else int(value)
    for key in ('od', 'do'):
        value = query.get(key) or None
        if value:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                raise ValueError('Daty w formacie YYYY-MM-DD.') from None
        out[key] = value
    if out['od'] and out['do'] and out['od'] > out['do']:
        raise ValueError('Data od nie może być późniejsza niż data do.')
    return out


def _sejm_rows(identities):
    """Wszystkie głosy osoby w Sejmie z wynikiem i zgodnością z klubem (bez stronicowania; widok tnie)."""
    from news.przeszlosc_osoba import VOTE_LABEL, _ballots, club_line, vote_url
    from news.przeszlosc_v3 import outcome
    ballots = list(_ballots(identities).select_related('voting__article')
                   .order_by(F('voting__article__published_date').desc(nulls_last=True), '-pk'))
    line = club_line(ballots) if ballots else {}
    rows = []
    for b in ballots:
        v = b.voting
        majority = line.get((b.voting_id, b.club)) if b.club else None
        with_club = None if majority is None or b.vote not in ('YES', 'NO', 'ABSTAIN') else b.vote == majority
        when = v.article.published_date
        rows.append({'kind': 'sejm', 'id': f'sejm:{v.term}/{v.sitting}/{v.number}', 'term': v.term,
                     'date': when.date().isoformat() if when else None, 'title': v.article.title[:300], 'motion': (v.motion or '')[:300],
                     'vote': VOTE_LABEL.get(b.vote, 'inne'), 'club': b.club, 'with_club': with_club,
                     'outcome': outcome(v.counts), 'url': vote_url(v)})
    return rows


def _ep_rows(figure, identities):
    from news.zrodla_profil import POSITION, ep_ids, records
    own = set(ep_ids(figure))
    if not own:
        from news.public_records_models import PublicRecordPerson
        from scraper.public_records import EP_TERM
        own = set(PublicRecordPerson.objects.filter(figure=figure, term=EP_TERM).values_list('mp_id', flat=True))
    rows = []
    for r in records(figure, identities, 'howtheyvote', ['ep_vote']):
        data = r.data or {}
        mine = next((v for v in data.get('votes') or [] if v.get('ep_id') in own), {})
        rows.append({'kind': 'pe', 'id': f'pe:{r.pk}', 'term': None, 'date': r.date.isoformat() if r.date else None,
                     'title': (r.title or '')[:300], 'motion': str(data.get('reference') or '')[:300],
                     'vote': POSITION.get(mine.get('position'), 'brak w danych'), 'club': mine.get('group', ''),
                     'with_club': None, 'outcome': EP_RESULT.get(str(data.get('result') or '').upper(), 'nieustalone'),
                     'url': r.source_url})
    return rows


def person_rows(figure):
    """{rodzaj: [pozycje]} - cache 1 h (pełne listy osoby; filtry działają na nich w pamięci)."""
    from news.przeplyw_cache import revision
    from news.przeszlosc_osoba import mp_identities
    key = f'przeszlosc:glosowania-rodzaje:{revision()}:{figure.pk}'
    data = cache.get(key)
    if data is None:
        identities = mp_identities(figure)
        data = {'sejm': _sejm_rows(identities), 'komisje': [], 'senat': [], 'pe': _ep_rows(figure, identities)}
        cache.set(key, data, 3600)
    return data


def kinds(counts):
    """Wszystkie rodzaje z liczbą pozycji; pusty rodzaj z opisem braku."""
    out = []
    for key, meta in KINDS.items():
        n = counts.get(key, 0)
        out.append({'key': key, 'label': meta['label'], 'count': n, 'available': n > 0, 'source': meta['source'], 'url': meta['url'],
                    'note': '' if n else meta.get('note') or 'Brak pozycji w naszych danych dla tej osoby.'})
    return out


def filtered(rows, p):
    out = []
    for r in rows:
        if p['kadencja'] and r['term'] != p['kadencja']:
            continue
        if p['od'] and (not r['date'] or r['date'] < p['od']):
            continue
        if p['do'] and (not r['date'] or r['date'] > p['do']):
            continue
        if p['wynik'] and r['outcome'] != p['wynik']:
            continue
        if p['klub'] and r['with_club'] is not CLUB[p['klub']]:
            continue
        out.append(r)
    return out


def person_payload(figure, p):
    data = person_rows(figure)
    rows = filtered(data[p['rodzaj']], p)
    pages = max(1, -(-len(rows) // PER_PAGE))
    page = min(p['strona'], pages)
    terms = sorted({r['term'] for r in data['sejm'] if r['term']}, reverse=True)
    return {'kinds': kinds({k: len(v) for k, v in data.items()}), 'filters': p, 'terms': terms,
            'club_filter': p['rodzaj'] == 'sejm',
            'club_note': '' if p['rodzaj'] == 'sejm' else 'Zgodność z klubem liczymy tylko dla Sejmu; w PE mamy głosy wyłącznie europosłów z Polski.',
            'count': len(rows), 'page': page, 'pages': pages, 'results': rows[(page - 1) * PER_PAGE: page * PER_PAGE]}


def general_kinds():
    """Liczniki rodzajów dla widoku ogólnego /przeszlosc/glosowania (cały zbiór, nie osoba)."""
    from news.models import ParliamentaryVoting
    from news.public_records_models import PublicRecord
    key = 'przeszlosc:glosowania-rodzaje:ogolne'
    data = cache.get(key)
    if data is None:
        data = kinds({'sejm': ParliamentaryVoting.objects.count(),
                      'pe': PublicRecord.objects.filter(source='howtheyvote', kind='ep_vote').count()})
        cache.set(key, data, 600)
    return data


def ep_page(p, per_page):
    """Widok ogólny, rodzaj PE: głosowania PE z liczbą głosów europosłów z Polski."""
    from news.public_records_models import PublicRecord
    from news.zrodla_profil import POSITION
    rows = PublicRecord.objects.filter(source='howtheyvote', kind='ep_vote')
    if p.get('od'):
        rows = rows.filter(date__gte=p['od'])
    if p.get('do'):
        rows = rows.filter(date__lte=p['do'])
    if p.get('q'):
        rows = rows.filter(title__icontains=p['q'])
    rows = rows.order_by(F('date').desc(nulls_last=True), '-pk')
    # najpierw tylko numer i wynik (bez pełnych danych głosowań europosłów), pełne rekordy tylko dla jednej strony
    picked = []
    for pk, raw in rows.values_list('pk', 'data__result').iterator():
        result = EP_RESULT.get(str(raw or '').upper(), 'nieustalone')
        if not p.get('wynik') or result == p['wynik']:
            picked.append((pk, result))
    total = len(picked)
    pages = max(1, -(-total // per_page))
    page = min(p.get('strona') or 1, pages)
    chunk = picked[(page - 1) * per_page: page * per_page]
    full = PublicRecord.objects.in_bulk([pk for pk, _ in chunk])
    items = [(full[pk], result) for pk, result in chunk if pk in full]
    results = [{'id': f'pe:{r.pk}', 'kind': 'pe', 'title': (r.title or '')[:300], 'motion': str((r.data or {}).get('reference') or ''),
                'date': r.date.isoformat() if r.date else None, 'outcome': result,
                'polish': {POSITION.get(k, k): n for k, n in ((r.data or {}).get('polish') or {}).items()}, 'url': r.source_url}
               for r, result in items]
    return {'count': total, 'page': page, 'pages': pages, 'results': results}


@api_view(['GET'])
@permission_classes([AllowAny])
def person_view(request, ident):
    """GET /api/przeszlosc/osoba/<ident>/glosowania/?rodzaj=sejm|komisje|senat|pe&kadencja=&od=&do=&wynik=&zgodnosc=zgodnie|inaczej&strona="""
    from news.przeszlosc import enabled
    from news.przeszlosc_osoba import resolve
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    try:
        p = params(request.query_params)
    except ValueError as error:
        return Response({'detail': str(error)}, status=400)
    figure = resolve(ident)
    if figure is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej w naszych danych.'}, status=404)
    return Response(person_payload(figure, p))
