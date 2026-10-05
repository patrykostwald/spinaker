"""Naprawy automatyczne pętli (właściciel 6.10: „gdzie się da, naprawiaj sam, bez mojej reakcji; naprawy są częścią alertów”).

Każdy bezpiecznik (petle_bezpieczniki) najpierw wywołuje tu naprawę, a alarmuje dopiero wtedy, gdy naprawa się nie udała
albo nie jest możliwa. Każda naprawa ma limit prób i ślad w dzienniku napraw (RepairAction, reguły „petle:*”). Raport pętli
wypisuje je w sekcji „Naprawione automatycznie”, a koło zębate w panelu pokazuje „naprawione HH:MM”.
Nigdy nic nie usuwa, nigdy nie publikuje raportów Raportysty i nie wywołuje modeli (ponawia tylko zadania Celery,
które same pilnują limitów).

(a) stare wpisy: ustalenia, oceny, audyty, raporty i sygnały po 7 dniach -> done („archiwum automatyczne”);
    pomysły i eksperymenty: Seba przepuścił i wynik >= 80 -> bilet sprintu; wynik < 50 -> odrzucone z powodem;
    środek -> jeszcze jedna ocena Seby i decyzja według jej progu (gdy drugiej oceny nie będzie: próg 65);
(b) cisza i zielony puls bez wyniku: ponowienie zadania pętli (najwyżej 2 na dobę), z poszanowaniem trybu Dyrygenta
    i limitów Konsylium (bez wolnego modelu ponowienie po resecie o 02:00, bez alarmu); twardy błąd modelu -> Mechanik;
(c) duplikaty: zostaje najnowszy, reszta odrzucona „duplikat #id”; kolejka Seby > 48 h: ponowienie z autorem „local”,
    po kolejnych 48 h bez modelu decyzja progiem (>= 80 przepuść, reszta odrzuć);
(d) odbiorca: agent -> ponowienie jego zadania; właściciel -> bilety S/M bez zastrzeżeń Prawnika zatwierdzone po 48 h
    (auto: brak decyzji 48 h), L i raporty Raportysty tylko w przypomnieniu raz dziennie w Raporcie pętli;
(e) błąd zadania przejściowy (timeout, 5xx, DataError, TransactionManagementError) -> ponowienie; zadania z listy
    Naprawiacza (repairer.SAFE_TASKS) idą jego ścieżką retry_task."""
import json
import os
from datetime import timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
STATE = 'petle-naprawy'
STALE_DAYS = 7
SPRINT_MIN, REJECT_BELOW, MIDDLE_THRESHOLD = 80, 50, 65
ARCHIVE_KINDS = ('finding', 'review', 'audit', 'report', 'signal')
IDEA_KINDS = ('idea', 'experiment')
MAX_RETRIGGERS = 2
TICKET_WAIT = timedelta(hours=48)
SEBA_WAIT = timedelta(hours=48)
RESET_HOUR = 2
BATCH = 200
PENDING_TEXT = 'naprawa w toku'
TRANSIENT_EXTRA = ('dataerror', 'value too long', 'transactionmanagementerror', 'timeouterror', 'readtimeout')
DONE = ('fixed', 'retried')
NO_RETRIGGER = ('dyzurny', 'raport-petli')  # Dyżurny nie ponawia sam siebie; raport wychodzi raz na dobę (idempotentny)
OWN_REPAIR = ('tresc', 'dane')  # treść i zbieracze: tylko zadania zatwierdzone dla Naprawiacza, resztą zajmuje się Ratownik


def enabled():
    return os.environ.get('LOOP_AUTOREPAIR', 'true').strip().lower() == 'true'


# --- stan i dziennik ---------------------------------------------------------------------------------------------

def load():
    from news.models import RepairerState
    row = RepairerState.objects.filter(key=STATE).first()
    return dict(row.data) if row else {}


