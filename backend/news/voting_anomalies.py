"""Odstępstwa od klubu w głosowaniach Sejmu (plan Architekta 6.10, przeszłość.today).

Metoda (ta sama dla każdego klubu, bez AI):
- liczymy tylko oddane głosy: za, przeciw, wstrzymał się (nieobecność i głos na liście nie są odstępstwem);
- większość klubu w głosowaniu to najczęstszy głos jego posłów; remis albo mniej niż 3 oddane głosy klubu - głosowanie pomijamy;
- odstępstwo: poseł oddał inny głos niż większość swojego klubu (klub z dnia głosowania, z oficjalnych danych Sejmu);
- udział odstępstw posła = odstępstwa / policzone głosy; porównujemy go z medianą klubu (posłowie z co najmniej 20 głosami);
- wyróżniamy posłów, u których udział jest wyższy od mediany klubu o więcej niż 5 punktów procentowych;
- głos wbrew klubowi: odstępstwo w głosowaniu, w którym co najmniej 80% oddanych głosów klubu było takich samych.
Odstępstwo nie jest zarzutem - bywa głosem sumienia, pomyłką albo zapowiedzią zmiany klubu.
"""
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import groupby
from statistics import median

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

CAST = {'YES': 'za', 'NO': 'przeciw', 'ABSTAIN': 'wstrzymał się'}
NO_CLUB = {'', 'niez.', 'niezrzeszeni', 'niezrz.'}
MIN_CLUB_CAST = 3
UNITY = 0.8
MIN_VOTES = 20
MIN_CLUB_MPS = 3
EXCESS_PP = 5.0
WINDOW_DAYS = 90
MEMBER_REBELLIONS = 10
CLUB_REBELLIONS = 30
SKIP_KINDS = {'ON_LIST'}

METHOD = ('Liczymy oddane głosy (za, przeciw, wstrzymał się). Odstępstwo to głos inny niż większość klubu w tym głosowaniu. '
          'Wyróżniamy posłów, u których odstępstw jest o ponad 5 pkt proc. więcej niż u typowego posła klubu (mediana, '
          'co najmniej 20 głosów), oraz głosy wbrew klubowi, gdy co najmniej 80% klubu głosowało tak samo. '
          'Te same progi dla każdego klubu. Odstępstwo nie jest zarzutem.')
THRESHOLDS = {'excess_pp': EXCESS_PP, 'unity': UNITY, 'min_votes': MIN_VOTES, 'min_club_cast': MIN_CLUB_CAST,
              'min_club_mps': MIN_CLUB_MPS, 'window_days': WINDOW_DAYS}


def vote_url(term, sitting, number):
    return (f'https://www.sejm.gov.pl/sejm{term}.nsf/agent.xsp?symbol=glosowania&NrKadencji={term}'
            f'&NrPosiedzenia={sitting}&NrGlosowania={number}')


def club_majority(ballots):
    """ballots: [(mp_id, vote)] jednego klubu → (głos większości, jednomyślność 0-1) albo (None, 0) przy remisie lub małej próbie."""
    cast = Counter(vote for _, vote in ballots if vote in CAST)
    total = sum(cast.values())
    if total < MIN_CLUB_CAST:
        return None, 0.0
    (top, n), *rest = cast.most_common()
    if rest and rest[0][1] == n:
        return None, 0.0
    return top, n / total


