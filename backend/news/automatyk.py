"""Automatyk (właściciel 5.10): ekspert od automatyzacji i pętli agentów obu portali (spin.clinic i przeszłość.today).

Raz dziennie:
1. Bez AI sprawdza każdą pętlę (LOOPS) na żywych danych rejestru agentów: kroki wyłączone, z błędem, spóźnione,
   bez harmonogramu; pętle bez strażnika; propozycje agentów, które czekają na decyzję dłużej niż tydzień.
2. Model ekspert proponuje usprawnienia (harmonogram, kolejność, strażnik, scalenie, próg, monitoring...) z gotowym zleceniem;
   drugi model innej firmy odrzuca ogólniki i propozycje bez oparcia w danych.
3. Zapisuje raport w panelu, trzy najważniejsze usprawnienia jako pomysły do decyzji (krytykuje je też Seba).
Automatyk proponuje; zmiany wprowadzają Claude i Codex po zgodzie właściciela (tak jak w każdej pętli)."""
from datetime import timedelta

from django.utils import timezone

from news import agents_common as common
from news.agent_models import AgentNote

# Pętle obu portali: kroki w kolejności przepływu; id = klucz w rejestrze agentów (None = człowiek lub poza harmonogramem);
# g = strażnik rzetelności, legalności albo czytelności.
LOOPS = [
    ('spin.clinic', 'Diagnozy', 'co 10 min, 7-22', [('Zbieracz X', 'political_poll_task', 0), ('Strażnik wpisów', 'screen', 1),
        ('Dr. Spin z Konsylium', 'dr-spin', 0), ('Miernik', 'plain-meter', 1), ('Strażnik rzetelności', 'plain-guard', 1),
        ('Redaktor prostoty', 'plain-editor', 0), ('Inkwizytor', 'inquisitor', 1), ('Recenzent', 'recenzent', 1),
        ('Publikacja X', 'x-publish', 0), ('Publikacja FB i IG', 'social', 0)]),
    ('spin.clinic', 'Spinki', 'codziennie i co 20 min', [('Wątek Dr. Spina', 'spin-thread', 0), ('Spinka narracji', 'narrative-threads', 0),
        ('Sygnały i narracje', 'signal-threads', 0), ('Kontrola spinek', 'thread-review', 1), ('Czytelnicy oceniają', None, 0),
        ('Recenzent', 'recenzent', 1)]),
    ('spin.clinic', 'Wywiad dnia', '2 razy dziennie', [('Kandydaci', 'interview-candidates', 0), ('Głosowanie czytelników', None, 0),
        ('Wybór wywiadu', 'interview-pick', 0), ('Wywiad dnia', 'interviews', 0), ('Recenzent', 'recenzent', 1)]),
    ('spin.clinic', 'Przekaz dnia', '5 razy dziennie', [('Zbieracz X', 'political_poll_task', 0), ('Przekaz dnia', 'messages', 0),
        ('Recenzent', 'recenzent', 1), ('Spinka narracji', 'narrative-threads', 0)]),
    ('spin.clinic', 'Konsylium', 'co noc i co tydzień', [('Pielgrzym', 'pilgrim', 0), ('Ekspert AI', 'ekspert-ai', 0),
        ('Rekruter', 'recruiter', 0), ('Audytor', 'auditor', 1), ('Mechanik', 'mechanik', 0), ('Karta Konsylium', 'council', 1)]),
    ('spin.clinic', 'Rozwój serwisu', 'w wolnym oknie modeli', [('Strateg', 'strateg', 0), ('Pielgrzym', 'pilgrim', 0),
        ('Seba', 'seba', 1), ('Właściciel', None, 1), ('Claude i Codex', None, 0), ('Projektant', 'projektant', 1), ('Recenzent', 'recenzent', 1)]),
    ('spin.clinic', 'Niezawodność', 'co 5 min', [('Dyżurny', 'duty', 1), ('Naprawiacz', 'repairer', 0), ('Mechanik', 'mechanik', 0),
        ('Kontrola dostępności', 'schedule-health', 1)]),
    ('spin.clinic', 'Konta polityków', 'codziennie', [('Strażnik kont', 'warden', 1), ('Drugi klucz', 'second-key', 1), ('Agent KRS', 'krs', 0)]),
    ('spin.clinic', 'Raporty', 'w nocy i co tydzień', [('Raportysta', 'raportysta', 0), ('Seba', 'seba', 1), ('Raport tygodnia', 'weekly', 0)]),
    ('przeszłość.today', 'Pracownia OSINT', 'co tydzień', [('Kartograf, Zwiadowca, Wynalazca, Technolog', 'pracownia-osint', 0),
        ('Prawnik', 'pracownia-osint', 1), ('Architekt', 'pracownia-osint', 0), ('Claude i Codex', None, 0), ('Recenzent', 'recenzent', 1),
        ('Projektant', 'projektant', 1), ('Dziennikarz testowy i Kontroler', 'pracownia-osint', 1), ('Właściciel: wdrożenie', None, 1)]),
    ('przeszłość.today', 'Tematy dnia', 'codziennie 5:10', [('Zbieracze Sejmu i X', 'political_poll_task', 0),
        ('Tematy dnia', 'przeszlosc-topics', 0), ('Dziennikarz testowy', 'pracownia-osint', 1)]),
    ('przeszłość.today', 'Dane', 'codziennie', [('Zbieracz Sejmu i ELI', 'import_official_task', 0), ('Agent KRS', 'krs', 0),
        ('Kontroler danych', 'pracownia-osint', 1), ('Zwiadowca', 'pracownia-osint', 0), ('Prawnik', 'pracownia-osint', 1)]),
]
DAY = timedelta(hours=20)
PROPOSERS = ('strateg', 'pielgrzym', 'ekspert', 'projektant', 'kartograf', 'zwiadowca', 'wynalazca', 'technolog', 'architekt', 'automatyk')
CONTEXT = [
    'spin.clinic: Klinika spinu - automatyczne diagnozy wpisów polityków (Dr. Spin z Konsylium 4 modeli), przekazy dnia obu stron, '
    'wywiad dnia, spinki (łańcuchy materiałów z połączeniami ocenianymi przez czytelników), publikacja na X, FB, IG.',
    'przeszłość.today: narzędzie OSINT dla dziennikarzy (tematy jako drzewa powiązań: osoby, KRS, Sejm, wpisy, media), '
    'rozwijane przez Pracownię OSINT: badacze -> Prawnik -> Architekt -> budowa -> strażnicy -> wdrożenie.',
    'Zasady: diagnozy nigdy nie zmieniają sensu (tylko forma), ta sama miara dla wszystkich stron, tylko dane publiczne i legalne, '
    'darmowe modele w dziennych limitach (koszt najpierw), wdrożenie wyłącznie po zgodzie właściciela, agenci tylko proponują.',
    'Cel: pełna automatyzacja z szeregiem strażników rzetelności i czytelności; właściciel dba tylko o odbiór u ludzi.',
]