def save(data, now):
    from news.models import RepairerState
    day = reset_day(now)
    data = {k: v for k, v in data.items() if not k.startswith('_')}
    data['suppress'] = {k: v for k, v in (data.get('suppress') or {}).items() if (_stamp(v.get('until')) or now) > now}
    data['beats'] = {k: v for k, v in (data.get('beats') or {}).items() if k.startswith(day + '|')}
    data['last_beat'] = {k: v for k, v in (data.get('last_beat') or {}).items()
                         if isinstance(v, dict) and (_stamp(v.get('at')) or now) > now - timedelta(days=2)}
    data['seba'] = {k: v for k, v in (data.get('seba') or {}).items() if (_stamp(v) or now) > now - 4 * SEBA_WAIT}
    RepairerState.objects.update_or_create(key=STATE, defaults={'data': data})


def _stamp(value):
    from news.repairer import stamp
    return stamp(value)


def reset_day(now):
    """Doba limitów Konsylium: reset o 02:00 czasu polskiego."""
    return (now.astimezone(WARSAW) - timedelta(hours=RESET_HOUR)).date().isoformat()


def next_reset(now):
    local = now.astimezone(WARSAW)
    target = local.replace(hour=RESET_HOUR, minute=5, second=0, microsecond=0)
    return target if target > local else target + timedelta(days=1)


def hhmm(now):
    return now.astimezone(WARSAW).strftime('%H:%M')


def log(rule, loop, target, result, description, now):
    from news.models import RepairAction
    return RepairAction.objects.create(created_at=now, rule=f'petle:{rule}'[:40], target=f'{loop}|{target}'[:160],
                                       result=result, description=description[:300])


def suppress(data, key, until, note):
    data.setdefault('suppress', {})[key] = {'until': until.isoformat(), 'note': note[:120]}


def suppressed(key, now, data=None):
    """Notatka naprawy w toku dla bezpiecznika albo None (alarm wstrzymany, bo naprawa jeszcze działa)."""
    data = load() if data is None else data
    row = (data.get('suppress') or {}).get(key)
    return row['note'] if row and (_stamp(row.get('until')) or now) > now else None


def seba_requeued(now, data=None):
    """Oceny Seby ponowione przez naprawę w ostatnich 48 h (kolejka nie alarmuje, czeka na wynik)."""
    data = load() if data is None else data
    return {int(pk) for pk, at in (data.get('seba') or {}).items() if (_stamp(at) or now) > now - SEBA_WAIT}


def actions(now, hours=24):
    """Naprawy pętli z ostatniej doby (dla Raportu pętli i kół zębatych w panelu)."""
    from news.models import RepairAction
    rows = RepairAction.objects.filter(rule__startswith='petle:', created_at__gte=now - timedelta(hours=hours)).order_by('created_at', 'pk')
    return [{'rule': r.rule.split(':', 1)[1], 'loop': r.target.split('|', 1)[0], 'target': r.target.split('|', 1)[-1],
             'result': r.result, 'description': r.description, 'at': r.created_at} for r in rows]


# --- (a) stare wpisy -----------------------------------------------------------------------------------------------

def _auto(note, action, reason, now, **extra):
    data = dict(note.scores or {})
    data['auto'] = {**(data.get('auto') or {}), 'action': action, 'reason': reason[:240], 'at': now.isoformat(), **extra}
    return data


def _set(note, status, action, reason, now, **extra):
    """Zmiana statusu tylko z otwartego (idempotentne, bez wyścigu z decyzją właściciela). Nigdy nie usuwa."""
    from news.agent_models import AgentNote
    from news.raport_petli import OPEN
    return AgentNote.objects.filter(pk=note.pk, status__in=OPEN).update(status=status, scores=_auto(note, action, reason, now, **extra))


def _has_ideas(note):
    return note.kind == 'finding' and any(isinstance(i, dict) and i.get('title') for i in (note.scores or {}).get('ideas', []))


