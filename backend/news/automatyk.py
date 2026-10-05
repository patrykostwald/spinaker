"""Automatyk (właściciel 5.10): ekspert od automatyzacji i pętli agentów obu portali (spin.clinic i przeszłość.today).

Raz dziennie:
1. Bez AI sprawdza każdą pętlę (LOOPS) na żywych danych rejestru agentów: kroki wyłączone, z błędem, spóźnione,
   bez harmonogramu; pętle bez strażnika; propozycje agentów, które czekają na decyzję dłużej niż tydzień.
2. Model ekspert proponuje usprawnienia (harmonogram, kolejność, strażnik, scalenie, próg, monitoring...) z gotowym zleceniem;
   drugi model innej firmy odrzuca ogólniki i propozycje bez oparcia w danych.
3. Zapisuje raport w panelu, trzy najważniejsze usprawnienia jako pomysły do decyzji (krytykuje je też Seba).
4. W wolnym czasie (raz w tygodniu, po codziennym przeglądzie) uczy się najnowszej wiedzy o automatyzacji i agentach AI
   z uznanych źródeł (LEARN_FEEDS); lekcje ze źródłem, sprawdzone przez drugi model, trafiają do jego codziennego przeglądu.
Automatyk proponuje; zmiany wprowadzają Claude i Codex po zgodzie właściciela (tak jak w każdej pętli)."""
from datetime import timedelta

from django.utils import timezone

from news import agents_common as common, council_registry as registry
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
        ('Seba', 'seba', 1), ('Właściciel', 'owner-decisions', 1), ('Claude i Codex', None, 0), ('Projektant', 'projektant', 1), ('Recenzent', 'recenzent', 1)]),
    ('spin.clinic', 'Niezawodność', 'co 5 min', [('Dyżurny', 'duty', 1), ('Naprawiacz', 'repairer', 0), ('Mechanik', 'mechanik', 0),
        ('Kontrola dostępności', 'schedule-health', 1)]),
    ('spin.clinic', 'Konta polityków', 'codziennie', [('Strażnik kont', 'warden', 1), ('Drugi klucz', 'second-key', 1), ('Agent KRS', 'krs', 0)]),
    ('spin.clinic', 'Raporty', 'w nocy i co tydzień', [('Raportysta', 'raportysta', 0), ('Seba', 'seba', 1), ('Raport tygodnia', 'weekly', 0)]),
    ('oba portale', 'Research', 'codziennie 3:20', [('Badacz: odkrywa źródła', 'badacz', 0), ('Drugi model: ocena jakości', 'badacz', 1),
        ('Automatyk, Projektant, Pracownia: czytają', 'automatyk', 0), ('Uśpienie martwych źródeł', 'badacz', 1)]),
    ('oba portale', 'Design', 'każda zmiana i co tydzień', [('Projektant: wiedza i przewodnik', 'projektant', 0), ('Claude: projekt', None, 0),
        ('Panel designu: UX, laik, dostępność', None, 1), ('Claude: poprawki i pomiar', None, 0), ('Projektant: przegląd stron', 'projektant', 1),
        ('Recenzent: teksty', 'recenzent', 1), ('Właściciel: odbiór', 'owner-decisions', 1)]),
    ('przeszłość.today', 'Pracownia OSINT', 'co tydzień', [('Kartograf, Zwiadowca, Wynalazca, Technolog', 'pracownia-osint', 0),
        ('Prawnik', 'pracownia-osint', 1), ('Architekt', 'pracownia-osint', 0), ('Claude i Codex', None, 0), ('Recenzent', 'recenzent', 1),
        ('Projektant', 'projektant', 1), ('Dziennikarz testowy i Kontroler', 'pracownia-osint', 1), ('Właściciel: wdrożenie', 'owner-decisions', 1)]),
    ('przeszłość.today', 'Tematy dnia', 'codziennie 5:10', [('Zbieracze Sejmu i X', 'political_poll_task', 0),
        ('Tematy dnia', 'przeszlosc-topics', 0), ('Dziennikarz testowy', 'pracownia-osint', 1)]),
    ('przeszłość.today', 'Dane', 'codziennie', [('Zbieracz Sejmu i ELI', 'import_official_task', 0), ('Agent KRS', 'krs', 0),
        ('Kontroler danych', 'pracownia-osint', 1), ('Zwiadowca', 'pracownia-osint', 0), ('Prawnik', 'pracownia-osint', 1)]),
]
DAY = timedelta(hours=20)
WEEK = timedelta(days=6)
LEARN_FEEDS = {
    'Anthropic (agenci i narzędzia)': 'https://www.anthropic.com/news/rss.xml',
    'LangChain (agenci, orkiestracja)': 'https://blog.langchain.dev/rss/',
    'n8n (automatyzacja przepływów)': 'https://blog.n8n.io/rss/',
    'Temporal (niezawodne przepływy)': 'https://temporal.io/blog/rss.xml',
    'Celery (wydania)': 'https://github.com/celery/celery/releases.atom',
    'Simon Willison (agenci w praktyce)': 'https://simonwillison.net/atom/everything/',
    'Hamel Husain (ewaluacja LLM)': 'https://hamel.dev/index.xml',
    'Eugene Yan (systemy z LLM)': 'https://eugeneyan.com/rss/',
    'Martin Fowler (architektura)': 'https://martinfowler.com/feed.atom',
    'Google SRE i niezawodność': 'https://sre.google/feed.xml',
}
# Szeroki research (właściciel 5.10): gdy podstawowe źródła nie mają nic nowego, Automatyk idzie dalej - co tydzień kolejna porcja,
# aż przejdzie wszystkie, potem od początku. Tylko publiczne kanały RSS/Atom (bez logowania i bez scrapowania).
WIDE_FEEDS = {
    'arXiv: systemy wieloagentowe': 'https://export.arxiv.org/rss/cs.MA',
    'arXiv: sztuczna inteligencja': 'https://export.arxiv.org/rss/cs.AI',
    'arXiv: inżynieria oprogramowania': 'https://export.arxiv.org/rss/cs.SE',
    'Hacker News: agenci AI': 'https://hnrss.org/newest?q=AI+agents&points=50',
    'Hacker News: automatyzacja': 'https://hnrss.org/newest?q=automation&points=50',
    'Reddit r/LocalLLaMA': 'https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week',
    'Reddit r/MachineLearning': 'https://www.reddit.com/r/MachineLearning/top/.rss?t=week',
    'OpenAI': 'https://openai.com/news/rss.xml',
    'Google DeepMind': 'https://deepmind.google/blog/rss.xml',
    'Microsoft Research': 'https://www.microsoft.com/en-us/research/feed/',
    'Hugging Face': 'https://huggingface.co/blog/feed.xml',
    'Latent Space': 'https://www.latent.space/feed',
    'InfoQ: AI i dane': 'https://feed.infoq.com/ai-ml-data-eng/',
    'Prefect': 'https://www.prefect.io/blog/rss.xml',
    'Dagster': 'https://dagster.io/rss.xml',
    'Apache Airflow (wydania)': 'https://github.com/apache/airflow/releases.atom',
    'CrewAI (wydania)': 'https://github.com/crewAIInc/crewAI/releases.atom',
    'AutoGen (wydania)': 'https://github.com/microsoft/autogen/releases.atom',
    'LangGraph (wydania)': 'https://github.com/langchain-ai/langgraph/releases.atom',
    'LlamaIndex': 'https://www.llamaindex.ai/blog/feed',
    'Chip Huyen': 'https://huyenchip.com/feed.xml',
    'Lilian Weng': 'https://lilianweng.github.io/index.xml',
}
WIDE_BATCH = 6
FRESH_MIN = 5
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
          'które nikt nie zamyka, brakującego sprzężenia zwrotnego (wynik pętli nie wraca do jej początku). Korzystaj ze swojej wiedzy '
          '(knowledge: lekcje z najnowszych źródeł o automatyzacji), gdy pasuje. Nie powtarzaj previous '
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
    rows[OWNER] = owner_row()
    return rows


