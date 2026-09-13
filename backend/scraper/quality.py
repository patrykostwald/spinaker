"""Checks of metadata snapshots, not claims. Never rewrites source records.

New records have a monotonic cursor; a separate bounded pass revisits old metadata.
Reads happen outside write transactions. Each 50-record batch commits flags and its
cursor together. Later Article edits are reflected by a subsequent review pass.
"""
from datetime import timedelta
import time
import uuid
from django.db import transaction
from django.db.models import Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from news.models import Article, ImportState, QualityIssue
from scraper.utils import safe_url

CODES = {'missing_date', 'future_date', 'unclassified', 'possible_duplicate', 'invalid_url'}
BATCH_SIZE = 50
LEASE_SECONDS = 120
ARTICLE_FIELDS = ('pk', 'source_id', 'title', 'url', 'published_date', 'category')

def findings(article, now):
    issues = {}
    if article.published_date is None:
        issues['missing_date'] = {'message': 'Nie ustalono daty publikacji. To brak metadanych, nie ocena wiarygodności.'}
    elif article.published_date > now + timedelta(days=1):
        issues['future_date'] = {'published_date': article.published_date.isoformat(), 'message': 'Data publikacji ponad dobę w przyszłości — sprawdź źródło.'}
    if article.category == 'other':
        issues['unclassified'] = {'message': 'Brak ustalonego rodzaju materiału.'}
    if not safe_url(article.url):
        issues['invalid_url'] = {'message': 'Adres nie jest poprawnym publicznym odnośnikiem HTTP(S).'}
    if article.published_date and article.title:
        # Without the subquery SQLite may scan every article of this publisher
        # for every checked record. Use the existing title index first.
        title_ids = Article.objects.filter(title=article.title).order_by().values('pk')
        matches = list(Article.objects.filter(pk__in=Subquery(title_ids), source_id=article.source_id, title=article.title, published_date=article.published_date).exclude(pk=article.pk).order_by('pk').values_list('pk', flat=True)[:20])
        if matches:
            issues['possible_duplicate'] = {'other_article_ids': matches, 'message': 'To samo źródło, tytuł i data. Możliwy duplikat — bez automatycznego łączenia.'}
    return issues

def _acquire_scan():
    """A durable lease avoids two schedulers consuming the same cursor."""
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name='quality:metadata')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        now = timezone.now()
        cursor = dict(state.cursor)
        lease_until = parse_datetime(cursor.get('lease_until', ''))
        if (cursor.get('lease_id') and lease_until and
                timezone.is_aware(lease_until) and lease_until > now):
            return None
        highwater = max(0, int(cursor.get('last_pk', 0)))
        review_pk = max(0, int(cursor.get('review_pk', 0)))
        ceiling = max(0, int(cursor.get('review_ceiling', 0)))
        if review_pk >= ceiling:
            review_pk, ceiling = 0, highwater
        cursor.update(last_pk=highwater, review_pk=review_pk,
                      review_ceiling=ceiling, lease_id=uuid.uuid4().hex,
                      lease_until=(now + timedelta(seconds=LEASE_SECONDS)).isoformat())
        state.last_started = now
        state.cursor = cursor
        state.save(update_fields=['last_started', 'cursor'])
        return state.pk, cursor


def _persist_batch(state_id, cursor, rows, observed_at, lane, totals):
    """Flags and checkpoint either both commit or neither does."""
    with transaction.atomic():
        state = ImportState.objects.select_for_update().get(pk=state_id)
        if state.cursor.get('lease_id') != cursor['lease_id']:
            raise RuntimeError('Quality scan lease lost')
        existing = {(issue.article_id, issue.code): issue for issue in
                    QualityIssue.objects.filter(article_id__in=[pk for pk, _ in rows], code__in=CODES)}
        created, changed = [], []
        for article_id, issues in rows:
            for code in CODES:
                issue = existing.get((article_id, code))
                if issue is not None:
                    issue.active = code in issues
                    issue.last_checked = observed_at
                    if issue.active:
                        issue.evidence = issues[code]
                    changed.append(issue)
                elif code in issues:
                    created.append(QualityIssue(article_id=article_id, code=code,
                        evidence=issues[code], first_detected=observed_at, last_checked=observed_at))
        QualityIssue.objects.bulk_create(created, batch_size=BATCH_SIZE)
        QualityIssue.objects.bulk_update(changed, ['active', 'evidence', 'last_checked'], batch_size=BATCH_SIZE)
        next_cursor = dict(cursor)
        next_cursor['last_pk' if lane == 'new' else 'review_pk'] = rows[-1][0]
        next_cursor.update(totals)
        next_cursor['lease_until'] = (timezone.now() + timedelta(seconds=LEASE_SECONDS)).isoformat()
        state.cursor = next_cursor
        state.imported = totals['checked']
        state.last_success = timezone.now()
        state.last_error = ''
        state.save(update_fields=['cursor', 'imported', 'last_success', 'last_error'])
    return next_cursor


