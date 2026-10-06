"""Zasilanie bazy (właściciel 6.10: „jak najszybciej, legalnie”).

Każde włączone źródło dostaje całą historię: od początku X kadencji Sejmu (13.11.2023), a dla źródeł z oknem
TED - ostatnie 12 miesięcy (PUBLIC_RECORDS_TED_BACKFILL_MONTHS), BZP - 365 dni (BZP_BACKFILL_DAYS, osobny zbieracz
scraper.bzp_backfill), KRS - aktualny odpis każdego obserwowanego podmiotu (RegisteredOrganisation).

To ta sama trwała kolejka (PublicCollectionJob), ta sama karta dostępu i ten sam odstęp hosta co zwykły zbieracz
(scraper.public_records). Inny jest tylko budżet: osobny limit zasilania PUBLIC_RECORDS_<ŹRÓDŁO>_BACKFILL_CAP
(zapytań na dobę, domyślnie BACKFILL_CAP), liczony obok dziennego limitu zwykłego zbieracza, nigdy ponad kartę.

Tryby (zadanie scraper.tasks.zasil_baze_task, dwa pasy: „sejm” i „inne”):
- noc (01:00-05:59): do limitu zasilania każdego źródła;
- resztka (23:00-23:59): przed północnym resetem dziennych limitów kart (darmowe API bez kwot: Sejm, KRS, TED)
  zużywa to, co z karty zostało - bez limitu zasilania, ale nigdy ponad dzienny limit karty.
Źródło jest gotowe, gdy cykl od daty docelowej skończył się bez zaległych zadań. Gotowe źródło zadanie pomija na
stałe (bez działania właściciela). Postęp: ImportState 'zasil-baze:<źródło>', manage.py zasil_baze --plan i Raport pętli.
Bez AI, bez scrapowania za logowaniem; tylko źródła z zatwierdzoną kartą dostępu i włączoną flagą.
"""
from datetime import date, timedelta
from math import ceil
from time import monotonic, sleep
import os

from django.db import transaction
from django.utils import timezone

from news.models import ImportState
from news.repairer import flag
from scraper.public_records import (KRS_API, SEJM_SOURCES, SOURCES, START, TED_FIELDS, TED_SEARCH, collect, enqueue,
                                    setting_int)

LANES = {
    'sejm': ('votes', 'statements', 'interpellations', 'questions', 'consultations', 'processes', 'committees',
             'assets', 'lobby_sejm', 'videos'),
    'inne': ('krs_changes', 'ted', 'lobby_mswia', 'pkw', 'eu_transparency'),
    # Otwarte zbiory spoza administracji polskiej (raport źródeł 6.10): osobny pas, inne hosty.
    'otwarte': ('howtheyvote', 'wikidata', 'kohesio', 'fts', 'integrity_watch', 'mileage'),
}
MODES = {'noc': range(1, 6), 'resztka': range(23, 24)}
# Zapytań zasilania na dobę na źródło (bezpieczne domyślne; env PUBLIC_RECORDS_<ŹRÓDŁO>_BACKFILL_CAP, 1-20000).
BACKFILL_CAP = {'votes': 1200, 'statements': 1500, 'interpellations': 300, 'questions': 300, 'consultations': 100,
                'processes': 600, 'committees': 150, 'assets': 400, 'lobby_sejm': 20, 'krs_changes': 500, 'ted': 300,
                'lobby_mswia': 20, 'pkw': 100, 'eu_transparency': 2,
                'videos': 1500, 'howtheyvote': 1500, 'wikidata': 2, 'kohesio': 120, 'fts': 3, 'integrity_watch': 3,
                'mileage': 400}
# Szacunek wszystkich zapytań pełnej historii (X kadencja do 10.2026; strony po 20 pozycji), tylko do --plan.
ESTIMATE = {'votes': 7400, 'statements': 26000, 'interpellations': 750, 'questions': 450, 'consultations': 600,
            'processes': 2100, 'committees': 45, 'assets': 1000, 'lobby_sejm': 5, 'lobby_mswia': 6, 'pkw': 150,
            'eu_transparency': 1, 'videos': 4500, 'howtheyvote': 2600, 'wikidata': 2, 'kohesio': 105, 'fts': 6,
            'integrity_watch': 3, 'mileage': 735}