TEXT = {'type': 'string'}
INT = {'type': 'integer'}
ISSUE = {'type': 'object', 'properties': {'loop': TEXT, 'step': TEXT, 'problem': TEXT,
         'severity': {'type': 'string', 'enum': ['wysoki', 'średni', 'niski']}}, 'required': ['loop', 'problem', 'severity']}
FIX = {'type': 'object', 'properties': {
    'loop': TEXT, 'change': TEXT, 'why': TEXT, 'evidence': TEXT,
    'kind': {'type': 'string', 'enum': ['harmonogram', 'kolejność', 'strażnik', 'scalenie', 'nowy krok', 'usunięcie', 'próg', 'monitoring', 'koszt']},
    'effort': {'type': 'string', 'enum': ['S', 'M', 'L']}, 'impact': INT, 'risk': TEXT, 'brief': TEXT},
    'required': ['loop', 'change', 'why', 'evidence', 'kind', 'effort', 'impact', 'brief']}
SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'issues': {'type': 'array', 'items': ISSUE},
          'fixes': {'type': 'array', 'items': FIX}}, 'required': ['summary', 'issues', 'fixes']}
CHECK = {'type': 'object', 'properties': {'remove': {'type': 'array', 'items': INT}, 'reason': TEXT}, 'required': ['remove', 'reason']}
PROMPT = ('Jesteś Automatykiem: ekspertem od automatyzacji, pętli zwrotnych i niezawodności systemów wieloagentowych '
          '(przepływ, wąskie gardła, kolejki, ponowienia, idempotencja, strażnicy jakości, obserwowalność, koszt). Znasz kontekst '
          'obu portali (context). Masz pętle z żywym stanem każdego kroku (loops: włączony, wynik, ostatnie uruchomienie, harmonogram, '
          'podsumowanie), automatyczne uwagi (checks), przepływ propozycji agentów (proposals) i swoje wcześniejsze zalecenia (previous). '
          'Wypisz problemy (issues) i do 8 usprawnień (fixes) od najważniejszego: co zmienić, dlaczego, dowód z danych (evidence), rodzaj, '
          'wysiłek, wpływ 1-10, ryzyko i brief - gotowe zlecenie dla programisty. Szukaj: pętli bez strażnika, kroków, które się dublują '
          'albo czekają na siebie, złej kolejności (np. publikacja przed kontrolą), harmonogramów kolidujących o limity modeli, propozycji, '
          'które nikt nie zamyka, brakującego sprzężenia zwrotnego (wynik pętli nie wraca do jej początku). Nie powtarzaj previous '
          'przyjętych lub odrzuconych. Szanuj zasady z context.')
