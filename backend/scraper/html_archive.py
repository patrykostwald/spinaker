"""Explicit KPRM HTML archive links; listing dates never become publication dates."""
import re
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from math import ceil
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs
from uuid import uuid4
from django.db import transaction
from django.utils import timezone
from news.models import Source, ImportState, ArchiveJob
from news.metadata import decode_source_html, extract_metadata
from scraper.archive import robots, USER_AGENT, host_state, SourceDelay
from scraper.utils import fetch_feed, safe_url

START_URL = 'https://www.gov.pl/web/premier/wydarzenia'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


def listing_page(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.gov.pl' or parts.path != '/web/premier/wydarzenia' or parts.fragment:
        raise ValueError('invalid_listing_url')
    params = parse_qs(parts.query, strict_parsing=True)
    if set(params) - {'page','size'} or any(len(value) != 1 for value in params.values()):
        raise ValueError('invalid_listing_query')
    if params.get('size', ['10']) != ['10']:
        raise ValueError('invalid_page_size')
    page = int(params.get('page', ['1'])[0])
    if page < 1 or page > 100000:
        raise ValueError('invalid_page_number')
    return page


class KPRMListing(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.stack = []
        self.rows = []
        self.current = None
        self.next_url = None
        self.last_url = None
        self.current_page = None
        self.container_seen = False

    def inside(self, class_name):
        return any(class_name in attrs.get('class','').split() for _, attrs in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('id') in {'js-pagination-page-next','js-pagination-pages-count'}:
            value = urljoin(self.url, attrs.get('href',''))
            listing_page(value)
            if attrs['id'] == 'js-pagination-page-next': self.next_url = value
            else: self.last_url = value
        if tag == 'input' and attrs.get('id') == 'js-pagination-page':
            self.current_page = int(attrs.get('value',''))
        if 'art-prev' in attrs.get('class','').split(): self.container_seen = True
        if tag == 'li' and self.inside('art-prev') and self.current is None:
            self.current = {'url':'','title_parts':[], 'date_parts':[], 'image_url':''}
        if self.current is not None:
            if tag == 'a' and self.inside('title'):
                self.current['url'] = urljoin(self.url, attrs.get('href',''))
            if tag == 'img' and not self.current['image_url']:
                self.current['image_url'] = urljoin(self.url, attrs.get('src',''))
        if tag not in VOID: self.stack.append((tag, attrs))

    def handle_data(self, data):
        if self.current is not None:
            if self.inside('title'): self.current['title_parts'].append(data)
            if self.inside('date'): self.current['date_parts'].append(data)

    def handle_endtag(self, tag):
        if tag == 'li' and self.current is not None:
            self.rows.append(self.current); self.current = None
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index][0] == tag:
                del self.stack[index:]; break


def parse_listing(raw, url):
    page = listing_page(url)
    parser = KPRMListing(url); parser.feed(decode_source_html(raw)); parser.close()
    if not parser.container_seen or not 1 <= len(parser.rows) <= 10 or parser.current_page != page or not parser.last_url:
        raise ValueError('listing_structure_changed')
    last_page = listing_page(parser.last_url)
    if last_page < page or (parser.next_url and listing_page(parser.next_url) != page + 1) or (page < last_page and not parser.next_url):
        raise ValueError('pagination_incomplete')
    records, seen = [], set()
    for row in parser.rows:
        parts = urlsplit(row['url'])
        title = ' '.join(' '.join(row['title_parts']).split())
        if not safe_url(row['url']) or parts.netloc != 'www.gov.pl' or not re.fullmatch(r'/web/premier/[^/]+',parts.path) or parts.path.endswith('/wydarzenia') or parts.query or parts.fragment or not title:
            raise ValueError('invalid_article_link')
        if row['url'] not in seen:
            records.append({'url':row['url'], 'title':title, 'listing_date_raw':' '.join(' '.join(row['date_parts']).split()), 'image_url':row['image_url']})
            seen.add(row['url'])
    return {'records':records, 'page':page, 'last_page':last_page, 'last_url':parser.last_url, 'next_url':parser.next_url}


class KPRMEventDate(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_date = False
        self.values = []
        self.current = []
        self.in_article = False
        self.has_heading = False
        self.is_listing = False
        self.has_parent = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href') == '/web/premier/wydarzenia': self.has_parent = True
        if tag == 'article' and attrs.get('id') == 'main-content' and 'article-area__article' in attrs.get('class','').split(): self.in_article = True
        if self.in_article and tag == 'h2': self.has_heading = True
        if self.in_article and 'art-prev' in attrs.get('class','').split(): self.is_listing = True
        if self.in_article and tag == 'p' and 'event-date' in attrs.get('class','').split():
            self.in_date = True; self.current = []
    def handle_data(self, data):
        if self.in_date: self.current.append(data)
    def handle_endtag(self, tag):
        if tag == 'article': self.in_article = False
        if tag == 'p' and self.in_date:
            self.values.append(' '.join(' '.join(self.current).split())); self.in_date = False


def extract_kprm_metadata(raw, url):
    """Preserve event dates separately: an event date is not a publication timestamp."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.gov.pl' or not re.fullmatch(r'/web/premier/[^/]+',parts.path):
        raise ValueError('not_kprm_article')
    parser = KPRMEventDate(); parser.feed(decode_source_html(raw)); parser.close()
    values = set(parser.values)
    if not parser.has_parent or not parser.has_heading or parser.is_listing or len(values) != 1: raise ValueError('ambiguous_event_date')
    value = values.pop()
    if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}',value): raise ValueError('invalid_event_date')
    event_date = datetime.strptime(value,'%d.%m.%Y').date()
    data = extract_metadata(raw,url)
    # Site pages use og:type=website; the publisher's event-date identifies this record.
    data['publisher_type'] = 'article'
    data['event_date'] = event_date.isoformat()
    data['event_date_source'] = 'html:p.event-date'
    data['event_date_raw'] = value
    data['event_date_is_future'] = event_date > timezone.localdate()
    return data


def retry_delay(exc, failures):
    delay = min(86400,60*2**min(failures,10))
    response = getattr(exc,'response',None)
    value = getattr(response,'headers',{}).get('Retry-After','')
    try:
        requested = int(value) if str(value).isdigit() else ceil((parsedate_to_datetime(value)-timezone.now()).total_seconds())
        delay = max(delay,requested)
    except (ValueError,TypeError,OverflowError):
        pass
    return delay


def fetch_listing(url):
    listing_page(url)
    gate = host_state('www.gov.pl')
    if not gate['lock'].acquire(blocking=False): raise SourceDelay()
    attempted, delay = False, 3
    try:
        if time.monotonic() < gate['next_allowed']: raise SourceDelay()
        attempted = True
        policy = robots(url)
        if not policy.can_fetch(USER_AGENT,url): raise ValueError('robots_disallowed')
        delay = max(3, policy.crawl_delay(USER_AGENT) or 0)
        rate = policy.request_rate(USER_AGENT)
        if rate and rate.requests: delay = max(delay,rate.seconds/rate.requests)
        return fetch_feed(url)
    finally:
        if attempted: gate['next_allowed'] = time.monotonic()+delay
        gate['lock'].release()


def eligible(source):
    return (source.is_active and source.scrape_enabled and source.catalog_stage == 'configured'
        and source.url and urlsplit(source.url).netloc == 'www.gov.pl'
        and (urlsplit(source.url).path == '/web/premier' or urlsplit(source.url).path.startswith('/web/premier/')))


def run_kprm_listing(source_id):
    """One resumable listing page. Safe to call from a scheduler; no sleep or fulltext reads."""
    source = Source.objects.get(pk=source_id)
    if not eligible(source): return {'status':'disabled','queued':0}
    now, token = timezone.now(), uuid4().hex
    with transaction.atomic():
        state, _ = ImportState.objects.get_or_create(name=f'html-archive:kprm:{source.pk}')
        state = ImportState.objects.select_for_update().get(pk=state.pk)
        cursor = dict(state.cursor)
        if cursor.get('complete'):
            if state.last_success and now-state.last_success < timedelta(hours=1):
                return {'status':'complete','queued':0, 'pages_completed':cursor.get('pages_completed',0)}
            # After the first complete pass, inspect the head hourly and stop at overlap.
            cursor = {'refresh':True,'pages_completed':0}
        if cursor.get('available_at','') > now.isoformat(): return {'status':'deferred','queued':0}
        url = cursor.get('next_url') or START_URL
        listing_page(url)
        cursor.update(lease=token,available_at=(now+timedelta(minutes=10)).isoformat())
        state.cursor = cursor; state.last_started = now
        state.save(update_fields=['cursor','last_started'])
    try:
        result = parse_listing(fetch_listing(url),url)
        with transaction.atomic():
            source = Source.objects.select_for_update().get(pk=source_id)
            state = ImportState.objects.select_for_update().get(pk=state.pk)
            if state.cursor.get('lease') != token: return {'status':'superseded','queued':0}
            if not eligible(source):
                state.cursor = {**state.cursor,'lease':None,'available_at':timezone.now().isoformat()}
                state.save(update_fields=['cursor']); return {'status':'disabled','queued':0}
            created = 0
            for record in result['records']:
                _, added = ArchiveJob.objects.get_or_create(url=record['url'], defaults={'source':source,'kind':'page'})
                created += added
            complete = result['next_url'] is None or bool(cursor.get('refresh') and created == 0)
            state.cursor = {'next_url':None if complete else result['next_url'], 'last_url':url, 'complete':complete,
                'refresh':cursor.get('refresh',False),
                'pages_completed':cursor.get('pages_completed',0)+1, 'declared_pages':result['last_page'],
                'available_at':(timezone.now()+timedelta(seconds=3)).isoformat(), 'lease':None, 'failures':0}
            state.imported += created; state.last_success = timezone.now(); state.last_error = ''
            state.save(update_fields=['cursor','imported','last_success','last_error'])
        return {'status':'complete' if complete else 'ok', 'queued':created, 'page':result['page'],
            'declared_pages':result['last_page'], 'next_url':result['next_url']}
    except Exception as exc:
        with transaction.atomic():
            state = ImportState.objects.select_for_update().get(pk=state.pk)
            if state.cursor.get('lease') == token:
                failures = cursor.get('failures',0)+(0 if isinstance(exc,SourceDelay) else 1)
                delay = 3 if isinstance(exc,SourceDelay) else retry_delay(exc,failures)
                state.cursor = {**cursor,'next_url':url,'lease':None,'failures':failures,'available_at':(timezone.now()+timedelta(seconds=delay)).isoformat()}
                state.last_error = '' if isinstance(exc,SourceDelay) else type(exc).__name__
                state.save(update_fields=['cursor','last_error'])
        return {'status':'deferred' if isinstance(exc,SourceDelay) else 'error', 'queued':0,'error':None if isinstance(exc,SourceDelay) else type(exc).__name__}


def kprm_listing_cycle():
    source = Source.objects.filter(url__startswith='https://www.gov.pl/web/premier',
        is_active=True, scrape_enabled=True, catalog_stage='configured').first()
    return run_kprm_listing(source.pk) if source else {'status':'idle','queued':0}
