"""Resumable publisher archive discovery. Sitemap lastmod is never publication time."""
from datetime import datetime, timedelta, timezone as dt_timezone
from hashlib import sha256
import time
import os
import re
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree
import requests
from django.core.cache import cache
from django.conf import settings
from django.db import transaction, close_old_connections, connections
from django.db.models import Q, Count, Max, F
from django.utils import timezone
from news.models import ArchiveJob, Article, ArticleContent, FetchAttempt, Source, ImportState, SourceRecoveryCase, SourceAccessInstruction
from news.metadata import extract_metadata, MetadataParser, decode_source_html
from scraper.utils import fetch_feed, upsert_article, safe_url, HostRateLimited
from scraper.utils import retry_delay
from scraper.access_gate import approved_instruction, require_approved_instruction, AccessDenied

USER_AGENT = 'ContextBeforeContent'
# A safety ceiling for configuration, not a claim about measured throughput.
MAX_ARCHIVE_WORKERS = 64
HOST_CIRCUIT_FAILURES = 3
HOST_CIRCUIT_MAX_SECONDS = 900
MAX_ARCHIVE_ATTEMPTS = 5
TERMINAL_ERRORS = frozenset({
    'empty_directory', 'non_article_route', 'not_a_sitemap', 'robots_disallowed',
})
_HOST_STATES = {}
_HOST_STATES_LOCK = Lock()

def host_state(host):
    with _HOST_STATES_LOCK:
        return _HOST_STATES.setdefault(host, {'lock': Lock(), 'next_allowed': 0.0,
            'failures': 0, 'circuit_until': 0.0})

class SourceDelay(Exception):
    # A deliberate retry later, rather than a failed source request.
    def __init__(self, retry_after_seconds=None):
        self.retry_after_seconds = retry_after_seconds
        super().__init__('source_delay')

class ArchiveCutoff(Exception):
    pass

def _transient_error(exc):
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)
    return status == 429 or status is not None and 500 <= status <= 599 or isinstance(exc, (TimeoutError, requests.Timeout, requests.ConnectionError))

def _record_host_failure(state, exc):
    state['failures'] += 1
    if state['failures'] >= HOST_CIRCUIT_FAILURES:
        state['circuit_until'] = time.monotonic() + min(HOST_CIRCUIT_MAX_SECONDS, retry_delay(exc, state['failures']))

def _clear_host_failures(state):
    state['failures'] = 0
    state['circuit_until'] = 0.0


def _record_recovery_case(job, error, terminal):
    """Create one audit case for a source failure; never re-enable a source."""
    fingerprint = str(error or 'unknown_error')[:128]
    open_case = SourceRecoveryCase.objects.filter(source_id=job.source_id,
        failure_fingerprint=fingerprint).exclude(
            status__in=[SourceRecoveryCase.Status.CLOSED, SourceRecoveryCase.Status.RETIRED]).first()
    if open_case:
        open_case.last_observed_at = timezone.now()
        open_case.sample_error = fingerprint[:500]
        open_case.save(update_fields=['last_observed_at', 'sample_error'])
        return open_case
    return SourceRecoveryCase.objects.create(
        source_id=job.source_id,
        trigger='terminal_error' if terminal else 'retry_threshold',
        failure_fingerprint=fingerprint,
        sample_error=fingerprint[:500],
        status=SourceRecoveryCase.Status.DETECTED,
        boxes_before=Article.objects.filter(source_id=job.source_id).count(),
        audit_evidence={'first_job_id': job.pk, 'first_job_url': job.url},
    )

def same_host(url, base):
    def normalized(value):
        return (urlsplit(value).hostname or '').casefold().removeprefix('www.')
    return normalized(url) == normalized(base)

def archive_child_allowed(source, url):
    """Apply optional publisher-specific allow patterns to sitemap children."""
    from scraper.news_sitemaps import matching_catalog_row
    row = matching_catalog_row(source, require_archive_approval=True) or {}
    patterns = row.get('archive_sitemap_child_patterns') or []
    return not patterns or any(re.search(pattern, url) for pattern in patterns)