PROMPT_CHECK = ('Sprawdź zalecenia kolegi. W remove podaj numery (od 0) zaleceń bez oparcia w loops/checks/proposals, ogólnikowych, '
                'łamiących zasady z context (np. edycja sensu diagnoz, płatne modele, wdrożenie bez zgody) albo powtarzających previous.')

_used = {'author': None, 'checker': None}


def health():
    """Żywy stan kroków z rejestru (bez AI)."""
    from news.agent_registry import snapshot
    rows = {}
    for row in snapshot():
        identity = row['id'].rsplit(':', 1)[0]
        rows.setdefault(identity, row)
    return rows


def loops_state(rows=None):
    rows = rows if rows is not None else health()
    out, checks = [], []
    for portal, name, rhythm, steps in LOOPS:
        items = []
        for label, ident, guard in steps:
            row = rows.get(ident) if ident else None
            state = {'step': label, 'guard': bool(guard), 'human': ident is None}
            if row:
                last = row.get('last_run')
                state.update(enabled=row['enabled'], result=row['result'], schedule=row['schedule'], summary=str(row.get('summary', ''))[:160],
                             last_run=last.isoformat(timespec='minutes') if hasattr(last, 'isoformat') else last)
                if not row['enabled']:
                    checks.append(f'{portal} · {name}: krok „{label}” jest wyłączony - pętla stoi w tym miejscu.')
                elif row['result'] == 'error':
                    checks.append(f'{portal} · {name}: krok „{label}” kończy się błędem ({state["summary"][:80]}).')
                elif row['result'] == 'warn' and row.get('last_run'):
                    checks.append(f'{portal} · {name}: krok „{label}” jest spóźniony albo pominięty ({state["summary"][:80]}).')
                elif row['schedule'] == 'wkrótce':
                    checks.append(f'{portal} · {name}: krok „{label}” nie ma harmonogramu.')
            elif ident:
                checks.append(f'{portal} · {name}: krok „{label}” nie istnieje w rejestrze agentów ({ident}).')
            items.append(state)
        if not any(s['guard'] for s in items):
            checks.append(f'{portal} · {name}: pętla bez strażnika rzetelności lub czytelności.')
        out.append({'portal': portal, 'loop': name, 'rhythm': rhythm, 'steps': items})
    return out, checks