def settle(c, now, days, verdicts=None, data=None):
    """Rozstrzyga wpisy pętli starsze niż `days` dni. Zwraca listę wyników (do testów i dziennika)."""
    from news import raport_petli, sprint
    from news.agent_models import AgentNote, SebaReview
    from news import seba
    verdicts = sprint._verdicts() if verdicts is None else verdicts
    rows = list(raport_petli._notes(c).filter(status__in=raport_petli.OPEN, created_at__lt=now - timedelta(days=days))
                .order_by('created_at', 'pk')[:BATCH])
    out, to_sprint = [], []
    for note in rows:
        title = f'#{note.pk} {note.title[:120]}'
        if note.kind == 'request':
            proposal = AgentNote.objects.filter(pk=(note.scores or {}).get('proposal_id') or 0).first()
            if proposal and proposal.status in ('rejected', 'denied') and _set(note, 'denied', 'odrzucone', f'propozycja #{proposal.pk} odrzucona', now):
                log('koszt', c['key'], f'#{note.pk}', 'fixed', f'Prośba o koszt odrzucona razem z propozycją: {title}', now)
                out.append((note.pk, 'denied'))
            continue  # pieniądze: decyzja właściciela, tylko przypomnienie w raporcie
        if note.kind in IDEA_KINDS or _has_ideas(note):
            auto = (note.scores or {}).get('auto') or {}
            review = SebaReview.objects.filter(note=note).first()
            if review and review.status == 'queued':
                if auto.get('stage') != 'seba':
                    AgentNote.objects.filter(pk=note.pk).update(scores=_auto(note, 'czeka', 'czeka na ocenę Seby', now, stage='seba'))
                out.append((note.pk, 'waiting'))
                continue
            passed = review is None or review.status == 'passed'
            seba_text = f"Seba: {'przepuścił' if passed else 'odrzucił'}" if review else 'bez oceny Seby'
            if auto.get('seba_requeued'):
                decision = 'sprint' if passed else 'reject'
                reason = f'druga ocena Seby: {"przepuścił" if passed else "odrzucił"}'
            elif note.score < REJECT_BELOW:
                decision, reason = 'reject', f'wynik {note.score}/100 poniżej {REJECT_BELOW} po {days} dniach'
            elif passed and note.score >= SPRINT_MIN:
                decision, reason = 'sprint', f'wynik {note.score}/100, {seba_text}'
            elif review and review.rounds < 2 and seba.enabled():
                changed = SebaReview.objects.filter(pk=review.pk).exclude(status='queued').update(
                    status='queued', phase='critique', due_at=now, lease_until=None, lease_token='',
                    last_error='Druga ocena (naprawa automatyczna).')
                if changed:
                    if data is not None:
                        data.setdefault('seba', {})[str(review.pk)] = now.isoformat()  # kolejka Seby czeka 48 h bez alarmu
                    AgentNote.objects.filter(pk=note.pk).update(scores=_auto(note, 'seba', 'jeszcze jedna ocena Seby', now,
                                                                             stage='seba', seba_requeued=now.isoformat()))
                    log('seba', c['key'], f'#{note.pk}', 'retried', f'Jeszcze jedna ocena Seby (wynik {note.score}/100): {title}', now)
                out.append((note.pk, 'requeued'))
                continue
            else:
                ok = passed and note.score >= MIDDLE_THRESHOLD
                decision = 'sprint' if ok else 'reject'
                reason = f'wynik {note.score}/100, {seba_text}, próg {MIDDLE_THRESHOLD}'
            if decision == 'sprint' and sprint._legal(note, note.title, verdicts) == 'niedozwolone':
                decision, reason = 'reject', 'Prawnik: niedozwolone'
            if decision == 'reject':
                if _set(note, 'rejected', 'odrzucone', reason, now):
                    log('odrzucone', c['key'], f'#{note.pk}', 'fixed', f'Odrzucone automatycznie ({reason}): {title}', now)
                    out.append((note.pk, 'rejected'))
            elif _set(note, 'accepted', 'sprint', reason, now):
                to_sprint.append(note)
                out.append((note.pk, 'sprint'))
            continue
        if note.kind in ARCHIVE_KINDS and _set(note, 'done', 'archiwum', 'archiwum automatyczne', now):
            log('archiwum', c['key'], f'#{note.pk}', 'fixed', f'Archiwum automatyczne: {title}', now)
            out.append((note.pk, 'done'))
    if to_sprint:
        hand_to_sprint(c, to_sprint, now)
    return out