def robots(url, *, hostname_transport=False, audit_source=None, audit_instruction=None):
    parsed = urlsplit(url)
    address = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    key = 'archive-robots:' + sha256(address.encode()).hexdigest()
    raw = cache.get(key)
    if raw is not None:
        policy = RobotFileParser(); policy.parse(raw.splitlines()); return policy
    try:
        # robots.txt is its own network request.  An HTML (or sitemap) card
        # for a publisher section must not silently authorize the host root.
        # A narrow sitemap-channel card for this single file is therefore
        # required whenever the caller is audited.
        robots_instruction = audit_instruction
        if audit_source is not None:
            robots_instruction = approved_instruction(
                audit_source, SourceAccessInstruction.Channel.SITEMAP, address)
            if robots_instruction is None:
                raise AccessDenied('robots_not_covered_by_instruction')
        raw = fetch_feed(address, hostname_transport=hostname_transport,
            audit_source=audit_source, audit_instruction=robots_instruction,
            requested_kind=FetchAttempt.RequestedKind.ROBOTS).decode('utf-8', errors='replace')
    except Exception as exc:
        response = getattr(exc, 'response', None)
        if response is not None and response.status_code in (404, 410):
            raw = ''
        else:
            raise
    cache.set(key, raw, 3600)
    policy = RobotFileParser()
    policy.parse(raw.splitlines())
    return policy

def discover(source):
    from scraper.news_sitemaps import verified_maps
    source = Source.objects.filter(pk=source.pk, is_active=True,
        scrape_enabled=True, catalog_stage='configured').first()
    if source is None:
        return 0
    # Discovery performs a real robots request.  It therefore needs a
    # reviewed sitemap instruction whose endpoint covers the source root.
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.SITEMAP,
        source.url)
    if instruction is None:
        return 0
    policy = robots(source.url, hostname_transport=True, audit_source=source,
        audit_instruction=instruction)
    count = 0
    for url in dict.fromkeys((policy.site_maps() or []) + verified_maps(source)):
        if safe_url(url) and same_host(url, source.url) and len(url) <= 1024:
            with transaction.atomic():
                current = Source.objects.select_for_update().filter(pk=source.pk,
                    url=source.url, is_active=True, scrape_enabled=True,
                    catalog_stage='configured').first()
                if current is None:
                    break
                _, created = ArchiveJob.objects.get_or_create(url=url, defaults={'source': current, 'kind': 'sitemap'})
                if not created:
                    ArchiveJob.objects.filter(url=url, source=current, kind='sitemap', status='done', checked_at__lt=timezone.now()-timedelta(days=1)).update(status='pending', available_at=timezone.now())
                count += created
    return count

def article_body(raw, url=None):
    """Select one attributable article body; ambiguous publisher data stays link-only."""
    parser = MetadataParser()
    parser.feed(decode_source_html(raw))
    matched, anonymous = set(), set()
    foreign_articles = False

    def same_page(address):
        if not url or not isinstance(address, str):
            return False
        resolved = urlsplit(urljoin(url, address))
        requested = urlsplit(url)
        # Keep query parameters: on many publishers they identify the article.
        return (resolved.scheme, resolved.netloc.lower(), resolved.path.rstrip('/'), resolved.query) == (
            requested.scheme, requested.netloc.lower(), requested.path.rstrip('/'), requested.query)

    def walk(value, depth=0):
        nonlocal foreign_articles
        if depth > 20: return
        if isinstance(value, list):
            for item in value: walk(item, depth + 1)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if isinstance(types, str): types = [types]
            if not isinstance(types, list): types = []
            if any(t in ['Article', 'NewsArticle', 'ReportageNewsArticle', 'BlogPosting'] for t in types):
                addresses = []
                for key in ('url', 'mainEntityOfPage'):
                    address = value.get(key)
                    if isinstance(address, dict): address = address.get('@id')
                    if address: addresses.append(address)
                body = value.get('articleBody')
                usable = isinstance(body, str) and bool(body.strip()) and len(body) <= 500000
                if addresses:
                    if all(same_page(address) for address in addresses):
                        if usable: matched.add(body)
                    else:
                        foreign_articles = True
                elif usable:
                    anonymous.add(body)
            for key in ('@graph', 'mainEntity'):
                if key in value: walk(value[key], depth + 1)

    for document in parser.json_documents:
        walk(document)
    if len(matched) == 1:
        return next(iter(matched))
    if not matched and not foreign_articles and len(anonymous) == 1:
        return next(iter(anonymous))
    return ''