TED_PAGES_PER_MONTH = 65    # ok. 6500 ogłoszeń zamawiających z Polski miesięcznie, 100 na stronę
LANE_NIGHT = 4500           # zapytań na pas w nocy: 5 h, odstęp hosta 3 s + czas odpowiedzi
BZP_PAGES_PER_DAY = 30      # ok. 750 ogłoszeń BZP w dzień roboczy, 25 na stronę
BZP_DAILY = 480             # karta BZP: jedno zapytanie co 3 min (audyt UZP), nie przyspieszamy
LINKS = 'zasil-baze:linki'


def _name(source):
    return 'zasil-baze:' + source


def info(source):
    row = ImportState.objects.filter(name=_name(source)).first()
    return dict(row.cursor or {}) if row else {}


def _update(source, **values):
    row, _ = ImportState.objects.get_or_create(name=_name(source))
    with transaction.atomic():
        row = ImportState.objects.select_for_update().get(pk=row.pk)
        row.cursor = {**(row.cursor or {}), **values}
        row.save(update_fields=['cursor'])
    return row.cursor


def cap(source):
    return setting_int(source, 'BACKFILL_CAP', BACKFILL_CAP.get(source, 50), 20000)


def ted_months():
    value = int(os.environ.get('PUBLIC_RECORDS_TED_BACKFILL_MONTHS', '12'))
    if not 1 <= value <= 36:
        raise ValueError('invalid_ted_backfill_months')
    return value


def target(source, days=None):
    """Data, od której źródło ma mieć całą historię."""
    today = timezone.localdate()
    if days:
        start = today - timedelta(days=int(days))
    elif source == 'ted':
        start = today - timedelta(days=ted_months() * 31)
    elif source == 'fts':
        # Pliki roczne FTS: obecne wieloletnie ramy finansowe (od 2021), env PUBLIC_RECORDS_FTS_FIRST_YEAR.
        start = date(min(max(2014, int(os.environ.get('PUBLIC_RECORDS_FTS_FIRST_YEAR', '2021'))), today.year), 1, 1)
    else:
        start = START
    return max(start, START) if source in SEJM_SOURCES else start


def reserve(source, mode):
    """Jedno zapytanie zasilania (wołane w transakcji fetch). False = limit zasilania na dziś wyczerpany."""
    row, _ = ImportState.objects.get_or_create(name=_name(source))
    row = ImportState.objects.select_for_update().get(pk=row.pk)
    data = dict(row.cursor or {})
    today = timezone.localdate().isoformat()
    if data.get('day') != today:
        data['day'], data['requests_today'] = today, 0
    if mode != 'resztka' and data['requests_today'] >= cap(source):
        return False
    data['requests_today'] += 1
    data['requests_total'] = int(data.get('requests_total') or 0) + 1
    row.cursor = data
    row.save(update_fields=['cursor'])
    return True


def seed_history(state, since):
    """Nasiona pełnej historii tam, gdzie zwykły cykl patrzy tylko na ostatnie dni. True = obsłużone."""
    today = timezone.localdate()
    if state.source == 'krs_changes':
        from news.political_models import RegisteredOrganisation
        for org in RegisteredOrganisation.objects.filter(archived=False).exclude(krs_number='').order_by('krs_number'):
            register = org.register if org.register in {'P', 'S'} else 'P'
            enqueue(state, f'{KRS_API}/OdpisAktualny/{org.krs_number}?rejestr={register}&format=json', 'krs_extract',
                    {'krs': org.krs_number, 'day': today.isoformat(), 'organisation_id': org.pk})
        return True
    if state.source == 'ted':
        # Miesiącami od najnowszego: API zwraca najwyżej 15 000 ogłoszeń na zapytanie.
        month = today.replace(day=1)
        while month >= since.replace(day=1):
            last = min((month + timedelta(days=32)).replace(day=1) - timedelta(days=1), today)
            first = max(month, since)
            body = {'query': f'buyer-country=POL AND publication-date>={first:%Y%m%d} AND publication-date<={last:%Y%m%d}',
                    'fields': TED_FIELDS, 'limit': 100, 'page': 1, 'paginationMode': 'PAGE_NUMBER', 'scope': 'ALL'}
            enqueue(state, TED_SEARCH, 'ted_page', {'body': body})
            month = (month - timedelta(days=1)).replace(day=1)
        return True
    return False


