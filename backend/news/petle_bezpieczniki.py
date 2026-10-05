"""Bezpieczniki pętli agentów (audyt pętli 5.10, punkt 5.2). Tylko baza i cache, bez modeli.

Cztery kontrole Dyżurnego (duty_extra.CHECKS -> DutyAlarm, panel „Wymaga uwagi”, stan_bledow, Raport pętli):
(a) check_unused_outputs - agent ma ponad LOOP_UNUSED_MAX wpisów „new/pending” starszych niż LOOP_UNUSED_DAYS dni,
    albo pętla przez 3 rytmy nic nie wyprodukowała, choć puls zadania jest zielony;
(b) check_silent_loops - brak wyniku pętli dłużej niż 2 rytmy (pętle Pracowni i Opiekunów chowały się w „czeka”);
(c) check_quality - powtórzone tytuły pomysłów agenta, kolejka Seby starsza niż 48 h;
(d) check_consumers - wynik pętli ma odbiorcę i odbiorca działa w terminie SLA (właściciel rozstrzyga w panelu,
    Prawnik i Architekt czytają ustalenia badaczy).
Alarmy mają wagę „warning”: widać je w panelu i w Raporcie pętli, ale nie budzą właściciela mailem co 6 godzin.
Raport pętli bierze z fuses() poziom: „bad” stawia pętlę na czerwono, „warn” na żółto."""
import os
from datetime import timedelta
from difflib import SequenceMatcher

from django.utils import timezone

SEBA_QUEUE_HOURS = 48
DUPLICATE_RATIO = .85
DUPLICATE_PAIRS = 3
ZERO_RUNS = 3


def _int(name, default):
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def fuse(loop, key, level, title, details, since, instruction):
    return {'loop': loop, 'key': f'petle:{key}'[:180], 'level': level, 'title': title[:240], 'details': details,
            'since': since, 'instruction': instruction[:300]}


def _active():
    from news import raport_petli
    return [c for c in raport_petli.CONTRACTS if raport_petli._enabled(c)]


def _loop_for(agent):
    from news import raport_petli
    return next((c['key'] for c in raport_petli.CONTRACTS if agent in c['agents']), agent)


def unused_outputs(now):
    """(a) Wyniki bez odbiorcy: stos starych wpisów agenta i zielony puls bez wyniku."""
    from django.db.models import Count, Min
    from news import raport_petli
    days, limit = _int('LOOP_UNUSED_DAYS', 7), _int('LOOP_UNUSED_MAX', 10)
    out = []
    for c in raport_petli.CONTRACTS:  # per pętla, nie per agent: raporty Czytelnika testowego to nie zator Stratega
        if not c['agents']:
            continue
        row = (raport_petli._notes(c).filter(status__in=raport_petli.OPEN, created_at__lt=now - timedelta(days=days))
               .aggregate(n=Count('pk'), oldest=Min('created_at')))
        if row['n'] > limit:
            out.append(fuse(c['key'], f"unused:{c['key']}", 'bad' if row['n'] > 3 * limit else 'warn',
                            f"{c['label']}: {row['n']} wpisów czeka ponad {days} dni",
                            {'loop': c['key'], 'waiting': row['n'], 'days': days}, row['oldest'],
                            'Przejrzyj wpisy agenta w panelu (Przeczytane / Odrzucam) albo zmień odbiorcę pętli.'))
    for c in _active():
        if not (c['agents'] or c['counter']):
            continue
        window = now - timedelta(hours=ZERO_RUNS * c['cadence_h'])
        made = (raport_petli._notes(c).filter(created_at__gte=window).count() if c['agents'] else raport_petli._counter(c, window)[0])
        pulses = [raport_petli.pulse(b) for b in c['beats']]
        green = any(p.get('result') == 'ok' and (raport_petli._stamp(p.get('last_success')) or window) > window for p in pulses)
        if green and not made:
            out.append(fuse(c['key'], f"green-empty:{c['key']}", 'bad', f"{c['label']}: zielony puls, brak wyniku przez {ZERO_RUNS} rytmy",
                            {'loop': c['key'], 'hours': ZERO_RUNS * c['cadence_h']}, window,
                            'Zadanie kończy się „OK”, ale nic nie zapisuje: sprawdź warunki pominięcia i limity modeli.'))
    return out


