"""Bounded publisher access audit. Evidence only: no Source, Article or ArchiveJob writes."""
import gzip
import io
import ipaddress
import json
import socket
import ssl
import time
from hashlib import sha256
from html.parser import HTMLParser
from threading import Lock
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import feedparser
import requests
import urllib3
from django.utils import timezone

from news.metadata import decode_source_html, extract_metadata
from news.models import ImportState, OfficialRecord
from scraper.utils import safe_url, parse_published

USER_AGENT = 'ContextBeforeContent'
MAX_BYTES = 5_000_000
PROBE_VERSION = 1


class ProbeError(Exception):
    pass


def origin(url):
    p = urlsplit(url)
    return f'{p.scheme}://{p.netloc}'


def source_signature(source):
    values = [source.url, source.rss_url, source.source_type, source.catalog_stage]
    return sha256(json.dumps(values, ensure_ascii=False).encode('utf-8')).hexdigest()


def public_link(url):
    value = safe_url(url)
    if not value:
        return ''
    host = urlsplit(value).hostname or ''
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
        return ''
    try:
        if not ipaddress.ip_address(host).is_global:
            return ''
    except ValueError:
        pass
    return value


class ProbeNetwork:
    """Shared host gates include every redirect and robots request, including failed requests."""
    def __init__(self, delay=3):
        self.delay = delay
        self.hosts = {}
        self.hosts_lock = Lock()
        self.policies = {}
        self.policy_locks = {}

    def host(self, address):
        name = (urlsplit(address).hostname or '').lower()
        with self.hosts_lock:
            return self.hosts.setdefault(name, {'lock': Lock(), 'next': 0.0, 'delay': self.delay})

    def raw(self, address):
        if not public_link(address):
            raise ProbeError('invalid_public_url')
        host_state = self.host(address)
        with host_state['lock']:
            time.sleep(max(0, host_state['next'] - time.monotonic()))
            try:
                p = urlsplit(address)
                hostname = p.hostname.encode('idna').decode('ascii')
                port = p.port or (443 if p.scheme == 'https' else 80)
                addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                    raise ProbeError('non_public_address')
                ip = addresses[0][4][0]
                pool = (urllib3.HTTPSConnectionPool(ip, port=port, server_hostname=hostname,
                    assert_hostname=hostname, cert_reqs=ssl.CERT_REQUIRED, ca_certs=requests.certs.where())
                    if p.scheme == 'https' else urllib3.HTTPConnectionPool(ip, port=port))
                host_header = f'[{hostname}]' if ':' in hostname else hostname
                if p.port:
                    host_header += f':{p.port}'
                response = None
                started = time.monotonic()
                try:
                    response = pool.urlopen('GET', urlunsplit(('', '', p.path or '/', p.query, '')),
                        redirect=False, preload_content=False, retries=False,
                        timeout=urllib3.Timeout(connect=5, read=12),
                        headers={'Host': host_header, 'User-Agent': USER_AGENT + '/1.0 source access audit'})
                    headers = {name: response.headers[name] for name in
                        ('X-WP-Total', 'X-WP-TotalPages', 'Link', 'Content-Type') if name in response.headers}
                    if response.status in (301, 302, 303, 307, 308):
                        return {'status': response.status, 'location': response.headers.get('Location', ''), 'raw': b'', 'headers': headers}
                    if response.status >= 400:
                        return {'status': response.status, 'raw': b'', 'headers': headers}
                    chunks, size = [], 0
                    for chunk in response.stream(65536, decode_content=True):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ProbeError('response_too_large')
                        if time.monotonic() - started > 25:
                            raise ProbeError('response_deadline')
                        chunks.append(chunk)
                    return {'status': response.status, 'raw': b''.join(chunks), 'headers': headers}
                finally:
                    if response is not None:
                        response.close()
                    pool.close()
            finally:
                host_state['next'] = time.monotonic() + host_state['delay']

    def robots(self, address):
        site = origin(address)
        with self.hosts_lock:
            lock = self.policy_locks.setdefault(site, Lock())
        with lock:
            if site in self.policies:
                return self.policies[site]
            url = site + '/robots.txt'
            info = {'url': url, 'kind': 'robots'}
            policy = RobotFileParser()
            try:
                current = url
                for _ in range(4):
                    response = self.raw(current)
                    if 'location' in response:
                        current = urljoin(current, response['location']); continue
                    break
                else:
                    raise ProbeError('robots_redirect_limit')
                if response['status'] in (404, 410):
                    content = ''
                    info.update(status='absent', http_status=response['status'])
                elif response['status'] >= 400:
                    raise ProbeError(f"robots_http_{response['status']}")
                else:
                    content = response['raw'].decode('utf-8', errors='replace')
                    if '<html' in content[:300].lower() or '<!doctype html' in content[:300].lower():
                        raise ProbeError('robots_returned_html')
                    info.update(status='ok', http_status=response['status'], sha256=sha256(response['raw']).hexdigest())
                policy.parse(content.splitlines())
                rate = policy.request_rate(USER_AGENT)
                delay = max(self.delay, policy.crawl_delay(USER_AGENT) or 0,
                            rate.seconds / rate.requests if rate and rate.requests else 0)
                self.host(address)['delay'] = delay
                info['sitemap_urls'] = policy.site_maps() or []
                info['ai_bot_restrictions'] = [bot for bot in ('GPTBot', 'ChatGPT-User', 'Google-Extended')
                    if not policy.can_fetch(bot, site + '/')]
                result = (policy, info, '')
            except Exception as exc:
                error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
                info.update(status='error', error=error)
                result = (None, info, error)
            self.policies[site] = result
            return result

    def fetch(self, address):
        current, policies = address, []
        for _ in range(4):
            policy, info, error = self.robots(current)
            policies.append(info)
            if error:
                raise ProbeError(error)
            if not policy.can_fetch(USER_AGENT, current):
                raise ProbeError('robots_disallowed')
            response = self.raw(current)
            if 'location' in response:
                current = urljoin(current, response['location']); continue
            if response['status'] >= 400:
                raise ProbeError(f"http_{response['status']}")
            return response['raw'], current, policies
        raise ProbeError('redirect_limit')


class PublisherLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None
        self.canonical = ''
        self.refresh = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('a', 'link') and attrs.get('href'):
            item = {'href': attrs['href'], 'type': attrs.get('type') or '', 'rel': attrs.get('rel') or '', 'text': ''}
            self.links.append(item)
            if tag == 'a':
                self.current = item
            if (attrs.get('rel') or '').lower() == 'canonical':
                self.canonical = attrs['href']
        if tag == 'meta' and (attrs.get('http-equiv') or '').lower() == 'refresh':
            content = attrs.get('content') or ''
            if 'url=' in content.lower():
                self.refresh = content[content.lower().index('url=') + 4:].strip(' "\'')

    def handle_endtag(self, tag):
        if tag == 'a':
            self.current = None

    def handle_data(self, text):
        if self.current is not None:
            self.current['text'] += text[:200]


def parse_sitemap(raw, url):
    if raw.startswith(b'\x1f\x8b'):
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ProbeError('expanded_sitemap_too_large')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ProbeError('xml_dtd_not_allowed')
    root = ElementTree.fromstring(raw)
    kind = root.tag.rsplit('}', 1)[-1]
    if kind not in ('sitemapindex', 'urlset'):
        raise ProbeError('not_a_sitemap')
    entries = []
    child_kind = 'sitemap' if kind == 'sitemapindex' else 'url'
    for node in root:
        if node.tag.rsplit('}', 1)[-1] != child_kind:
            continue
        loc = next((child.text for child in node if child.tag.rsplit('}', 1)[-1] == 'loc'), None)
        if not loc or not public_link(loc.strip()):
            continue
        publication_date = next((child.text for child in node.iter()
            if child.tag == '{http://www.google.com/schemas/sitemap-news/0.9}publication_date'), None)
        entries.append({'url': loc.strip(), 'news_publication_date': publication_date})
    return kind, entries