def _state(source):
    from news.public_records_models import PublicCollectionState
    return PublicCollectionState.objects.filter(source=source).first()


def finished(source, state=None, days=None):
    """Cykl od daty docelowej bez zaległych zadań: skończony bez błędu albo nasz cykl zasilania (z uwagami)."""
    state = state or _state(source)
    if state is None or not state.since or not state.cycle_started_at or state.jobs.filter(done=False).exists():
        return False
    ours = info(source).get('cycle') == state.cycle_started_at.isoformat()
    clean = bool(state.last_complete_at and state.last_complete_at >= state.cycle_started_at)
    return state.since <= target(source, days) and (clean or ours)


def complete(source):
    return bool(info(source).get('complete_at'))


def _mark_complete(source, state):
    return _update(source, complete_at=timezone.now().isoformat(),
                   note='z uwagami' if state.status == 'needs_review' else 'ok', records=state.record_count)


def run_source(source, mode='noc', max_requests=20, days=None):
    """Jedna porcja zasilania jednego źródła; wznawia kolejkę, nowy cykl historii zaczyna tylko bez zaległych zadań."""
    from news.public_records_models import PublicRecord
    if not flag(SOURCES[source].flag(source), False):
        return {'status': 'disabled', 'completed': 0, 'added': 0}
    if complete(source):
        return {'status': 'complete', 'completed': 0, 'added': 0, 'complete': True}
    state = _state(source)
    if state and finished(source, state, days):
        _mark_complete(source, state)
        return {'status': 'complete', 'completed': 0, 'added': 0, 'complete': True}
    before = PublicRecord.objects.filter(source=source).count()
    pending = bool(state and state.jobs.filter(done=False).exists())
    try:
        if pending:
            result = collect(source, max_requests=max_requests, backfill=mode)
        else:
            goal = target(source, days)
            result = collect(source, since=goal, max_requests=max_requests, backfill=mode)
            state = _state(source)
            if state and state.since == goal and result['status'] not in ('already_running', 'disabled'):
                _update(source, cycle=state.cycle_started_at.isoformat(), target=goal.isoformat())
    except ValueError as exc:  # inny cykl historii w toku albo zła konfiguracja: bez sieci
        result = {'status': 'error', 'error': str(exc)[:120], 'completed': 0}
    result = {**result, 'added': PublicRecord.objects.filter(source=source).count() - before}
    state = _state(source)
    if state and finished(source, state, days):
        _mark_complete(source, state)
        result['complete'] = True
    _update(source, last_run=timezone.now().isoformat(), last_status=result['status'])
    return result


def in_window(mode, now=None):
    return timezone.localtime(now or timezone.now()).hour in MODES[mode]


def run(lane='sejm', mode='noc', seconds=480, force=False, now=None):
    """Zadanie nocne jednego pasa: po kolei małe porcje każdego niegotowego źródła aż do końca czasu."""
    if mode not in MODES or lane not in LANES:
        raise ValueError('unknown_lane_or_mode')
    if not flag('ZASIL_BAZE_ENABLED', True):
        return {'status': 'disabled', 'produced': 0}
    if not force and not in_window(mode, now):
        return {'status': 'skipped', 'produced': 0}
    active = [s for s in LANES[lane] if flag(SOURCES[s].flag(s), False) and not complete(s)]
    if not active:
        return {'status': 'complete', 'produced': 0, 'sources_left': 0}
    deadline, added, requests, stalled = monotonic() + seconds, 0, 0, {}
    while active and monotonic() < deadline:
        progressed = False
        for source in list(active):
            if monotonic() >= deadline:
                break
            result = run_source(source, mode, max_requests=10)
            added += max(0, result.get('added', 0))
            requests += result.get('requests', 0) or 0
            if result.get('completed'):
                progressed, stalled[source] = True, 0
            else:
                stalled[source] = stalled.get(source, 0) + 1
            if (result.get('complete') or result['status'] in ('complete', 'disabled', 'blocked_access_review')
                    or stalled[source] >= 3):
                active.remove(source)  # gotowe, zablokowane albo limit na dziś: następne źródło
        if active and not progressed:
            sleep(3)
    links = link_after(lane) if added else None
    left = sum(1 for s in LANES[lane] if flag(SOURCES[s].flag(s), False) and not complete(s))
    return {'status': 'ok', 'produced': added, 'requests': requests, 'sources_left': left,
            **({'linked': links['linked']} if links else {})}