def process(job, cutoff_at=None, allowed_scope=None):
    from scraper.directory_archive import directory_spec, directory_links
    job_kind = getattr(job, 'kind', None)
    source = instruction = None
    # The network boundary enforces access again.  A scheduler may narrow the
    # job pool, but it must never be the sole permission check.
    if job_kind in ('sitemap', 'page'):
        source = Source.objects.filter(pk=job.source_id, is_active=True,
            scrape_enabled=True, catalog_stage='configured').first()
        channel = (SourceAccessInstruction.Channel.SITEMAP if job_kind == 'sitemap'
            else SourceAccessInstruction.Channel.HTML)
        instruction = require_approved_instruction(source, channel, job.url)
        if allowed_scope is not None and allowed_scope != instruction.allowed_scope:
            raise AccessDenied('access_scope_mismatch')
        allowed_scope = instruction.allowed_scope
    if job_kind == 'sitemap':
        if source is None or not same_host(job.url, source.url):
            raise ValueError('source_unavailable')
    listing = job_kind == 'page' and directory_spec(job.url) is not None
    if listing:
        if source is None or not same_host(job.url, source.url):
            raise ValueError('source_unavailable')
    # Gate spans robots and the complete fetch; LocMem eviction cannot remove it.
    state = host_state(urlsplit(job.url).hostname)
    if not state['lock'].acquire(blocking=False):
        raise SourceDelay()
    delay = 3
    attempted = False
    try:
        if time.monotonic() < state['circuit_until']:
            raise SourceDelay()
        if time.monotonic() < state['next_allowed']:
            raise SourceDelay()
        attempted = True
        try:
            # Only jobs carrying an access scope have passed the reviewed
            # source gate. They may use normal hostname transport for CDNs;
            # direct/internal callers retain pinned-IP transport.
            hostname_transport = allowed_scope is not None
            audit_kwargs = {}
            if source is not None:
                audit_kwargs = {'audit_source': source, 'audit_instruction': instruction}
            policy = robots(job.url, hostname_transport=hostname_transport, **audit_kwargs)
            if not policy.can_fetch(USER_AGENT, job.url):
                raise ValueError('robots_disallowed')
            delay = max(policy.crawl_delay(USER_AGENT) or 0, 3)
            request_rate = policy.request_rate(USER_AGENT)
            if request_rate and request_rate.requests:
                delay = max(delay, request_rate.seconds / request_rate.requests)
            requested_kind = (FetchAttempt.RequestedKind.SITEMAP if job_kind == 'sitemap'
                else FetchAttempt.RequestedKind.PAGE)
            capture_snapshot = bool(
                allowed_scope == SourceAccessInstruction.Scope.SNAPSHOT
                and settings.EVIDENCE_SNAPSHOT_ENABLED
            )
            fetched = fetch_feed(job.url, hostname_transport=hostname_transport,
                requested_kind=requested_kind, return_receipt=capture_snapshot,
                **audit_kwargs)
            if capture_snapshot:
                raw, snapshot_fetch_attempt = fetched
            else:
                raw, snapshot_fetch_attempt = fetched, None
            _clear_host_failures(state)
        except HostRateLimited as exc:
            # The durable gateway stopped this job before a page request went
            # to the network. It is queue back-pressure, not source failure.
            raise SourceDelay(max(3, int(exc.retry_after_seconds or 3))) from exc
        except Exception as exc:
            if _transient_error(exc):
                _record_host_failure(state, exc)
            raise
    finally:
        if attempted:
            state['next_allowed'] = time.monotonic() + delay
        state['lock'].release()
    if job.kind == 'sitemap':
        source = Source.objects.filter(pk=job.source_id, is_active=True,
            scrape_enabled=True, catalog_stage='configured').first()
        if source is None:
            raise ValueError('source_unavailable')
        # No external entities/DTD, and fetch_feed enforces a decompressed byte limit.
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('unsupported_xml_declaration')
        root = ElementTree.fromstring(raw)
        kind = root.tag.split('}')[-1]
        if kind not in ('sitemapindex', 'urlset'): raise ValueError('not_a_sitemap')
        jobs = []
        for entry in root:
            location = next((child.text for child in entry if child.tag.split('}')[-1] == 'loc'), None)
            if not location: continue
            url = location.strip()
            if (safe_url(url) and same_host(url, source.url) and len(url) <= 1024
                    and (kind != 'sitemapindex' or archive_child_allowed(source, url))):
                jobs.append(ArchiveJob(source=source, url=url, kind='sitemap' if kind == 'sitemapindex' else 'page', priority=10 if job.priority == 10 else 0))
        with transaction.atomic():
            if not Source.objects.select_for_update().filter(pk=source.pk,
                    url=source.url, is_active=True, scrape_enabled=True,
                    catalog_stage='configured').exists():
                raise ValueError('source_unavailable')
            if job.status == 'running' and not ArchiveJob.objects.filter(pk=job.pk,
                    status='running', available_at=job.available_at).exists():
                raise SourceDelay()
            ArchiveJob.objects.bulk_create(jobs, ignore_conflicts=True, batch_size=500)
            targets = ArchiveJob.objects.filter(source=source, url__in=[j.url for j in jobs])
            if kind == 'sitemapindex':
                targets.filter(kind='sitemap', status='done', checked_at__lt=timezone.now()-timedelta(days=1)).update(status='pending', available_at=timezone.now())
            if job.priority == 10:
                targets.filter(status='pending', priority__lt=10).update(priority=10)
        return len(jobs)
    if listing:
        publications, next_pages = directory_links(raw, job.url)
        # A catalogue is discovery evidence, never an Article even if its shared
        # page template leaks article-like metadata. Targets get their own fetch.
        with transaction.atomic():
            source = Source.objects.select_for_update().filter(pk=job.source_id,
                is_active=True, scrape_enabled=True, catalog_stage='configured').first()
            if source is None or not same_host(job.url, source.url):
                raise ValueError('source_unavailable')
            if job.status == 'running' and not ArchiveJob.objects.filter(pk=job.pk,
                    status='running', available_at=job.available_at).exists():
                raise SourceDelay()
            ArchiveJob.objects.bulk_create([ArchiveJob(source=source, url=url, kind='page')
                for url in dict.fromkeys(publications + next_pages)], ignore_conflicts=True, batch_size=200)
        # pages_completed counts the visited listing; new_articles stays zero.
        return 0
    metadata = extract_metadata(raw, job.url)
    if (urlsplit(job.url).hostname == 'www.gov.pl' and source is not None
            and instruction is not None):
        from scraper.gov_justice_archive import extract_article_metadata
        try:
            metadata = extract_article_metadata(
                raw, job.url, urlsplit(instruction.endpoint).path.rstrip('/'))
        except ValueError as exc:
            # Keep generic behavior for non-justice gov.pl sources.  For the
            # dedicated adapter, a malformed article shell remains a safe
            # rejection rather than an invented record.
            if urlsplit(instruction.endpoint).path.startswith(('/web/prokuratura-', '/web/pr-')):
                raise exc
    if urlsplit(job.url).netloc == 'www.gov.pl' and urlsplit(job.url).path.startswith('/web/premier/'):
        from scraper.html_archive import extract_kprm_metadata
        try:
            metadata = extract_kprm_metadata(raw, job.url)
        except ValueError:
            pass
    if metadata.get('page_classification') == 'non_article':
        raise ValueError('non_article_route')
    if not metadata['title']: raise ValueError('missing_source_title')
    if cutoff_at is not None and metadata.get('published_date'):
        published = datetime.fromisoformat(metadata['published_date'].replace('Z', '+00:00'))
        cutoff = cutoff_at.astimezone(dt_timezone.utc)
        if published.astimezone(dt_timezone.utc) > cutoff:
            raise ArchiveCutoff()
    # The public Box needs metadata. Full-text extraction is a separate,
    # explicitly enabled processing mode because source permissions differ.
    store_full_text = (allowed_scope in ('content', 'snapshot')
        and os.environ.get('ARCHIVE_STORE_FULL_TEXT', '').strip().lower() in ('1', 'true', 'yes', 'on'))
    body = article_body(raw, job.url) if store_full_text else ''
    if metadata['publisher_type'] != 'article' and not body and not metadata['published_date']:
        raise ValueError('unclassified_page')
    article_url = metadata.get('canonical_url') or job.url
    article, created = upsert_article(source=job.source, title=metadata['title'], url=article_url,
        published_date=metadata['published_date'], category='statement' if job.source.source_type == 'institution' else 'article',
        description=metadata['description'], image_url=metadata['image_url'], author=metadata['author'], ingestion_method='archive',
        tags=metadata.get('tags'), declared_genre=metadata.get('declared_genre', ''),
        category_evidence=metadata.get('category_evidence', ''))
    if created and metadata.get('event_date'):
        # Keep publisher event evidence separate from publication time.
        note = f"Data wydarzenia wg {metadata['event_date_source']}: {metadata['event_date_raw']}. Nie jest dowodem daty publikacji. Źródło: {job.url}"
        Article.objects.filter(pk=article.pk).update(evidence_note=note)
    if not created and article.published_date is None and not article.category_reviewed and metadata['published_date']:
        from scraper.utils import parse_published
        from news.signals import invalidate_search
        changed = Article.objects.filter(pk=article.pk, published_date__isnull=True, category_reviewed=False).update(
            published_date=parse_published(metadata['published_date']),
            evidence_note=(article.evidence_note + '\nUzupełniono datę ze źródła: ' + metadata['date_source'] + ' = ' + metadata['date_raw'] + ' (' + job.url + ')').strip())
        if changed: invalidate_search()
    # Preserve first extraction; later source changes require a versioned review.
    if not created:
        from news.enrichment import fill_missing_thumbnail
        fill_missing_thumbnail(article.pk, metadata, job.url, sha256(raw).hexdigest())
    ArticleContent.objects.get_or_create(article=article, defaults={'text': body,
        'status': 'extracted_text' if body else 'metadata_only',
        'method': 'publisher_jsonld_url_matched_v2' if body else 'metadata_only_by_policy',
        'response_sha256': sha256(raw).hexdigest(), 'source_url': job.url})
    if snapshot_fetch_attempt is not None:
        from news.evidence_snapshot import (
            SnapshotArtifactType, SnapshotConsentStatus, SnapshotRetentionPolicy,
            capture_snapshot,
        )
        capture_snapshot(
            article, fetch_attempt=snapshot_fetch_attempt, source_url=job.url,
            content=raw, artifact_type=SnapshotArtifactType.HTML,
            parser_version='archive.raw_html/v1',
            consent_status=SnapshotConsentStatus.ALLOWED,
            retention_policy=SnapshotRetentionPolicy.EVIDENCE_HOLD,
            allowed_uses=[],
        )
    return int(created)