def hand_to_sprint(c, notes, now):
    """Przyjęte pomysły trafiają do Sprintu tygodnia jako bilety `proposed` (do limitu MAX_PROPOSED; reszta czeka na intake)."""
    from news import sprint
    from news.agent_models import BuildTicket
    ids = {n.pk for n in notes}
    room = sprint.MAX_PROPOSED - BuildTicket.objects.filter(status='proposed').count()
    made = {}
    for cand in [cand for cand in sprint.candidates(now) if cand['note'].pk in ids][:max(0, room)]:
        ticket = sprint.create_ticket(cand, now)
        made.setdefault(cand['note'].pk, []).append(ticket.pk)
    for note in notes:
        title = f'#{note.pk} {note.title[:120]}'
        if made.get(note.pk):
            log('sprint', c['key'], f'#{note.pk}', 'fixed', f"Do sprintu (bilet {', '.join('#' + str(t) for t in made[note.pk])}): {title}", now)
        elif note.agent in sprint.SKIP_AGENTS:
            log('sprint', c['key'], f'#{note.pk}', 'fixed', f'Przyjęte (poza sprintem, własna pętla napraw): {title}', now)
        else:
            log('sprint', c['key'], f'#{note.pk}', 'fixed', f'Przyjęte, czeka na miejsce w sprincie: {title}', now)


def settle_all(now, owner_sla=False, data=None):
    """Wszystkie pętle z notatkami: 7 dni; z owner_sla także pętle właściciela według SLA (gdy krótsze)."""
    from news import raport_petli, sprint
    verdicts = sprint._verdicts()
    out = []
    for c in raport_petli.CONTRACTS:
        if not c['agents']:
            continue
        days = min(STALE_DAYS, c['sla_days']) if owner_sla and c['consumer'] == 'owner:panel' else STALE_DAYS
        out += settle(c, now, days, verdicts, data)
    return out


# --- (b), (e) ponowienie zadania pętli -----------------------------------------------------------------------------

def _capacity():
    try:
        from news import dyrygent
        return dyrygent.capacity()
    except Exception:  # noqa: BLE001 - brak danych o limitach nie może blokować naprawy
        return 1.0


def _model_free(tasks):
    """Czy Dyrygent i limity Konsylium pozwalają teraz uruchomić zadania z AI (bez wywołań modeli)."""
    from news import dyrygent
    tiers = [dyrygent.AI_TASKS.get(t.rsplit('.', 1)[-1]) for t in tasks]
    tiers = [t for t in tiers if t]
    if not tiers:
        return True
    if any(t not in ('treść',) and not dyrygent.allowed(t) for t in tiers):
        return False
    return _capacity() > 0


def known_transient(pulse):
    from news.repairer import permanent, transient
    text = ' '.join(str(pulse.get(k) or '') for k in ('summary', 'repair_hint')).lower()
    if pulse.get('repair_error') == 'permanent' or permanent(text):
        return False
    return pulse.get('repair_error') == 'transient' or transient(text) or any(w in text for w in TRANSIENT_EXTRA)


def _ask_mechanik(c, pulses, data, now):
    """Twardy błąd modelu (404, 400, nie znaleziono) w pulsie pętli: Mechanik szuka zamiennika, raz na dobę."""
    from news.mechanik import HARD
    hints = ' '.join(f"{p.get('summary') or ''} {p.get('repair_hint') or ''}" for p in pulses.values())
    day = reset_day(now)
    if not HARD.search(hints) or data.get('mechanik') == day:
        return
    from config.celery import app
    data['mechanik'] = day
    try:
        app.send_task('news.tasks.mechanik_task', retry=False)
        log('mechanik', c['key'], 'mechanik', 'retried', f"{c['label']}: twardy błąd modelu, Mechanik szuka zamiennika.", now)
    except Exception:  # noqa: BLE001
        log('mechanik', c['key'], 'mechanik', 'failed', f"{c['label']}: nie udało się zlecić Mechanika.", now)