def _finish_scan(state_id, cursor, result, error=''):
    with transaction.atomic():
        state = ImportState.objects.select_for_update().get(pk=state_id)
        if state.cursor.get('lease_id') != cursor['lease_id']:
            return
        # Use the persisted cursor: an interrupted batch may not have committed.
        persisted = dict(state.cursor)
        persisted.pop('lease_id', None)
        persisted.pop('lease_until', None)
        persisted.update(result)
        state.cursor = persisted
        state.last_error = error[:200]
        if not error:
            state.last_success = timezone.now()
            state.imported = result['checked']
        state.save(update_fields=['cursor', 'last_error', 'last_success', 'imported'])


def scan_quality(limit=1000, *, max_seconds=5):
    """At most `limit` snapshots, in batches of 50; budget checked between batches.

    Ten percent of a normal run is reserved for old records before new work,
    so sustained imports cannot starve rechecks. The old pass has a fixed upper
    bound. Empty new work may use its quota for the remainder of that old pass.
    A single slow DB query cannot be interrupted by this cooperative time budget.
    """
    if not 1 <= limit <= 1000:
        raise ValueError('limit must be 1..1000')
    if not 0 < max_seconds <= 30:
        raise ValueError('max_seconds must be >0 and <=30')
    started = time.perf_counter()
    acquired = _acquire_scan()
    if acquired is None:
        return {'status': 'busy', 'checked': 0, 'findings': 0}
    state_id, cursor = acquired
    totals = {'checked': 0, 'findings': 0, 'new_checked': 0, 'reviewed': 0, 'batches': 0}
    read_ms = write_ms = max_write_ms = 0.0
    review_done = not cursor['review_ceiling']
    new_done = False
    review_quota = max(1, limit // 10) if limit > 1 and not review_done else 0
    error = ''
    try:
        while totals['checked'] < limit and time.perf_counter() - started < max_seconds:
            lane = 'review' if not review_done and (totals['reviewed'] < review_quota or new_done) else 'new'
            if lane == 'new' and new_done:
                break
            size = min(BATCH_SIZE, limit - totals['checked'])
            if lane == 'review' and not new_done:
                size = min(size, review_quota - totals['reviewed'])
            read_started = time.perf_counter()
            articles = Article.objects.order_by('pk').only(*ARTICLE_FIELDS)
            if lane == 'new':
                articles = articles.filter(pk__gt=cursor['last_pk'])
            else:
                articles = articles.filter(pk__gt=cursor['review_pk'], pk__lte=cursor['review_ceiling'])
            articles = list(articles[:size])
            observed_at = timezone.now()
            rows = [(article.pk, findings(article, observed_at)) for article in articles]
            read_ms += (time.perf_counter() - read_started) * 1000
            if not rows:
                if lane == 'new':
                    new_done = True
                else:
                    review_done = True
                    # All remaining IDs up to this frozen ceiling were deleted.
                    cursor['review_pk'] = cursor['review_ceiling']
                continue
            next_totals = dict(totals)
            next_totals['checked'] += len(rows)
            next_totals['findings'] += sum(len(issues) for _, issues in rows)
            next_totals['new_checked' if lane == 'new' else 'reviewed'] += len(rows)
            next_totals['batches'] += 1
            write_started = time.perf_counter()
            cursor = _persist_batch(state_id, cursor, rows, observed_at, lane, next_totals)
            duration = (time.perf_counter() - write_started) * 1000
            write_ms += duration
            max_write_ms = max(max_write_ms, duration)
            totals = next_totals
            if lane == 'review' and cursor['review_pk'] >= cursor['review_ceiling']:
                review_done = True
            # Yield the writer between short transactions when catching up.
            time.sleep(0.005)
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        result = dict(totals, elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                      read_ms=round(read_ms, 3), write_ms=round(write_ms, 3),
                      max_write_ms=round(max_write_ms, 3),
                      budget_exhausted=time.perf_counter() - started >= max_seconds)
        # Empty old ranges are safe to retire only after the corresponding read;
        # never copy the new-record cursor from uncommitted local state.
        if review_done:
            result['review_pk'] = cursor['review_ceiling']
        _finish_scan(state_id, cursor, result, error)
    return dict(result, status='ok')