def silent_loops(now):
    """(b) Cisza: ostatni wynik (albo bieg, gdy pętla nie liczy wyników) starszy niż 2 rytmy."""
    from news import raport_petli
    out = []
    for c in _active():
        state = raport_petli.loop_state(c, now)
        reference = raport_petli._stamp(state['last_output']) or (raport_petli._stamp(state['last_run']) if not state['counted'] else None)
        if reference and now - reference <= timedelta(hours=2 * c['cadence_h']):
            continue
        hours = round((now - reference).total_seconds() / 3600, 1) if reference else None
        out.append(fuse(c['key'], f"silent:{c['key']}", 'bad',
                        f"{c['label']}: cisza" + (f' od {hours:g} h' if hours is not None else ' - brak jakiegokolwiek wyniku'),
                        {'loop': c['key'], 'hours': hours, 'cadence_h': c['cadence_h']}, reference or now,
                        'Sprawdź puls zadania w mapie agentów i powód „czeka” (limity modeli, Dyrygent, flagi).'))
    return out


def quality(now):
    """(c) Jakość: powtórzone tytuły pomysłów agenta; kolejka Seby starsza niż 48 h."""
    from news.agent_models import AgentNote, SebaReview
    out = []
    recent = AgentNote.objects.filter(kind__in=('idea', 'experiment', 'finding'), created_at__gte=now - timedelta(days=14))
    for agent in set(recent.values_list('agent', flat=True)):
        titles = list(recent.filter(agent=agent).order_by('-created_at').values_list('title', flat=True)[:30])
        pairs = [(a, b) for i, a in enumerate(titles) for b in titles[i + 1:]
                 if SequenceMatcher(None, a.lower(), b.lower()).ratio() > DUPLICATE_RATIO]
        if len(pairs) >= DUPLICATE_PAIRS:
            out.append(fuse(_loop_for(agent), f'duplicates:{agent}', 'warn', f'{agent}: {len(pairs)} par prawie takich samych tytułów',
                            {'agent': agent, 'pairs': len(pairs), 'example': pairs[0][0][:120]}, now - timedelta(days=14),
                            'Agent powtarza propozycje: dodaj wcześniejsze tytuły do „previous” albo zmniejsz częstotliwość.'))
    old = SebaReview.objects.filter(status='queued', created_at__lt=now - timedelta(hours=SEBA_QUEUE_HOURS))
    count = old.count()
    if count:
        oldest = old.order_by('created_at').values_list('created_at', flat=True).first()
        reasons = sorted({r for r in old.values_list('last_error', flat=True) if r})[:3]
        out.append(fuse('seba', 'seba-queue', 'warn', f'Seba: {count} ocen czeka ponad {SEBA_QUEUE_HOURS} h',
                        {'queued': count, 'reasons': reasons}, oldest,
                        'Sprawdź limit SEBA_DAILY_CALLS i powody w kolejce; stare duplikaty usuń: manage.py porzadki_petli --wykonaj.'))
    return out