def proposals():
    """Przepływ propozycji agentów: ile powstaje, ile czeka na decyzję dłużej niż tydzień (zatkana pętla)."""
    week = timezone.now() - timedelta(days=7)
    data = {}
    for agent in PROPOSERS:
        rows = AgentNote.objects.filter(agent=agent, kind__in=['idea', 'finding', 'experiment'])
        new = rows.filter(created_at__gte=week).count()
        waiting = rows.filter(status='new', created_at__lt=week).count()
        decided = rows.filter(status__in=['accepted', 'done', 'rejected', 'approved', 'denied'], created_at__gte=week - timedelta(days=21)).count()
        if new or waiting or decided:
            data[agent] = {'nowe_7_dni': new, 'czekają_ponad_tydzień': waiting, 'zdecydowane_4_tyg': decided}
    return data


def previous():
    rows = []
    for note in AgentNote.objects.filter(agent='automatyk', kind='idea')[:30]:
        rows.append({'change': (note.scores or {}).get('change', note.title), 'status': note.status})
    return rows


def step(force=False):
    last = AgentNote.objects.filter(agent='automatyk', kind='audit').first()
    if last and not force and timezone.now() - last.created_at < DAY:
        return last
    loops, checks = loops_state()
    flow = proposals()
    for agent, d in flow.items():
        if d['czekają_ponad_tydzień'] >= 5:
            checks.append(f'Propozycje agenta {agent}: {d["czekają_ponad_tydzień"]} czeka na decyzję ponad tydzień - pętla rozwoju się zatyka.')
    data = {'context': CONTEXT, 'loops': loops, 'checks': checks, 'proposals': flow, 'previous': previous()}
    answer, author = common.ask_any(PROMPT, data, SCHEMA, force)
    _used['author'] = author
    fixes = [f for f in answer.get('fixes', []) if isinstance(f, dict) and f.get('change')][:8]
    reason = ''
    if fixes:
        verdict, checker = common.ask_any(PROMPT_CHECK, {**data, 'fixes': fixes}, CHECK, force, exclude=(author,))
        _used['checker'] = checker
        drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
        fixes, reason = [f for n, f in enumerate(fixes) if n not in drop], verdict.get('reason', '')
    fixes.sort(key=lambda f: -int(f.get('impact') or 0))
    issues = [i for i in answer.get('issues', []) if isinstance(i, dict)][:12]
    result = {'summary': answer.get('summary', ''), 'issues': issues, 'fixes': fixes, 'checks': checks, 'check': reason,
              'authors': [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]}
    note = AgentNote.objects.create(agent='automatyk', kind='audit', status='new' if fixes or checks else 'done',
        title=f'Pętle: {len(checks)} uwag, {len(fixes)} usprawnień ({timezone.localdate():%d.%m.%Y})', body=readable(result), scores=result)
    for f in fixes[:3]:
        AgentNote.objects.create(agent='automatyk', kind='idea', status='new', title=f"Pętla {f['loop']}: {f['change']}"[:240],
            body=f"{f['why']}\nDowód: {f['evidence']}\nZlecenie: {f['brief']}", score=max(0, min(100, int(f.get('impact') or 0) * 10)),
            scores={'audit': note.pk, **f})
    if any(i.get('severity') == 'wysoki' for i in issues) or any('wyłączony' in c or 'błędem' in c for c in checks):
        common.notify(note)
    return note


def readable(r):
    lines = [r.get('summary', ''), '']
    if r.get('checks'):
        lines += ['Sprawdzenia automatyczne:'] + [f'- {c}' for c in r['checks']] + ['']
    order = {'wysoki': 0, 'średni': 1, 'niski': 2}
    for i in sorted(r.get('issues', []), key=lambda i: order.get(i.get('severity'), 3)):
        lines.append(f"[{i['severity']}] {i['loop']}{' · ' + i['step'] if i.get('step') else ''}: {i['problem']}")
    lines.append('')
    for n, f in enumerate(r.get('fixes', []), 1):
        lines += [f"{n}. {f['loop']}: {f['change']} [{f['kind']}, wysiłek {f['effort']}, wpływ {f['impact']}/10]",
                  f"   Dlaczego: {f['why']} Dowód: {f['evidence']}", f"   Zlecenie: {f['brief']}"]
    if r.get('check'):
        lines += ['', f"Sprawdzenie drugiego eksperta: {r['check']}"]
    return chr(10).join(lines).strip()
