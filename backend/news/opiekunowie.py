"""Opiekunowie pętli (właściciel 5.10): każda pętla obu portali ma czterech opiekunów z pełnym kontekstem tej pętli.

- Alarmowy (bez AI, co godzinę): krok pętli z błędem albo spóźniony -> wpis w panelu i mail, najwyżej raz na 6 godzin na pętlę.
- Naprawiacz (AI, gdy jest alarm): z kontekstu pętli i stanu kroku proponuje konkretną naprawę ze zleceniem dla wykonawcy.
- Usprawniacz (AI, codziennie kolejne pętle): usprawnienia tylko tej jednej pętli, znając jej kroki, strażników i historię.
- Strażnik bezpieczeństwa (bez AI + AI raz w tygodniu na pętlę): dane osobowe, sekrety, treści z zewnątrz trafiające do modeli
  (wstrzyknięcia poleceń), koszty, publikacja bez strażnika przed nią, zgodność z prawem i zasadą tej samej miary.

Zamiast 4 osobnych agentów na każdą z kilkunastu pętli (dziesiątki agentów i limitów) to cztery role, które obchodzą pętle
po kolei - każda pętla ma swoich opiekunów, a koszt i limity modeli zostają pod kontrolą. Opiekunowie tylko proponują i alarmują.
Pętle i ich stan bierzemy z Automatyka (LOOPS, health), więc nowa pętla dopisana tam od razu dostaje opiekunów."""
import re
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from news import agents_common as common, council_registry as registry
from news import automatyk
from news.agent_models import AgentNote

ALARM_EVERY = timedelta(hours=6)
IMPROVE_PER_DAY = 3      # usprawniacz: tyle pętli dziennie (po kolei, najdawniej odwiedzane najpierw)
SECURITY_EVERY = timedelta(days=7)
SECURITY_PER_RUN = 1
TEXT = {'type': 'string'}
INT = {'type': 'integer'}
FIX = {'type': 'object', 'properties': {'change': TEXT, 'why': TEXT, 'evidence': TEXT, 'brief': TEXT, 'impact': INT,
       'effort': {'type': 'string', 'enum': ['S', 'M', 'L']}}, 'required': ['change', 'why', 'evidence', 'brief', 'impact', 'effort']}
FIXES = {'type': 'object', 'properties': {'summary': TEXT, 'fixes': {'type': 'array', 'items': FIX}}, 'required': ['summary', 'fixes']}
RISK = {'type': 'object', 'properties': {'risk': TEXT, 'where': TEXT, 'severity': {'type': 'string', 'enum': ['wysoki', 'średni', 'niski']},
        'guard': TEXT}, 'required': ['risk', 'where', 'severity', 'guard']}
RISKS = {'type': 'object', 'properties': {'summary': TEXT, 'risks': {'type': 'array', 'items': RISK}}, 'required': ['summary', 'risks']}
CHECK = {'type': 'object', 'properties': {'remove': {'type': 'array', 'items': INT}, 'reason': TEXT}, 'required': ['remove', 'reason']}

ROLE_PROMPT = {
    'naprawiacz': ('Jesteś Naprawiaczem jednej pętli agentów (loop) i znasz jej pełny kontekst (context, steps). Pętla ma alarm (alerts). '
                   'Zaproponuj do 3 konkretnych napraw: co zmienić, dlaczego, dowód z danych kroku, gotowe zlecenie dla programisty. '
                   'Najpierw najmniejsza zmiana, która przywraca działanie. Szanuj zasady z context.'),
    'usprawniacz': ('Jesteś Usprawniaczem jednej pętli agentów (loop) i znasz jej pełny kontekst (context, steps, notes - ostatnie wpisy '
                    'agentów tej pętli, automatyk - wcześniejsze zalecenia dla całości). Zaproponuj do 4 usprawnień TYLKO tej pętli: '
                    'szybszy przepływ, lepszy strażnik, brakujące sprzężenie zwrotne, mniejszy koszt, czytelniejszy wynik dla ludzi. '
                    'Każde z dowodem i gotowym zleceniem. Nie powtarzaj previous.'),
}
SECURITY = ('Jesteś Strażnikiem bezpieczeństwa jednej pętli agentów (loop) i znasz jej pełny kontekst (context, steps). Wypisz do 5 ryzyk: '
            'dane osobowe i osoby prywatne, sekrety i klucze, treści z zewnątrz (wpisy, artykuły, strony) trafiające do modeli jako polecenia, '
            'koszty bez limitu, publikacja bez strażnika przed nią, prawo (RODO, prawo prasowe, licencje), zasada tej samej miary. '
            'Dla każdego: gdzie (krok), waga i jaki strażnik to zatrzyma. Tylko ryzyka wynikające z kroków tej pętli. Automatyczne uwagi: checks.')
