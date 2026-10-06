"""Koszty pętli (właściciel 7.10: „naprawcie agentów i pętle, tracimy tokeny w tle”). Bez sieci, bez AI.

Trzy rzeczy w jednym miejscu:
1. Licznik zapytań do modeli na zadanie i dzień: każde przyznane miejsce w limicie Konsylium (council_registry.reserve)
   i każde zapytanie do Inception (inception.record) dolicza się do zadania Celery, które właśnie biegnie
   (task_heartbeat ustawia nazwę przy starcie zadania). Klucze w cache po dniu, 8 dni wstecz.
2. Licznik pominiętych przebiegów: pętla, która nic nie zrobiła, bo wejście się nie zmieniło (skip), zamiast pytać model.
3. Znak wodny (watermark): skrót wejścia pętli; `changed(key, payload)` mówi, czy od ostatniego przebiegu coś się zmieniło,
   `mark(key, payload)` zapamiętuje stan po udanym przebiegu. Pętla bez zmian wejścia nie woła modelu (tanio, bez utraty treści).

Raport pętli pokazuje z tego sekcję „Koszty pętli”: zapytania dziś i w 7 dni na pętlę oraz liczbę pominiętych przebiegów.
"""
import hashlib
import json
from contextvars import ContextVar
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
TTL = 8 * 86400
MARK_TTL = 60 * 86400
PREFIX = 'news.tasks.'
OTHER = 'poza zadaniem'  # zapytania spoza zadania Celery (komenda, panel, test)
_task = ContextVar('petle_koszty_task', default='')


def begin(task_name):
    """Zadanie Celery rusza: od teraz zapytania liczą się na jego konto (task_heartbeat.started)."""
    return _task.set(short(task_name))


def end(token=None):
    if token is not None:
        try:
            _task.reset(token)
            return
        except ValueError:
            pass
    _task.set('')


def current():
    return _task.get() or OTHER


def short(task_name):
    name = str(task_name or '')
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


def _day(now=None):
    return (now or timezone.now()).astimezone(WARSAW).date().isoformat()


def _key(kind, day, task):
    return f'petle:{kind}:{day}:{task}'


def _incr(kind, task=None, now=None):
    task = task or current()
    key = _key(kind, _day(now), task)
    try:
        cache.add(key, 0, TTL)
        return cache.incr(key)
    except Exception:  # noqa: BLE001 - licznik nie może zatrzymać zapytania ani pętli
        return 0


def count_call(task=None, now=None):
    """Jedno zapytanie do modelu na konto bieżącego zadania."""
    return _incr('llm', task, now)


def count_skip(task=None, now=None):
    """Jeden przebieg pominięty tanio (wejście bez zmian, nic do zrobienia)."""
    return _incr('skip', task, now)


def skipped(reason='bez zmian', task=None, **extra):
    """Wynik zadania, które nie wołało modelu, bo nie miało nowego wejścia; liczy się jako pominięty przebieg."""
    count_skip(task)
    return {'status': 'ok', 'unchanged': 1, 'reason': reason, **extra}


# --- znak wodny -------------------------------------------------------------------------------------------------------

def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


def changed(key, payload):
    """True, gdy wejście pętli różni się od zapamiętanego po ostatnim udanym przebiegu (albo nic nie zapamiętano)."""
    return cache.get(f'petle:mark:{key}') != digest(payload)


def mark(key, payload):
    cache.set(f'petle:mark:{key}', digest(payload), MARK_TTL)


def unchanged_since(key, payload, task=None):
    """Skrót dla pętli: gdy bez zmian, dolicza pominięty przebieg i zwraca True; gdy są zmiany, zwraca False (bez zapisu -
    pętla woła mark() po udanym przebiegu, żeby błąd modelu nie zgubił zmiany)."""
    if changed(key, payload):
        return False
    count_skip(task)
    return True


# --- raport -------------------------------------------------------------------------------------------------------

def _task_names():
    """Zadania z harmonogramu (beat), rejestru agentów i zapytania spoza zadań."""
    names = set()
    try:
        from config.celery import app
        names |= {short(entry['task']) for entry in app.conf.beat_schedule.values()}
    except Exception:  # noqa: BLE001
        pass
    try:
        from news.agent_registry import REGISTRY
        names |= {short(spec['task']) for spec in REGISTRY.values()}
    except Exception:  # noqa: BLE001
        pass
    names.add(OTHER)
    return sorted(names)


def usage(now=None, days=7):
    """{zadanie: {'dzis': n, 'tydzien': n, 'pominiete_dzis': n, 'pominiete_tydzien': n}} tylko dla zadań z jakimkolwiek ruchem."""
    now = now or timezone.now()
    tasks = _task_names()
    day_keys = [_day(now - timedelta(days=i)) for i in range(days)]
    keys = [_key(kind, day, task) for kind in ('llm', 'skip') for day in day_keys for task in tasks]
    try:
        values = cache.get_many(keys)
    except Exception:  # noqa: BLE001
        values = {}
    out = {}
    for task in tasks:
        row = {'dzis': int(values.get(_key('llm', day_keys[0], task), 0) or 0),
               'tydzien': sum(int(values.get(_key('llm', d, task), 0) or 0) for d in day_keys),
               'pominiete_dzis': int(values.get(_key('skip', day_keys[0], task), 0) or 0),
               'pominiete_tydzien': sum(int(values.get(_key('skip', d, task), 0) or 0) for d in day_keys)}
        if any(row.values()):
            out[task] = row
    return out


def report_lines(now=None, limit=20):
    """Linie do Raportu pętli: suma i najdroższe pętle (zapytania dziś / 7 dni, pominięte przebiegi)."""
    rows = usage(now)
    if not rows:
        return ['Brak zapisanych zapytań do modeli (licznik od 7.10; dane z cache, 8 dni).']
    total_day = sum(r['dzis'] for r in rows.values())
    total_week = sum(r['tydzien'] for r in rows.values())
    skipped_day = sum(r['pominiete_dzis'] for r in rows.values())
    skipped_week = sum(r['pominiete_tydzien'] for r in rows.values())
    lines = [f'Zapytania do modeli: dziś {total_day}, 7 dni {total_week}; przebiegi pominięte bez zapytania (wejście bez zmian): '
             f'dziś {skipped_day}, 7 dni {skipped_week}.']
    ordered = sorted(rows.items(), key=lambda kv: (-kv[1]['tydzien'], -kv[1]['dzis'], kv[0]))[:limit]
    for task, r in ordered:
        skip = f", pominięte {r['pominiete_dzis']} / {r['pominiete_tydzien']}" if r['pominiete_tydzien'] else ''
        lines.append(f"- {task}: {r['dzis']} / {r['tydzien']}{skip}")
    return lines
