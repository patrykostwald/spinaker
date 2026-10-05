"""Sprint tygodnia (audyt pętli 5.3): przyjęty pomysł agenta zawsze staje się biletem budowy z terminem.

W poniedziałek o 6:00 intake() zbiera kandydatów z dziennika agentów, usuwa duplikaty, liczy ranking i tworzy do 8 biletów
`proposed`. W pozostałe dni dopełnia kolejkę, gdy otwartych biletów jest mniej niż 3. Właściciel jednym kliknięciem
zatwierdza („Buduj”) albo odkłada („Nie teraz”); `manage.py sprint_zlecenia` wypisuje zatwierdzone bilety jako zlecenia
dla Claude lub Codexa i zamyka je po commicie (notatka źródłowa dostaje status `done`, więc agent widzi to w `previous`).
Bez wywołań sieciowych i bez modeli AI."""
from datetime import date, timedelta
from difflib import SequenceMatcher

from django.db import transaction
from django.utils import timezone

from news.agent_models import AgentNote, BuildTicket

MAX_PROPOSED = 8
MIN_OPEN = 3
SIMILAR = .85
NEW_MIN_SCORE = 80
SOURCES = ('architekt', 'wynalazca', 'strateg', 'pielgrzym', 'automatyk')
SKIP_AGENTS = ('opiekun', 'dyrygent')  # naprawy Opiekunów mają własną pętlę (Naprawiacz); plan Dyrygenta to nie pomysł
KINDS = ('idea', 'experiment', 'finding')
EFFORT_DAYS = {'S': 3, 'M': 7, 'L': 14}
EFFORT_BONUS = {'S': 3, 'M': 2, 'L': 1}  # wartość/wysiłek: wartość 0-10 razy premia za mały wysiłek
DROP_PAUSE = timedelta(days=28)  # „Nie teraz” właściciela: pomysł wraca najwcześniej po 4 tygodniach
LOOKBACK = timedelta(days=60)


def _norm(text):
    text = (text or '').lower()
    for prefix in ('przeszłość.today:', 'pętla '):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return ' '.join(text.split())


