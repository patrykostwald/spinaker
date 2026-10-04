"""Dyrygent (właściciel 5.10): zna wszystkie pętle, harmonogram i limity; pilnuje hierarchii, żeby całość grała razem.

Hierarchia (od najważniejszej): 1 treść serwisu (diagnozy, przekazy, wywiady - Dyrygent ich nie dotyka, mają własną rezerwę),
2 strażnicy (Recenzent, kontrola spinek, bezpieczeństwo), 3 niezawodność (alarmy, naprawy), 4 rozwój (Pracownia, Automatyk,
Usprawniacze, Strateg), 5 nauka (Badacz, nauka Automatyka i Projektanta).

Co 15 minut liczy wolną pojemność darmowych modeli i ustawia tryb:
- pełny (ponad 50% wolnego): wszystkie poziomy;
- oszczędny (20-50%): bez nauki;
- strażnicy (poniżej 20%): tylko strażnicy i niezawodność; rozwój i nauka czekają na następne okno.
Agenci pytają o zgodę przez ask_any (poziom ustawia zadanie: with dyrygent.tier('nauka')).
Raz dziennie plan dnia: tryb, kolizje harmonogramu (kilka zadań z AI w tym samym 10-minutowym oknie), kolejka budowy
dla wykonawców (Codex, gdy ma limit; inaczej Claude) z przyjętych pomysłów agentów."""
import contextvars
import os
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

TIERS = ['treść', 'strażnicy', 'niezawodność', 'rozwój', 'nauka']
MODES = {'pełny': set(TIERS), 'oszczędny': set(TIERS[:4]), 'strażnicy': set(TIERS[:3])}
MODE_KEY = 'dyrygent:mode'
_tier = contextvars.ContextVar('dyrygent_tier', default='rozwój')
# zadania z AI i ich poziom (do kolizji harmonogramu i planu dnia)
AI_TASKS = {'recenzent_task': 'strażnicy', 'thread_reviews_task': 'strażnicy', 'opiekunowie_task': 'niezawodność', 'mechanik_task': 'niezawodność',
            'pracownia_osint_task': 'rozwój', 'automatyk_task': 'rozwój', 'agents_window_task': 'rozwój', 'ekspert_ai_task': 'rozwój',
            'projektant_task': 'nauka', 'badacz_task': 'nauka', 'institutional_reports_task': 'rozwój', 'signal_threads_task': 'rozwój',
            'narrative_thread_task': 'rozwój'}
CODEX_BACK = os.environ.get('CODEX_AVAILABLE_FROM', '2026-10-10')  # limit Codexa (plan ChatGPT właściciela); po resecie wpis w .env


@contextmanager
def tier(name):
    token = _tier.set(name)
    try:
        yield
    finally:
        _tier.reset(token)


def capacity():
    """Wolna część dziennych limitów darmowych modeli (0-1), z pominięciem rezerwy na treść."""
    from news import agents_common as common
    from news.clinic_council import DEFAULT_COUNCIL, _members
    from news import council_registry as registry
    total = used = 0
    for member in _members('CLINIC_COUNCIL', DEFAULT_COUNCIL):
        if not common.free_member(member) or not registry.available(member):
            continue
        ceiling = max(1, common.ceiling(member))
        total += ceiling
        used += min(ceiling, cache.get(registry.limit_key(member), 0))
    return 1.0 if not total else max(0.0, 1 - used / total)


def decide():
    free = capacity()
    mode = 'pełny' if free > .5 else 'oszczędny' if free >= .2 else 'strażnicy'
    cache.set(MODE_KEY, {'mode': mode, 'free': round(free, 2), 'at': timezone.now().isoformat(timespec='minutes')}, 3600)
    return mode, free


def mode():
    state = cache.get(MODE_KEY)
    return state['mode'] if state else 'pełny'


def allowed(name=None):
    return (name or _tier.get()) in MODES.get(mode(), MODES['pełny'])


def collisions():
    """Zadania z AI uruchamiane w tym samym 10-minutowym oknie (konkurują o te same limity)."""
    from news.daily_schedule import BEAT_PLAN
    slots = defaultdict(list)
    for key, (task, cron) in BEAT_PLAN.items():
        if task not in AI_TASKS:
            continue
        hours = str(cron.get('hour', '*'))
        minutes = str(cron.get('minute', '0'))
        if hours == '*' or '/' in hours or '/' in minutes or minutes == '*' or '-' in hours:
            continue  # zadania częste i zakresy pomijamy - same pilnują okna
        for h in hours.split(','):
            for m in minutes.split(','):
                slots[(int(h), int(m) // 10)].append(task)
    return [{'okno': f'{h:02d}:{w * 10:02d}', 'zadania': sorted(set(t))} for (h, w), t in sorted(slots.items()) if len(set(t)) > 1]


def build_queue(limit=10):
    """Kolejka budowy: przyjęte pomysły agentów (najpierw przyjęte przez właściciela, potem wysoko ocenione nowe)."""
    from news.agent_models import AgentNote
    rows = AgentNote.objects.filter(kind='idea', agent__in=['architekt', 'automatyk', 'opiekun', 'strateg']).exclude(
        status__in=['rejected', 'denied', 'done'])
    rows = sorted(rows, key=lambda n: (n.status != 'accepted', -n.score, -n.pk))[:limit]
    codex = date.today() >= date.fromisoformat(CODEX_BACK)
    out = []
    for n in rows:
        effort = (n.scores or {}).get('effort', 'M')
        who = 'Codex' if codex and effort in ('S', 'M') else 'Claude'
        out.append({'id': n.pk, 'title': n.title, 'status': n.status, 'effort': effort, 'who': who})
    return out, codex


def plan(force=False):
    from news import agents_common as common
    from news.agent_models import AgentNote
    last = AgentNote.objects.filter(agent='dyrygent', kind='report').first()
    if last and not force and timezone.now() - last.created_at < timedelta(hours=20):
        return last
    mode_now, free = decide()
    clash = collisions()
    queue, codex = build_queue()
    lines = [f'Tryb: {mode_now} (wolne limity darmowych modeli: {round(free * 100)}%).',
             f"Codex: {'dostępny' if codex else 'limit do ' + CODEX_BACK + ', buduje Claude'}.", '']
    if clash:
        lines += ['Kolizje harmonogramu (zadania z AI w tym samym oknie, warto rozsunąć):'] + [f"- {c['okno']}: {', '.join(c['zadania'])}" for c in clash] + ['']
    lines += ['Kolejka budowy:'] + [f"- #{q['id']} [{q['status']}, {q['effort']}, {q['who']}] {q['title']}" for q in queue]
    note = AgentNote.objects.create(agent='dyrygent', kind='report', status='new', title=f'Plan dnia: tryb {mode_now}, {len(queue)} w kolejce budowy',
                                    body=chr(10).join(lines), scores={'mode': mode_now, 'free': free, 'collisions': clash, 'queue': queue})
    if clash or mode_now == 'strażnicy':
        common.notify(note)
    return note