def consumers(now):
    """(d) Odbiorca działa w SLA: właściciel rozstrzyga w panelu, Prawnik i Architekt czytają ustalenia badaczy."""
    from news import raport_petli
    from news.agent_models import AgentNote
    out = []
    for c in _active():
        if not c['consumer']:
            out.append(fuse(c['key'], f"no-consumer:{c['key']}", 'bad', f"{c['label']}: wynik bez odbiorcy", {'loop': c['key']}, now,
                            'Dopisz odbiorcę pętli w raport_petli.CONTRACTS.'))
            continue
        if not c['agents']:
            continue
        sla = timedelta(days=c['sla_days'])
        overdue = raport_petli._notes(c).filter(status__in=raport_petli.OPEN, created_at__lt=now - sla)
        oldest = overdue.order_by('created_at').values_list('created_at', flat=True).first()
        if not oldest:
            continue
        if c['consumer'] == 'owner:panel':
            acted = raport_petli._notes(c).filter(decided_at__gte=now - sla).exists()
            if not acted:
                out.append(fuse(c['key'], f"consumer:{c['key']}", 'warn', f"{c['label']}: brak decyzji w panelu od {c['sla_days']} dni",
                                {'loop': c['key'], 'overdue': overdue.count()}, oldest,
                                'Rozstrzygnij wpisy w panelu agentów (Biorę / Przeczytane / Odrzucam).'))
        elif c['consumer'].startswith('agent:'):
            reader = c['consumer'].split(':', 1)[1]
            if not AgentNote.objects.filter(agent=reader, created_at__gt=oldest).exists():
                out.append(fuse(c['key'], f"consumer:{c['key']}", 'warn', f"{c['label']}: {reader} nie przeczytał wyników w {c['sla_days']} dni",
                                {'loop': c['key'], 'reader': reader, 'overdue': overdue.count()}, oldest,
                                f'Sprawdź, czy pętla {reader} działa (puls i powód „czeka”).'))
    return out


def deadlines(now):
    """(e) Terminy: raporty dla instytucji czekające na zgodę ponad 24 h, bilety sprintu po terminie,
    pomysły i bilety bez decyzji właściciela dłużej niż SLA."""
    from news import raport_petli
    from news.report_models import InstitutionalReport
    out = []
    reports = InstitutionalReport.objects.filter(status='awaiting_approval', awaiting_since__lt=now - timedelta(hours=24))
    if reports.exists():
        oldest = reports.order_by('awaiting_since').values_list('awaiting_since', flat=True).first()
        out.append(fuse('raporty', 'reports-awaiting', 'warn', f'Raporty: {reports.count()} czeka na Twoją zgodę ponad 24 h',
                        {'reports': list(reports.values_list('pk', flat=True)[:10])}, oldest,
                        'Zatwierdź albo odrzuć raporty w panelu (Raportysta: raporty do zatwierdzenia).'))
    sprint = raport_petli.tickets(now)
    if sprint['overdue']:
        first = sprint['overdue_list'][0]
        out.append(fuse('sprint', 'tickets-overdue', 'bad', f"Sprint: {sprint['overdue']} bilet(y) po terminie",
                        {'tickets': [t['id'] for t in sprint['overdue_list']]}, now,
                        f"Zbuduj albo przesuń bilet #{first['id']} ({first['title'][:80]}); zamknięcie: manage.py sprint_zlecenia."))
    owner = raport_petli.owner_decisions(now)
    if owner['waiting']:
        out.append(fuse('decyzje', 'owner-decisions', 'warn',
                        f"Decyzje: {owner['waiting']} propozycji czeka ponad {owner['sla_days']} dni",
                        {'waiting': owner['waiting'], 'last_decision': owner['last_decision'].isoformat() if owner['last_decision'] else None},
                        owner['oldest'] or now, 'Rozstrzygnij pomysły i bilety w panelu (Biorę / Odrzucam, Buduj / Nie teraz).'))
    return out


RULES = (('check_unused_outputs', unused_outputs), ('check_silent_loops', silent_loops),
         ('check_quality', quality), ('check_consumers', consumers), ('check_deadlines', deadlines))


def fuses(now=None):
    now = now or timezone.now()
    out = []
    for _, rule in RULES:
        out += rule(now)
    return out


def by_loop(now=None):
    grouped = {}
    for f in fuses(now):
        grouped.setdefault(f['loop'], []).append(f)
    return grouped


def _alarms(rule, ctx):
    from news.duty import alarm
    return [alarm(f['key'], 'warning', f['title'], f['details'], f['since'], f['instruction']) for f in rule(ctx.now)]


def check_unused_outputs(ctx):
    return _alarms(unused_outputs, ctx)


def check_silent_loops(ctx):
    return _alarms(silent_loops, ctx)


def check_quality(ctx):
    return _alarms(quality, ctx)


def check_consumers(ctx):
    return _alarms(consumers, ctx)


def check_deadlines(ctx):
    return _alarms(deadlines, ctx)


CHECKS = (check_unused_outputs, check_silent_loops, check_quality, check_consumers, check_deadlines)
