"""Codzienny Raport pętli (audyt pętli 5.10, punkt 5.1): jeden mail rano zamiast rozproszonych powiadomień.

Każda pętla ma kontrakt (CONTRACTS): kto produkuje (agenci AgentNote albo licznik z bazy), w jakim rytmie (cadence_h),
kto konsumuje wynik (consumer) i w ile dni ma go przeczytać lub rozstrzygnąć (sla_days). Raport mówi dla każdej pętli:
czy ruszyła w 24 h, ile wyprodukowała (24 h i 7 dni), ile wpisów czeka dłużej niż SLA, najlepsze nowe pomysły i błędy.
Tylko baza i cache, bez modeli i bez sieci (poza wysyłką maila). Stały temat maila pozwala znaleźć raport w Gmailu:
subject:"Raport pętli"."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
PROPOSALS = ('idea', 'experiment', 'finding')
OPEN = ('new', 'pending')
CATEGORIES = (('tresc', 'Treść dnia'), ('agenci', 'Agenci rozwoju'), ('przeszlosc', 'przeszłość.today'),
              ('niezawodnosc', 'Niezawodność'), ('konsylium', 'Konsylium'), ('dane', 'Zbieracze danych'))
CONSUMERS = {'owner:panel': 'właściciel w panelu', 'owner:mail': 'właściciel mailem', 'public': 'czytelnicy',
             'claude:sprint': 'Claude i Codex (sprint)', 'agent:prawnik': 'Prawnik', 'agent:architekt': 'Architekt',
             'agent:recruiter': 'Rekruter', 'agent:all': 'wszyscy agenci', 'agent:council': 'Konsylium'}
PENDING_TEXT = {'reports': '{n} raport(y) czeka na zgodę ponad 24 h', 'proposals': '{n} propozycji czeka na decyzję ponad {sla} dni',
                'tickets': '{n} bilet(y) po terminie', 'quorum': '{n} diagnoz(y) czeka na kworum Konsylium ponad 12 h'}
LIST_MAX = 40
PLAIN_READER = {'scores__reader': 'plain'}  # raporty Czytelnika testowego zapisywane jako strateg/report


def contract(key, label, category, cadence_h, consumer, sla_days=7, agents=(), kinds=None, beats=(), registry='', counter='',
             role=None, title='', match=None, exclude=None, pending=''):
    # label najwyżej 14 znaków (podpis pod kołem zębatym w panelu), pełna nazwa w title
    return dict(key=key, label=label, title=title or label, category=category, cadence_h=cadence_h, consumer=consumer, sla_days=sla_days,
                agents=tuple(agents), kinds=kinds, beats=tuple(beats), registry=registry, counter=counter, role=role,
                match=match or {}, exclude=exclude or {}, pending=pending)


# Rytm (cadence_h) to oczekiwany odstęp między WYNIKAMI pętli (nie między uruchomieniami zadania).
CONTRACTS = (
    # Treść dnia - konsumentem są czytelnicy
    contract('diagnozy', 'Diagnozy', 'tresc', 6, 'public', 1, beats=('clinic-diagnoses-day',), registry='dr-spin', counter='diagnoses', title='Diagnozy Dr. Spina'),
    contract('przekaz', 'Przekaz dnia', 'tresc', 24, 'public', 1, beats=('clinic-daily-messages-day',), registry='messages', counter='messages'),
    contract('wywiad', 'Wywiad dnia', 'tresc', 24, 'public', 1, beats=('clinic-interview-10m',), registry='interviews', counter='interviews'),
    contract('spinki', 'Spinki', 'tresc', 24, 'public', 1, beats=('dr-spin-thread-daily', 'thread-reviews-20m'),
             registry='spin-thread', counter='threads', title='Spinki Dr. Spina'),
    contract('raporty', 'Raporty', 'tresc', 24, 'owner:panel', 1, beats=('institutional-reports-night',), registry='raportysta',
             pending='reports', title='Raporty dla instytucji'),
    contract('raport-tyg', 'Raport tyg.', 'tresc', 168, 'owner:panel', 7, beats=('raport-tygodniowy-mon',), registry='raport-tygodniowy',
             counter='weekly_issues', title='Raport tygodniowy dla instytucji (PDF + CSV)'),
    contract('zapytania', 'Zapytania', 'tresc', 1, 'owner:mail', 2, beats=('zapytania-1h',), registry='zapytania',
             title='Zapytania: raporty dla instytucji i piloci'),
    contract('czytelnik', 'Czytelnik', 'tresc', 168, 'owner:panel', 14, agents=('strateg',), match=PLAIN_READER, beats=('plain-reader-weekly',),
             registry='plain-reader', title='Czytelnik testowy'),
    contract('zmiana-zdania', 'Zmiana zdania', 'tresc', 24, 'public', 1, beats=('zmiana-zdania-30m',), registry='zmiana-zdania',
             counter='position_checks', title='Zmiana zdania przy diagnozach'),
    contract('odbior-spinu', 'Odbiór spinu', 'tresc', 24, 'public', 1, beats=('odbior-spinu-1h',), registry='odbior-spinu',
             counter='reception', title='Jak spin zadziałał (po 24 h)'),
    contract('recenzent', 'Recenzent', 'tresc', 24, 'owner:panel', 7, agents=('recenzent',), beats=('recenzent-2h',), registry='recenzent'),
    # Agenci rozwoju spin.clinic
    contract('strateg', 'Strateg', 'agenci', 24, 'owner:panel', 7, agents=('strateg',), exclude=PLAIN_READER, beats=('agents-window-hourly',),
             registry='strateg'),
    contract('pielgrzym', 'Pielgrzym', 'agenci', 48, 'owner:panel', 7, agents=('pielgrzym',), beats=('agents-window-hourly',), registry='pilgrim'),
    contract('projektant', 'Projektant', 'agenci', 168, 'owner:panel', 7, agents=('projektant',), beats=('projektant-daily',),
             registry='projektant', title='Projektant UX/UI'),
    contract('automatyk', 'Automatyk', 'agenci', 24, 'owner:panel', 7, agents=('automatyk',), beats=('automatyk-daily',), registry='automatyk'),
    contract('decyzje', 'Decyzje', 'agenci', 72, 'claude:sprint', 7, counter='decisions', pending='proposals',
             title='Decyzje właściciela (pomysły i bilety)'),
    contract('sprint', 'Sprint', 'agenci', 168, 'claude:sprint', 7, beats=('sprint-intake',), registry='sprint', counter='tickets',
             pending='tickets', title='Sprint tygodnia (bilety budowy)'),
    contract('seba', 'Seba', 'agenci', 24, 'owner:panel', 2, beats=('seba-hourly',), registry='seba', counter='seba', title='Seba - krytyk propozycji'),
    # przeszłość.today - Pracownia OSINT
    contract('kartograf', 'Kartograf', 'przeszlosc', 168, 'agent:prawnik', 7, agents=('kartograf',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('zwiadowca', 'Zwiadowca', 'przeszlosc', 168, 'agent:prawnik', 7, agents=('zwiadowca',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('wynalazca', 'Wynalazca', 'przeszlosc', 72, 'agent:prawnik', 7, agents=('wynalazca',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('technolog', 'Technolog', 'przeszlosc', 168, 'agent:prawnik', 7, agents=('technolog',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('prawnik', 'Prawnik', 'przeszlosc', 168, 'agent:architekt', 7, agents=('prawnik',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('dziennikarz', 'Dziennikarz', 'przeszlosc', 72, 'agent:architekt', 7, agents=('dziennikarz',), beats=('pracownia-osint',),
             registry='pracownia-osint', title='Dziennikarz testowy'),
    contract('kontroler', 'Kontroler', 'przeszlosc', 24, 'agent:architekt', 7, agents=('kontroler',), beats=('pracownia-osint',),
             registry='pracownia-osint', title='Kontroler danych'),
    contract('architekt', 'Architekt', 'przeszlosc', 168, 'claude:sprint', 7, agents=('architekt',), beats=('pracownia-osint',),
             registry='pracownia-osint'),
    contract('tematy', 'Tematy dnia', 'przeszlosc', 24, 'public', 1, beats=('przeszlosc-topics',), registry='przeszlosc-topics', title='Tematy dnia przeszłość.today'),
    # Niezawodność
    contract('opiekun', 'Opiekunowie', 'niezawodnosc', 24, 'owner:panel', 3, agents=('opiekun',), beats=('opiekunowie-1h',),
             registry='opiekunowie', title='Opiekunowie pętli'),
    contract('dyrygent', 'Dyrygent', 'niezawodnosc', 24, 'claude:sprint', 7, agents=('dyrygent',), beats=('dyrygent-15m',), registry='dyrygent'),
    contract('dyzurny', 'Dyżurny', 'niezawodnosc', 1, 'owner:panel', 1, beats=('duty-15m',), registry='duty'),
    contract('raport-petli', 'Raport pętli', 'niezawodnosc', 24, 'owner:mail', 1, beats=('raport-petli-daily',), registry='raport-petli'),
    # Konsylium
    contract('ekspert', 'Ekspert AI', 'konsylium', 168, 'agent:recruiter', 14, agents=('ekspert',), beats=('ekspert-ai-daily',),
             registry='ekspert-ai'),
    contract('mechanik', 'Mechanik', 'konsylium', 24, 'agent:council', 7, beats=('mechanik-1h',), registry='mechanik'),
    contract('rekruter', 'Rekruter', 'konsylium', 24, 'agent:council', 7, beats=('council-recruiter-night',), registry='recruiter'),
    # Kworum (6.10): wynik = powtórzone diagnozy (ostatni wynik = ostatnia nocna kontrola, także bez powtórek do zrobienia);
    # czekające na kworum ponad 12 h to ostrzeżenie.
    contract('kworum', 'Kworum', 'konsylium', 24, 'public', 1, beats=('konsylium-powtorz-night',), registry='konsylium-powtorz',
             counter='quorum_reruns', pending='quorum', title='Kworum Konsylium (czekające i powtórki)'),
    # Zbieracze danych
    contract('zbieracz-x', 'Zbieracz X', 'dane', 2, 'agent:all', 1, beats=('political-x-minute',), registry='political_poll_task', counter='posts'),
    contract('badacz', 'Badacz', 'dane', 24, 'agent:all', 7, beats=('badacz-daily',), registry='badacz', title='Badacz - nowe źródła'),
    contract('zasil-baze', 'Zasilanie bazy', 'dane', 24, 'agent:all', 1, beats=('zasil-baze-sejm', 'zasil-baze-inne'),
             registry='zasil-baze', counter='public_records', title='Zasilanie bazy (historia źródeł)'),
)
BY_KEY = {c['key']: c for c in CONTRACTS}


def _stamp(value):
    from news.repairer import stamp
    return stamp(value)


def pulse(beat):
    """Puls zadania: cache (świeży) uzupełniony trwałym zapisem w bazie (po restarcie cache)."""
    from news.models import RepairerState
    row = RepairerState.objects.filter(key='pulse:' + beat).first()
    return {**(row.data if row else {}), **(cache.get('heartbeat:' + beat) or {})}


def _enabled(c):
    from news import agent_registry
    spec = agent_registry.REGISTRY.get(c['registry'])
    return agent_registry.enabled(spec) if spec else True


def _notes(c):
    from news.agent_models import AgentNote
    rows = AgentNote.objects.filter(agent__in=c['agents'])
    if c['kinds']:
        rows = rows.filter(kind__in=c['kinds'])
    if c['role']:
        rows = rows.filter(scores__role=c['role'])
    if c['match']:
        rows = rows.filter(**c['match'])
    if c['exclude']:
        rows = rows.exclude(pk__in=AgentNote.objects.filter(**c['exclude']).values('pk'))
    return rows


def owner_decisions(now=None):
    """Krok „Właściciel” (audyt 5.10, P6): ostatnia decyzja w panelu (notatki agentów i bilety sprintu) oraz pomysły
    i bilety, które czekają na decyzję dłużej niż SLA. Puls dla automatyk.LOOPS i dla pętli „Decyzje”."""
    from django.db.models import Max
    from news.agent_models import AgentNote, BuildTicket
    now = now or timezone.now()
    sla = timedelta(days=BY_KEY['decyzje']['sla_days'])
    last = [AgentNote.objects.aggregate(at=Max('decided_at'))['at'], BuildTicket.objects.aggregate(at=Max('decided_at'))['at']]
    waiting = AgentNote.objects.filter(kind__in=('idea', 'experiment', 'request'), status__in=OPEN, created_at__lt=now - sla)
    proposed = BuildTicket.objects.filter(status='proposed', created_at__lt=now - sla)
    oldest = min([d for d in (waiting.order_by('created_at').values_list('created_at', flat=True).first(),
                              proposed.order_by('created_at').values_list('created_at', flat=True).first()) if d], default=None)
    return {'last_decision': max([d for d in last if d], default=None), 'waiting': waiting.count() + proposed.count(),
            'oldest': oldest, 'sla_days': sla.days}


def tickets(now=None):
    """Bilety Sprintu tygodnia: otwarte, zatwierdzone i po terminie (zatwierdzone albo w budowie po due_date)."""
    from news.agent_models import BuildTicket
    now = now or timezone.now()
    today = now.astimezone(WARSAW).date()
    rows = BuildTicket.objects.filter(status__in=BuildTicket.OPEN)
    building = rows.filter(status__in=('approved', 'in_progress'))
    overdue = building.filter(due_date__lt=today)

    def pack(qs):
        return [{'id': t.pk, 'title': t.title, 'status': t.status, 'executor': t.executor,
                 'due': t.due_date.isoformat() if t.due_date else None} for t in qs.order_by('due_date', '-rank')[:10]]
    return {'open': rows.count(), 'proposed': rows.filter(status='proposed').count(), 'approved': building.count(),
            'overdue': overdue.count(), 'overdue_list': pack(overdue), 'approved_list': pack(building)}


def _pending(c, now):
    """Wyniki czekające na odbiorcę dłużej niż SLA w pętlach bez notatek agentów."""
    if c['pending'] == 'reports':
        from news.report_models import InstitutionalReport
        return InstitutionalReport.objects.filter(status='awaiting_approval', awaiting_since__lt=now - timedelta(hours=24)).count()
    if c['pending'] == 'proposals':
        return owner_decisions(now)['waiting']
    if c['pending'] == 'tickets':
        return tickets(now)['overdue']
    if c['pending'] == 'quorum':
        from news.clinic import quorum_waiting
        return quorum_waiting().filter(created_at__lt=now - timedelta(hours=12)).count()
    return 0


def _counter(c, since):
    """Wyniki pętli bez notatek agentów: liczba rekordów od chwili since i czas ostatniego."""
    from django.db.models import Max
    name = c['counter']
    if name == 'diagnoses':
        from news.clinic_models import SpinDiagnosis
        rows, field = SpinDiagnosis.objects.exclude(diagnosed_at__isnull=True), 'diagnosed_at'
    elif name == 'messages':
        from news.clinic_models import ClinicDailyMessage
        rows, field = ClinicDailyMessage.objects.all(), 'created_at'
    elif name == 'interviews':
        from news.clinic_models import ClinicInterview
        rows, field = ClinicInterview.objects.exclude(diagnosed_at__isnull=True), 'diagnosed_at'
    elif name == 'threads':
        from news.account_models import PersonalContextThread
        rows, field = PersonalContextThread.objects.filter(owner__isnull=True), 'created_at'
    elif name == 'posts':
        from news.political_models import PoliticalPost
        rows, field = PoliticalPost.objects.all(), 'fetched_at'
    elif name == 'decisions':
        from news.agent_models import AgentNote, BuildTicket
        count = AgentNote.objects.filter(decided_at__gte=since).count() + BuildTicket.objects.filter(decided_at__gte=since).count()
        return count, owner_decisions()['last_decision']
    elif name == 'tickets':
        from news.agent_models import BuildTicket
        rows, field = BuildTicket.objects.all(), 'created_at'
    elif name == 'position_checks':
        from news.clinic_models import PositionCheck
        rows, field = PositionCheck.objects.exclude(checked_at__isnull=True), 'checked_at'
    elif name == 'reception':
        from news.clinic_models import ReceptionCheck
        rows, field = ReceptionCheck.objects.filter(status__in=('done', 'no_model')), 'checked_at'
    elif name == 'public_records':
        from news.public_records_models import PublicRecord
        rows, field = PublicRecord.objects.all(), 'fetched_at'
    elif name == 'quorum_reruns':
        from news.council_rerun import done_since
        return done_since(since)
    elif name == 'weekly_issues':
        from news.sales_models import WeeklyReportIssue
        rows, field = WeeklyReportIssue.objects.exclude(status='failed'), 'generated_at'
    elif name == 'seba':
        from news.agent_models import SebaReview
        rows, field = SebaReview.objects.exclude(status='queued'), 'due_at'
    else:
        return None, None
    return rows.filter(**{field + '__gte': since}).count(), rows.aggregate(at=Max(field))['at']


FIRST_SEEN = 'petle-first-seen'
OLD = '2026-01-01T00:00:00+00:00'
# Pętle wdrożone 6.10 (zanim powstał zapis first_seen): pierwszy rytm liczymy od dnia wdrożenia.
ADDED = {'zmiana-zdania': '2026-10-06T23:00:00+02:00', 'odbior-spinu': '2026-10-07T12:00:00+02:00', 'raport-petli': '2026-10-06T23:00:00+02:00',
         'raport-tyg': '2026-10-07T12:00:00+02:00', 'zapytania': '2026-10-07T12:00:00+02:00'}


def first_seen(now, keys=None):
    """Kiedy pętla pojawiła się pierwszy raz (trwały zapis w bazie). Nowa pętla dostaje jeden rytm + 1 h na pierwszy
    wynik, zanim Raport pętli i bezpieczniki uznają ciszę za „STOI” (fałszywe alarmy po wdrożeniu 6.10).
    Przy pierwszym zapisie pętle już istniejące dostają starą datę (bez okresu ochronnego); każda pętla dopisana
    później do CONTRACTS dostaje chwilę, w której Raport pętli zobaczył ją pierwszy raz."""
    from news.models import RepairerState
    keys = keys or [c['key'] for c in CONTRACTS]
    try:
        row, created = RepairerState.objects.get_or_create(key=FIRST_SEEN)
        data = dict(row.data or {})
        if created or not data:
            data = {c['key']: ADDED.get(c['key'], OLD) for c in CONTRACTS}
        missing = [k for k in keys if k not in data]
        data.update({k: ADDED.get(k, now.isoformat()) for k in missing})
        if created or missing or row.data != data:
            row.data = data
            row.save(update_fields=['data'])
        return {k: _stamp(v) for k, v in data.items() if _stamp(v)}
    except Exception:  # noqa: BLE001 - raport zawsze wychodzi
        return {}


def _new_loop(c, now, seen):
    """Okres ochronny nowej pętli: od pierwszego pojawienia się minęło mniej niż rytm + 1 h."""
    first = seen.get(c['key'])
    return bool(first) and now - first < timedelta(hours=c['cadence_h'] + 1)


def _error_line(beat, p):
    why = p.get('last_error') or p.get('repair_hint') or ''
    return f"{beat}: błąd ({p.get('consecutive_errors') or 1} z rzędu){': ' + why if why else ''}"


def loop_state(c, now, seen=None):
    from django.db.models import Max
    pulses = [pulse(b) for b in c['beats']]
    runs = [_stamp(p.get('started_at') or p.get('last_event')) for p in pulses]
    last_run = max([r for r in runs if r], default=None)
    errors = []
    partial = []
    for beat, p in zip(c['beats'], pulses):
        if p.get('result') == 'error':
            errors.append(_error_line(beat, p))
        elif p.get('result') == 'ok' and p.get('partial'):
            partial.append(f"{beat}: częściowo - {p['partial']}")
    waiting_only = bool(pulses) and all(p.get('result') == 'skipped' for p in pulses if p)
    day, week = now - timedelta(hours=24), now - timedelta(days=7)
    pending, top = 0, []
    if c['agents']:
        rows = _notes(c)
        out_24, out_7 = rows.filter(created_at__gte=day).count(), rows.filter(created_at__gte=week).count()
        last_output = rows.aggregate(at=Max('created_at'))['at']
        pending = rows.filter(status__in=OPEN, created_at__lt=now - timedelta(days=c['sla_days'])).count()
        top = [{'id': n.pk, 'agent': n.agent, 'title': n.title, 'score': n.score} for n in
               rows.filter(kind__in=PROPOSALS, status='new', created_at__gte=week).order_by('-score', '-created_at')[:5]]
    elif c['counter']:
        out_7, last_output = _counter(c, week)
        out_24, _ = _counter(c, day)
    else:
        out_24 = out_7 = None
        last_output = max([_stamp(p.get('last_output_at')) for p in pulses if p.get('last_output_at')], default=None)
    if c['pending'] and not c['agents']:
        pending = _pending(c, now)
    pulse_output = max([_stamp(p.get('last_output_at')) for p in pulses if p.get('last_output_at')], default=None)
    if pulse_output and (not last_output or pulse_output > last_output):
        last_output = pulse_output
    enabled = _enabled(c)
    reference = last_output or (last_run if not (c['agents'] or c['counter']) else None)
    silence_h = round((now - reference).total_seconds() / 3600, 1) if reference else None
    silent = enabled and (reference is None or silence_h > 2 * c['cadence_h'])
    new = False
    if silent and reference is None:
        new = _new_loop(c, now, seen if seen is not None else first_seen(now, [c['key']]))
        silent = not new
    state, reasons = 'ok', []
    if not enabled:
        state, reasons = 'idle', ['wyłączona flagą']
    else:
        if errors:
            reasons.append(errors[0])
        if silent:
            reasons.append('brak wyniku' + (f' od {silence_h:g} h' if silence_h is not None else '') + f" (rytm {c['cadence_h']:g} h)")
        if errors or silent:
            state = 'bad'
        else:
            reasons += partial[:1]
            if pending:
                reasons.append(PENDING_TEXT.get(c['pending'], '{n} czeka dłużej niż {sla} dni').format(n=pending, sla=c['sla_days']))
            if waiting_only and not out_24:
                reasons.append('tylko „czeka na okno”, bez wyniku')
            if reasons:
                state = 'warn'
            if new:  # okres ochronny: nie „STOI”, tylko informacja
                reasons.insert(0, f"nowa pętla - pierwszy wynik w ciągu {c['cadence_h'] + 1:g} h")
    return {'key': c['key'], 'label': c['label'], 'title': c['title'], 'category': c['category'], 'state': state, 'reason': '; '.join(reasons),
            'enabled': enabled, 'last_run': last_run.isoformat() if last_run else None,
            'last_output': last_output.isoformat() if last_output else None, 'ran_24h': bool(last_run and last_run >= day),
            'outputs_24h': out_24 or 0, 'outputs_7d': out_7 or 0, 'counted': out_7 is not None, 'pending': pending,
            'consumer': CONSUMERS.get(c['consumer'], c['consumer']), 'consumer_key': c['consumer'], 'cadence_h': c['cadence_h'],
            'sla_days': c['sla_days'], 'top': top, 'errors': errors, 'new': new}


def short(reason, limit=60):
    """Krótki powód pod kołem w panelu: pierwszy powód, najwyżej limit znaków."""
    first = (reason or '').split('; ')[0]
    return first if len(first) <= limit else first[:limit - 1].rstrip() + '…'


def build(now=None):
    now = now or timezone.now()
    seen = first_seen(now)
    loops = [loop_state(c, now, seen) for c in CONTRACTS]
    _apply_fuses(loops, now)
    auto = _apply_repairs(loops, now)
    summary = {s: sum(l['state'] == s for l in loops) for s in ('ok', 'warn', 'bad', 'idle')}
    categories = [{'key': key, 'label': label, 'loops': [l for l in loops if l['category'] == key]} for key, label in CATEGORIES]
    top = sorted((t for l in loops for t in l['top']), key=lambda t: -t['score'])[:5]
    return {'generated_at': now.isoformat(), 'day': now.astimezone(WARSAW).strftime('%d.%m'), 'summary': summary,
            'categories': categories, 'top': top, 'sprint': tickets(now), 'auto': auto, 'build': to_build(),
            'baza': _baza(), 'koszty': _koszty(now)}


def _koszty(now):
    """Płatne odczyty X poza zbieraniem wpisów (odbior_spinu): odczyty i USD z dnia i 30 dni."""
    try:
        from news.odbior_spinu import report_line
        return [report_line(now)]
    except Exception:  # noqa: BLE001 - raport zawsze wychodzi
        return []


def _baza():
    """Postęp zasilania bazy per źródło (scraper.zasil_baze): % historii, +24 h, razem, dni do końca."""
    try:
        from scraper.zasil_baze import report_lines
        return report_lines()
    except Exception:  # noqa: BLE001 - raport zawsze wychodzi
        return []


def to_build(limit=10):
    """Zatwierdzone bilety sprintu jako gotowe zlecenia (sprint.brief) - Claude bierze je z maila Raportu pętli."""
    from news import sprint
    from news.agent_models import BuildTicket
    rows = BuildTicket.objects.select_related('note').filter(status__in=('approved', 'in_progress')).order_by('due_date', '-rank', 'pk')[:limit]
    return [{'id': t.pk, 'title': t.title, 'status': t.status, 'auto': sprint.auto_decided(t), 'brief': sprint.brief(t)} for t in rows]


def _apply_repairs(loops, now):
    """Naprawy automatyczne (petle_naprawy) w stanie pętli: udana naprawa -> „naprawione HH:MM” przy stanie ok,
    naprawa w toku -> co najwyżej „warn” (bez czerwonego), nieudana -> „warn” z powodem. Zwraca dane dla raportu."""
    try:
        from news import petle_naprawy as fix
        done, state, waiting = fix.actions(now), fix.load(), fix.owner_waiting(now)
    except Exception:  # noqa: BLE001 - raport zawsze wychodzi
        return {'done': [], 'failed': [], 'deferred': [], 'waiting': {}}
    for loop in loops:
        mine = [a for a in done if a['loop'] == loop['key']]
        notes = [fix.suppressed(f"petle:{kind}:{loop['key']}", now, state) for kind in ('silent', 'green-empty', 'error', 'consumer')]
        pending = next((n for n in notes if n), None)
        failed = [a for a in mine if a['result'] == 'failed']
        loop['repairs'] = [{k: (v.isoformat() if k == 'at' else v) for k, v in a.items()} for a in mine[-10:]]
        if loop['state'] == 'idle':
            continue
        if pending and loop['state'] == 'bad' and not failed:
            loop['state'] = 'warn'
            loop['reason'] = '; '.join(r for r in (fix.PENDING_TEXT + ': ' + pending, loop['reason']) if r)
        elif failed and loop['state'] == 'ok':
            loop['state'] = 'warn'
            loop['reason'] = 'naprawa nieudana: ' + failed[-1]['description']
        elif loop['state'] == 'ok' and any(a['result'] in fix.DONE for a in mine):
            last = max(a['at'] for a in mine if a['result'] in fix.DONE)
            loop['reason'] = f'naprawione {fix.hhmm(last)}'
    return {'done': [a for a in done if a['result'] in fix.DONE], 'failed': [a for a in done if a['result'] == 'failed'],
            'deferred': [a for a in done if a['result'] == 'skipped'], 'waiting': waiting}


def _apply_fuses(loops, now):
    """Bezpieczniki pętli (petle_bezpieczniki) podnoszą stan pętli; ich awaria nie może zatrzymać raportu."""
    try:
        from news.petle_bezpieczniki import by_loop
        fired = by_loop(now)
    except ImportError:
        return
    except Exception:  # noqa: BLE001 - raport zawsze wychodzi
        return
    rank = {'idle': -1, 'ok': 0, 'warn': 1, 'bad': 2}
    try:
        from news import petle_naprawy as fix
        state = fix.load()

        def held(key):
            return fix.suppressed(key, now, state)  # naprawa w toku
    except Exception:  # noqa: BLE001
        def held(key):
            return None
    for loop in loops:
        for fuse in fired.get(loop['key'], []):
            if fuse['level'] == 'info':
                continue  # tylko przypomnienie w raporcie („Czeka na Ciebie”)
            loop.setdefault('fuses', []).append(fuse['title'])
            if loop['state'] == 'idle' or fuse['key'].startswith('petle:silent:') or held(fuse['key']):
                continue  # cisza jest już w stanie pętli (loop_state); naprawa w toku nie podnosi stanu
            target = fuse['level']
            if rank[target] > rank[loop['state']]:
                loop['state'] = target
            if fuse['title'] not in loop['reason']:
                loop['reason'] = '; '.join(r for r in (loop['reason'], fuse['title']) if r)


def text(report):
    """Zwykły tekst dla właściciela, stałe nagłówki sekcji, bez sekretów."""
    from news.management.commands.stan_bledow import clean
    s = report['summary']
    lines = [f"Raport pętli spin.clinic i przeszłość.today - {report['day']}",
             f"Działa: {s['ok']} · do sprawdzenia: {s['warn']} · stoi: {s['bad']} · wyłączone: {s['idle']}", '']
    marks = {'ok': 'OK', 'warn': 'UWAGA', 'bad': 'STOI', 'idle': 'wył.'}
    lines += _build_lines(report, clean) + _auto_lines(report, clean)
    problems = [l for c in report['categories'] for l in c['loops'] if l['state'] in ('bad', 'warn')]
    lines.append('== Wymaga uwagi ==')
    lines += [f"[{marks[l['state']]}] {l['title']}: {clean(l['reason'])}" for l in sorted(problems, key=lambda l: l['state'] != 'bad')] or ['Nic.']
    lines.append('')
    for category in report['categories']:
        lines.append(f"== {category['label']} ==")
        for l in category['loops']:
            made = (f"wyniki 24 h: {l['outputs_24h']}, 7 dni: {l['outputs_7d']}" if l['counted'] else 'wyniki: puls zadania')
            ran = 'ruszyła w 24 h' if l['ran_24h'] else 'nie ruszyła w 24 h'
            extra = f", czeka ponad SLA: {l['pending']}" if l['pending'] else ''
            lines.append(f"[{marks[l['state']]}] {l['title']} - {ran}, {made}{extra}; odbiorca: {l['consumer']}")
        lines.append('')
    if report.get('koszty'):
        lines.append('== Koszty X (odpowiedzi) ==')
        lines += [clean(line) for line in report['koszty']] + ['']
    if report.get('baza'):
        lines.append('== Zasilanie bazy (historia źródeł) ==')
        lines += [clean(line) for line in report['baza']] + ['']
    sprint = report.get('sprint') or {}
    lines.append('== Sprint tygodnia ==')
    lines.append(f"Otwarte bilety: {sprint.get('open', 0)} (czeka na decyzję: {sprint.get('proposed', 0)}, "
                 f"zatwierdzone: {sprint.get('approved', 0)}, po terminie: {sprint.get('overdue', 0)})")
    lines += [f"- PO TERMINIE #{t['id']} {clean(t['title'])} (termin {t['due']}, {t['executor']})" for t in sprint.get('overdue_list', [])]
    lines += [f"- #{t['id']} {clean(t['title'])} (termin {t['due']}, {t['executor']})" for t in sprint.get('approved_list', [])
              if t not in sprint.get('overdue_list', [])]
    lines.append('')
    lines.append('== Najlepsze nowe pomysły i ustalenia (7 dni) ==')
    lines += [f"- {t['score']}/100 · {t['agent']}: {clean(t['title'])}" for t in report['top']] or ['Brak nowych.']
    lines += ['', 'Panel: https://spin.clinic/panel · Szczegóły: python manage.py raport_petli']
    return chr(10).join(lines)


def _build_lines(report, clean):
    """Na górze maila: zatwierdzone bilety jako gotowe zlecenia - Claude bierze je stąd w sesji."""
    rows = report.get('build') or []
    lines = ['== Do zbudowania przez Claude ==']
    if not rows:
        return lines + ['Nic zatwierdzonego.', '']
    from news.management.commands.stan_bledow import SECRET
    lines.append('Zatwierdzone bilety sprintu, gotowe zlecenia (Claude albo Codex w sesji):')
    for t in rows:
        lines += ['', SECRET.sub('[ukryte]', t['brief'])[:3000] + (' [zatwierdzony automatycznie: brak decyzji 48 h]' if t['auto'] else '')]
    return lines + ['']


def _auto_lines(report, clean):
    """Naprawy automatyczne z ostatniej doby i to, co zostaje tylko dla właściciela (przypomnienie raz dziennie)."""
    auto = report.get('auto') or {}
    done = auto.get('done') or []
    lines = ['== Naprawione automatycznie ==']
    lines += [f"- {a['at'].astimezone(WARSAW):%H:%M} {clean(a['description'])}" for a in done[:LIST_MAX]] or ['Nic do naprawy.']
    if len(done) > LIST_MAX:
        lines.append(f'- i {len(done) - LIST_MAX} więcej (dziennik napraw w panelu: Naprawiacz)')
    lines += [f"- ponowienie po 02:00: {clean(a['description'])}" for a in (auto.get('deferred') or [])[:10]]
    lines += [f"- NIEUDANE: {clean(a['description'])}" for a in (auto.get('failed') or [])[:10]]
    waiting = auto.get('waiting') or {}
    owner = []
    if waiting.get('reports'):
        owner.append(f"Raporty Raportysty czekają na Twoją zgodę ponad 24 h: {', '.join('#' + str(r) for r in waiting['reports'])} "
                     '(nie publikujemy ich sami).')
    owner += [f"Bilet #{t['id']} ({t['effort']}) czeka na decyzję ponad 48 h: {clean(t['title'])}" for t in waiting.get('tickets', [])]
    if waiting.get('costs'):
        owner.append(f"Prośby o koszt bez decyzji ponad 7 dni: {waiting['costs']}.")
    lines += ['', '== Czeka na Ciebie (przypomnienie raz dziennie) ==']
    lines += [f'- {o}' for o in owner] or ['Nic.']
    return lines + ['']


def recipient():
    from news.social_publish import _env
    return next((_env(name) for name in ('LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL', 'X_POST_ALERT_EMAIL') if _env(name)), '')


BEAT = 'raport-petli-daily'


def _touch_pulse(now, sent):
    """Wysyłka ręczna (manage.py raport_petli --wyslij) też jest biegiem pętli: puls jak po zadaniu Celery,
    żeby raport następnego dnia nie mówił „nie ruszyła w 24 h”."""
    from news.models import RepairerState
    from news.task_heartbeat import TTL
    stamp = now.isoformat()
    data = {'phase': 'ok' if sent else 'skipped', 'result': 'ok' if sent else 'skipped', 'last_event': stamp,
            'started_at': stamp, 'finished_at': stamp, 'summary': 'Raport wysłany.' if sent else 'Raport bez wysyłki.',
            'consecutive_errors': 0, 'error_since': None, 'last_error': '', 'last_produced': int(bool(sent))}
    if sent:
        data.update(last_success=stamp, last_output_at=stamp)
    try:
        cache.set('heartbeat:' + BEAT, {**(cache.get('heartbeat:' + BEAT) or {}), **data}, TTL)
        row, _ = RepairerState.objects.get_or_create(key='pulse:' + BEAT)
        row.data = {**(row.data or {}), **data}
        row.save(update_fields=['data'])
    except Exception:  # noqa: BLE001 - puls nie zatrzymuje raportu
        pass


def send(now=None, force=False):
    """Jeden mail dziennie (important=True: zastępuje rozproszone powiadomienia). Ścieżka automatyczna (zadanie 7:05,
    ponowienia, naprawy) wysyła najwyżej raz na dzień; force=True to jawna wysyłka ręczna (--wyslij)."""
    from django.db import transaction
    from news.models import RepairerState
    from news.social_publish import _mail
    now = now or timezone.now()
    key = f"raport-petli:{now.astimezone(WARSAW).date().isoformat()}"
    with transaction.atomic():
        RepairerState.objects.get_or_create(key=key)
        state = RepairerState.objects.select_for_update().get(key=key)
        data = dict(state.data or {})
        if not force and (data.get('sent') or data.get('sending_until') and (_stamp(data['sending_until']) or now) > now):
            return {'status': 'already_run', 'produced': 0}
        # Rezerwacja przed SMTP: dwa równoległe biegi nie wyślą dwóch maili.
        state.data = {**data, 'sending_until': (now + timedelta(minutes=10)).isoformat()}
        state.save(update_fields=['data'])
    report = build(now)
    to = recipient()
    sent = False
    try:
        sent = bool(to) and _mail(to, f"spin.clinic · Raport pętli {report['day']}", text(report), important=True)
    finally:
        sends = list(data.get('sends') or []) + ([{'at': now.isoformat(), 'manual': bool(force)}] if sent else [])
        state.data = {'sent': bool(sent or data.get('sent')), 'summary': report['summary'], 'at': now.isoformat(),
                      'sends': sends[-10:], 'sending_until': None,
                      'loops': {l['key']: l['state'] for c in report['categories'] for l in c['loops']}}
        state.save(update_fields=['data'])
        _touch_pulse(now, sent)
    return {'status': 'ok' if sent else 'not_configured' if not to else 'error', 'produced': int(bool(sent)),
            **{k: v for k, v in report['summary'].items()}}


def panel_section(now):
    """Karta „Pętle agentów” w panelu dowodzenia."""
    from news.admin_status import card, metric
    report = build(now)
    s = report['summary']
    items = [card(l['title'], 'error' if l['state'] == 'bad' else 'warn', l['reason'], l['last_output'] or l['last_run'],
                  [metric('Wyniki 24 h', l['outputs_24h']), metric('Wyniki 7 dni', l['outputs_7d']), metric('Czeka ponad SLA', l['pending'])])
             for c in report['categories'] for l in c['loops'] if l['state'] in ('bad', 'warn')]
    return card('Pętle agentów', 'error' if s['bad'] else 'warn' if s['warn'] else 'ok',
                'Kontrakty pętli: wynik, odbiorca i termin. Codzienny raport mailem o 7:05.', now,
                [metric('Działa', s['ok']), metric('Do sprawdzenia', s['warn']), metric('Stoi', s['bad']), metric('Wyłączone', s['idle'])],
                items)
