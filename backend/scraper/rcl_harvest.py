"""Nocny zbieracz Rządowego Procesu Legislacyjnego (legislacja.rcl.gov.pl).

Kolejność w nocy: robots.txt, nowości i zmiany (lista ostatnio zmienionych), szczegóły zmienionych projektów,
potem stopniowo archiwum (kursor po liście wg daty utworzenia) i szczegóły kolejnych projektów, aż do budżetu zapytań na noc.
Wszystko wznawialne: kursory i kolejka są w bazie (ImportState, LegislativeProject.needs_refresh), więc przerwanie o 06:00,
po 429/503 albo po wyczerpaniu budżetu niczego nie gubi.  Zapisy są wersjonowane (LegislativeChange), nic nie jest
nadpisywane po cichu.  Warunki zgody RCL: scraper.rcl_guard; zapytania: scraper.rcl_client.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from django.db import transaction
from django.utils import timezone

from news.models import (FetchAttempt, ImportState, LegislativeChange, LegislativeDocument, LegislativeProject,
                         LegislativeStage, RclFetchEvent, Source, SourceAccessInstruction)
from scraper import rcl_guard, rcl_parser
from scraper.access_gate import approved_instruction
from scraper.rcl_client import RclClient, RclResponse, RclStop, RclTransient, absolute_url
from scraper.rcl_parser import RclParseError

SOURCE_URL = rcl_guard.RCL_BASE_URL + '/'
SOURCE_NAME = 'Rządowe Centrum Legislacji - Rządowy Proces Legislacyjny'
DEFAULT_TYPE_IDS = (2, 1, 10, 6)
PAGE_SIZE = 100
MAX_FAILURES = 3
CONSECUTIVE_ERROR_LIMIT = 5

PROJECT_LIST_FIELDS = ('title', 'applicant', 'wykaz_number', 'wykaz_url', 'created_on', 'list_modified_on')
PROJECT_DETAIL_FIELDS = ('title', 'applicant', 'wykaz_number', 'wykaz_url', 'wykaz_name', 'status', 'term', 'departments',
                         'keywords', 'notes', 'sejm_url', 'rm_number', 'info', 'created_on')
STAGE_FIELDS = ('number', 'name', 'kind', 'state', 'started_on', 'ended_on', 'modified_on', 'catalog_url')
DOCUMENT_FIELDS = ('name', 'file_url', 'file_ext', 'author', 'created_on', 'folder_rcl_id', 'folder_name', 'category')


# --- ustawienia (środowisko czytane przy każdym uruchomieniu) ---

def env_int(name, default, low, high):
    try:
        value = int(os.environ.get(name, '') or default)
    except ValueError:
        value = default
    return max(low, min(high, value))


def type_ids():
    raw = os.environ.get('RCL_TYPE_IDS', '')
    ids = [int(x) for x in raw.replace(' ', '').split(',') if x.isdigit()]
    return tuple(ids) or DEFAULT_TYPE_IDS


def nightly_budget():
    return env_int('RCL_NIGHTLY_REQUEST_BUDGET', 3000, 1, 3600)


def robots_override():
    """Wyłącznie świadoma decyzja właściciela po ocenie Prawnika; domyślnie robots.txt rozstrzyga."""
    return os.environ.get('RCL_ROBOTS_OVERRIDE', '').strip().lower() == 'written_consent'


def list_url(type_id, page, key='modifiedDate', order='desc'):
    return f'/lista?typeId={int(type_id)}&sKey={key}&sOrder={order}&pSize={PAGE_SIZE}&pNumber={int(page)}'


# --- dostęp (karta źródła) ---

def configured_access():
    """(źródło, karta) albo (None, None): bez zatwierdzonej karty zbieracz nie wysyła nic."""
    source = Source.objects.filter(url=SOURCE_URL).first()
    if source is None:
        return None, None
    return source, approved_instruction(source, SourceAccessInstruction.Channel.HTML, SOURCE_URL)


# --- stan przebiegu ---

@dataclass
class Run:
    counters: Counter = field(default_factory=Counter)
    attempted: set = field(default_factory=set)
    folder_names: Counter = field(default_factory=Counter)
    stage_names: Counter = field(default_factory=Counter)
    consecutive_errors: int = 0
    type_failures: Counter = field(default_factory=Counter)
    type_successes: Counter = field(default_factory=Counter)
    stopped: str = ''
    recon_projects: int | None = None
    projects_done: int = 0
    lobbying_stages: int = 0

    def error(self, kind):
        self.counters[kind] += 1
        self.consecutive_errors += 1
        if self.consecutive_errors >= CONSECUTIVE_ERROR_LIMIT:
            raise RclStop('too_many_errors', kind)

    def ok(self):
        self.consecutive_errors = 0

    def type_failed(self, type_id):
        """Strona projektu albo katalogu nie ma oczekiwanej struktury.  Rodzaj aktu, w którym kolejne 3 odczyty zawiodły
        bez żadnego sukcesu, wypada z tego przebiegu (np. inny układ strony dla innego typeId), a reszta idzie dalej."""
        self.counters['parse_errors'] += 1
        self.type_failures[type_id] += 1

    def type_ok(self, type_id):
        self.type_successes[type_id] += 1
        self.type_failures[type_id] = 0

    def skipped_types(self):
        return [t for t, n in self.type_failures.items() if n >= MAX_FAILURES and not self.type_successes[t]]


def _state(name):
    state, _ = ImportState.objects.get_or_create(name=name)
    return state


def _event(kind, url='', status=None, **detail):
    RclFetchEvent.objects.create(kind=kind, url=rcl_guard._safe_path(url), http_status=status, detail=detail)


# --- wersjonowanie ---

def _plain(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _differences(instance, new, fields):
    out = {}
    for name in fields:
        if name in new and getattr(instance, name) != new[name]:
            out[name] = [_plain(getattr(instance, name)), _plain(new[name])]
    return out


def _log(project, entity, key, kind, changes, fetched_at, url):
    LegislativeChange.objects.create(project=project, entity=entity, entity_key=str(key), kind=kind,
                                     changes=changes, fetched_at=fetched_at, source_url=url[:1024])


# --- lista ---

def upsert_list_row(row, type_id, label, fetched_at, priority):
    """Podsumowanie projektu z listy.  Zwraca 'created', 'changed' albo 'same'."""
    url = LegislativeProject.url_for(row['rcl_id'])
    new = {'title': row['title'][:1000], 'applicant': row['applicant'][:300], 'wykaz_number': row['wykaz_number'][:40],
           'wykaz_url': row['wykaz_url'][:1024], 'created_on': row['created_on'], 'list_modified_on': row['modified_on']}
    with transaction.atomic():
        project = LegislativeProject.objects.select_for_update().filter(rcl_id=row['rcl_id']).first()
        if project is None:
            project = LegislativeProject.objects.create(
                rcl_id=row['rcl_id'], act_type_id=type_id, act_type=label, source_url=url, list_fetched_at=fetched_at,
                needs_refresh=True, refresh_priority=priority, **new)
            _log(project, 'project', project.rcl_id, 'created', {k: [None, _plain(v)] for k, v in new.items() if v}, fetched_at, url)
            return 'created'
        changes = _differences(project, new, PROJECT_LIST_FIELDS)
        # Projekt mógł zmienić rodzaj (inny typeId na liście); zapisujemy to jak każdą zmianę.
        if project.act_type_id != type_id:
            changes['act_type_id'] = [project.act_type_id, type_id]
            project.act_type_id, project.act_type = type_id, label
        for name in PROJECT_LIST_FIELDS:
            setattr(project, name, new[name])
        project.list_fetched_at = fetched_at
        if 'list_modified_on' in changes or project.fetched_at is None:
            project.needs_refresh = True
            project.refresh_priority = max(project.refresh_priority, priority)
        if changes:
            _log(project, 'project', project.rcl_id, 'changed', changes, fetched_at, url)
        project.save()
        return 'changed' if changes else 'same'


def _type_label(type_id, parsed):
    return (parsed.types.get(type_id)
            or dict(LegislativeProject.ActType.choices).get(type_id, ''))[:80]


def _fetch_list(client, run, type_id, page, key, order):
    url = list_url(type_id, page, key, order)
    response = client.get(url)
    if response.status != 200:
        run.error('list_http_error')
        return None, None
    try:
        parsed = rcl_parser.parse_list(response.text)
    except RclParseError as exc:
        _event('parse_error', url, response.status, page='list', reason=str(exc))
        run.error('parse_errors')
        return None, None
    run.ok()
    run.counters['list_pages'] += 1
    return parsed, response


def _count(run, outcome):
    if outcome != 'same':
        run.counters['projects_' + outcome] += 1


def news_pass(client, run, type_id):
    """Nowości i zmiany: lista wg daty modyfikacji malejąco, do znacznika sprzed ostatniego pełnego przejścia."""
    state = _state(f'rcl:news:{type_id}')
    raw = (state.cursor or {}).get('watermark')
    watermark = date.fromisoformat(raw) if raw else None
    max_pages = 1 if watermark is None else env_int('RCL_NEWS_MAX_PAGES', 20, 1, 100)
    newest, page, reached = None, 1, watermark is None
    while page <= max_pages:
        try:
            parsed, response = _fetch_list(client, run, type_id, page, 'modifiedDate', 'desc')
        except RclTransient:
            run.error('transient_errors')
            return
        if parsed is None:
            return
        label = _type_label(type_id, parsed)
        for row in parsed.rows:
            if row['modified_on'] and (newest is None or row['modified_on'] > newest):
                newest = row['modified_on']
            if watermark and row['modified_on'] and row['modified_on'] < watermark - timedelta(days=1):
                reached = True
                break
            _count(run, upsert_list_row(row, type_id, label, response.fetched_at, 1))
        if reached or len(parsed.rows) < PAGE_SIZE:
            reached = True
            break
        page += 1
    if newest and reached:
        state.cursor = {**(state.cursor or {}), 'watermark': newest.isoformat()}
        state.last_success = timezone.now()
        state.save(update_fields=['cursor', 'last_success'])


def archive_list_pass(client, run, type_id, pages):
    """Archiwum: lista wg daty utworzenia rosnąco, od zapisanej strony; po dojściu do końca ponowne przejście po 30 dniach."""
    state = _state(f'rcl:archive:{type_id}')
    cursor = dict(state.cursor or {})
    if cursor.get('complete'):
        done_at = cursor.get('complete_at')
        if not done_at or timezone.now() - datetime.fromisoformat(done_at) < timedelta(days=30):
            return
        cursor = {}
    page = int(cursor.get('page') or 1)
    for _ in range(pages):
        try:
            parsed, response = _fetch_list(client, run, type_id, page, 'createDate', 'asc')
        except RclTransient:
            run.error('transient_errors')
            return
        if parsed is None:
            return
        label = _type_label(type_id, parsed)
        for row in parsed.rows:
            _count(run, upsert_list_row(row, type_id, label, response.fetched_at, 0))
        last = len(parsed.rows) < PAGE_SIZE
        cursor.update(page=page if last else page + 1, total=parsed.total, complete=last)
        if last:
            cursor['complete_at'] = timezone.now().isoformat()
        state.cursor, state.last_success = cursor, timezone.now()
        state.save(update_fields=['cursor', 'last_success'])
        if last:
            return
        page += 1


# --- projekt, etapy, dokumenty ---

def _stage_needs_catalog(stage):
    if not stage.catalog_url:
        return False
    if stage.catalog_fetched_at is None or stage.modified_on != stage.catalog_modified_seen:
        return True
    recheck = env_int('RCL_ACTIVE_RECHECK_DAYS', 7, 1, 90)
    return stage.state == 'active' and timezone.now() - stage.catalog_fetched_at > timedelta(days=recheck)


def apply_project_page(project_id, page, fetched_at, url):
    """Zapisuje stronę projektu i jego etapy; zwraca (projekt, lista etapów do pobrania katalogu)."""
    with transaction.atomic():
        project = LegislativeProject.objects.select_for_update().get(pk=project_id)
        new = {name: page[name] for name in PROJECT_DETAIL_FIELDS}
        new['title'] = new['title'][:1000]
        new['applicant'] = new['applicant'][:300]
        changes = _differences(project, new, PROJECT_DETAIL_FIELDS)
        for name in PROJECT_DETAIL_FIELDS:
            setattr(project, name, new[name])
        digest = sha256(json.dumps({**{k: _plain(new[k]) for k in PROJECT_DETAIL_FIELDS},
                                     'stages': [{k: _plain(v) for k, v in s.items()} for s in page['stages']]},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        project.content_hash, project.fetched_at, project.source_url = digest, fetched_at, url
        type_label = page['types'].get(project.act_type_id)
        if type_label and not project.act_type:
            project.act_type = type_label[:80]
        if changes:
            _log(project, 'project', project.rcl_id, 'changed', changes, fetched_at, url)
        project.save()
        wanted = []
        for item in page['stages']:
            stage = LegislativeStage.objects.filter(project=project, rcl_id=item['rcl_id']).first()
            if stage is None:
                stage = LegislativeStage.objects.create(project=project, **{k: item[k] for k in ('rcl_id', *STAGE_FIELDS)})
                _log(project, 'stage', stage.rcl_id, 'created', {k: [None, _plain(item[k])] for k in STAGE_FIELDS if item[k]}, fetched_at, url)
            else:
                diff = _differences(stage, item, STAGE_FIELDS)
                for name in STAGE_FIELDS:
                    setattr(stage, name, item[name])
                stage.last_seen_at = fetched_at
                stage.save()
                if diff:
                    _log(project, 'stage', stage.rcl_id, 'changed', diff, fetched_at, url)
            if _stage_needs_catalog(stage):
                wanted.append(stage)
        wanted.sort(key=lambda s: (s.modified_on or date.min, s.rcl_id), reverse=True)
        return project, wanted


def apply_catalog(project, stage, catalog, fetched_at, url):
    """Dokumenty etapu; dokumenty, które zniknęły ze strony, oznaczamy (nie kasujemy) i dopisujemy do dziennika."""
    counts = Counter()
    with transaction.atomic():
        seen = set()
        for item in catalog['documents']:
            seen.add(item['rcl_doc_id'])
            new = {k: item[k] for k in DOCUMENT_FIELDS}
            new['name'], new['author'] = new['name'][:500], new['author'][:300]
            doc = LegislativeDocument.objects.filter(project=project, rcl_doc_id=item['rcl_doc_id']).first()
            if doc is None:
                doc = LegislativeDocument.objects.create(
                    project=project, stage=stage, rcl_doc_id=item['rcl_doc_id'], source_page_url=url, fetched_at=fetched_at, **new)
                _log(project, 'document', doc.rcl_doc_id, 'created', {k: [None, _plain(v)] for k, v in new.items() if v}, fetched_at, url)
                counts['docs_new'] += 1
                continue
            diff = _differences(doc, new, DOCUMENT_FIELDS)
            if doc.stage_id != stage.pk:
                diff['stage'] = [doc.stage.rcl_id if doc.stage_id else None, stage.rcl_id]
            kind = 'changed'
            if doc.removed_at is not None:
                kind, diff['removed_at'] = 'reappeared', [_plain(doc.removed_at), None]
                doc.removed_at = None
            for name in DOCUMENT_FIELDS:
                setattr(doc, name, new[name])
            doc.stage, doc.source_page_url, doc.fetched_at, doc.last_seen_at = stage, url, fetched_at, fetched_at
            doc.save()
            if diff:
                _log(project, 'document', doc.rcl_doc_id, kind, diff, fetched_at, url)
                counts['docs_changed'] += 1
        for doc in LegislativeDocument.objects.filter(project=project, stage=stage, removed_at__isnull=True).exclude(rcl_doc_id__in=seen):
            doc.removed_at = fetched_at
            doc.save(update_fields=['removed_at'])
            _log(project, 'document', doc.rcl_doc_id, 'removed', {'removed_at': [None, _plain(fetched_at)]}, fetched_at, url)
            counts['docs_removed'] += 1
        stage.catalog_fetched_at, stage.catalog_modified_seen = fetched_at, stage.modified_on
        stage.save(update_fields=['catalog_fetched_at', 'catalog_modified_seen'])
    return counts


def _failed(project, reason):
    LegislativeProject.objects.filter(pk=project.pk).update(
        refresh_failures=project.refresh_failures + 1, last_error=reason[:120])


def refresh_project(client, run, project):
    """Strona projektu (1 zapytanie) i katalogi etapów, których dotyczy zmiana."""
    page_url = absolute_url(f'/projekt/{project.rcl_id}')
    try:
        response = client.get(page_url)
        if response.status != 200:
            raise RclTransient(f'http_{response.status}')
        page = rcl_parser.parse_project(response.text, project.rcl_id)
    except RclParseError as exc:
        _event('parse_error', page_url, None, page='project', reason=str(exc))
        _failed(project, f'parse:{exc}')
        run.type_failed(project.act_type_id)
        return
    except RclTransient as exc:
        _failed(project, f'transient:{exc}')
        run.error('transient_errors')
        return
    project, wanted = apply_project_page(project.pk, page, response.fetched_at, page_url)
    run.type_ok(project.act_type_id)
    run.counters['projects_refreshed'] += 1
    run.projects_done += 1
    run.stage_names.update(s['name'] for s in page['stages'])
    complete = True
    for stage in wanted:
        try:
            catalog_response = client.get(stage.catalog_url)
            if catalog_response.status != 200:
                raise RclTransient(f'http_{catalog_response.status}')
            catalog = rcl_parser.parse_stage_catalog(catalog_response.text, stage.rcl_id)
        except RclParseError as exc:
            _event('parse_error', stage.catalog_url, None, page='catalog', reason=str(exc))
            run.type_failed(project.act_type_id)
            complete = False
            continue
        except RclTransient as exc:
            run.error('transient_errors')
            complete = False
            _failed(project, f'transient:{exc}')
            continue
        counts = apply_catalog(project, stage, catalog, catalog_response.fetched_at, catalog_response.url)
        run.ok()
        run.counters.update(counts)
        run.counters['catalogs_read'] += 1
        run.folder_names.update(f['name'] for f in catalog['folders'])
        if catalog['stage']['kind'] == 'lobbing':
            run.lobbying_stages += 1
    if complete:
        LegislativeProject.objects.filter(pk=project.pk).update(
            needs_refresh=False, refresh_priority=0, refresh_failures=0, last_error='')
        run.ok()


def drain_queue(client, run, *, priority_min=None, limit=None):
    while limit is None or run.projects_done < limit:
        queue = (LegislativeProject.objects.filter(needs_refresh=True, refresh_failures__lt=MAX_FAILURES)
                 .exclude(pk__in=run.attempted).exclude(act_type_id__in=run.skipped_types()))
        if priority_min is not None:
            queue = queue.filter(refresh_priority__gte=priority_min)
        project = queue.order_by('-refresh_priority', '-list_modified_on', '-rcl_id').first()
        if project is None:
            return
        run.attempted.add(project.pk)
        refresh_project(client, run, project)


# --- przebieg nocy ---

def run_with_client(client, *, types=None, recon=False, archive_pages=None):
    """Cały przebieg na podanym kliencie (prawdziwym albo z plików).  Zawsze zwraca podsumowanie, nie rzuca RclStop."""
    run = Run(recon_projects=4 if recon else None)
    types = tuple(types or type_ids())
    pages = archive_pages if archive_pages is not None else env_int('RCL_ARCHIVE_LIST_PAGES_PER_NIGHT', 30, 0, 200)
    try:
        for type_id in types:
            news_pass(client, run, type_id)
        drain_queue(client, run, priority_min=1, limit=run.recon_projects)
        if not recon:
            for type_id in types:
                archive_list_pass(client, run, type_id, pages)
            drain_queue(client, run)
            fetch_files(client, run, env_int('RCL_FILES_PER_NIGHT', 200, 1, 2000))
    except RclStop as stop:
        run.stopped = stop.reason
    summary = {
        'stopped': run.stopped or 'finished',
        'requests': client.requests_made,
        'counters': dict(run.counters),
        'skipped_types_after_parse_failures': run.skipped_types(),
        'folder_names': dict(run.folder_names.most_common(40)),
        'stage_names': dict(run.stage_names.most_common(40)),
        'lobbying_stages_read': run.lobbying_stages,
        'robots_override_used': getattr(client, 'robots_override_used', False),
    }
    return summary


def _night_state(now):
    state = _state('rcl:night')
    cursor = dict(state.cursor or {})
    today = rcl_guard.local_now(now).date().isoformat()
    if cursor.get('date') != today:
        cursor = {'date': today, 'used': 0}
    return state, cursor


def run_night(*, seconds=None, recon=False, budget=None, dump_dir=None, now=None, sleep=time.sleep, monotonic=time.monotonic):
    """Jedna porcja nocnego zbierania (zadanie Celery woła ją co kilka minut w oknie 01:05-05:55)."""
    now = now or timezone.now()
    if not rcl_guard.fetch_enabled():
        return {'status': 'disabled', 'requests': 0}
    if not rcl_guard.window_open(now, allowance_seconds=rcl_guard.REQUEST_ALLOWANCE_SECONDS):
        return {'status': 'outside_window', 'requests': 0}
    until = rcl_guard.halted_until(now)
    if until is not None:
        return {'status': 'halted', 'until': until.isoformat(), 'requests': 0}
    source, instruction = configured_access()
    if instruction is None:
        return {'status': 'no_access_card', 'requests': 0}
    state, night = _night_state(now)
    budget = budget if budget is not None else nightly_budget()
    left = budget - night['used']
    if left <= 0:
        return {'status': 'budget_exhausted', 'requests': 0}
    client = RclClient(source, instruction, request_budget=left, sleep=sleep, monotonic=monotonic,
                       robots_override=robots_override(), deadline_seconds=seconds, dump_dir=dump_dir)
    summary = run_with_client(client, recon=recon)
    summary['status'] = 'ran'
    night['used'] += client.requests_made
    state.cursor = night
    state.save(update_fields=['cursor'])
    if summary['stopped'] not in ('slice_end', 'finished', 'budget'):
        _event('run_stopped', '', None, **{k: summary[k] for k in ('stopped', 'requests', 'counters')})
    done = _state('rcl:last-run')
    done.cursor, done.last_started, done.last_success = summary, now, timezone.now()
    done.save(update_fields=['cursor', 'last_started', 'last_success'])
    return summary


# --- pliki (opcjonalny krok, domyślnie wyłączony; te same okno, odstęp i budżet co reszta) ---

def files_enabled():
    return os.environ.get('RCL_FILES_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def files_dir():
    from django.conf import settings
    return Path(os.environ.get('RCL_FILES_DIR') or Path(settings.BASE_DIR) / 'var' / 'rcl_files')


def fetch_files(client, run, limit):
    """Pobiera pliki dokumentów (domyślnie tylko PDF) na dysk i zapisuje skrót SHA-256 oraz rozmiar; treści nie analizuje."""
    if not files_enabled():
        return
    extensions = [x.strip().lower() for x in (os.environ.get('RCL_FILES_EXTENSIONS') or 'pdf').split(',') if x.strip()]
    queue = (LegislativeDocument.objects.filter(file_fetched_at__isnull=True, removed_at__isnull=True, file_ext__in=extensions)
             .select_related('project').order_by('-created_on', '-rcl_doc_id'))
    for doc in queue[:limit]:
        try:
            response = client.get(doc.file_url)
        except RclTransient as exc:
            if 'too large' in str(exc).lower():
                LegislativeDocument.objects.filter(pk=doc.pk).update(file_fetched_at=timezone.now(), file_size=0)
            run.error('transient_errors')
            continue
        if response.status != 200:
            LegislativeDocument.objects.filter(pk=doc.pk).update(file_fetched_at=response.fetched_at, file_size=0)
            continue
        target = files_dir() / str(doc.project.rcl_id)
        target.mkdir(parents=True, exist_ok=True)
        (target / f'{doc.rcl_doc_id}.{doc.file_ext}').write_bytes(response.body)
        LegislativeDocument.objects.filter(pk=doc.pk).update(
            file_fetched_at=response.fetched_at, file_sha256=response.sha256, file_size=len(response.body))
        run.counters['files_fetched'] += 1
        run.ok()


# --- tryb offline na fixtures ---

class FixtureClient:
    """Udaje klienta RCL na podstawie plików z scraper/fixtures/rcl; niczego nie wysyła."""

    def __init__(self, directory=None):
        self.directory = Path(directory or Path(__file__).parent / 'fixtures' / 'rcl')
        self.requests_made = 0
        self.robots_override_used = False
        self.catalogs = {}
        for path in sorted(self.directory.glob('katalog_*.html')):
            dom = rcl_parser.build_dom(path.read_text(encoding='utf-8'))
            for node in rcl_parser.timeline_nodes(dom):
                if node.find('li', cls='doc') or node.find('li', cls='childdir'):
                    self.catalogs.setdefault(int(node.get('id')), path)

    def get(self, path_or_url, *, kind=FetchAttempt.RequestedKind.PAGE):
        url = absolute_url(path_or_url)
        self.requests_made += 1
        now = timezone.now()
        path = url.split(rcl_guard.RCL_HOST, 1)[1]
        if path.startswith('/lista'):
            found = self.directory / 'lista_typ2.html'
        elif '/katalog/' in path:
            # Etap bez kopii katalogu: strona projektu z tym etapem zwinięta daje pusty katalog.
            found = self.catalogs.get(int(path.rsplit('/', 1)[1])) or self.directory / 'projekt_12414050.html'
        elif path.startswith('/projekt/'):
            found = self.directory / ('katalog_13223895_konsultacje_z_uwagami.html' if path.endswith(f'/{DEMO_PROJECT}')
                                      else 'projekt_12414050.html')
        else:
            found = None
        return RclResponse(url, 200 if found else 404, found.read_bytes() if found else b'', now)


DEMO_PROJECT = 12414100   # projekt z kopią katalogu konsultacji w fixtures


def dry_run():
    """Przebieg na plikach testowych w transakcji, która jest wycofywana: pokazuje, co zostałoby zapisane."""
    client = FixtureClient()
    with transaction.atomic():
        upsert_list_row({'rcl_id': DEMO_PROJECT, 'title': 'Projekt demonstracyjny z fixtures', 'applicant': '', 'applicant_id': '',
                         'wykaz_number': '', 'wykaz_url': '', 'created_on': None, 'modified_on': date(2026, 9, 1)},
                        2, 'Projekty ustaw', timezone.now(), 1)
        summary = run_with_client(client, types=(2,), archive_pages=1)
        summary['status'] = 'dry_run'
        summary['would_store'] = {
            'projects': LegislativeProject.objects.count(), 'stages': LegislativeStage.objects.count(),
            'documents': LegislativeDocument.objects.count(), 'changes': LegislativeChange.objects.count()}
        transaction.set_rollback(True)
    return summary
