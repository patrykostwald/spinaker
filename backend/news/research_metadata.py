"""Bounded enrichment of cited URLs using publisher metadata, never model prose.

One session belongs to one AI response. Web callers only enqueue by default.
The scheduler cycle explicitly enables fetching in the existing importer process.
Work is first persisted in ArchiveJob;
the optional fast lane has only three process-wide slots, no executor backlog,
and cannot write Article records after its waiting deadline. An already active
HTTP read cannot be forcibly stopped; it releases its slot and lease on return.
"""
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
from hashlib import sha256
from functools import wraps
from threading import BoundedSemaphore, Lock, RLock, local
from urllib.parse import urlsplit

from django.db import close_old_connections, connections, transaction
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.utils import timezone

from news.enrichment import fill_missing_thumbnail
from news.metadata import extract_metadata
from news.models import Article, ArticleContent, ArchiveJob, Source
from news.serializers import ArticleSerializer
from news.signals import invalidate_search
from scraper.archive import host_state
from scraper.queue import enqueue_requested_url
from scraper.source_probe import ProbeError, ProbeNetwork, origin, public_link
from scraper.utils import parse_published, upsert_article

MAX_URLS = 15
MAX_SECONDS = 20
MAX_WORKERS = 3
_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='research-metadata')
_SLOTS = BoundedSemaphore(MAX_WORKERS)
_HOSTS = set()
_HOSTS_LOCK = Lock()
_DB_WRITES = RLock()