CHECK_PROMPT = ('Sprawdź propozycje kolegi dla tej pętli. W remove podaj numery (od 0) propozycji ogólnikowych, bez oparcia w danych '
                'pętli albo łamiących zasady z context.')


def _note(role, loop, kind, title, body, data, score=0, author=None):
    if author is not None:  # Seba wybiera krytyka innej firmy i może poprosić autora o jedną poprawkę
        data = {**data, 'author': registry.metadata(author) if author else {'company': 'local'}}
    return AgentNote.objects.create(agent='opiekun', kind=kind, status='new', title=f'{loop} · {role}: {title}'[:240], body=body,
                                    scores={'role': role, 'loop': loop, **data}, score=score)


def error_kind(summary):
    """Rodzaj błędu z podsumowania kroku: nazwa wyjątku albo tekst bez liczb i dat (ten sam błąd = ten sam klucz)."""
    text = str(summary or '')
    found = re.search(r'\b([A-Z]\w*(?:Error|Exception|Timeout))\b', text)
    if found:
        return found.group(1)
    return re.sub(r'\s+', ' ', re.sub(r'[\d:./-]+', '#', text)).strip()[:60]


def alarm_key(bad):
    """Klucz otwartego alarmu: kroki, wynik i rodzaj błędu (6.10: sto prawie identycznych wpisów o tym samym błędzie)."""
    return ' | '.join(sorted(f"{s.get('step')}:{s.get('result')}:{error_kind(s.get('summary'))}" for s in bad))[:400]


def open_note(role, loop, key):
    return AgentNote.objects.filter(agent='opiekun', status='new', scores__role=role, scores__loop=loop, scores__key=key).first()


def _loop_context(loop):
    """Pełny kontekst jednej pętli: definicja, stan kroków, ostatnie wpisy agentów z tej pętli."""
    rows = automatyk.health()
    state, _ = automatyk.loops_state(rows)
    item = next(l for l in state if l['loop'] == loop)
    notes = [{'agent': n.agent, 'title': n.title, 'status': n.status} for n in AgentNote.objects.filter(scores__loop=loop)[:10]]
    return {'context': automatyk.CONTEXT, 'loop': f"{item['portal']} · {loop}", 'rhythm': item['rhythm'], 'steps': item['steps'],
            'notes': notes}


def _ask(prompt, data, schema, force, key, used=None):
    answer, author = common.ask_any(prompt, data, schema, force)
    if used is not None:
        used['author'] = author
    rows = [r for r in answer.get(key, []) if isinstance(r, dict)]
    reason = ''
    if rows:
        verdict, _ = common.ask_any(CHECK_PROMPT, {**data, key: rows}, CHECK, force, exclude=(author,))
        drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
        rows, reason = [r for n, r in enumerate(rows) if n not in drop], verdict.get('reason', '')
    return answer.get('summary', ''), rows, reason