OWNER = 'owner-decisions'


def owner_row(now=None):
    """Krok „Właściciel” jako puls (audyt 5.10, P6): ostatnia decyzja w panelu; „warn”, gdy propozycje czekają ponad SLA."""
    from news.raport_petli import owner_decisions
    now = now or timezone.now()
    data = owner_decisions(now)
    late = data['waiting'] > 0
    summary = (f"{data['waiting']} propozycji czeka na decyzję ponad {data['sla_days']} dni" if late
               else 'Brak propozycji czekających ponad termin.')
    return {'id': OWNER + ':panel', 'enabled': True, 'result': 'warn' if late else 'ok', 'schedule': 'decyzje w panelu',
            'summary': summary, 'last_run': data['last_decision'] or (data['oldest'] if late else None)}


def loops_state(rows=None):
    rows = rows if rows is not None else health()
    out, checks = [], []
    for portal, name, rhythm, steps in LOOPS:
        items = []
        for label, ident, guard in steps:
            row = rows.get(ident) if ident else None
            state = {'step': label, 'guard': bool(guard), 'human': ident is None or ident == OWNER}
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
    data = {'context': CONTEXT, 'loops': loops, 'checks': checks, 'proposals': flow, 'previous': previous(), 'knowledge': knowledge(), 'canons': _canons()}
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
            scores={'audit': note.pk, **f, 'author': registry.metadata(author) if author else {'company': 'local'}})
    if any(i.get('severity') == 'wysoki' for i in issues) or any('wyłączony' in c or 'błędem' in c for c in checks):
        common.notify(note)
    return note


LESSON = {'type': 'object', 'properties': {'title': TEXT, 'lesson': TEXT, 'apply': TEXT, 'source_url': TEXT},
          'required': ['title', 'lesson', 'apply', 'source_url']}
