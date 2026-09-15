from datetime import datetime, timezone as dt_timezone
from functools import wraps
from urllib.parse import urlparse
from hashlib import sha256
from email.utils import parsedate_to_datetime
import ipaddress, logging, os, random, socket, re
import requests
from dateutil.parser import parse as parse_date
from django.core.cache import cache
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.utils.html import strip_tags
from news.models import Article, ArticleCategory, FetchAttempt, Source, SourceType
from news.classification import publisher_category, normalize_publisher_tags

log = logging.getLogger('scraper')


class HostRateLimited(Exception):
    """The durable host gate declined this request before network I/O."""

    def __init__(self, retry_after_seconds):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f'host_rate_limited:{retry_after_seconds:.3f}')

def safe_url(url):
    value = str(url or '').strip()
    try:
        parsed = urlparse(value)
        parsed.port  # Reject malformed ports before any downstream network call.
        return value if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and len(value) <= 4096 else ''
    except ValueError:
        return ''

def parse_published(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        if not re.search(r'\b\d{4}\b', value):
            return None
        try:
            dt = parse_date(value)
        except (ValueError, TypeError, OverflowError):
            return None
    else:
        return None
    # Unknown timezone is not silently assumed to be UTC or Warsaw.
    return None if timezone.is_naive(dt) else dt

def guarded(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            log.info('%s imported=%s', fn.__name__, result)
            cache.set('import-status:' + fn.__name__, {'status': 'ok', 'imported': result, 'at': timezone.now().isoformat()}, 86400)
            return result
        except Exception as exc:
            # Never include request URLs containing API credentials in logs.
            log.error('%s failed (%s)', fn.__name__, type(exc).__name__)
            cache.set('import-status:' + fn.__name__, {'status': 'error', 'error': type(exc).__name__, 'at': timezone.now().isoformat()}, 86400)
            return 0
    return wrapped

def reserve_budget(name, units, limit, seconds):
    key = 'budget:' + name
    cache.add(key, 0, timeout=seconds)
    # Atomic INCR on Redis; conservative reservations include failed requests.
    used = cache.incr(key, units)
    if used > limit:
        cache.decr(key, units)
        log.error('Import budget exhausted: %s', name)
    return used <= limit

def retry_delay(exc, failures, cap=86400):
    """Return bounded exponential backoff, honoring a provider Retry-After floor."""
    failures = max(1, int(failures or 1))
    base = min(cap, 60 * 2 ** min(failures - 1, 10))
    delay = base + random.uniform(0, base * 0.25)
    response = getattr(exc, 'response', None)
    value = getattr(response, 'headers', {}).get('Retry-After', '') if response is not None else ''
    try:
        requested = int(value) if str(value).isdigit() else (parsedate_to_datetime(value) - datetime.now(dt_timezone.utc)).total_seconds()
        delay = max(delay, requested)
    except (TypeError, ValueError, OverflowError):
        pass
    return min(cap, max(0, round(delay)))

def get_or_create_source(*, name, url, source_type=SourceType.PORTAL, rss_url='', twitter_user_id='', scrape_frequency_minutes=60):
    from hashlib import sha256
    key = sha256(url.encode('utf-8')).hexdigest()
    original = Source.objects.filter(catalog_seed_key=key).first()
    if original is not None:
        return original
    source, _ = Source.objects.get_or_create(url=url, defaults={
        'name': name[:255], 'source_type': source_type, 'rss_url': rss_url, 'twitter_user_id': twitter_user_id,
        'scrape_frequency_minutes': scrape_frequency_minutes, 'catalog_seed_key': key})
    if not source.catalog_seed_key:
        source.catalog_seed_key = key
        source.save(update_fields=['catalog_seed_key'])
    return source

def source_from_article_url(article_url, fallback_name):
    parsed = urlparse(article_url)
    return get_or_create_source(name=parsed.netloc.replace('www.', '') or fallback_name,
        url=f'{parsed.scheme}://{parsed.netloc}', source_type=SourceType.PORTAL)

def upsert_article(*, source, title, url, published_date, category=ArticleCategory.ARTICLE,
                   image_url='', author=None, description='', tweet_id='',
                   likes_count=0, retweets_count=0, discovered_at=None, ingestion_method='manual', category_reviewed=False,
                   tags=None, declared_genre='', category_evidence=''):
    url = safe_url(url)
    if not url or len(url) > 1024 or not title:
        return None, False
    tags = normalize_publisher_tags(tags)
    if declared_genre in ('interview', 'reportage', 'video', 'podcast') and category_evidence and category in ('article', 'other') and not category_reviewed:
        category = declared_genre
    if ingestion_method in ('rss', 'archive') and not category_reviewed and category in ('article', 'other'):
        category, url_evidence = publisher_category(url, category)
        category_evidence = url_evidence or category_evidence
    defaults = dict(source=source, title=strip_tags(str(title))[:500], published_date=parse_published(published_date),
        category=category, evidence_note=category_evidence, tags=tags,
        image_url=safe_url(image_url) if len(str(image_url or '')) <= 1024 else '',
        author=str(author or '')[:200], discovered_at=discovered_at, ingestion_method=ingestion_method, category_reviewed=category_reviewed, description=strip_tags(str(description or ''))[:4000],
        tweet_id=str(tweet_id or '')[:64], likes_count=max(0, int(likes_count or 0)), retweets_count=max(0, int(retweets_count or 0)))
    try:
        with transaction.atomic():
            article, created = Article.objects.get_or_create(url=url, defaults=defaults)
            if created:
                Source.objects.filter(pk=source.pk).update(total_articles=F('total_articles') + 1)
            elif article.source_id == source.pk:
                # Never replace existing source facts or a manually reviewed genre.
                if tags and not article.tags:
                    Article.objects.filter(pk=article.pk, tags=[]).update(tags=tags)
                    article.refresh_from_db(fields=['tags'])
                if (not article.category_reviewed and article.category in ('article', 'other')
                        and category_evidence and category in ('interview', 'reportage', 'video', 'podcast', 'sponsored')):
                    note = (article.evidence_note + '\n' + category_evidence).strip()
                    Article.objects.filter(pk=article.pk, category_reviewed=False,
                        category__in=['article', 'other']).update(category=category, evidence_note=note)
                    article.refresh_from_db(fields=['category', 'evidence_note'])
            return article, created
    except IntegrityError:
        return Article.objects.get(url=url), False

def _fetch_fingerprint(url):
    """A keyed digest keeps query parameters out of the audit record."""
    key = str(settings.SECRET_KEY).encode('utf-8')
    return sha256(key + b'\0' + str(url).encode('utf-8')).hexdigest()


def record_fetch_refusal(*, source, channel, requested_kind, url, outcome, error_code):
    """Record an access refusal without resolving or requesting the URL."""
    return FetchAttempt.objects.create(
        source=source, channel=channel, requested_kind=requested_kind,
        url_fingerprint=_fetch_fingerprint(url), url_host=(urlparse(url).hostname or '').lower(),
        adapter_revision='scraper.fetch_feed/v1', transport='pre_network_gate',
        request_user_agent='ContextBeforeContent/1.0 source reader',
        outcome=outcome, network_started=False, error_code=error_code)


def _record_transport_attempt(*, source, instruction, requested_kind, url, outcome,
                              http_status=None, bytes_received=0, response_sha256='', error_code='',
                              hostname_transport=False, network_started=True):
    return FetchAttempt.objects.create(
        source=source, instruction=instruction, instruction_version=instruction.version,
        channel=instruction.channel, requested_kind=requested_kind,
        url_fingerprint=_fetch_fingerprint(url), url_host=(urlparse(url).hostname or '').lower(),
        adapter_revision='scraper.fetch_feed/v1',
        transport=('hostname_https' if hostname_transport else 'pinned_ip_https')
        if urlparse(url).scheme == 'https' else 'pinned_ip_http',
        request_user_agent='ContextBeforeContent/1.0 source reader',
        decision_basis=str(instruction.evidence.get('basis') or instruction.terms_url)[:500],
        outcome=outcome, network_started=network_started, http_status=http_status,
        bytes_received=bytes_received, response_sha256=response_sha256, error_code=error_code)


def fetch_feed(url, *, hostname_transport=False, audit_source=None, audit_instruction=None,
               requested_kind=None, return_receipt=False):
    """Bounded HTTP fetch, optionally emitting an append-only audit receipt."""
    if (audit_source is None) != (audit_instruction is None):
        raise ValueError('Fetch audit requires both source and instruction.')
    if audit_source is not None and requested_kind is None:
        raise ValueError('Fetch audit requires a requested kind.')
    gateway = worker_id = host = None
    if audit_source is not None:
        from scraper.host_gateway import HostGateway
        host = (urlparse(url).hostname or '').lower()
        # Durable source identity, rather than a transient Python object id.
        worker_id = f'fetch:{os.getpid()}:{audit_source.pk}'
        gateway = HostGateway(minimum_interval_seconds=audit_instruction.minimum_interval_seconds)
        reservation = gateway.acquire(host, worker_id)
        if not reservation.granted:
            _record_transport_attempt(source=audit_source, instruction=audit_instruction,
                requested_kind=requested_kind, url=url,
                outcome=FetchAttempt.Outcome.RATE_LIMIT_PREEMPTIVE,
                error_code=f'host_rate_limited:{reservation.retry_after_seconds:.3f}',
                hostname_transport=hostname_transport, network_started=False)
            raise HostRateLimited(reservation.retry_after_seconds)
    try:
        try:
            raw = _fetch_feed_raw(url, hostname_transport=hostname_transport)
        except Exception as exc:
            if audit_source is not None:
                response = getattr(exc, 'response', None)
                status = getattr(response, 'status_code', None)
                outcome = FetchAttempt.Outcome.HTTP_ERROR if status else FetchAttempt.Outcome.NETWORK_ERROR
                code = f'http_{status}' if status else type(exc).__name__.lower()[:64]
                _record_transport_attempt(source=audit_source, instruction=audit_instruction,
                    requested_kind=requested_kind, url=url, outcome=outcome,
                    http_status=status, error_code=code, hostname_transport=hostname_transport)
                if status == 429:
                    value = response.headers.get('Retry-After', '') if response is not None else ''
                    gateway.extend_on_429(host, worker_id, int(value) if str(value).isdigit() else 60)
            raise
        receipt = None
        if audit_source is not None:
            receipt = _record_transport_attempt(source=audit_source, instruction=audit_instruction,
                requested_kind=requested_kind, url=url, outcome=FetchAttempt.Outcome.OK,
                http_status=200, bytes_received=len(raw), response_sha256=sha256(raw).hexdigest(),
                hostname_transport=hostname_transport)
        return (raw, receipt) if return_receipt else raw
    finally:
        if gateway is not None:
            gateway.complete(host, worker_id)
def _fetch_feed_raw(url, *, hostname_transport=False):
    """Bounded public HTTP fetch with validation on every redirect.

    ``hostname_transport`` is reserved for an already approved publisher
    source.  It keeps the normal HTTPS hostname connection that CDNs require,
    while the DNS preflight still rejects private destinations.  Arbitrary
    URLs retain the pinned-IP transport by default.
    """
    from urllib.parse import urljoin, urlunsplit
    import ssl
    import urllib3
    initial_host = (urlparse(url).hostname or '').lower()
    for _ in range(4):
        if not safe_url(url):
            raise ValueError('Invalid source URL')
        parsed = urlparse(url)
        hostname = parsed.hostname.encode('idna').decode('ascii')
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Source address must be public')
        # Arbitrary URLs use a pinned IP, avoiding a second DNS lookup that
        # could rebind locally.  Approved publishers can opt into normal
        # hostname transport because many CDN/load-balancer deployments reject
        # direct connections to an edge IP.
        address = addresses[0][4][0]
        if hostname_transport:
            pool = urllib3.PoolManager(cert_reqs=ssl.CERT_REQUIRED,
                ca_certs=requests.certs.where())
            request_url = url
            headers = {'User-Agent': 'ContextBeforeContent/1.0 source reader'}
        elif parsed.scheme == 'https':
            pool = urllib3.HTTPSConnectionPool(address, port=port, server_hostname=hostname,
                assert_hostname=hostname, cert_reqs=ssl.CERT_REQUIRED, ca_certs=requests.certs.where())
            host_header = f'[{hostname}]' if ':' in hostname else hostname
            if parsed.port:
                host_header += ':' + str(port)
            request_url = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
            headers = {'Host': host_header, 'User-Agent': 'ContextBeforeContent/1.0 source reader'}
        else:
            pool = urllib3.HTTPConnectionPool(address, port=port)
            host_header = f'[{hostname}]' if ':' in hostname else hostname
            if parsed.port:
                host_header += ':' + str(port)
            request_url = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
            headers = {'Host': host_header, 'User-Agent': 'ContextBeforeContent/1.0 source reader'}
        response = None
        try:
            response = pool.urlopen('GET', request_url, redirect=False, preload_content=False, retries=False,
                timeout=urllib3.Timeout(connect=5, read=30),
                headers=headers)
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers['Location'])
                if (urlparse(url).hostname or '').lower() != initial_host:
                    raise ValueError('Cross-host redirect requires a separate access instruction')
                continue
            if response.status >= 400:
                error_response = requests.Response()
                error_response.status_code = response.status
                error_response.headers.update(dict(response.headers))
                raise requests.HTTPError(f'HTTP {response.status}', response=error_response)
            chunks, size = [], 0
            for chunk in response.stream(65536, decode_content=True):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source response too large')
                chunks.append(chunk)
            return b''.join(chunks)
        finally:
            if response is not None:
                response.close()
            close = getattr(pool, 'close', None) or getattr(pool, 'clear', None)
            if close is not None:
                close()
    raise ValueError('Too many source redirects')