def retrigger(c, now, data, fuse_key, why):
    """Ponawia zadanie pętli. Wynik: pending, retried, retried-again, deferred, exhausted, impossible, failed.
    Pierwsze ponowienie (i ponowienie po 02:00) wstrzymuje alarm; gdy wynik nie przyszedł i trzeba ponawiać znowu,
    naprawa nie pomogła, więc alarm jest widoczny (retried-again, exhausted, impossible, failed)."""
    from config.celery import app
    from news import raport_petli, repairer
    if suppressed(fuse_key, now, data):
        return 'pending'
    entries = app.conf.beat_schedule
    beats = [b for b in c['beats'] if b in entries]
    if c['category'] in OWN_REPAIR:
        beats = [b for b in beats if entries[b]['task'] in repairer.SAFE_TASKS]
    if not beats or c['key'] in NO_RETRIGGER:
        return 'impossible'
    pulses = {b: raport_petli.pulse(b) for b in beats}
    if any(p.get('result') == 'error' and not known_transient(p) for p in pulses.values()):
        _ask_mechanik(c, pulses, data, now)
        return 'impossible'  # trwały błąd (klucz, konfiguracja, 402): decyzja właściciela
    wait = timedelta(hours=min(12, max(2, c['cadence_h'])))
    for b, p in pulses.items():
        started = _stamp(p.get('started_at'))
        if p.get('phase') == 'running' and started and now - started < timedelta(hours=3):
            suppress(data, fuse_key, now + timedelta(hours=1), PENDING_TEXT + ' (zadanie działa)')
            return 'pending'
        info = (data.get('last_beat') or {}).get(b) or {}
        last = _stamp(info.get('at'))
        if last and now - last < wait:
            if info.get('first'):  # wspólne zadanie kilku pętli: pierwsza próba wstrzymuje alarm każdej z nich
                suppress(data, fuse_key, last + wait, f'ponowiono {hhmm(last)}')
                return 'pending'
            return 'retried-again'  # powtórna próba w toku: poprzednia nie pomogła, alarm widoczny
    day = reset_day(now)
    counts = data.setdefault('beats', {})
    if max(counts.get(f'{day}|{b}', 0) for b in beats) >= MAX_RETRIGGERS:
        return 'exhausted'
    _ask_mechanik(c, pulses, data, now)
    if not _model_free([entries[b]['task'] for b in beats]):
        until = next_reset(now)
        if not suppressed(fuse_key, now, data):
            log('ponowienie', c['key'], why, 'skipped',
                f"{c['label']}: brak wolnego modelu albo tryb Dyrygenta; ponowienie po 02:00 bez alarmu.", now)
        suppress(data, fuse_key, until, 'ponowienie po 02:00')
        return 'deferred'
    sent = data.setdefault('_sent', {})  # w jednym biegu: tożsamość zadania -> wynik (bez podwójnego zlecenia)
    first = not any((_stamp(((data.get('last_beat') or {}).get(b) or {}).get('at')) or now - timedelta(days=2)) > now - timedelta(hours=24)
                    for b in beats)
    try:
        for b in beats:
            entry = entries[b]
            identity = json.dumps([entry['task'], list(entry.get('args', ())), entry.get('kwargs', {})], sort_keys=True)
            if sent.get(identity) == 'failed':
                raise RuntimeError('broker')
            if identity in sent:
                continue
            sent[identity] = 'failed'
            if entry['task'] in repairer.SAFE_TASKS:  # zatwierdzona ścieżka Naprawiacza (limity i dziennik „task”)
                repairer.retry_task(repairer.Run(now), b, entry)
            else:
                app.send_task(entry['task'], args=entry.get('args', ()), kwargs=entry.get('kwargs', {}),
                              **{**entry.get('options', {}), 'retry': False})
            sent[identity] = 'sent'
            counts[f'{day}|{b}'] = counts.get(f'{day}|{b}', 0) + 1
            data.setdefault('last_beat', {})[b] = {'at': now.isoformat(), 'first': first}
    except Exception:  # noqa: BLE001 - broker niedostępny: alarm
        log('ponowienie', c['key'], why, 'failed', f"{c['label']}: nie udało się ponowić zadania (broker).", now)
        return 'failed'
    if first:
        suppress(data, fuse_key, now + wait, f'ponowiono {hhmm(now)}')
    reasons = {'silent': 'cisza', 'green-empty': 'zielony puls bez wyniku', 'error': 'błąd przejściowy', 'consumer': 'odbiorca nie czyta'}
    log('ponowienie', c['key'], why, 'retried', f"{c['label']}: ponowiono zadanie ({', '.join(beats)}), powód: {reasons.get(why, why)}"
        + ('.' if first else '; poprzednie ponowienie nie dało wyniku.'), now)
    return 'retried' if first else 'retried-again'