def link_after(lane='sejm'):
    """Po zasileniu: dopięcie nowych dokumentów Sejmu do osób (bez sieci, idempotentne); wynik do raportu."""
    if lane not in ('sejm', 'otwarte'):
        return None
    from news.public_record_people import link_people
    result = link_people()
    row, _ = ImportState.objects.get_or_create(name=LINKS)
    row.cursor = {**result, 'at': timezone.now().isoformat()}
    row.save(update_fields=['cursor'])
    return result


def _card_cap(source):
    """Dzienny limit zatwierdzonej karty dostępu (najmniejszy z kart źródła); 0 = brak ważnej karty. Bez sieci."""
    from news.models import SourceAccessInstruction
    from scraper.management.commands.configure_public_records import cards
    try:
        rows = cards(source)
    except Exception:  # noqa: BLE001 - np. meta_ads bez wersji API
        return 0
    caps = []
    for root, channel, endpoint, _, _ in rows:
        card = (SourceAccessInstruction.objects.filter(source__url=root, channel=channel, endpoint=endpoint,
                status='approved', valid_until__gt=timezone.now()).order_by('-version').first())
        caps.append(card.daily_request_cap if card else 0)
    return min(caps) if caps else 0


def _estimate(source, state):
    if source == 'ted':
        return ted_months() * TED_PAGES_PER_MONTH
    if source == 'krs_changes':
        from news.political_models import RegisteredOrganisation
        return RegisteredOrganisation.objects.filter(archived=False).exclude(krs_number='').count()
    return ESTIMATE.get(source, 10)