def run_batch(limit=10, source_ids=None, metrics=None, cutoff_at=None, state_callback=None,
              per_source_limit=None, source_access_scopes=None):
    completed = 0
    counters = {key: 0 for key in ('pages_completed', 'sitemaps_completed', 'new_articles', 'deferred_jobs', 'failed_jobs')}
    if cutoff_at is not None:
        counters['skipped_cutoff'] = 0
    source_counts = {}
    source_order = deque()
    if source_ids is not None:
        # Start with publishers least recently checked, then rotate. A newly
        # enabled small archive must not wait behind a large publisher's queue.
        source_order = deque(Source.objects.filter(pk__in=source_ids)
            .annotate(last_archive_check=Max('archive_jobs__checked_at'))
            .order_by(F('last_archive_check').asc(nulls_first=True), 'pk')
            .values_list('pk', flat=True))
    for index in range(limit):
        if index: time.sleep(3)
        now = timezone.now()
        with transaction.atomic():
            eligible = ArchiveJob.objects.select_for_update().filter(status__in=['pending', 'error', 'running'], available_at__lte=now, source__is_active=True, source__scrape_enabled=True)
            if source_ids is not None:
                eligible = eligible.filter(source_id__in=source_ids)
            if per_source_limit is not None:
                remaining_sources = [source_id for source_id in (source_ids or [])
                    if source_counts.get(source_id, 0) < per_source_limit]
                eligible = eligible.filter(source_id__in=remaining_sources)
            # One in four slots favors search/editorial requests. Historical work
            # retains the other slots even while new requests keep arriving.
            job = eligible.filter(priority__gt=0).order_by('-priority', 'available_at', 'pk').first() if index % 4 == 0 else None
            if job is None and source_order:
                for _ in range(len(source_order)):
                    source_id = source_order[0]
                    source_order.rotate(-1)
                    job = eligible.filter(source_id=source_id).order_by('available_at', 'pk').first()
                    if job is not None:
                        break
            if job is None and not source_order:
                job = eligible.order_by('available_at', 'pk').first()
            if job is None: break
            job.status = 'running'; job.attempts += 1; job.available_at = now + timedelta(minutes=15)
            job.save(update_fields=['status', 'attempts', 'available_at'])
            lease = job.available_at
            source_counts[job.source_id] = source_counts.get(job.source_id, 0) + 1
        try:
            scope = (source_access_scopes or {}).get(job.source_id)
            created = process(job, allowed_scope=scope) if cutoff_at is None else process(
                job, cutoff_at=cutoff_at, allowed_scope=scope)
            job.status = 'done'; job.last_error = ''; completed += 1
            if job.kind == 'page':
                counters['pages_completed'] += 1
                counters['new_articles'] += int(created or 0)
            else:
                counters['sitemaps_completed'] += 1
        except ArchiveCutoff:
            counters['skipped_cutoff'] += 1
            job.status = 'done'; job.last_error = 'after_cutoff'
            completed += 1
        except SourceDelay as exc:
            counters['deferred_jobs'] += 1
            job.status = 'pending'; job.attempts -= 1
            retry_seconds = getattr(exc, 'retry_after_seconds', None)
            job.available_at = timezone.now() + timedelta(seconds=retry_seconds or 60)
        except Exception as exc:
            counters['failed_jobs'] += 1
            known_error = str(exc) if str(exc) in TERMINAL_ERRORS | {
                'missing_source_title', 'unclassified_page', 'directory_link_limit',
                'source_unavailable', 'unsupported_xml_declaration'} else type(exc).__name__
            job.last_error = known_error
            terminal = known_error in TERMINAL_ERRORS
            exhausted = job.attempts >= MAX_ARCHIVE_ATTEMPTS
            job.status = 'quarantined' if terminal or exhausted else 'error'
            if terminal or job.attempts >= HOST_CIRCUIT_FAILURES:
                _record_recovery_case(job, known_error, terminal)
            delay = retry_delay(exc, job.attempts) if _transient_error(exc) else min(86400, 3600 * 2 ** min(job.attempts, 5))
            job.available_at = timezone.now() + timedelta(seconds=delay)
        job.checked_at = timezone.now()
        updated = ArchiveJob.objects.filter(pk=job.pk, status='running', available_at=lease).update(
            status=job.status, last_error=job.last_error, available_at=job.available_at, checked_at=job.checked_at, attempts=job.attempts)
        # A stale worker whose lease was already reclaimed must not report a
        # completion the job row never actually recorded.
        if state_callback is not None and updated:
            state_callback(job)
    if metrics is not None:
        metrics.update(counters)
    return completed