def retry_errors(now, data):
    """(e) Pętle z przejściowym błędem zadania: ponowienie (ten sam limit 2 na dobę)."""
    from news import petle_bezpieczniki as fuses, raport_petli
    out = {}
    for c in fuses._active():
        pulses = [raport_petli.pulse(b) for b in c['beats']]
        if any(p.get('result') == 'error' and known_transient(p) for p in pulses):
            out[f"petle:error:{c['key']}"] = retrigger(c, now, data, f"petle:error:{c['key']}", 'error')
    return out


# --- (c) duplikaty i kolejka Seby ---------------------------------------------------------------------------------

def merge_duplicates(now):
    """Zostaje najnowszy (albo już przyjęty), pozostałe otwarte dostają rejected „duplikat #id”. Nigdy nie usuwa."""
    from news import petle_bezpieczniki as fuses
    from news.agent_models import AgentNote
    from news.raport_petli import OPEN
    recent = AgentNote.objects.filter(kind__in=('idea', 'experiment', 'finding'), created_at__gte=now - timedelta(days=14)).exclude(
        status__in=('rejected', 'denied'))
    merged = []
    for agent in set(recent.values_list('agent', flat=True)):
        rows = list(recent.filter(agent=agent).order_by('-created_at', '-pk')[:30])
        clusters = []
        for row in rows:
            home = next((cl for cl in clusters if any(SequenceMatcher(None, row.title.lower(), o.title.lower()).ratio() > fuses.DUPLICATE_RATIO
                                                      for o in cl)), None)
            (home.append(row) if home is not None else clusters.append([row]))
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            keeper = next((r for r in cluster if r.status not in OPEN), cluster[0])
            for row in cluster:
                if row.pk == keeper.pk or row.status not in OPEN:
                    continue
                if _set(row, 'rejected', 'duplikat', f'duplikat #{keeper.pk}', now, duplicate_of=keeper.pk):
                    log('duplikat', fuses._loop_for(agent), f'#{row.pk}', 'fixed',
                        f'Duplikat #{keeper.pk} odrzucony: #{row.pk} {row.title[:120]}', now)
                    merged.append(row.pk)
    return merged


def seba_queue(now, data):
    """Kolejka Seby > 48 h: najpierw ponowienie z autorem „local” (krytyk dowolnej firmy), po kolejnych 48 h decyzja progiem."""
    from news.agent_models import AgentNote, SebaReview
    from news import petle_bezpieczniki as fuses
    marks = data.setdefault('seba', {})
    out = []
    for review in SebaReview.objects.select_related('note').filter(status='queued', created_at__lt=now - timedelta(hours=fuses.SEBA_QUEUE_HOURS))[:BATCH]:
        key = str(review.pk)
        marked = _stamp(marks.get(key))
        if marked and now - marked < SEBA_WAIT:
            continue
        note = review.note
        if not marked:
            if note:
                scores = dict(note.scores or {})
                author = scores.get('author') if isinstance(scores.get('author'), dict) else {}
                if author.get('company') != 'local':
                    scores['author_before_auto'] = author
                    scores['author'] = {**author, 'company': 'local'}
                    AgentNote.objects.filter(pk=note.pk).update(scores=scores)
            SebaReview.objects.filter(pk=review.pk, status='queued').update(phase='critique', due_at=now, lease_until=None,
                                                                           lease_token='', last_error='Ponowienie z autorem local.')
            marks[key] = now.isoformat()
            log('seba', 'seba', f'#{review.pk}', 'retried', f'Seba: ponowienie oceny #{review.pk} z autorem local (kolejka > 48 h).', now)
            out.append((review.pk, 'requeued'))
            continue
        if note is None:
            status, reason = 'passed', 'Seba bez modelu 96 h: komentarz pominięty (decydują dowody).'
        elif note.score >= SPRINT_MIN:
            status, reason = 'passed', f'Seba bez modelu 96 h: wynik {note.score}/100, próg {SPRINT_MIN} (automatycznie).'
        else:
            status, reason = 'rejected', f'Seba bez modelu 96 h: wynik {note.score}/100 poniżej {SPRINT_MIN} (automatycznie).'
        if SebaReview.objects.filter(pk=review.pk, status='queued').update(status=status, lease_until=None, lease_token='',
                                                                          last_error=reason[:240]):
            log('seba', 'seba', f'#{review.pk}', 'fixed', reason, now)
            marks.pop(key, None)
            out.append((review.pk, status))
    return out