def plan_row(source, lane):
    from news.public_records_models import PublicRecord
    spec, state, data = SOURCES[source], _state(source), info(source)
    enabled = flag(spec.flag(source), False)
    records = PublicRecord.objects.filter(source=source)
    day_ago = timezone.now() - timedelta(hours=24)
    done = state.jobs.filter(done=True).count() if state else 0
    pending = state.jobs.filter(done=False).count() if state else 0
    covered = bool(state and state.since and state.since <= target(source))
    total = max(_estimate(source, state), done + pending if covered else 0)
    if data.get('complete_at'):
        percent, remaining = 100, 0
    elif covered:
        percent, remaining = min(99, int(100 * done / total)) if total else 0, max(pending, total - done)
    else:
        percent, remaining = 0, total
    active = max(1, sum(1 for s in LANES[lane] if flag(SOURCES[s].flag(s), False) and not complete(s)))
    card = _card_cap(source)
    nightly = min(cap(source), LANE_NIGHT // active, card or 0)
    daily = nightly + min(spec.cap, int((card or 0) * 0.6))
    return {'source': source, 'title': spec.title, 'lane': lane, 'enabled': enabled, 'card_cap': card,
            'backfill_cap': cap(source), 'target': target(source).isoformat(), 'records': records.count(),
            'added_24h': records.filter(fetched_at__gte=day_ago).count(), 'pending': pending, 'done': done,
            'estimate': total, 'remaining': remaining, 'percent': percent,
            'days': 0 if not remaining else (ceil(remaining / daily) if enabled and daily else None),
            'complete_at': data.get('complete_at'), 'requests_today': data.get('requests_today', 0)
            if data.get('day') == timezone.localdate().isoformat() else 0,
            'requests_total': data.get('requests_total', 0), 'status': state.status if state else 'brak',
            'error': state.last_error if state else ''}


def bzp_row():
    from django.conf import settings
    from scraper.bzp_backfill import STATE_NAME, history_floor
    row = ImportState.objects.filter(name=STATE_NAME).first()
    cursor = dict(row.cursor or {}) if row else {}
    enabled = bool(getattr(settings, 'BZP_API_ENABLED', False))
    base = {'source': 'bzp', 'title': 'Biuletyn Zamówień Publicznych (osobny zbieracz)', 'lane': 'bzp',
            'enabled': enabled, 'card_cap': BZP_DAILY, 'backfill_cap': BZP_DAILY, 'records': row.imported if row else 0,
            'added_24h': None, 'pending': 0, 'done': 0, 'requests_today': 0, 'requests_total': 0,
            'status': 'brak' if not row else ('gotowe' if cursor.get('complete') else 'w toku'),
            'error': row.last_error if row else ''}
    if not cursor:
        days = min(1095, max(1, int(os.environ.get('BZP_BACKFILL_DAYS', '365'))))
        pages = days * BZP_PAGES_PER_DAY
        return {**base, 'target': (timezone.localdate() - timedelta(days=days)).isoformat(), 'estimate': pages,
                'remaining': pages, 'percent': 0, 'days': ceil(pages / BZP_DAILY) if enabled else None,
                'complete_at': None}
    floor, cutoff, day = history_floor(cursor), date.fromisoformat(cursor['cutoff']), date.fromisoformat(cursor['day'])
    span = max(1, (cutoff - floor).days + 1)
    left = 0 if cursor.get('complete') else max(0, (day - floor).days + 1)
    history = cursor.get('history_complete_at')
    pages = left * BZP_PAGES_PER_DAY
    return {**base, 'target': floor.isoformat(), 'estimate': span * BZP_PAGES_PER_DAY, 'remaining': pages,
            'percent': 100 if history or cursor.get('complete') else min(99, int(100 * (span - left) / span)),
            'days': ceil(pages / BZP_DAILY) if enabled else None, 'complete_at': history}


def youtube_row():
    """YouTube: archiwa potwierdzonych kanałów z resztki darmowego limitu przed resetem (youtube_leftover_task 8:35)."""
    try:
        from news.youtube_collect import enabled, official_channels
        channels = list(official_channels().values_list('channel_id', flat=True))
        on = bool(enabled())
    except Exception:  # noqa: BLE001
        channels, on = [], False
    done = ImportState.objects.filter(name__in=['youtube-backfill:' + c for c in channels], cursor__done=True).count()
    left = len(channels) - done
    return {'source': 'youtube', 'title': 'YouTube: archiwa oficjalnych kanałów (resztka limitu 8:35)', 'lane': 'youtube',
            'enabled': on, 'card_cap': None, 'backfill_cap': None, 'target': '-', 'records': None, 'added_24h': None,
            'pending': left, 'done': done, 'estimate': len(channels), 'remaining': left,
            'percent': 100 if channels and not left else int(100 * done / len(channels)) if channels else 0,
            'days': None, 'complete_at': None, 'requests_today': 0, 'requests_total': 0,
            'status': 'gotowe' if channels and not left else 'w toku', 'error': ''}


def plan():
    rows = [plan_row(source, lane) for lane, sources in LANES.items() for source in sources]
    return rows + [bzp_row(), youtube_row()]


def links_summary():
    from django.db.models import Count, Q
    from news.public_records_models import PublicRecordPerson
    people = PublicRecordPerson.objects.aggregate(total=Count('pk'), linked=Count('pk', filter=Q(figure__isnull=False)))
    last = ImportState.objects.filter(name=LINKS).first()
    return {**people, 'unlinked': people['total'] - people['linked'], 'last_run': (last.cursor or {}).get('at') if last else None}


def _line(r):
    if not r['enabled']:
        return f"{r['source']}: wyłączone flagą"
    if r['percent'] == 100:
        state = f"gotowe ({(r['complete_at'] or '')[:10] or 'okno zebrane'})"
    else:
        days = f", ok. {r['days']} dni" if r['days'] else ('' if r['days'] == 0 else ', brak karty lub limitu')
        state = f"{r['percent']}%, zostało ok. {r['remaining']} zapytań{days}"
    added = f", +{r['added_24h']} / 24 h" if r['added_24h'] is not None else ''
    total = f", razem {r['records']}" if r['records'] is not None else ''
    return f"{r['source']}: {state}{added}{total}"


def report_lines():
    """Sekcja Raportu pętli: jedna linia na źródło."""
    rows = plan()
    links = links_summary()
    lines = [_line(r) for r in rows]
    lines.append(f"Powiązania z osobami: {links['linked']} z {links['total']} (bez osoby: {links['unlinked']})")
    return lines