def run_parallel_batch(workers=4, per_worker=20, metrics=None, source_ids=None, cutoff_at=None,
                       state_callback=None, per_source_limit=None, source_access_scopes=None):
    if not 1 <= workers <= MAX_ARCHIVE_WORKERS or not 1 <= per_worker <= 100:
        raise ValueError(f'Use 1..{MAX_ARCHIVE_WORKERS} workers and 1..100 jobs per worker')
    jobs = ArchiveJob.objects.filter(status__in=['pending', 'error', 'running'],
        available_at__lte=timezone.now(), source__is_active=True, source__scrape_enabled=True)
    if source_ids is not None:
        jobs = jobs.filter(source_id__in=source_ids)
    sources = list(jobs
        .order_by().values('source_id').annotate(queued=Count('id')).order_by('-queued', 'source_id'))
    if metrics is not None:
        metrics.update(active_workers=min(workers, len(sources)), eligible_sources=len(sources))
    if not sources: return 0
    # Sources on one host share the same HostGateway window.  Splitting them
    # across thread workers merely creates deliberate rate-limit deferrals;
    # keep a host on one worker and parallelise only independent hosts.
    host_sources = {}
    for row in sources:
        source = Source.objects.only('url').get(pk=row['source_id'])
        host = (urlsplit(source.url or '').hostname or '').lower()
        host_sources.setdefault(host, []).append(row)
    groups = [[] for _ in range(min(workers, len(host_sources)))]
    loads = [0] * len(groups)
    for host_rows in sorted(host_sources.values(), key=lambda rows: -sum(row['queued'] for row in rows)):
        index = min(range(len(groups)), key=lambda i: loads[i])
        groups[index].extend(row['source_id'] for row in host_rows)
        loads[index] += sum(row['queued'] for row in host_rows)
    def consume(ids):
        close_old_connections()
        try:
            counters = {}
            limit = per_source_limit * len(ids) if per_source_limit is not None else per_worker
            options = {'source_ids': ids, 'metrics': counters}
            if cutoff_at is not None:
                options['cutoff_at'] = cutoff_at
            if state_callback is not None:
                options['state_callback'] = state_callback
            if per_source_limit is not None:
                options['per_source_limit'] = per_source_limit
            if source_access_scopes is not None:
                options['source_access_scopes'] = {
                    source_id: source_access_scopes[source_id]
                    for source_id in ids if source_id in source_access_scopes}
            completed = run_batch(limit, **options)
            return completed, counters
        finally:
            connections.close_all()
    # One process shares host gates; local scheduler's OS lock prevents duplicates.
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        results = list(pool.map(consume, groups))
    if metrics is not None:
        for _, counters in results:
            for key, value in counters.items():
                metrics[key] = metrics.get(key, 0) + value
    return sum(completed for completed, _ in results)