def spread_sample(items, limit=3):
    if len(items) <= limit:
        return items
    return [items[i] for i in sorted({0, len(items) // 2, len(items) - 1})][:limit]


def empty_result(source):
    return {'probe_version': PROBE_VERSION, 'source_id': source.pk, 'name': source.name,
        'checked_at': None, 'source_url': source.url or '', 'configured_rss_url': source.rss_url,
        'catalog_stage': source.catalog_stage, 'signature': source_signature(source), 'audit_status': 'running',
        'rss': {'status': 'not_found' if not source.rss_url else 'unknown', 'url': source.rss_url,
                'entry_count': 0, 'usable_entry_count': 0, 'error': ''},
        'archive': {'status': 'unknown', 'sitemap_urls': [], 'listing_urls': [], 'error': '',
            'root_sitemap_counts': [], 'child_sitemap_count': 0, 'sampled_child_count': 0,
            'page_urls_observed': 0, 'sitemap_url_samples': [],
            'volume_estimate': {'status': 'not_estimated', 'reason': 'Brak zweryfikowanych map.'}},
        'errors': [], 'recommendation': '', 'evidence': []}


def failed_result(source, exc):
    """Return a JSON-safe, reviewable failure without changing source state."""
    result = empty_result(source)
    detail = str(exc).strip().replace('\n', ' ')[:500]
    result.update(audit_status='failed', fatal_error=type(exc).__name__,
                  fatal_error_detail=detail, checked_at=timezone.now().isoformat(),
                  recommendation='Nie aktywować automatycznie. Sprawdź błąd techniczny i źródło ręcznie.')
    result['errors'].append({'kind': 'fatal_probe', 'url': source.url or source.rss_url or '',
                             'error': type(exc).__name__, 'detail': detail})
    return result


class SourceProbe:
    def __init__(self, source, network, request_limit=16):
        self.source, self.network = source, network
        self.result = empty_result(source)
        self.request_limit = request_limit
        self.cache = {}
        self.map_candidates = []
        self.sample_url = ''
        self.feed_home = ''

    def fetch(self, url, kind):
        url = public_link(url)
        if not url:
            return None, ''
        if url in self.cache:
            return self.cache[url]
        if len(self.cache) >= self.request_limit:
            self.result['errors'].append({'url': url, 'kind': kind, 'error': 'probe_request_limit'})
            return None, ''
        note = {'kind': kind, 'url': url}
        self.result['evidence'].append(note)
        self.cache[url] = (None, '')
        try:
            raw, final_url, policies = self.network.fetch(url)
            note.update(status='ok', final_url=final_url, bytes=len(raw), sha256=sha256(raw).hexdigest())
            for policy in policies:
                if not any(item.get('kind') == 'robots' and item.get('url') == policy['url'] for item in self.result['evidence']):
                    self.result['evidence'].append(dict(policy))
                self.map_candidates.extend(policy.get('sitemap_urls', []))
            self.cache[url] = (raw, final_url)
            return raw, final_url
        except Exception as exc:
            error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
            note.update(status='error', error=error)
            self.result['errors'].append({'kind': kind, 'url': url, 'error': error})
            cached_policy = getattr(self.network, 'policies', {}).get(origin(url))
            if cached_policy:
                policy = cached_policy[1]
                if not any(item.get('kind') == 'robots' and item.get('url') == policy['url'] for item in self.result['evidence']):
                    self.result['evidence'].append(dict(policy))
                self.map_candidates.extend(policy.get('sitemap_urls', []))
            return None, ''

    def feed(self, url):
        raw, final_url = self.fetch(url, 'rss')
        result = {'status': 'unavailable', 'url': url, 'entry_count': 0, 'usable_entry_count': 0, 'error': ''}
        if raw is None:
            result['error'] = next((e['error'] for e in reversed(self.result['errors']) if e['url'] == url), 'unavailable')
            return result
        if b'<!ENTITY' in raw.upper():
            result['error'] = 'xml_entities_not_allowed'; return result
        parsed = feedparser.parse(raw)
        if not parsed.get('version'):
            result['error'] = 'not_a_feed'; return result
        usable = [entry for entry in parsed.get('entries', []) if str(entry.get('title', '')).strip() and public_link(entry.get('link', ''))]
        result.update(status='working' if usable else 'empty', entry_count=len(parsed.entries),
                      usable_entry_count=len(usable), feed_version=parsed.version, final_url=final_url)
        if usable:
            self.sample_url = usable[0]['link']
            self.feed_home = public_link(parsed.feed.get('link', ''))
            date = parse_published(usable[0].get('published'))
            result['sample'] = {'url': self.sample_url, 'title': usable[0]['title'][:500],
                'published_date': date.isoformat() if date else None, 'date_raw': usable[0].get('published'),
                'publication_date_present': bool(date)}
        return result

    def homepage(self):
        source_url = self.source.url or self.source.rss_url
        is_feed_path = any(word in urlsplit(source_url).path.lower() for word in ('/rss', '/feed'))
        choices = list(dict.fromkeys([self.feed_home] + ([origin(source_url), source_url] if is_feed_path else [source_url, origin(source_url)])))
        parsed_home = None
        home_url = ''
        for url in choices:
            if not url:
                continue
            raw, final = self.fetch(url, 'publisher_page')
            if raw is None or not any(marker in raw[:8192].lower() for marker in (b'<html', b'<!doctype html', b'<head', b'<body')):
                continue
            parsed_home = PublisherLinks(); parsed_home.feed(decode_source_html(raw)); home_url = final
            # Follow an explicitly declared refresh once; never synthesize a new publisher domain.
            if parsed_home.refresh:
                target = urljoin(home_url, parsed_home.refresh)
                target_raw, target_final = self.fetch(target, 'publisher_refresh')
                if target_raw is not None:
                    parsed_home = PublisherLinks(); parsed_home.feed(decode_source_html(target_raw)); home_url = target_final
            break
        if parsed_home is None:
            return []
        # Many retired gov.pl RSS addresses redirect to the shared portal. A shared
        # homepage is not proof that the named institution has a usable listing.
        source_parts = urlsplit(source_url)
        if self.source.source_type == 'institution' and source_parts.hostname == 'www.gov.pl':
            segments = source_parts.path.strip('/').split('/')
            expected = '/' + '/'.join(segments[:2]) if len(segments) >= 2 and segments[0] == 'web' else ''
            if expected and not urlsplit(home_url).path.startswith(expected + '/') and urlsplit(home_url).path.rstrip('/') != expected:
                def institution_link(parser, base):
                    return next((public_link(urljoin(base, item['href'])) for item in parser.links
                        if urlsplit(urljoin(base, item['href'])).hostname == source_parts.hostname
                        and urlsplit(urljoin(base, item['href'])).path.rstrip('/') == expected), '')
                target = institution_link(parsed_home, home_url)
                if not target:
                    directory = next((public_link(urljoin(home_url, item['href'])) for item in parsed_home.links
                        if urlsplit(urljoin(home_url, item['href'])).hostname == source_parts.hostname
                        and urlsplit(urljoin(home_url, item['href'])).path.rstrip('/').endswith('/ministerstwa')), '')
                    if directory:
                        raw, final = self.fetch(directory, 'institution_directory')
                        if raw is not None:
                            directory_links = PublisherLinks(); directory_links.feed(decode_source_html(raw))
                            target = institution_link(directory_links, final)
                if target:
                    raw, final = self.fetch(target, 'institution_publisher_page')
                    if raw is not None and (urlsplit(final).path.rstrip('/') == expected
                            or urlsplit(final).path.startswith(expected + '/')):
                        parsed_home = PublisherLinks(); parsed_home.feed(decode_source_html(raw)); home_url = final
                    else:
                        target = ''
                if not target:
                    self.result['errors'].append({'kind': 'publisher_page', 'url': source_url,
                        'error': 'institution_redirected_to_shared_home'})
                    self.result['shared_portal_page'] = home_url
                    return []
        self.result['publisher_page'] = home_url
        feeds, listings = [], []
        host = (urlsplit(home_url).hostname or '').removeprefix('www.')
        for item in parsed_home.links:
            url = public_link(urljoin(home_url, item['href']))
            if not url:
                continue
            path = urlsplit(url).path.lower()
            text = item['text'].strip().lower()
            # An explicitly declared RSS/Atom service may be hosted on another
            # public domain. Every network hop is still checked by ProbeNetwork.
            explicit_feed = any(t in item['type'].lower() for t in ('rss', 'atom'))
            if explicit_feed and 'comment' not in path:
                feeds.append(url)
            if 'https://api.w.org/' in item['rel'] or '/wp-json' in path:
                self.result['evidence'].append({'kind': 'publisher_api_link', 'url': url,
                    'status': 'discovered_not_checked', 'rel': item['rel']})
            if (urlsplit(url).hostname or '').removeprefix('www.') != host:
                continue
            if not explicit_feed and any(t in path for t in ('/rss', '/feed')):
                if 'comment' not in path:
                    feeds.append(url)
            if 'sitemap' in path and (path.endswith('.xml') or path.endswith('.xml.gz')):
                self.map_candidates.append(url)
            if any(t in text for t in ('aktualności', 'wiadomości', 'archiwum', 'wydarzenia', 'kronika', 'wszystkie aktualności')):
                listings.append(url)
        self.result['archive']['listing_urls'] = list(dict.fromkeys(listings))[:12] or [home_url]
        self.result['archive']['status'] = 'html_candidate'
        return list(dict.fromkeys(feeds))

    def maps(self):
        archive = self.result['archive']
        candidates = list(dict.fromkeys(public_link(u) for u in self.map_candidates if public_link(u)))
        archive['declared_sitemap_urls'] = candidates
        children, pages = [], set()
        sampled_counts = []
        for url in candidates[:2]:
            raw, _ = self.fetch(url, 'root_sitemap')
            if raw is None:
                continue
            try:
                kind, entries = parse_sitemap(raw, url)
            except Exception as exc:
                self.result['errors'].append({'kind': 'root_sitemap', 'url': url,
                    'error': str(exc) if isinstance(exc, ProbeError) else type(exc).__name__})
                continue
            archive['sitemap_urls'].append(url)
            archive['root_sitemap_counts'].append({'url': url, 'kind': kind, 'loc_count': len(entries)})
            if kind == 'sitemapindex':
                children.extend(item['url'] for item in entries)
            else:
                pages.update(item['url'] for item in entries)
                archive['sitemap_url_samples'].extend(spread_sample(entries))
        children = list(dict.fromkeys(children))
        archive['child_sitemap_count'] = len(children)
        archive['sampled_child_maps'] = []
        for url in spread_sample(children):
            raw, _ = self.fetch(url, 'sample_child_sitemap')
            if raw is None:
                continue
            try:
                kind, entries = parse_sitemap(raw, url)
            except Exception as exc:
                self.result['errors'].append({'kind': 'sample_child_sitemap', 'url': url,
                    'error': str(exc) if isinstance(exc, ProbeError) else type(exc).__name__})
                continue
            archive['sampled_child_maps'].append({'url': url, 'kind': kind, 'loc_count': len(entries)})
            if kind == 'urlset':
                sampled_counts.append(len(entries))
                pages.update(item['url'] for item in entries)
                archive['sitemap_url_samples'].extend(spread_sample(entries))
        archive['sampled_child_count'] = len(archive['sampled_child_maps'])
        archive['page_urls_observed'] = len(pages)
        archive['sitemap_url_samples'] = archive['sitemap_url_samples'][:12]
        if not self.sample_url and archive['sitemap_url_samples']:
            self.sample_url = archive['sitemap_url_samples'][0]['url']
        if archive['sitemap_urls']:
            archive['status'] = 'sitemap'
            archive['error'] = ''
            fully_counted = (len(candidates) <= 2 and len(archive['root_sitemap_counts']) == len(candidates)
                and len(children) == len(sampled_counts))
            archive['volume_estimate'] = {
                'status': 'counted_declared_maps' if fully_counted else 'sample_only',
                'observed_unique_urls': len(pages), 'declared_root_count': len(candidates),
                'roots_checked': len(archive['root_sitemap_counts']), 'child_maps_declared': len(children),
                'leaf_maps_sampled': len(sampled_counts),
                'method': 'Do dwóch zadeklarowanych map głównych; pierwsza, środkowa i ostatnia mapa podrzędna w kolejności indeksu. Kolejność indeksu nie dowodzi kolejności dat.',
                'caution': 'Liczba URL w mapach nie jest liczbą potwierdzonych artykułów ani dowodem kompletności archiwum.'}
            if sampled_counts and not fully_counted:
                archive['volume_estimate']['naive_entry_range_from_samples'] = [min(sampled_counts) * len(children), max(sampled_counts) * len(children)]
                archive['volume_estimate']['range_caution'] = 'Wyłącznie arytmetyczna ekstrapolacja min/max wielkości próbek na liczbę map; nie przedział ufności ani potwierdzony zakres. Typy map i duplikaty mogą silnie zniekształcać wynik.'
        elif not archive['listing_urls']:
            archive['status'] = 'unavailable'
            archive['error'] = 'Nie potwierdzono dostępnej mapy ani strony kandydującej do odczytu HTML.'

    def run(self):
        result = self.result
        if self.source.catalog_stage == 'excluded' or not (self.source.url or self.source.rss_url):
            reason = 'excluded' if self.source.catalog_stage == 'excluded' else 'missing_url'
            result.update(audit_status='skipped', skipped_reason=reason, checked_at=timezone.now().isoformat())
            result['rss']['status'] = 'unknown'
            result['recommendation'] = 'Wykluczone przez właściciela — nie odpytywano.' if reason == 'excluded' else 'Ustal adres wydawcy; nie wymyślamy brakującego URL.'
            return result
        if self.source.rss_url:
            result['rss'] = self.feed(self.source.rss_url)
        candidates = self.homepage()
        if result['rss']['status'] != 'working':
            for url in candidates[:3]:
                if url == self.source.rss_url:
                    continue
                checked = self.feed(url)
                if checked['status'] == 'working':
                    result['rss'] = checked; break
                if checked['status'] == 'empty' and result['rss']['status'] != 'empty':
                    result['rss'] = checked
        self.maps()
        if self.source.source_type == 'institution' and (urlsplit(self.source.url or '').hostname or '') == 'api.sejm.gov.pl':
            record = OfficialRecord.objects.filter(article__source_id=self.source.pk).order_by('-fetched_at').values('api_url').first()
            if record:
                raw, final_url = self.fetch(record['api_url'], 'official_api_record')
                result['official_api'] = {'status': 'unavailable', 'url': record['api_url'], 'sample_record_checked': False}
                if raw is not None:
                    try:
                        payload = json.loads(raw)
                        if not isinstance(payload, (dict, list)):
                            raise ValueError('not_json_container')
                        result['official_api'].update(status='working', sample_record_checked=True, final_url=final_url)
                    except (ValueError, UnicodeError):
                        result['official_api']['error'] = 'not_valid_json'
        if self.sample_url and len(self.cache) < self.request_limit:
            raw, final = self.fetch(self.sample_url, 'sample_metadata')
            if raw is not None:
                try:
                    meta = extract_metadata(raw, final)
                    result['sample_metadata'] = {key: value for key, value in meta.items() if key in
                        ('url', 'title', 'image_url', 'published_date', 'date_raw', 'date_source', 'category', 'warnings')}
                except Exception as exc:
                    result['errors'].append({'kind': 'sample_metadata', 'url': self.sample_url, 'error': type(exc).__name__})
        if result.get('official_api', {}).get('status') == 'working':
            result['recommendation'] = 'Działa próbka oficjalnego API; zachowaj dedykowany importer. Brak RSS nie oznacza awarii API.'
        elif result['rss']['status'] == 'working':
            result['recommendation'] = 'Kanał zwraca użyteczne metadane. ' + ('Zastosuj potwierdzony RSS w konfiguracji. ' if result['rss']['url'] != self.source.rss_url else '')
            result['recommendation'] += 'Archiwum przez mapy wymaga osobnego importu.' if result['archive']['status'] == 'sitemap' else 'Pełny zakres historyczny niepotwierdzony.'
        elif result['archive']['status'] == 'sitemap':
            result['recommendation'] = 'Potwierdzono mapę XML. Możliwy importer archiwum; nie potwierdzono działającego RSS.'
        elif result['archive']['status'] == 'html_candidate':
            result['recommendation'] = 'Dostępna strona HTML. Wymaga dedykowanego odczytu list i kontroli dat; kandydat, nie gotowy importer.'
        else:
            result['recommendation'] = 'Brak potwierdzonej metody w ograniczonej kontroli. Zachowaj jawną lukę i zweryfikuj błędy.'
        result.update(checked_at=timezone.now().isoformat(), audit_status='completed', requests_checked=len(self.cache))
        # Metadata parser may return datetime objects; durable cursor is always JSON-safe.
        return json.loads(json.dumps(result, ensure_ascii=False, default=str))


def probe_source(source, network=None):
    return SourceProbe(source, network or ProbeNetwork()).run()


def begin_source_audit(source):
    """Short checkpoint write; never hold a database transaction during network I/O."""
    ImportState.objects.update_or_create(name=f'source-check:{source.pk}', defaults={
        'last_started': timezone.now(), 'last_error': '', 'cursor': empty_result(source)})


def save_source_audit(source, result):
    """last_success denotes a finished audit, including unavailable or deliberately skipped sources."""
    complete = result.get('audit_status') in ('completed', 'skipped')
    defaults = {'cursor': result, 'last_error': '' if complete else result.get('fatal_error', 'audit_failed')[:200]}
    if complete:
        defaults['last_success'] = timezone.now()
    ImportState.objects.update_or_create(name=f'source-check:{source.pk}', defaults=defaults)


def audit_source(source, network=None):
    begin_source_audit(source)
    try:
        result = probe_source(source, network)
    except Exception as exc:
        result = failed_result(source, exc)
    save_source_audit(source, result)
    return result