# --- (d) odbiorca i decyzje właściciela -------------------------------------------------------------------------

def approve_tickets(now):
    """Bilety S/M bez decyzji 48 h i bez zastrzeżeń Prawnika: zatwierdzone automatycznie. L zostaje w propozycjach."""
    from django.db import transaction
    from news import sprint
    from news.agent_models import BuildTicket
    verdicts = sprint._verdicts()
    out = []
    for ticket in BuildTicket.objects.select_related('note').filter(status='proposed', created_at__lt=now - TICKET_WAIT).order_by('created_at'):
        if ticket.effort == 'L' or (ticket.note and sprint._legal(ticket.note, ticket.title, verdicts)):
            continue
        with transaction.atomic():
            locked = BuildTicket.objects.select_for_update().filter(pk=ticket.pk, status='proposed').first()
            if not locked:
                continue
            sprint.decide(locked, 'approved', user=None, now=now)
        log('bilet', 'sprint', f'#{ticket.pk}', 'fixed', f'Bilet #{ticket.pk} zatwierdzony ({sprint.AUTO_DECISION}): {ticket.title[:160]}', now)
        out.append(ticket.pk)
    return out


def owner_waiting(now):
    """Co czeka na właściciela po naprawach: przypomnienie raz dziennie w Raporcie pętli (bez alarmów)."""
    from news.agent_models import AgentNote, BuildTicket
    from news.report_models import InstitutionalReport
    reports = list(InstitutionalReport.objects.filter(status='awaiting_approval', awaiting_since__lt=now - timedelta(hours=24))
                   .order_by('awaiting_since').values_list('pk', flat=True)[:10])
    large = list(BuildTicket.objects.filter(status='proposed', created_at__lt=now - TICKET_WAIT)
                 .order_by('created_at').values_list('pk', 'title', 'effort')[:10])
    costs = AgentNote.objects.filter(kind='request', status__in=('new', 'pending'), created_at__lt=now - timedelta(days=STALE_DAYS)).count()
    return {'reports': reports, 'tickets': [{'id': pk, 'title': t, 'effort': e} for pk, t, e in large], 'costs': costs}


# --- wejście dla bezpieczników ------------------------------------------------------------------------------------

def remedy(check, now):
    """Naprawa przed alarmem dla jednej kontroli Dyżurnego. Zwraca {klucz bezpiecznika: wynik naprawy}."""
    from news import petle_bezpieczniki as fuses, raport_petli
    data = load()
    out = {}
    try:
        if check == 'check_unused_outputs':
            settle_all(now, data=data)
            for f in fuses.unused_outputs(now):
                if f['key'].startswith('petle:green-empty:'):
                    out[f['key']] = retrigger(raport_petli.BY_KEY[f['loop']], now, data, f['key'], 'green-empty')
        elif check == 'check_silent_loops':
            for f in fuses.silent_loops(now):
                out[f['key']] = retrigger(raport_petli.BY_KEY[f['loop']], now, data, f['key'], 'silent')
            out.update(retry_errors(now, data))
        elif check == 'check_quality':
            merge_duplicates(now)
            seba_queue(now, data)
        elif check == 'check_consumers':
            settle_all(now, owner_sla=True, data=data)
            for f in fuses.consumers(now):
                c = raport_petli.BY_KEY.get(f['loop'])
                reader = raport_petli.BY_KEY.get((f['details'] or {}).get('reader', ''))
                if c and reader and c['consumer'].startswith('agent:'):
                    out[f['key']] = retrigger(reader, now, data, f['key'], 'consumer')
        elif check == 'check_deadlines':
            approve_tickets(now)
    except Exception as error:  # noqa: BLE001 - nieudana naprawa = alarm, nie zatrzymanie Dyżurnego
        from news.admin_telemetry import safe_error
        log('awaria', 'naprawy', check, 'failed', f'Naprawa automatyczna ({check}) nie powiodła się: {safe_error(error)}', now)
    save(data, now)
    return out