def approved_queued_source_ids():
    """Return sources that have at least one currently authorised queued job.

    Historical sitemap backfill has a stricter, sitemap-only allowlist.  The
    normal archive queue also contains explicitly discovered HTML pages (for
    example the reviewed gov.pl justice listings), so reusing that allowlist
    made those lawful jobs permanently idle.  Each job is still checked again
    in :func:`process` immediately before network access.
    """
    jobs = (ArchiveJob.objects.filter(
        status__in=['pending', 'error', 'running'],
        available_at__lte=timezone.now(),
        source__is_active=True,
        source__scrape_enabled=True,
        source__catalog_stage='configured',
    ).select_related('source').order_by('source_id', 'pk'))
    approved = set()
    for job in jobs:
        channel = (SourceAccessInstruction.Channel.SITEMAP if job.kind == 'sitemap'
                   else SourceAccessInstruction.Channel.HTML)
        if approved_instruction(job.source, channel, job.url) is not None:
            approved.add(job.source_id)
    return sorted(approved)


def archive_cycle():
    # Recent feed/manual records are read separately from the historical backlog.
    articles = Article.objects.filter(ingestion_method__in=['rss', 'manual'], content__isnull=True).exclude(url__in=ArchiveJob.objects.values('url')).exclude(category__in=['tweet', 'video']).order_by('-pk')[:20]
    for article in articles:
        ArchiveJob.objects.get_or_create(url=article.url, defaults={'source': article.source, 'kind': 'page'})
    # The generic queue accepts explicitly reviewed HTML and sitemap jobs.
    # Backfill remains deliberately stricter because it walks a whole sitemap.
    source_ids = approved_queued_source_ids()
    if not source_ids:
        return {'status': 'blocked_access_review', 'completed': 0, 'workers': 0,
            'elapsed_seconds': 0, 'failed_job_ids': [], 'active_workers': 0,
            'eligible_sources': 0}
    started = timezone.now()
    tick = time.monotonic()
    workers = int(os.environ.get('ARCHIVE_WORKERS', '4'))
    metrics = {}
    completed = run_parallel_batch(workers=workers, metrics=metrics,
        source_ids=source_ids)
    failed = list(ArchiveJob.objects.filter(status='error', checked_at__gte=started).values_list('pk', flat=True))
    return {'status': 'partial' if failed else 'ok' if completed else 'idle', 'completed': completed,
        'workers': workers, 'elapsed_seconds': round(time.monotonic() - tick, 2), 'failed_job_ids': failed, **metrics}

def discovery_cycle():
    import json
    from pathlib import Path
    local_config = Path(__file__).parent / 'data' / 'verified_local_sources.json'
    sitemap_only_urls = []
    if local_config.exists():
        sitemap_only_urls = [row['url'] for row in json.loads(local_config.read_text(encoding='utf-8')) if row.get('sitemap_urls')]
    failed, discovered = [], 0
    for source in Source.objects.filter(is_active=True, scrape_enabled=True, catalog_stage='configured').filter(
            ~Q(rss_url='') | Q(url__in=sitemap_only_urls)).exclude(source_type='twitter'):
        state, _ = ImportState.objects.get_or_create(name=f'archive-discovery:{source.pk}')
        state.last_started = timezone.now(); state.save(update_fields=['last_started'])
        try:
            state.imported = discover(source); discovered += state.imported; state.last_success = timezone.now(); state.last_error = ''
        except Exception as exc:
            state.last_error = type(exc).__name__; failed.append(source.pk)
        state.save(update_fields=['imported', 'last_success', 'last_error'])

    return {'status': 'partial' if failed else 'ok', 'discovered': discovered, 'failed_source_ids': failed}
