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


def contract(key, label, category, cadence_h, consumer, sla_days=7, agents=(), kinds=None, beats=(), registry='', counter='',
             role=None, title=''):
    # label najwyżej 14 znaków (podpis pod kołem zębatym w panelu), pełna nazwa w title
    return dict(key=key, label=label, title=title or label, category=category, cadence_h=cadence_h, consumer=consumer, sla_days=sla_days,
                agents=tuple(agents), kinds=kinds, beats=tuple(beats), registry=registry, counter=counter, role=role)


# Rytm (cadence_h) to oczekiwany odstęp między WYNIKAMI pętli (nie między uruchomieniami zadania).
CONTRACTS = (
    # Treść dnia - konsumentem są czytelnicy
    contract('diagnozy', 'Diagnozy', 'tresc', 6, 'public', 1, beats=('clinic-diagnoses-day',), registry='dr-spin', counter='diagnoses', title='Diagnozy Dr. Spina'),
    contract('przekaz', 'Przekaz dnia', 'tresc', 24, 'public', 1, beats=('clinic-daily-messages-day',), registry='messages', counter='messages'),
    contract('wywiad', 'Wywiad dnia', 'tresc', 24, 'public', 1, beats=('clinic-interview-10m',), registry='interviews', counter='interviews'),
    contract('spinki', 'Spinki', 'tresc', 24, 'public', 1, beats=('dr-spin-thread-daily', 'thread-reviews-20m'),
             registry='spin-thread', counter='threads', title='Spinki Dr. Spina'),
    contract('recenzent', 'Recenzent', 'tresc', 24, 'owner:panel', 7, agents=('recenzent',), beats=('recenzent-2h',), registry='recenzent'),
    # Agenci rozwoju spin.clinic
    contract('strateg', 'Strateg', 'agenci', 24, 'owner:panel', 7, agents=('strateg',), beats=('agents-window-hourly',), registry='strateg'),
    contract('pielgrzym', 'Pielgrzym', 'agenci', 48, 'owner:panel', 7, agents=('pielgrzym',), beats=('agents-window-hourly',), registry='pilgrim'),
    contract('projektant', 'Projektant', 'agenci', 168, 'owner:panel', 7, agents=('projektant',), beats=('projektant-daily',),
             registry='projektant', title='Projektant UX/UI'),
    contract('automatyk', 'Automatyk', 'agenci', 24, 'owner:panel', 7, agents=('automatyk',), beats=('automatyk-daily',), registry='automatyk'),
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
    # Zbieracze danych
    contract('zbieracz-x', 'Zbieracz X', 'dane', 2, 'agent:all', 1, beats=('political-x-minute',), registry='political_poll_task', counter='posts'),
    contract('badacz', 'Badacz', 'dane', 24, 'agent:all', 7, beats=('badacz-daily',), registry='badacz', title='Badacz - nowe źródła'),
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
    return rows


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
    elif name == 'seba':
        from news.agent_models import SebaReview
        rows, field = SebaReview.objects.exclude(status='queued'), 'due_at'
    else:
        return None, None
    return rows.filter(**{field + '__gte': since}).count(), rows.aggregate(at=Max(field))['at']


def loop_state(c, now):
    from django.db.models import Max
    pulses = [pulse(b) for b in c['beats']]
    runs = [_stamp(p.get('started_at') or p.get('last_event')) for p in pulses]
    last_run = max([r for r in runs if r], default=None)
    errors = []
    for beat, p in zip(c['beats'], pulses):
        if p.get('result') == 'error':
            errors.append(f"{beat}: błąd ({p.get('consecutive_errors') or 1} z rzędu){' - ' + p['repair_hint'] if p.get('repair_hint') else ''}")
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
    pulse_output = max([_stamp(p.get('last_output_at')) for p in pulses if p.get('last_output_at')], default=None)
    if pulse_output and (not last_output or pulse_output > last_output):
        last_output = pulse_output
    enabled = _enabled(c)
    reference = last_output or (last_run if not (c['agents'] or c['counter']) else None)
    silence_h = round((now - reference).total_seconds() / 3600, 1) if reference else None
    silent = enabled and (reference is None or silence_h > 2 * c['cadence_h'])
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
            if pending:
                reasons.append(f"{pending} czeka dłużej niż {c['sla_days']} dni")
            if waiting_only and not out_24:
                reasons.append('tylko „czeka na okno”, bez wyniku')
            if reasons:
                state = 'warn'
    return {'key': c['key'], 'label': c['label'], 'title': c['title'], 'category': c['category'], 'state': state, 'reason': '; '.join(reasons),
            'enabled': enabled, 'last_run': last_run.isoformat() if last_run else None,
            'last_output': last_output.isoformat() if last_output else None, 'ran_24h': bool(last_run and last_run >= day),
            'outputs_24h': out_24 or 0, 'outputs_7d': out_7 or 0, 'counted': out_7 is not None, 'pending': pending,
            'consumer': CONSUMERS.get(c['consumer'], c['consumer']), 'consumer_key': c['consumer'], 'cadence_h': c['cadence_h'],
            'sla_days': c['sla_days'], 'top': top, 'errors': errors}


def short(reason, limit=60):
    """Krótki powód pod kołem w panelu: pierwszy powód, najwyżej limit znaków."""
    first = (reason or '').split('; ')[0]
    return first if len(first) <= limit else first[:limit - 1].rstrip() + '…'


def build(now=None):
    now = now or timezone.now()
    loops = [loop_state(c, now) for c in CONTRACTS]
    _apply_fuses(loops, now)
    summary = {s: sum(l['state'] == s for l in loops) for s in ('ok', 'warn', 'bad', 'idle')}
    categories = [{'key': key, 'label': label, 'loops': [l for l in loops if l['category'] == key]} for key, label in CATEGORIES]
    top = sorted((t for l in loops for t in l['top']), key=lambda t: -t['score'])[:5]
    return {'generated_at': now.isoformat(), 'day': now.astimezone(WARSAW).strftime('%d.%m'), 'summary': summary,
            'categories': categories, 'top': top}


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
    for loop in loops:
        for fuse in fired.get(loop['key'], []):
            loop.setdefault('fuses', []).append(fuse['title'])
            if loop['state'] == 'idle':
                continue
            target = 'bad' if fuse['severity'] == 'critical' else 'warn'
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
    lines.append('== Najlepsze nowe pomysły i ustalenia (7 dni) ==')
    lines += [f"- {t['score']}/100 · {t['agent']}: {clean(t['title'])}" for t in report['top']] or ['Brak nowych.']
    lines += ['', 'Panel: https://spin.clinic/panel · Szczegóły: python manage.py raport_petli']
    return chr(10).join(lines)


def recipient():
    from news.social_publish import _env
    return next((_env(name) for name in ('LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL', 'X_POST_ALERT_EMAIL') if _env(name)), '')


def send(now=None, force=False):
    """Jeden mail dziennie (important=True: zastępuje rozproszone powiadomienia). Idempotentne per dzień."""
    from news.models import RepairerState
    from news.social_publish import _mail
    now = now or timezone.now()
    key = f"raport-petli:{now.astimezone(WARSAW).date().isoformat()}"
    state, _ = RepairerState.objects.get_or_create(key=key)
    if state.data.get('sent') and not force:
        return {'status': 'already_run', 'produced': 0}
    report = build(now)
    to = recipient()
    sent = bool(to) and _mail(to, f"spin.clinic · Raport pętli {report['day']}", text(report), important=True)
    state.data = {'sent': sent, 'summary': report['summary'], 'at': now.isoformat(),
                  'loops': {l['key']: l['state'] for c in report['categories'] for l in c['loops']}}
    state.save(update_fields=['data'])
    return {'status': 'ok' if sent else 'not_configured' if not to else 'error', 'produced': int(sent),
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