LEARN_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'lessons': {'type': 'array', 'items': LESSON}}, 'required': ['summary', 'lessons']}
LEARN = ('Jesteś Automatykiem i w wolnym czasie uczysz się wszystkiego, co najnowsze o automatyzacji: agenci AI, orkiestracja, '
         'pętle zwrotne, ewaluacja modeli, niezawodne przepływy, kolejki, koszty. Na podstawie WYŁĄCZNIE items wybierz do 8 lekcji: '
         'czego się nauczyłeś (lesson) i jak to zastosować w naszych pętlach (apply: wskaż pętlę z loops, konkretnie). source_url z items. '
         'Bez mody dla mody; tylko to, co da się zrobić przy darmowych modelach i obecnym stosie (Django, Celery).')
LEARN_CHECK = ('Sprawdź lekcje kolegi. W remove podaj numery (od 0) lekcji bez pokrycia w items, ogólnikowych albo niemożliwych '
               'do zastosowania w podanych pętlach.')


def knowledge(limit=12):
    """Najnowsze sprawdzone lekcje Automatyka (do codziennego przeglądu)."""
    rows = []
    for note in AgentNote.objects.filter(agent='automatyk', kind='report')[:3]:
        rows += [f"{l['title']}: {l['apply']}" for l in (note.scores or {}).get('lessons', [])]
    return rows[:limit]


def learn(force=False):
    import re
    import feedparser
    import requests
    seen = set()
    for note in AgentNote.objects.filter(agent='automatyk', kind='report')[:12]:
        seen |= set((note.scores or {}).get('seen', []))

    def fetch(feeds):
        out = []
        for name, url in feeds.items():
            try:
                parsed = feedparser.parse(requests.get(url, timeout=15, headers={'User-Agent': 'spin.clinic Automatyk (+https://spin.clinic)'}).content)
            except requests.RequestException:
                continue
            for entry in parsed.entries[:5]:
                link = entry.get('link', '')
                if link.startswith('https://') and link not in seen:
                    out.append({'source': name, 'title': entry.get('title', '')[:200], 'url': link,
                                'summary': re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))[:400]})
        return out

    items, mode = fetch(LEARN_FEEDS), 'podstawowe'
    if len(items) < FRESH_MIN:  # podstawowe źródła wyczerpane: szeroki research, kolejna porcja co tydzień
        names = list(WIDE_FEEDS)
        start = (AgentNote.objects.filter(agent='automatyk', kind='report', scores__mode='szerokie').count() * WIDE_BATCH) % len(names)
        batch = (names + names)[start:start + WIDE_BATCH]
        items += fetch({**{n: WIDE_FEEDS[n] for n in batch}, **_found('automatyzacja')})
        mode = 'szerokie'
    if not items:
        raise common.WindowClosed('Brak nowości o automatyzacji do nauki.')
    urls = {i['url'] for i in items}
    loops = [f'{portal} · {name}' for portal, name, _, _ in LOOPS]
    answer, author = common.ask_any(LEARN, {'items': items[:45], 'loops': loops}, LEARN_SCHEMA, force)
    lessons = [l for l in answer.get('lessons', []) if isinstance(l, dict) and l.get('source_url') in urls]
    reason = ''
    if lessons:
        verdict, _ = common.ask_any(LEARN_CHECK, {'items': items[:45], 'loops': loops, 'lessons': lessons}, CHECK, force, exclude=(author,))
        drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
        lessons, reason = [l for n, l in enumerate(lessons) if n not in drop], verdict.get('reason', '')
    data = {'summary': answer.get('summary', ''), 'lessons': lessons, 'check': reason, 'mode': mode,
            'sources': sorted({i['source'] for i in items}), 'seen': sorted({i['url'] for i in items[:45]})}
    body = chr(10).join([data['summary'], ''] + [f"- {l['title']}: {l['lesson']}{chr(10)}  U nas: {l['apply']} ({l['source_url']})" for l in lessons])
    return AgentNote.objects.create(agent='automatyk', kind='report', status='new',
        title=f"Automatyk się uczy ({'szeroki research' if mode == 'szerokie' else 'podstawowe źródła'}): {len(lessons)} lekcji ({timezone.localdate():%d.%m.%Y})", body=body.strip(), scores=data,
        sources=sorted({l['source_url'] for l in lessons}))


def learn_due():
    last = AgentNote.objects.filter(agent='automatyk', kind='report').first()
    return last is None or timezone.now() - last.created_at >= WEEK


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


def _found(topic):
    """Odkryte przez Badacza źródła tematu (pętla researchu); pusto, gdy Badacz jeszcze nic nie przyjął."""
    try:
        from news import badacz
        return badacz.feeds(topic)
    except Exception:  # noqa: BLE001 - research nie może zatrzymać agenta
        return {}


def _canons():
    from news.kanony import canons
    return canons('automatyzacja') + canons('bezpieczeństwo')