def similar(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= SIMILAR


def _effort(value):
    value = str(value or 'M').strip().upper()[:1]
    return value if value in EFFORT_DAYS else 'M'


def executor(effort, today=None):
    from news.dyrygent import CODEX_BACK
    today = today or timezone.localdate()
    return 'codex' if today >= date.fromisoformat(CODEX_BACK) and effort in ('S', 'M') else 'claude'


def _verdicts():
    """Werdykty Prawnika: numer notatki -> lista (opis propozycji, werdykt); najnowsza ocena wygrywa."""
    out = {}
    for review in AgentNote.objects.filter(agent='prawnik', kind='review').order_by('created_at', 'pk')[:200]:
        for row in (review.scores or {}).get('verdicts', []):
            if isinstance(row, dict) and isinstance(row.get('note'), int):
                out.setdefault(row['note'], {})[row.get('what', '')] = row.get('verdict', '')
    return out


def _legal(note, title, verdicts):
    """'niedozwolone', 'warunkowo' albo '' (dozwolone lub brak oceny)."""
    rows = verdicts.get(note.pk, {})
    own = (note.scores or {}).get('verdict') or (note.scores or {}).get('legal')
    found = [v for what, v in rows.items() if _norm(title) and _norm(title) in _norm(what)] or list(rows.values())
    if isinstance(own, str):
        found.append(own)
    if 'niedozwolone' in found:
        return 'niedozwolone'
    if 'warunkowo' in found or 'do konsultacji' in found:
        return 'warunkowo'
    return ''


def _items(note):
    """Pozycje do budowy z notatki: ustalenie z listą pomysłów (Wynalazca) daje kilka, reszta jedną."""
    data = note.scores or {}
    ideas = [i for i in data.get('ideas', []) if isinstance(i, dict) and i.get('title')] if note.kind == 'finding' else []
    if ideas:
        for idea in ideas:
            value = int(idea.get('wow') or idea.get('value') or 0)
            yield {'title': str(idea['title'])[:240], 'score': max(0, min(100, value * 10)), 'value': value,
                   'effort': _effort(idea.get('effort') or {'darmowe': 'M', 'Pro': 'L'}.get(idea.get('tier'), 'M')),
                   'brief': '\n'.join(filter(None, [idea.get('what', ''), idea.get('example') and f"Przykład: {idea['example']}",
                                                    idea.get('data_used') and 'Dane: ' + ', '.join(idea['data_used'])])),
                   'acceptance': list(idea.get('acceptance') or []), 'multi': True}
        return
    value = data.get('value', data.get('impact'))
    try:
        value = int(value) if value is not None else round(note.score / 10)
    except (TypeError, ValueError):
        value = round(note.score / 10)
    yield {'title': note.title, 'score': note.score, 'value': max(0, min(10, value)), 'effort': _effort(data.get('effort')),
           'brief': str(data.get('brief') or note.body)[:4000], 'acceptance': [str(a) for a in data.get('acceptance') or []][:12],
           'multi': False}


def rank(score, value, effort, accepted, waited_days, legal):
    return round(.4 * score + (25 if accepted else 0) + value * EFFORT_BONUS[effort] + min(10, 2 * (waited_days // 7))
                 - (30 if legal == 'warunkowo' else 0), 1)


def candidates(now=None):
    """Kandydaci do sprintu, od najwyższego rankingu, bez duplikatów (także wobec otwartych i zrobionych biletów)."""
    from news.seba import can_show
    now = now or timezone.now()
    rows = AgentNote.objects.filter(kind__in=KINDS, created_at__gte=now - LOOKBACK).exclude(agent__in=SKIP_AGENTS)
    rows = rows.filter(status__in=('accepted', 'approved')) | rows.filter(status='new', agent__in=SOURCES)
    taken = list(BuildTicket.objects.select_related('note').filter(status__in=BuildTicket.OPEN + ('done',)))
    paused = list(BuildTicket.objects.select_related('note').filter(status='dropped', decided_by__isnull=False,
                                                                      decided_at__gte=now - DROP_PAUSE))
    blocked_titles = [t.title for t in taken] + [t.title for t in paused]
    blocked_notes = {t.note_id for t in taken if t.note and t.note.kind != 'finding'} | {t.note_id for t in paused if t.note and t.note.kind != 'finding'}
    verdicts = _verdicts()
    out = []
    for note in rows.order_by('-created_at', '-pk')[:400]:
        if note.pk in blocked_notes:
            continue
        accepted = note.status in ('accepted', 'approved')
        if not accepted and not can_show(note):
            continue  # nowe propozycje tylko po pozytywnej ocenie Seby
        built = set((note.scores or {}).get('zbudowane', []))
        for item in _items(note):
            if item['title'] in built or (not accepted and item['score'] < NEW_MIN_SCORE):
                continue
            legal = _legal(note, item['title'], verdicts)
            if legal == 'niedozwolone':
                continue
            waited = max(0, (now - note.created_at).days)
            out.append({**item, 'note': note, 'legal': legal, 'accepted': accepted,
                        'rank': rank(item['score'], item['value'], item['effort'], accepted, waited, legal)})
    out.sort(key=lambda c: (-c['rank'], -c['note'].pk))
    unique = []
    for cand in out:
        if any(similar(cand['title'], t) for t in blocked_titles) or any(similar(cand['title'], u['title']) for u in unique):
            continue
        unique.append(cand)
    return unique


def open_count():
    return BuildTicket.objects.filter(status__in=BuildTicket.OPEN).count()


def expire(now=None):
    """Poniedziałek: propozycje bez decyzji dłużej niż tydzień spadają (wrócą z premią za czekanie, jeśli nadal ważne)."""
    now = now or timezone.now()
    return BuildTicket.objects.filter(status='proposed', created_at__lt=now - timedelta(days=6)).update(
        status='dropped', decided_at=now)


@transaction.atomic
def intake(now=None, weekly=None):
    """Tworzy do 8 biletów `proposed`. weekly=None: poniedziałek pełny przegląd, inne dni dopełnienie przy < 3 otwartych."""
    now = now or timezone.now()
    local = timezone.localtime(now)
    weekly = local.weekday() == 0 if weekly is None else weekly
    expired = expire(now) if weekly else 0
    if not weekly and open_count() >= MIN_OPEN:
        return {'created': [], 'expired': 0, 'mode': 'pełna kolejka'}
    room = MAX_PROPOSED - BuildTicket.objects.filter(status='proposed').count()
    created = []
    for cand in candidates(now)[:max(0, room)]:
        created.append(BuildTicket.objects.create(
            note=cand['note'], title=cand['title'], rank=cand['rank'], brief=cand['brief'], acceptance=cand['acceptance'],
            effort=cand['effort'], executor=executor(cand['effort'], local.date()), status='proposed',
            due_date=local.date() + timedelta(days=7), created_at=now))
    return {'created': [t.pk for t in created], 'expired': expired, 'mode': 'tydzień' if weekly else 'dopełnienie'}


def decide(ticket, decision, user=None, now=None):
    """Decyzja właściciela: approved (termin według wysiłku) albo dropped."""
    now = now or timezone.now()
    ticket.status, ticket.decided_by, ticket.decided_at = decision, user, now
    if decision == 'approved':
        ticket.due_date = timezone.localtime(now).date() + timedelta(days=EFFORT_DAYS.get(ticket.effort, 7))
        ticket.executor = executor(ticket.effort, timezone.localtime(now).date())
    ticket.save(update_fields=['status', 'decided_by', 'decided_at', 'due_date', 'executor'])
    return ticket


def close(ticket, commit, now=None):
    """Bilet zrobiony: zapis commita i sprzężenie zwrotne do notatki źródłowej (agent widzi `done` w previous)."""
    now = now or timezone.now()
    with transaction.atomic():
        ticket.status, ticket.commit, ticket.done_at = 'done', commit[:64], now
        ticket.save(update_fields=['status', 'commit', 'done_at'])
        note = ticket.note
        if note:
            data = dict(note.scores or {})
            if note.kind == 'finding' and data.get('ideas'):
                data['zbudowane'] = sorted(set(data.get('zbudowane', [])) | {ticket.title})
                titles = {i.get('title') for i in data['ideas'] if isinstance(i, dict)}
                note.scores = data
                fields = ['scores']
                if titles <= set(data['zbudowane']):
                    note.status = 'done'
                    fields.append('status')
                note.save(update_fields=fields)
            else:
                note.status = 'done'
                note.save(update_fields=['status'])
    return ticket


def row(ticket):
    return {'id': ticket.pk, 'title': ticket.title, 'rank': ticket.rank, 'effort': ticket.effort, 'executor': ticket.executor,
            'status': ticket.status, 'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
            'agent': ticket.note.agent if ticket.note else '', 'note': ticket.note_id, 'brief': ticket.brief,
            'acceptance': ticket.acceptance, 'commit': ticket.commit,
            'created_at': ticket.created_at.isoformat(), 'decided_at': ticket.decided_at.isoformat() if ticket.decided_at else None,
            'done_at': ticket.done_at.isoformat() if ticket.done_at else None}


def brief(ticket):
    """Zlecenie gotowe do wklejenia (format zleceń Codexa: cel, dane, kryteria odbioru)."""
    lines = [f'Zlecenie #{ticket.pk} ({ticket.executor}, wysiłek {ticket.effort}, termin {ticket.due_date:%d.%m.%Y})'
             if ticket.due_date else f'Zlecenie #{ticket.pk} ({ticket.executor}, wysiłek {ticket.effort})',
             f'Cel: {ticket.title}']
    if ticket.note:
        lines.append(f'Źródło: notatka #{ticket.note_id} ({ticket.note.agent}/{ticket.note.kind})')
    lines += ['Zakres:', ticket.brief.strip() or '-']
    if ticket.acceptance:
        lines += ['Kryteria odbioru:'] + [f'- {a}' for a in ticket.acceptance]
    lines.append(f'Po commicie: python manage.py sprint_zlecenia --zrobione {ticket.pk} --commit <sha>')
    return '\n'.join(lines)