def alarms():
    """Bez AI: kroki z błędem albo spóźnione, per pętla; najwyżej raz na 6 godzin na pętlę. Jeden otwarty wpis na
    (pętla, kroki, rodzaj błędu): powtórka tego samego alarmu odświeża istniejący wpis zamiast tworzyć nowy."""
    state, _ = automatyk.loops_state()
    raised = []
    for item in state:
        bad = [s for s in item['steps'] if s.get('enabled') and (s.get('result') == 'error' or (s.get('result') == 'warn' and s.get('last_run')))]
        if not bad:
            continue
        key = f"opiekun:alarm:{item['loop']}"
        if not cache.add(key, 1, int(ALARM_EVERY.total_seconds())):
            continue
        lines = [f"- {s['step']}: {'błąd' if s['result'] == 'error' else 'spóźniony lub pominięty'} ({s.get('summary', '')[:120]})" for s in bad]
        signature, now = alarm_key(bad), timezone.now().isoformat()
        existing = open_note('alarmowy', item['loop'], signature)
        if existing:
            scores = dict(existing.scores)
            scores.update(alerts=bad, repeats=int(scores.get('repeats') or 1) + 1, last_seen=now)
            existing.scores, existing.body = scores, chr(10).join(lines)
            existing.save(update_fields=['scores', 'body'])
            continue
        note = _note('alarmowy', item['loop'], 'audit', f'{len(bad)} krok(i) do sprawdzenia', chr(10).join(lines),
                     {'alerts': bad, 'key': signature, 'repeats': 1, 'last_seen': now})
        common.notify(note)
        raised.append(note)
    return raised


def repair(note, force=False):
    loop = note.scores['loop']
    key = note.scores.get('key') or alarm_key(note.scores.get('alerts', []))
    existing = open_note('naprawiacz', loop, key)
    if existing:  # ten sam błąd ma już otwartą propozycję naprawy - bez wywołania modelu i bez nowego wpisu
        return existing
    data = {**_loop_context(loop), 'alerts': note.scores.get('alerts', [])}
    used = {}
    summary, fixes, reason = _ask(ROLE_PROMPT['naprawiacz'], data, FIXES, force, 'fixes', used)
    body = chr(10).join([summary, ''] + [f"- {f['change']} ({f['effort']}): {f['why']}{chr(10)}  Zlecenie: {f['brief']}" for f in fixes])
    return _note('naprawiacz', loop, 'finding', f'{len(fixes)} propozycji naprawy', body.strip(),
                 {'fixes': fixes, 'check': reason, 'alarm': note.pk, 'key': key},
                 score=max([int(f.get('impact') or 0) * 10 for f in fixes] or [0]), author=used.get('author'))


def _least_recent(role, count):
    loops = [name for _, name, _, _ in automatyk.LOOPS]
    last = {}
    for n in AgentNote.objects.filter(agent='opiekun', scores__role=role).order_by('-created_at')[:200]:
        last.setdefault(n.scores.get('loop'), n.created_at)
    return sorted(loops, key=lambda l: last.get(l) or timezone.make_aware(timezone.datetime(2000, 1, 1)))[:count], last


def improve(force=False, count=IMPROVE_PER_DAY):
    loops, last = _least_recent('usprawniacz', count)
    done = []
    for loop in loops:
        if not force and last.get(loop) and timezone.now() - last[loop] < timedelta(hours=20):
            continue
        previous = [n.title for n in AgentNote.objects.filter(agent='opiekun', scores__role='usprawniacz', scores__loop=loop)[:5]]
        data = {**_loop_context(loop), 'previous': previous,
                'automatyk': [n.title for n in AgentNote.objects.filter(agent='automatyk', kind='idea')[:6]]}
        used = {}
        summary, fixes, reason = _ask(ROLE_PROMPT['usprawniacz'], data, FIXES, force, 'fixes', used)
        body = chr(10).join([summary, ''] + [f"- {f['change']} ({f['effort']}, wpływ {f['impact']}/10): {f['why']}{chr(10)}  Zlecenie: {f['brief']}" for f in fixes])
        note = _note('usprawniacz', loop, 'idea' if fixes else 'report', f'{len(fixes)} usprawnień', body.strip(), {'fixes': fixes, 'check': reason},
                     score=max([int(f.get('impact') or 0) * 10 for f in fixes] or [0]), author=used.get('author'))
        done.append(note)
    return done


def security_checks(item):
    """Bez AI: publikacja bez strażnika przed nią, pętla bez strażnika."""
    checks, guarded = [], False
    for s in item['steps']:
        guarded = guarded or s['guard']
        if any(w in s['step'].lower() for w in ('publikacja', 'wdrożenie', 'wysyłka')) and not guarded:
            checks.append(f"Krok „{s['step']}” publikuje, a przed nim nie ma strażnika.")
    if not any(s['guard'] for s in item['steps']):
        checks.append('Pętla nie ma żadnego strażnika.')
    return checks