def serialized_write(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        # Network work remains concurrent; the short write sections share one
        # lane, including SQLite's immediate transactions and in-memory tests.
        with _DB_WRITES:
            return function(*args, **kwargs)
    return wrapped


def hostname(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')


def source_accepts(source, url):
    if (not source.url or hostname(source.url) != hostname(url)
            or not source.is_active or not source.scrape_enabled
            or source.catalog_stage != 'configured'
            or source.source_type in ('twitter', 'politician', 'editorial')):
        return False
    # gov.pl hosts multiple institutions. A URL must remain in this source's
    # configured institution scope, even if the legacy caller's map lost peers.
    if hostname(source.url) == 'gov.pl' and source.source_type == 'institution':
        parts = urlsplit(source.url).path.strip('/').split('/')
        if len(parts) >= 2 and parts[0] == 'web':
            prefix = '/' + '/'.join(parts[:2])
            path = urlsplit(url).path
            return path.rstrip('/') == prefix or path.startswith(prefix + '/')
    return True


class MetadataDeadline(ProbeError):
    pass


class FastNetwork(ProbeNetwork):
    """Reuse public DNS-pinned fetch and the importer process's archive host gate.

The HTTP operation itself retains ProbeNetwork's existing byte/read limits.
The thread-local deadline prevents starting another hop after budget expiry.
"""
    def __init__(self):
        super().__init__()
        self.context = local()
        self.policy_times = {}

    def raw(self, address):
        deadline = self.context.deadline
        if time.monotonic() >= deadline:
            raise MetadataDeadline('research_deadline')
        state = host_state(urlsplit(address).hostname)
        if not state['lock'].acquire(blocking=False):
            raise ProbeError('research_host_busy')
        attempted = False
        try:
            cooldown = max(0, state['next_allowed'] - time.monotonic())
            if time.monotonic() + cooldown >= deadline:
                raise MetadataDeadline('research_deadline')
            if cooldown:
                time.sleep(cooldown)
            if time.monotonic() >= deadline:
                raise MetadataDeadline('research_deadline')
            attempted = True
            response = super().raw(address)
            if time.monotonic() >= deadline:
                raise MetadataDeadline('research_deadline')
            return response
        finally:
            if attempted:
                network_host = self.host(address)
                state['research_last_completed'] = time.monotonic()
                state['next_allowed'] = max(state['next_allowed'], network_host['next'],
                    time.monotonic() + network_host['delay'])
            state['lock'].release()

    def robots(self, address):
        site = origin(address)
        with self.hosts_lock:
            cached = site in self.policies and time.monotonic() - self.policy_times.get(site, 0) <= 3600
            if not cached:
                self.policies.pop(site, None)
        result = super().robots(address)
        with self.hosts_lock:
            if result[2]:
                # A short research budget must not poison the shared policy cache.
                self.policies.pop(site, None)
            elif not cached:
                self.policy_times[site] = time.monotonic()
        if not result[2] and not cached:
            state = host_state(urlsplit(address).hostname)
            with state['lock']:
                state['next_allowed'] = max(state['next_allowed'],
                    state.get('research_last_completed', 0) + self.host(address)['delay'])
        return result


_NETWORK = FastNetwork()


@serialized_write
def _claim(job_id, source_id):
    now = timezone.now()
    with transaction.atomic():
        job = ArchiveJob.objects.select_for_update().select_related('source').filter(pk=job_id).first()
        if (job is None or job.source_id != source_id or job.kind != 'page'
                or job.status not in ('pending', 'error', 'running')
                or job.available_at > now or not source_accepts(job.source, job.url)):
            return None
        job.status = 'running'
        job.attempts += 1
        job.available_at = now + timedelta(minutes=15)
        job.save(update_fields=['status', 'attempts', 'available_at'])
        return job


@serialized_write
def _release(job, error, deferred=False):
    now = timezone.now()
    ArchiveJob.objects.filter(pk=job.pk, status='running', available_at=job.available_at).update(
        status='pending' if deferred else 'error',
        attempts=max(0, job.attempts - 1) if deferred else job.attempts,
        available_at=now + (timedelta(minutes=1) if deferred else timedelta(hours=min(24, 2 ** min(job.attempts, 5)))),
        last_error='' if deferred else error[:200], checked_at=now)


def _store(job, raw, final_url, deadline):
    if not public_link(final_url) or not source_accepts(job.source, final_url):
        raise ProbeError('publisher_redirect_outside_source')
    metadata = extract_metadata(raw, final_url)
    if hostname(final_url) == 'gov.pl' and urlsplit(final_url).path.startswith('/web/premier/'):
        from scraper.html_archive import extract_kprm_metadata
        try:
            metadata = extract_kprm_metadata(raw, final_url)
        except ValueError:
            pass
    if not metadata['title']:
        raise ProbeError('missing_source_title')
    if metadata['publisher_type'] != 'article' and not metadata['published_date']:
        raise ProbeError('unclassified_page')
    response_hash = sha256(raw).hexdigest()
    with _DB_WRITES, transaction.atomic():
        source = Source.objects.select_for_update().get(pk=job.source_id)
        lease_exists = ArchiveJob.objects.select_for_update().filter(pk=job.pk,
            status='running', available_at=job.available_at, source_id=source.pk).exists()
        if time.monotonic() >= deadline:
            raise MetadataDeadline('research_deadline')
        if not lease_exists or not source_accepts(source, job.url) or not source_accepts(source, final_url):
            raise ProbeError('research_source_or_lease_changed')
        existing = Article.objects.filter(url=job.url).first()
        if existing is not None and existing.source_id != source.pk:
            raise ProbeError('article_source_identity_conflict')
        article, created = upsert_article(source=source, title=metadata['title'], url=job.url,
            published_date=metadata['published_date'],
            category='statement' if source.source_type == 'institution' else 'article',
            description=metadata['description'], image_url=metadata['image_url'], author=metadata['author'],
            ingestion_method='archive', tags=metadata.get('tags'),
            declared_genre=metadata.get('declared_genre', ''),
            category_evidence=metadata.get('category_evidence', ''))
        if article is None:
            raise ProbeError('invalid_publisher_metadata')
        if not created:
            fill_missing_thumbnail(article.pk, metadata, job.url, response_hash)
            if (article.published_date is None and not article.category_reviewed
                    and article.ingestion_method in ('rss', 'archive') and metadata['published_date']):
                changed = Article.objects.filter(pk=article.pk, published_date__isnull=True,
                    category_reviewed=False).update(published_date=parse_published(metadata['published_date']),
                    evidence_note=(article.evidence_note + '\nUzupełniono datę ze źródła: '
                        + metadata['date_source'] + ' = ' + metadata['date_raw'] + ' (' + final_url + ')').strip())
                if changed:
                    transaction.on_commit(invalidate_search)
        ArticleContent.objects.get_or_create(article=article, defaults={'text': '', 'status': 'metadata_only',
            'method': 'research_publisher_metadata_v1', 'response_sha256': response_hash, 'source_url': final_url})
        if time.monotonic() >= deadline:
            # Roll back metadata if storage itself exhausted the short budget.
            raise MetadataDeadline('research_deadline')
        ArchiveJob.objects.filter(pk=job.pk, status='running', available_at=job.available_at).update(
            status='done', last_error='', checked_at=timezone.now())
        return article.pk


def _worker(job, deadline, host):
    close_old_connections()
    try:
        _NETWORK.context.deadline = deadline
        raw, final_url, _ = _NETWORK.fetch(job.url)
        return _store(job, raw, final_url, deadline)
    except Exception as exc:
        error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
        _release(job, error, deferred=error in ('research_deadline', 'research_host_busy', 'research_source_or_lease_changed'))
        return None
    finally:
        connections.close_all()
        with _HOSTS_LOCK:
            _HOSTS.discard(host)
        _SLOTS.release()


class ResearchMetadataSession:
    def __init__(self, sources, max_urls=MAX_URLS, deadline_seconds=MAX_SECONDS, *, allow_fetch=False):
        values = getattr(sources, 'all_sources', sources.values()) if isinstance(sources, dict) else sources
        self.source_ids = {source.pk for source in values if isinstance(source, Source)}
        self.max_urls = min(MAX_URLS, max(0, int(max_urls)))
        self.deadline_seconds = min(MAX_SECONDS, max(0, float(deadline_seconds)))
        self.seen = set()
        self.accepted = {}
        self.rejected = []
        self.attempted = 0
        self.deadline = None
        # The web process only queues URLs. Enable fetching exclusively in the
        # existing scheduler process, where archive/WP share the host locks.
        self.allow_fetch = allow_fetch

    def enrich(self, urls):
        if not isinstance(urls, (list, tuple)):
            raise ValueError('urls must be a bounded list of URL strings')
        started = time.monotonic()
        if self.deadline is None:
            self.deadline = started + self.deadline_seconds
        sources = list(Source.objects.filter(pk__in=self.source_ids))
        for value in urls[:MAX_URLS * 4]:
            if not isinstance(value, str):
                continue
            url = public_link(value)
            if value in self.seen or url in self.seen:
                continue
            if len(self.seen) >= self.max_urls:
                break
            self.seen.add(url or value)
            if not url or len(url) > 1024:
                self.rejected.append({'url': value[:1024], 'reason': 'invalid_public_url'})
                continue
            matches = [source for source in sources if source_accepts(source, url)]
            if len(matches) != 1:
                self.rejected.append({'url': url, 'reason': 'source_disabled_unknown_or_ambiguous'})
                continue
            source = matches[0]
            with _DB_WRITES:
                job = enqueue_requested_url(url, source)
            if job.source_id != source.pk or job.kind != 'page':
                self.rejected.append({'url': url, 'reason': 'queue_source_identity_conflict'})
                continue
            self.accepted[url] = (job.pk, source.pk)

        identity_filter = Q(pk__in=[])
        for url, (_, source_id) in self.accepted.items():
            identity_filter |= Q(url=url, source_id=source_id)
        stored = set(Article.objects.filter(identity_filter).values_list('url', flat=True))
        pending = [(url, job_id, source_id) for url, (job_id, source_id) in self.accepted.items() if url not in stored]
        active = set()
        while self.allow_fetch and (pending or active) and time.monotonic() < self.deadline:
            index = 0
            while index < len(pending) and time.monotonic() < self.deadline:
                url, job_id, source_id = pending[index]
                host = hostname(url)
                with _HOSTS_LOCK:
                    if host in _HOSTS:
                        index += 1
                        continue
                    if not _SLOTS.acquire(blocking=False):
                        break
                    _HOSTS.add(host)
                pending.pop(index)
                try:
                    job = _claim(job_id, source_id)
                    if job is None:
                        with _HOSTS_LOCK:
                            _HOSTS.discard(host)
                        _SLOTS.release()
                        continue
                    future = _POOL.submit(_worker, job, self.deadline, host)
                    self.attempted += 1
                    active.add(future)
                except Exception:
                    with _HOSTS_LOCK:
                        _HOSTS.discard(host)
                    _SLOTS.release()
                    raise
            if not active:
                break
            done, active = wait(active, timeout=max(0, self.deadline - time.monotonic()), return_when=FIRST_COMPLETED)
            for future in done:
                future.result()
        # Do not shut down/wait for the process-wide pool here. Late HTTP reads
        # cannot write Article data because _store rechecks the captured deadline.
        articles = list(Article.objects.filter(identity_filter,
            source__is_active=True, source__scrape_enabled=True, source__catalog_stage='configured')
            .exclude(category='tweet').select_related('source', 'content', 'voting', 'official_record')
            .prefetch_related('evidence_links').order_by(F('published_date').asc(nulls_last=True), 'pk')[:self.max_urls])
        stored = {article.url for article in articles}
        return {'articles': ArticleSerializer(articles, many=True).data,
            'pending_urls': [url for url in self.accepted if url not in stored],
            'rejected_urls': list(self.rejected), 'attempted': self.attempted,
            'elapsed_ms': round((time.monotonic() - started) * 1000)}


def research_metadata_cycle(limit=MAX_URLS, deadline_seconds=MAX_SECONDS):
    """Run inside the existing importer process, never as an extra web crawler."""
    limit = min(MAX_URLS, max(0, int(limit)))
    priority_ids = ArchiveJob.objects.filter(priority__gte=100).order_by().values('pk')
    jobs = list(ArchiveJob.objects.filter(pk__in=Subquery(priority_ids), kind='page', priority__gte=100,
        status__in=('pending', 'error', 'running'), available_at__lte=timezone.now(),
        source__is_active=True, source__scrape_enabled=True, source__catalog_stage='configured')
        .exclude(source__source_type__in=('twitter', 'politician', 'editorial'))
        .annotate(already_stored=Exists(Article.objects.filter(url=OuterRef('url'))))
        .filter(already_stored=False).select_related('source')
        .order_by('-priority', 'available_at', 'pk')[:limit])
    if not jobs:
        return {'status': 'idle', 'requested': 0, 'ready': 0, 'attempted': 0, 'pending': 0}
    sources = {job.source_id: job.source for job in jobs}
    result = ResearchMetadataSession(list(sources.values()), max_urls=limit,
        deadline_seconds=deadline_seconds, allow_fetch=True).enrich([job.url for job in jobs])
    failed = ArchiveJob.objects.filter(pk__in=[job.pk for job in jobs], status='error').count()
    ready = len(result['articles'])
    return {'status': 'partial' if failed else 'ok' if ready else 'idle',
        'requested': len(jobs), 'ready': ready, 'attempted': result['attempted'],
        'pending': len(result['pending_urls']), 'failed': failed, 'elapsed_ms': result['elapsed_ms']}