def analyse(votings):
    """votings: iterowalne słowniki {term, sitting, number, title, date (ISO), ballots: [(mp_id, name, club, vote)]}.
    Zwraca wynik gotowy do zapisania i pokazania (kluby w kolejności wielkości)."""
    members = {}
    club_rebellions = defaultdict(list)
    dates = []
    counted_votings = 0
    for voting in votings:
        by_club = defaultdict(list)
        for mp_id, name, club, vote in voting['ballots']:
            club = (club or '').strip()
            if club.lower() in NO_CLUB:
                continue
            by_club[club].append((mp_id, name, vote))
        used = False
        for club, rows in by_club.items():
            majority, unity = club_majority([(mp, vote) for mp, _, vote in rows])
            if majority is None:
                continue
            used = True
            for mp_id, name, vote in rows:
                if vote not in CAST:
                    continue
                key = (mp_id, club)
                m = members.setdefault(key, {'mp_id': mp_id, 'name': name, 'club': club, 'counted': 0, 'deviations': 0,
                                             'rebellions_total': 0, 'rebellions': []})
                m['name'] = name or m['name']
                m['counted'] += 1
                if vote == majority:
                    continue
                m['deviations'] += 1
                if unity >= UNITY:
                    m['rebellions_total'] += 1
                    event = {'date': voting.get('date'), 'title': (voting.get('title') or '')[:200],
                             'id': f"{voting['term']}/{voting['sitting']}/{voting['number']}",
                             'url': vote_url(voting['term'], voting['sitting'], voting['number']),
                             'mp_id': mp_id, 'name': name, 'club': club, 'vote': CAST[vote], 'club_vote': CAST[majority],
                             'unity': round(unity * 100)}
                    m['rebellions'].append(event)
                    club_rebellions[club].append(event)
        if used:
            counted_votings += 1
            if voting.get('date'):
                dates.append(voting['date'])
    by_club = defaultdict(list)
    for m in members.values():
        m['share'] = round(100 * m['deviations'] / m['counted'], 1) if m['counted'] else 0.0
        m['eligible'] = m['counted'] >= MIN_VOTES
        m['rebellions'] = sorted(m['rebellions'], key=lambda e: e['date'] or '', reverse=True)[:MEMBER_REBELLIONS]
        by_club[m['club']].append(m)
    clubs = []
    for club, rows in by_club.items():
        eligible = [m for m in rows if m['eligible']]
        club_median = round(median(m['share'] for m in eligible), 1) if len(eligible) >= MIN_CLUB_MPS else None
        for m in rows:
            m['club_median'] = club_median
            m['excess'] = round(m['share'] - club_median, 1) if club_median is not None and m['eligible'] else None
            m['flagged'] = m['excess'] is not None and m['excess'] > EXCESS_PP
        flagged = sorted((m for m in rows if m['flagged']), key=lambda m: (-m['excess'], m['name']))
        events = sorted(club_rebellions.get(club, []), key=lambda e: (e['date'] or '', e['id']), reverse=True)
        clubs.append({'club': club, 'mps': len(eligible), 'members': len(rows), 'median': club_median,
                      'flagged': [_public(m) for m in flagged], 'rebellions_total': len(events),
                      'rebellions': events[:CLUB_REBELLIONS]})
    clubs.sort(key=lambda c: (-c['members'], c['club']))
    dates.sort()
    return {'votings': counted_votings, 'range': {'from': dates[0][:10] if dates else None, 'to': dates[-1][:10] if dates else None},
            'method': METHOD, 'thresholds': THRESHOLDS, 'clubs': clubs,
            'members': {str(m['mp_id']) + ':' + m['club']: _public(m, events=True) for m in members.values()}}


def _public(m, events=False):
    row = {k: m[k] for k in ('mp_id', 'name', 'club', 'counted', 'deviations', 'share', 'club_median', 'excess', 'flagged',
                             'rebellions_total')}
    row['latest'] = m['rebellions'][0] if m['rebellions'] else None
    if events:
        row['rebellions'] = m['rebellions']
    return row


def load(term, since=None):
    """Głosowania kadencji z bazy (bez sieci), w porządku chronologicznym; ballots czytane strumieniowo."""
    from news.models import Ballot, ParliamentaryVoting
    votings = ParliamentaryVoting.objects.filter(term=term).exclude(kind__in=SKIP_KINDS)
    if since:
        votings = votings.filter(article__published_date__gte=since)
    meta = {v['pk']: v for v in votings.values('pk', 'term', 'sitting', 'number', 'article__title', 'article__published_date')}
    rows = (Ballot.objects.filter(voting_id__in=list(meta)).order_by('voting_id')
            .values_list('voting_id', 'mp_id', 'name', 'club', 'vote').iterator(chunk_size=20000))
    for voting_id, group in groupby(rows, key=lambda r: r[0]):
        v = meta[voting_id]
        when = v['article__published_date']
        yield {'term': v['term'], 'sitting': v['sitting'], 'number': v['number'], 'title': v['article__title'],
               'date': when.isoformat() if when else None, 'ballots': [r[1:] for r in group]}


