"""Strażnik mediów (raport źródeł 6.10, punkt 7): kopia cytowanego artykułu w Wayback Machine i alarm po cichej edycji.

1. Zbiór cytowań (bez sieci): adresy źródeł z opublikowanych diagnoz (sprawdzenie tez), diagnoz wystąpień z Sejmu
   i artykułów w tematach dnia przeszłość.today.
2. Kopia: najpierw Availability API (kopia z dnia cytowania już istnieje), inaczej Save Page Now (kluczem IA_S3_*
   gdy jest, bez klucza zwykłe zapytanie save) - najwyżej MEDIA_WATCH_SAVES_PER_RUN na przebieg, co 5 s (limit 15/min).
3. Raz na dobę: skrót SHA-256 tekstu akapitów artykułu (tekstu nie zapisujemy). Inny skrót niż poprzednio = zmiana
   po cytowaniu: data, licznik, nowa kopia w archiwum i link porównania Wayback. robots.txt jest respektowany.
Flaga MEDIA_WATCH_ENABLED (domyślnie wyłączona). Bez AI.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from hashlib import sha256
import logging
import os
import re
from time import sleep
from urllib.parse import quote, urlsplit

from django.core.cache import cache
from django.utils import timezone

from news.repairer import flag

logger = logging.getLogger(__name__)
AVAILABLE = 'https://archive.org/wayback/available'
SAVE = 'https://web.archive.org/save/'
SKIP_HOSTS = ('x.com', 'twitter.com', 'web.archive.org', 'archive.org', 'spin.clinic', 'przeszlosc.today', 'youtube.com',
              'www.youtube.com', 'facebook.com', 'www.facebook.com')
MAX_BYTES = 3_000_000


def enabled():
    return flag('MEDIA_WATCH_ENABLED', False)


def _int(name, default):
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def url_key(url):
    return sha256(url.encode()).hexdigest()


def usable(url):
    try:
        p = urlsplit(str(url))
    except ValueError:
        return False
    host = (p.hostname or '').lower()
    return (p.scheme == 'https' and bool(host) and not p.username and len(url) <= 1024
            and not any(host == h or host.endswith('.' + h) for h in SKIP_HOSTS))


def cited_urls():
    """{adres: {odwołania}} z opublikowanych treści (tylko baza)."""
    from news.clinic import published_diagnoses
    found = {}

    def add(url, ref):
        if usable(url):
            found.setdefault(url, set()).add(ref)

    since = timezone.now() - timedelta(days=_int('MEDIA_WATCH_DAYS', 30))
    for pk, claims in published_diagnoses().filter(diagnosed_at__gte=since).values_list('pk', 'claims'):
        for claim in claims or []:
            for source in claim.get('sources') or []:
                if isinstance(source, dict) and source.get('type') != 'istniejący fact-check':
                    add(source.get('url', ''), f'diagnosis:{pk}')
    from news.sejm_wideo import published
    for row in published().filter(diagnosed_at__gte=since):
        for claim in row.claims or []:
            for source in claim.get('sources') or []:
                if isinstance(source, dict):
                    add(source.get('url', ''), f'sejm:{row.pk}')
    try:
        from news.przeszlosc import auto_topics, topic_graph
        for topic in auto_topics()[:6]:
            for node in topic_graph(topic['topic'])['nodes']:
                if node.get('kind') == 'media':
                    add(node.get('url', ''), 'topic:' + topic['topic'][:60])
    except Exception:  # noqa: BLE001 - temat dnia nie może zatrzymać strażnika
        logger.warning('media watch: topics unavailable')
    return found


def register():
    from news.zrodla_models import CitedArticle
    created = 0
    for url, refs in cited_urls().items():
        row, new = CitedArticle.objects.get_or_create(url_sha256=url_key(url), defaults={'url': url, 'cited_by': sorted(refs)})
        created += int(new)
        if not new and not refs <= set(row.cited_by or []):
            row.cited_by = sorted(set(row.cited_by or []) | refs)[:50]
            row.save(update_fields=['cited_by'])
    return created


def _get(url, **kwargs):
    import requests
    from scraper.utils import SOURCE_USER_AGENT
    return requests.get(url, timeout=(10, 40), headers={'User-Agent': SOURCE_USER_AGENT}, **kwargs)


def available(url, when):
    """Kopia w Wayback z dnia cytowania (±3 dni) albo None."""
    response = _get(AVAILABLE, params={'url': url, 'timestamp': when.strftime('%Y%m%d%H%M%S')}, allow_redirects=False)
    response.raise_for_status()
    closest = ((response.json() or {}).get('archived_snapshots') or {}).get('closest') or {}
    stamp = str(closest.get('timestamp', ''))
    if not closest.get('available') or not re.fullmatch(r'\d{14}', stamp):
        return None
    taken = datetime.strptime(stamp, '%Y%m%d%H%M%S').replace(tzinfo=dt_timezone.utc)
    if abs((taken - when).total_seconds()) > 3 * 86400:
        return None
    return f'https://web.archive.org/web/{stamp}/{url}', taken


def save(url):
    """Save Page Now: z kluczem IA (news.clinic_lab.archive_request) albo zwykłe zapytanie save. (link, czas) albo None."""
    from news.clinic_lab import archive_request
    if os.environ.get('IA_S3_ACCESS') and os.environ.get('IA_S3_SECRET'):
        result = archive_request(url)
        stamp = str((result or {}).get('timestamp', ''))
        if re.fullmatch(r'\d{14}', stamp):
            return f'https://web.archive.org/web/{stamp}/{url}', timezone.now()
        return None  # zgłoszone, kopia powstaje w tle; kolejny przebieg znajdzie ją przez Availability API
    response = _get(SAVE + url, allow_redirects=False)
    location = response.headers.get('Content-Location') or response.headers.get('Location') or ''
    match = re.search(r'/web/(\d{14})/', location)
    if response.status_code in (200, 301, 302) and match:
        return f'https://web.archive.org/web/{match[1]}/{url}', timezone.now()
    return None


def robots_allowed(url):
    from urllib.robotparser import RobotFileParser
    from scraper.utils import SOURCE_USER_AGENT
    p = urlsplit(url)
    key = 'media-watch:robots:' + p.netloc
    rules = cache.get(key)
    if rules is None:
        try:
            response = _get(f'{p.scheme}://{p.netloc}/robots.txt', allow_redirects=False)
            rules = response.text[:200_000] if response.status_code == 200 else ''
        except Exception:  # noqa: BLE001
            rules = ''
        cache.set(key, rules, 86400)
    parser = RobotFileParser()
    parser.parse(rules.splitlines())
    return parser.can_fetch(SOURCE_USER_AGENT, url)


def fingerprint(raw):
    """(tytuł, skrót SHA-256 tekstu akapitów); sam tekst nie wychodzi poza funkcję."""
    from scraper.public_record_parsers import HTML
    root = HTML(raw[:MAX_BYTES]).root
    title = next((t.text() for t in root.find('title')), '')[:300]
    scope = next(root.find('article'), None) or root
    text = '\n'.join(p.text() for p in scope.find('p') if len(p.text()) > 40)
    if not text:
        return title, ''
    return title, sha256(' '.join(text.split()).encode()).hexdigest()


def check(row):
    """Jedno sprawdzenie artykułu; zwraca nowy stan (ok, zmieniony, niedostępny, robots, brak tekstu)."""
    now = timezone.now()
    if not robots_allowed(row.url):
        status, code, digest, title = 'robots', None, '', ''
    else:
        response = _get(row.url, allow_redirects=True, stream=True)
        code = response.status_code
        raw = response.raw.read(MAX_BYTES, decode_content=True) if code == 200 else b''
        response.close()
        title, digest = fingerprint(raw) if raw else ('', '')
        status = 'niedostępny' if code != 200 else ('brak tekstu' if not digest else 'ok')
    row.title = row.title or title
    if digest and not row.first_sha256:
        row.first_sha256 = row.last_sha256 = digest
    elif digest and digest != row.last_sha256:
        row.changed_at, row.change_count, row.last_sha256, status = now, row.change_count + 1, digest, 'zmieniony'
        try:
            saved = save(row.url)
        except Exception:  # noqa: BLE001
            saved = None
        if saved:
            row.changed_archive_url = saved[0]
    row.check_status, row.last_checked_at = status, now
    row.history = [{'at': now.isoformat(timespec='minutes'), 'sha256': digest[:16], 'http': code, 'status': status},
                   *(row.history or [])][:30]
    row.save()
    return status


def compare_url(row):
    """Link porównania wersji w Wayback (kopia z dnia cytowania vs kopia po zmianie)."""
    first = re.search(r'/web/(\d{14})/', row.archive_url or '')
    second = re.search(r'/web/(\d{14})/', row.changed_archive_url or '')
    if first and second:
        return f'https://web.archive.org/web/diff/{first[1]}/{second[1]}/{quote(row.url, safe=":/")}'
    return ''


def run(now=None):
    from news.zrodla_models import CitedArticle
    if not enabled():
        return {'status': 'disabled'}
    now = now or timezone.now()
    added = register()
    saved = checked = changed = 0
    for row in CitedArticle.objects.filter(archive_url='', archive_attempts__lt=5).order_by('first_cited_at')[:_int('MEDIA_WATCH_SAVES_PER_RUN', 8)]:
        try:
            result = available(row.url, row.first_cited_at) or save(row.url)
            sleep(0 if os.environ.get('PYTEST_VERSION') else 5)
        except Exception as error:  # noqa: BLE001 - archiwum chwilowo niedostępne: kolejna próba w następnym przebiegu
            logger.info('media watch archive %s: %s', row.pk, type(error).__name__)
            result = None
        row.archive_attempts += 1
        if result:
            row.archive_url, row.archived_at, row.archive_status = result[0][:1500], result[1], 'ok'
            saved += 1
        else:
            row.archive_status = 'czeka' if row.archive_attempts < 5 else 'brak kopii'
        row.save(update_fields=['archive_url', 'archived_at', 'archive_status', 'archive_attempts'])
    due = now - timedelta(hours=24)
    window = now - timedelta(days=_int('MEDIA_WATCH_DAYS', 30))
    rows = (CitedArticle.objects.filter(first_cited_at__gte=window)
            .exclude(last_checked_at__gte=due).order_by('last_checked_at')[:_int('MEDIA_WATCH_CHECKS_PER_RUN', 40)])
    for row in rows:
        try:
            status = check(row)
        except Exception as error:  # noqa: BLE001
            logger.info('media watch check %s: %s', row.pk, type(error).__name__)
            continue
        checked += 1
        changed += int(status == 'zmieniony')
    return {'status': 'ok', 'new': added, 'archived': saved, 'checked': checked, 'changed': changed}


def archives_for(urls):
    """{adres: {kopia, zmieniony}} dla źródeł diagnozy (strona diagnozy)."""
    from news.zrodla_models import CitedArticle
    keys = {url_key(u): u for u in urls if u}
    out = {}
    for row in CitedArticle.objects.filter(url_sha256__in=list(keys)).exclude(archive_url=''):
        out[keys[row.url_sha256]] = {'archive_url': row.archive_url, 'archived_at': row.archived_at,
                                     'changed_at': row.changed_at, 'compare_url': compare_url(row)}
    return out


def recent_changes(days=7):
    from news.zrodla_models import CitedArticle
    return CitedArticle.objects.filter(changed_at__gte=timezone.now() - timedelta(days=days)).order_by('-changed_at')