def security(force=False):
    loops, last = _least_recent('bezpieczeństwo', SECURITY_PER_RUN)
    done = []
    for loop in loops:
        if not force and last.get(loop) and timezone.now() - last[loop] < SECURITY_EVERY:
            continue
        ctx = _loop_context(loop)
        checks = security_checks({'steps': ctx['steps']})
        summary, risks, reason = _ask(SECURITY, {**ctx, 'checks': checks}, RISKS, force, 'risks')
        order = {'wysoki': 0, 'średni': 1, 'niski': 2}
        risks.sort(key=lambda r: order.get(r.get('severity'), 3))
        body = chr(10).join([summary, ''] + [f'- automatycznie: {c}' for c in checks] +
                            [f"- [{r['severity']}] {r['where']}: {r['risk']}{chr(10)}  Strażnik: {r['guard']}" for r in risks])
        note = _note('bezpieczeństwo', loop, 'audit', f"{sum(r['severity'] == 'wysoki' for r in risks)} ryzyk wysokich", body.strip(),
                     {'risks': risks, 'checks': checks, 'check': reason})
        if any(r['severity'] == 'wysoki' for r in risks):
            common.notify(note)
        done.append(note)
    return done


def step(force=False):
    """Co godzinę: alarmy dla wszystkich pętli; naprawy do nowych alarmów; raz dziennie usprawnienia kolejnych pętli;
    raz w tygodniu bezpieczeństwo każdej pętli (po jednej na uruchomienie). Jedna awaria nie zatrzymuje reszty."""
    out = {}
    for name, run in (('alarmy', alarms), ('naprawy', lambda: [repair(n, force) for n in alarms_without_repair()]),
                      ('usprawnienia', lambda: improve(force)), ('bezpieczeństwo', lambda: security(force))):
        try:
            out[name] = len(run())
        except common.WindowClosed as error:
            out[name] = f'czeka: {error}'
        except Exception as error:  # noqa: BLE001 - raport, kolejne role działają dalej
            out[name] = f'błąd: {type(error).__name__}: {str(error)[:120]}'
    return out


def alarms_without_repair(limit=2):
    repairs = [n.scores or {} for n in AgentNote.objects.filter(agent='opiekun', scores__role='naprawiacz')[:200]]
    repaired = {r.get('alarm') for r in repairs}
    open_keys = {((n.scores or {}).get('loop'), (n.scores or {}).get('key'))
                 for n in AgentNote.objects.filter(agent='opiekun', scores__role='naprawiacz', status='new')[:200]}
    return [n for n in AgentNote.objects.filter(agent='opiekun', scores__role='alarmowy',
                                                created_at__gte=timezone.now() - timedelta(days=1))[:10]
            if n.pk not in repaired and (n.scores.get('loop'), n.scores.get('key')) not in open_keys][:limit]


def duplicate_groups():
    """Otwarte wpisy Opiekuna pogrupowane po (rola, pętla, klucz błędu), najnowszy pierwszy. Do jednorazowego sprzątania."""
    rows = list(AgentNote.objects.filter(agent='opiekun', status='new').order_by('-created_at', '-pk'))
    alarm_keys = {n.pk: n.scores.get('key') or alarm_key(n.scores.get('alerts', []))
                  for n in rows if n.scores.get('role') == 'alarmowy'}
    groups = {}
    for n in rows:
        role, loop = n.scores.get('role'), n.scores.get('loop')
        if role == 'alarmowy':
            key = alarm_keys[n.pk]
        elif role == 'naprawiacz':
            key = n.scores.get('key') or alarm_keys.get(n.scores.get('alarm'))
            if key is None:
                source = AgentNote.objects.filter(pk=n.scores.get('alarm')).first()
                key = alarm_key(source.scores.get('alerts', [])) if source else re.sub(r'\d+', '#', n.title)
        else:
            key = re.sub(r'\d+', '#', n.title)
        groups.setdefault((role, loop, key), []).append(n)
    return groups
