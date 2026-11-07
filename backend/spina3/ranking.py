"""Ściana: migawka rankingu co 10 minut, kursor z wersją, wymiary, wyszukiwanie, półka podobnych, rząd "Dziś".

Migawka jest niezmienna: kursor oparty na kluczu (poziom, last_rating_at, n, id) zachowuje pozycję, a gdy wersja
wygasła, odpowiedź wraca z najnowszą wersją i tym samym kluczem (klient trzyma wersję do odświeżenia).
Kolejność: sekcje P5..P1 (w sekcji ostatnia ZAUFANA ocena malejąco, n, id), "Otwarta" na końcu najnowsze pierwsze.
Limit udziału (TOP_CAP): w sekcji P5 na pierwszym ekranie najwyżej 2 boxy jednego autora i 40% jednej partii.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from . import scoring
from .config import LEVELS, OPEN, ScoringConfig, config, election_silence, flags
from .models import Box, BoxLink, BoxSpinka, Comment, Pin, RankingSnapshot, Rating
from .public import box_item
from .text import normalize, tokens

PERIOD_BUCKETS = (7, 30, 90, 365)
DOC_KINDS = ('document', 'voting', 'legal_act')


def wall_boxes(period_days: int | None, now=None, cfg: ScoringConfig | None = None):
    cfg = cfg or config()
    now = now or timezone.now()
    qs = Box.objects.filter(status='published')
    days = period_days if period_days is not None else cfg.default_period_days
    if days > 0:
        qs = qs.filter(published_at__gte=now - timedelta(days=days))
    return qs


def _entry(box: Box, sp: BoxSpinka | None, has_diag: bool) -> dict:
    level = sp.level if sp else OPEN
    return {
        'id': box.pk, 'level': level, 'lp': (sp.last_rating_at.timestamp() if sp and sp.last_rating_at else 0.0),
        'n': sp.n if sp else 0, 'pub': box.published_at.timestamp() if box.published_at else 0.0,
        'kind': box.kind, 'sub': box.subtype, 'topic': box.topic, 'persons': [p.get('id') for p in (box.persons or []) if p.get('id')],
        'diag': has_diag, 'author': box.author_handle or box.author_name, 'group': box.author_group, 'domain': box.source_domain,
        'added': box.created_at.timestamp() if box.created_at else 0.0, 'by': box.added_by,
    }


def _published_at(entry):
    from datetime import datetime, timezone as dt_tz
    return datetime.fromtimestamp(entry['pub'], tz=dt_tz.utc)


def _last_pin(entry):
    from datetime import datetime, timezone as dt_tz
    return datetime.fromtimestamp(entry['lp'], tz=dt_tz.utc) if entry['lp'] else None


def level_key(entry) -> tuple:
    return scoring.sort_key(entry['level'], _last_pin(entry), entry['n'], entry['id'], _published_at(entry))


def newest_key(entry) -> tuple:
    return scoring.newest_key(_published_at(entry), entry['id'])


def apply_top_cap(entries: list[dict], cfg: ScoringConfig) -> list[dict]:
    """Na pierwszym ekranie sekcji P5: najwyżej 2 boxy jednego autora i 40% jednej partii; nadwyżka niżej w tej samej sekcji."""
    top = [e for e in entries if e['level'] == 'P5']
    rest = [e for e in entries if e['level'] != 'P5']
    if len(top) <= 1:
        return entries
    first, deferred = [], []
    authors, groups = Counter(), Counter()
    cap_group = max(1, int(cfg.top_cap_group_share * cfg.first_screen))
    for entry in top:
        if len(first) >= cfg.first_screen:
            deferred.append(entry)
            continue
        author, group = entry.get('author') or '', entry.get('group') or ''
        if (author and authors[author] >= cfg.top_cap_per_author) or (group and groups[group] >= cap_group):
            deferred.append(entry)
            continue
        first.append(entry)
        if author:
            authors[author] += 1
        if group:
            groups[group] += 1
    return first + deferred + rest


def build_snapshot(now=None, period_days: int | None = None, cfg: ScoringConfig | None = None) -> RankingSnapshot:
    cfg = cfg or config()
    now = now or timezone.now()
    days = period_days if period_days is not None else cfg.default_period_days
    boxes = list(wall_boxes(days, now, cfg).select_related('spinka'))
    diag_ids = set(BoxLink.objects.filter(kind='diagnosis_of', is_current=True, box__in=boxes).values_list('box_id', flat=True))
    entries = [_entry(b, getattr(b, 'spinka', None), b.pk in diag_ids) for b in boxes]
    entries.sort(key=level_key)
    entries = apply_top_cap(entries, cfg)
    rated = sum(1 for e in entries if e['level'] in LEVELS)
    snapshot = RankingSnapshot.objects.create(
        created_at=now, mode=cfg.mode, period_days=days, box_count=len(entries),
        rated_share=(rated / len(entries)) if entries else 0.0, entries=entries)
    prune_snapshots(now, cfg)
    return snapshot


def prune_snapshots(now=None, cfg: ScoringConfig | None = None) -> int:
    """Ostatnie `snapshot_keep` w całości, potem jedna na dobę przez `snapshot_retention_days` (dowód metodologii)."""
    cfg = cfg or config()
    now = now or timezone.now()
    keep_ids = set(RankingSnapshot.objects.order_by('-pk').values_list('pk', flat=True)[:cfg.snapshot_keep])
    seen_days = set()
    for pk, created in RankingSnapshot.objects.order_by('-pk').values_list('pk', 'created_at'):
        if pk in keep_ids:
            continue
        day = created.date()
        if day not in seen_days and created >= now - timedelta(days=cfg.snapshot_retention_days):
            seen_days.add(day)
            keep_ids.add(pk)
    deleted, _ = RankingSnapshot.objects.exclude(pk__in=keep_ids).delete()
    return deleted


def latest_snapshot(now=None, period_days: int | None = None, cfg: ScoringConfig | None = None) -> RankingSnapshot:
    cfg = cfg or config()
    now = now or timezone.now()
    days = period_days if period_days is not None else cfg.default_period_days
    snapshot = RankingSnapshot.objects.filter(period_days=days, mode=cfg.mode).order_by('-pk').first()
    if snapshot is None or snapshot.created_at < now - timedelta(seconds=cfg.snapshot_interval_seconds):
        return build_snapshot(now, days, cfg)
    return snapshot


# --- filtrowanie ---------------------------------------------------------------------------------------------

def _matches(entry: dict, kind: str | None, facets: dict, now) -> bool:
    if kind and kind != 'all':
        if kind == 'documents':
            if entry['kind'] not in DOC_KINDS:
                return False
        elif entry['kind'] != kind:
            return False
    if facets.get('person') and not set(map(str, entry['persons'])) & set(map(str, facets['person'])):
        return False
    if facets.get('topic') and entry['topic'] not in facets['topic']:
        return False
    if facets.get('level') and entry['level'] not in facets['level']:
        return False
    if facets.get('doc_kind') and entry['sub'] not in facets['doc_kind'] and entry['domain'] not in facets['doc_kind']:
        return False
    if facets.get('with_diagnosis') and not entry['diag']:
        return False
    if facets.get('period'):
        try:
            days = int(facets['period'][0])
        except (TypeError, ValueError, IndexError):
            days = 0
        if days and _published_at(entry) < now - timedelta(days=days):
            return False
    return True


def parse_facets(params) -> dict:
    out = {}
    for key in ('person', 'topic', 'level', 'doc_kind', 'period'):
        values = params.getlist(key) if hasattr(params, 'getlist') else params.get(key)
        if isinstance(values, str):
            values = [values]
        if values:
            out[key] = [v for raw in values for v in str(raw).split(',') if v]
    if str(params.get('with_diagnosis', '')).lower() in ('1', 'true', 'tak'):
        out['with_diagnosis'] = True
    return out


def wall(*, cursor: str | None, sort: str | None, kind: str | None, facets: dict, limit: int | None = None,
         period_days: int | None = None, now=None, user=None, cfg: ScoringConfig | None = None) -> dict:
    cfg = cfg or config()
    now = now or timezone.now()
    limit = min(limit or cfg.batch_size, cfg.batch_size)
    silence = election_silence(now)['active']
    requested_version, cursor_key = (None, None)
    if cursor:
        decoded = scoring.decode_cursor(cursor)
        if decoded is None:
            return {'error': 'Nieprawidłowy kursor.', 'status': 400}
        requested_version, cursor_key = decoded
    snapshot = None
    if requested_version is not None:
        snapshot = RankingSnapshot.objects.filter(pk=requested_version).first()
    if snapshot is None:
        snapshot = latest_snapshot(now, period_days, cfg)
    sort_mode = scoring.effective_sort(sort, snapshot.rated_share, cfg, silence)
    entries = [e for e in snapshot.entries if _matches(e, kind, facets, now)]
    if sort_mode == 'today':
        ids = [e['id'] for e in today_row(now, cfg)]
        order = {box_id: i for i, box_id in enumerate(ids)}
        entries = sorted([e for e in entries if e['id'] in order], key=lambda e: order[e['id']])
        key_fn = lambda e: (order[e['id']],)  # noqa: E731
    elif sort_mode == 'newest':
        key_fn = newest_key
        entries.sort(key=key_fn)
    else:
        key_fn = level_key  # kolejność z migawki (z TOP_CAP) już jest wg tego klucza
    if cursor_key is not None:
        entries = [e for e in entries if tuple(key_fn(e)) > tuple(cursor_key)] if sort_mode != 'level' else \
            _after_level_cursor(entries, cursor_key)
    page = entries[:limit]
    has_more = len(entries) > limit
    items = _serialize(page, user)
    next_cursor = scoring.encode_cursor(snapshot.pk, tuple(key_fn(page[-1]))) if (has_more and page) else None
    sections = _sections(page) if sort_mode == 'level' and not silence and flags().levels_visible else []
    return {
        'items': items, 'next_cursor': next_cursor, 'version': snapshot.pk, 'snapshot_at': snapshot.created_at.isoformat(),
        'sort': sort_mode, 'rated_share': round(snapshot.rated_share, 3), 'period_days': snapshot.period_days,
        'sections': sections, 'wall_end': not has_more, 'election_silence': silence,
        'end_message': ('To wszystko z %d dni. Jutro o %d:00 nowy rząd Dziś.' % (snapshot.period_days, cfg.today_hour)) if not has_more else '',
    }


def _after_level_cursor(entries: list[dict], cursor_key: tuple) -> list[dict]:
    """Migawka ma własną kolejność (TOP_CAP): szukamy pozycji wpisu o kluczu równym kursorowi; gdy go nie ma (nowa
    wersja), pierwszej pozycji o kluczu większym."""
    keys = [tuple(level_key(e)) for e in entries]
    for index, key in enumerate(keys):
        if key == tuple(cursor_key):
            return entries[index + 1:]
    for index, key in enumerate(keys):
        if key > tuple(cursor_key):
            return entries[index:]
    return []


def _sections(page: list[dict]) -> list[dict]:
    counts = Counter(e['level'] for e in page)
    order = [*reversed(LEVELS), OPEN]
    return [{'level': lv, 'count': counts[lv]} for lv in order if counts[lv]]


def tile_context(boxes: list[Box], user) -> tuple[dict, dict, dict]:
    """Jedno zapytanie na stronę: przypięcia (jedyne per box), moje oceny, liczby komentarzy."""
    from django.db.models import Count
    ids = [b.pk for b in boxes]
    pins = {p.box_id: p for p in Pin.objects.filter(box_id__in=ids).exclude(status='removed')
            .select_related('user__spina3_profile', 'pinned_box')}
    my = {}
    if user is not None and getattr(user, 'is_authenticated', False):
        my = dict(Rating.objects.filter(user=user, box_id__in=ids, status='active').values_list('box_id', 'stance'))
    counts = dict(Comment.objects.filter(box_id__in=ids, status='visible').values_list('box_id').annotate(c=Count('id')).values_list('box_id', 'c'))
    return pins, my, counts


def _serialize(entries: list[dict], user) -> list[dict]:
    ids = [e['id'] for e in entries]
    boxes = {b.pk: b for b in Box.objects.filter(pk__in=ids).select_related('spinka')}
    pins, my, counts = tile_context(list(boxes.values()), user)
    items = []
    for entry in entries:
        box = boxes.get(entry['id'])
        if box is None:
            continue
        items.append(box_item(box, getattr(box, 'spinka', None), my_rating=my.get(box.pk), has_diagnosis=entry['diag'],
                              pin=pins.get(box.pk), comment_count=counts.get(box.pk, 0)))
    return items


# --- wymiary --------------------------------------------------------------------------------------------------

def facets(kind: str | None = None, period_days: int | None = None, now=None, cfg: ScoringConfig | None = None) -> dict:
    """Liczności wymiarów; wymiar istnieje tylko, gdy co najmniej 5% boxów ma wartość (PETLA 3, anty-Excel)."""
    cfg = cfg or config()
    now = now or timezone.now()
    snapshot = latest_snapshot(now, period_days, cfg)
    entries = [e for e in snapshot.entries if _matches(e, kind, {}, now)]
    total = len(entries) or 1
    persons, topics, levels, docs, diag = Counter(), Counter(), Counter(), Counter(), 0
    periods = Counter()
    names = {}
    for e in entries:
        for pid in e['persons']:
            persons[pid] += 1
        if e['topic']:
            topics[e['topic']] += 1
        levels[e['level']] += 1
        if e['kind'] in DOC_KINDS and e['sub']:
            docs[e['sub']] += 1
        elif e['domain']:
            docs[e['domain']] += 1
        if e['diag']:
            diag += 1
        age = (now - _published_at(e)).days
        for days in PERIOD_BUCKETS:
            if age <= days:
                periods[days] += 1
    if persons:
        for box in Box.objects.filter(pk__in=[e['id'] for e in entries if e['persons']]).only('persons'):
            for p in box.persons or []:
                if p.get('id'):
                    names[p['id']] = p.get('name', '')
    out = {'total': len(entries), 'dimensions': {}}

    def add(name, counter, label):
        covered = sum(counter.values()) if name != 'level' else total
        if counter and covered / total >= cfg.facet_min_share:
            out['dimensions'][name] = {'label': label, 'values': [
                {'value': v, 'label': names.get(v, v) if name == 'person' else (v if name != 'level' else {'open': 'Otwarta'}.get(v, v)),
                 'count': c} for v, c in counter.most_common(40)]}
    add('person', persons, 'Osoba lub podmiot')
    add('topic', topics, 'Temat')
    out['dimensions']['period'] = {'label': 'Okres', 'values': [{'value': str(d), 'label': f'{d} dni', 'count': periods[d]} for d in PERIOD_BUCKETS],
                                   'default': str(cfg.default_period_days)}
    add('level', levels, 'Poziom')
    add('doc_kind', docs, 'Rodzaj dokumentu lub źródło')
    if diag / total >= cfg.facet_min_share:
        out['dimensions']['with_diagnosis'] = {'label': 'Z diagnozą Dr. Spina', 'values': [{'value': 'true', 'label': 'tak', 'count': diag}]}
    out['views_reserved'] = ['dispute', 'consensus', 'hot', 'change']
    out['views_enabled'] = flags().views_enabled
    return out


# --- wyszukiwanie --------------------------------------------------------------------------------------------

def search(q: str, limit: int = 48, now=None, user=None) -> dict:
    words = tokens(q)[:8]
    if not words:
        return {'items': [], 'suggestions': [], 'query': q}
    qs = Box.objects.filter(status='published')
    for word in words:
        qs = qs.filter(search_text__contains=word)
    boxes = list(qs.select_related('spinka').order_by('-published_at')[:limit])
    diag_ids = set(BoxLink.objects.filter(kind='diagnosis_of', is_current=True, box__in=boxes).values_list('box_id', flat=True))
    pins, my, counts = tile_context(boxes, user)
    items = [box_item(b, getattr(b, 'spinka', None), my_rating=my.get(b.pk), has_diagnosis=b.pk in diag_ids,
                      pin=pins.get(b.pk), comment_count=counts.get(b.pk, 0)) for b in boxes]
    prefix = words[-1]
    suggestions = []
    for title in Box.objects.filter(status='published', search_text__contains=prefix).values_list('title', flat=True)[:50]:
        for word in title.split():
            if normalize(word).startswith(prefix) and len(word) > len(prefix):
                suggestions.append(word.strip('.,;:"'))
                break
        if len(suggestions) >= 5:
            break
    return {'items': items, 'suggestions': sorted(set(suggestions))[:5], 'query': q, 'normalized': ' '.join(words)}


# --- półka podobnych ----------------------------------------------------------------------------------------

def related(box: Box, limit: int = 6, user=None) -> list[dict]:
    """Do 6 podobnych: dla wpisu najpierw diagnoza i dokumenty źródłowe (półka dowodów), potem temat i wspólne osoby."""
    picked: list[Box] = []
    seen = {box.pk}
    for link in BoxLink.objects.filter(box=box, is_current=True, kind__in=('diagnosis_of', 'evidence_of')).select_related('target__spinka').order_by('kind'):
        if link.target.status == 'published' and link.target.pk not in seen:
            picked.append(link.target)
            seen.add(link.target.pk)
    if box.kind == 'diagnosis':
        for link in BoxLink.objects.filter(target=box, is_current=True, kind='diagnosis_of').select_related('box__spinka'):
            if link.box.status == 'published' and link.box.pk not in seen:
                picked.append(link.box)
                seen.add(link.box.pk)
    person_ids = [p.get('id') for p in (box.persons or []) if p.get('id')]
    candidates = Box.objects.filter(status='published').exclude(pk__in=seen)
    filters = Q()
    if box.topic:
        filters |= Q(topic=box.topic)
    if box.author_handle:
        filters |= Q(author_handle=box.author_handle)
    if filters:
        candidates = candidates.filter(filters)
    elif not person_ids:
        candidates = candidates.none()
    scored = []
    for candidate in candidates.select_related('spinka').order_by('-published_at')[:200]:
        shared = len(set(person_ids) & {p.get('id') for p in (candidate.persons or [])})
        score = (2 if box.topic and candidate.topic == box.topic else 0) + shared + (1 if candidate.author_handle and candidate.author_handle == box.author_handle else 0)
        if score:
            scored.append((score, candidate.published_at, candidate))
    if person_ids and not filters:
        for candidate in Box.objects.filter(status='published').exclude(pk__in=seen).order_by('-published_at')[:500]:
            shared = len(set(person_ids) & {p.get('id') for p in (candidate.persons or [])})
            if shared:
                scored.append((shared, candidate.published_at, candidate))
    scored.sort(key=lambda row: (-row[0], -(row[1].timestamp() if row[1] else 0)))
    for _, _, candidate in scored:
        if len(picked) >= limit:
            break
        if candidate.pk not in seen:
            picked.append(candidate)
            seen.add(candidate.pk)
    picked = picked[:limit]
    pins, my, counts = tile_context(picked, user)
    return [box_item(b, getattr(b, 'spinka', None), my_rating=my.get(b.pk), pin=pins.get(b.pk), comment_count=counts.get(b.pk, 0))
            for b in picked]


# --- Dziś ----------------------------------------------------------------------------------------------------

def today_cutoff(now, cfg: ScoringConfig | None = None):
    cfg = cfg or config()
    local = timezone.localtime(now)
    cutoff = local.replace(hour=cfg.today_hour, minute=0, second=0, microsecond=0)
    if local < cutoff:
        cutoff -= timedelta(days=1)
    return cutoff - timedelta(days=1), cutoff


def today_row(now=None, cfg: ScoringConfig | None = None) -> list[dict]:
    """7 boxów dodanych przez importer od wczorajszej godziny odcięcia: wpisy z zatwierdzoną diagnozą, potem dokumenty,
    potem reszta; ta sama lista dla wszystkich do jutra (deterministycznie)."""
    cfg = cfg or config()
    now = now or timezone.now()
    since, until = today_cutoff(now, cfg)
    boxes = list(Box.objects.filter(status='published', added_by__in=('dr_spin', 'importer'), created_at__gte=since, created_at__lt=until)
                 .exclude(kind='diagnosis').select_related('spinka'))
    diag_ids = set(BoxLink.objects.filter(kind='diagnosis_of', is_current=True, box__in=boxes).values_list('box_id', flat=True))

    def rank(box):
        if box.kind == 'post' and box.pk in diag_ids:
            return 0
        if box.kind in DOC_KINDS:
            return 1
        return 2
    boxes.sort(key=lambda b: (rank(b), -(b.published_at.timestamp() if b.published_at else 0), b.pk))
    picked, authors = [], Counter()
    for box in boxes:
        key = box.author_handle or box.author_name
        if key and authors[key] >= cfg.top_cap_per_author:
            continue
        picked.append(box)
        if key:
            authors[key] += 1
        if len(picked) >= cfg.today_size:
            break
    pins, _, counts = tile_context(picked, None)
    return [{'id': b.pk, **box_item(b, getattr(b, 'spinka', None), has_diagnosis=b.pk in diag_ids, pin=pins.get(b.pk),
                                     comment_count=counts.get(b.pk, 0))} for b in picked]