def current_term():
    from news.models import ParliamentaryVoting
    return ParliamentaryVoting.objects.order_by('-term').values_list('term', flat=True).first()


def refresh(term=None):
    """Przelicza oba okresy (cała kadencja, ostatnie 90 dni do ostatniego głosowania) i zapisuje wynik."""
    from django.db.models import Max
    from django.utils import timezone
    from news.analysis_models import VotingDeviationSnapshot
    from news.models import ParliamentaryVoting
    term = term or current_term()
    if not term:
        return {'status': 'empty'}
    last = ParliamentaryVoting.objects.filter(term=term).aggregate(m=Max('article__published_date'))['m']
    out = {'status': 'ok', 'term': term, 'periods': {}}
    for period, since in (('term', None), ('90d', last - timedelta(days=WINDOW_DAYS) if last else None)):
        if period == '90d' and not since:
            continue
        data = analyse(load(term, since))
        data.update(term=term, period=period)
        VotingDeviationSnapshot.objects.update_or_create(term=term, period=period,
                                                         defaults={'data': data, 'computed_at': timezone.now()})
        out['periods'][period] = {'votings': data['votings'], 'flagged': sum(len(c['flagged']) for c in data['clubs']),
                       'rebellions': sum(c['rebellions_total'] for c in data['clubs'])}
    return out


def snapshot(term=None, period='90d'):
    from news.analysis_models import VotingDeviationSnapshot
    rows = VotingDeviationSnapshot.objects.filter(period=period)
    if term:
        rows = rows.filter(term=term)
    return rows.order_by('-term').first()


def member(mp_id, term=None, period='term'):
    """Wynik jednego posła (blok w profilu osoby); klucz to identyfikator Sejmu, nigdy nazwisko."""
    snap = snapshot(term, period)
    if not snap:
        return None
    rows = [m for key, m in snap.data.get('members', {}).items() if key.split(':', 1)[0] == str(mp_id)]
    if not rows:
        return None
    rows.sort(key=lambda m: -m['counted'])
    return {'term': snap.term, 'period': period, 'computed_at': snap.computed_at.isoformat(), 'method': snap.data.get('method'),
            'clubs': rows}


PERIODS = {'90d': '90d', '90': '90d', 'kadencja': 'term', 'term': 'term'}


@api_view(['GET'])
@permission_classes([AllowAny])
def deviations_view(request):
    """GET /api/przeszlosc/odstepstwa/?okres=90d|kadencja[&kadencja=10][&posel=<id Sejmu>]"""
    from news import przeszlosc
    if not przeszlosc.enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    from news.przeszlosc_dostep import has, locked
    if not has('deviations', request):
        return locked('deviations')
    period = PERIODS.get(request.query_params.get('okres', '90d'))
    if not period:
        return Response({'detail': 'Okres: 90d albo kadencja.'}, status=400)
    try:
        term = int(request.query_params['kadencja']) if request.query_params.get('kadencja') else None
        mp_id = int(request.query_params['posel']) if request.query_params.get('posel') else None
    except ValueError:
        return Response({'detail': 'Kadencja i poseł to liczby.'}, status=400)
    if mp_id is not None:
        data = member(mp_id, term, period)
        return Response(data or {'detail': 'Brak głosowań tego posła w wyniku.'}, status=200 if data else 404)
    snap = snapshot(term, period)
    if not snap:
        return Response({'term': term, 'period': period, 'computed_at': None, 'votings': 0, 'range': {'from': None, 'to': None},
                         'method': METHOD, 'thresholds': THRESHOLDS, 'clubs': []})
    data = {k: v for k, v in snap.data.items() if k != 'members'}
    data['computed_at'] = snap.computed_at.isoformat()
    return Response(data)

