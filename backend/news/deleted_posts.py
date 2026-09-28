"""Strażnica usuniętych postów polityków (OSINT): czy wpis nadal istnieje na X.

Sprawdzamy darmowym, publicznym oEmbed X (publish.twitter.com) — bez płatnego API. 404 oznacza, że wpis usunięto
albo stał się niedostępny. Zgodnie z zasadami X usuwamy wtedy jego treść u siebie; zostaje tylko fakt: kto, kiedy
opublikował, kiedy zniknął i czy Dr. Spin ocenił go jako spin. Tempo: najwyżej jedno zapytanie na 2 sekundy.

Archiwum: jeśli ktoś niezależny zachował wpis w Wayback Machine (archive.org) przed usunięciem, linkujemy do tej
kopii — sami treści nie przechowujemy. Sprawdzamy przez darmowe API CDX: przy wykryciu usunięcia, potem jeszcze
raz na dobę przez tydzień (kopie bywają dodawane później).
"""
import re
import time
from datetime import timedelta
from datetime import timezone as dt_timezone

import requests
from django.db.models import Count, F
from django.utils import timezone

from news.political_models import PoliticalPost

OEMBED = 'https://publish.twitter.com/oembed'
WINDOW_DAYS = 14  # po dwóch tygodniach posty już nie znikają „po cichu” — nie sprawdzamy ich w kółko
CDX = 'https://web.archive.org/cdx/search/cdx'
ARCHIVE_RETRY_DAYS = 7
STATUS = re.compile(r'(?:x|twitter)\.com/([^/]+)/status/(\d+)', re.I)


def _exists(url: str) -> bool | None:
    """True — wpis jest; False — usunięty albo niedostępny (404); None — nie wiadomo (limit, błąd sieci)."""
    try:
        response = requests.get(OEMBED, params={'url': url, 'omit_script': 'true'}, timeout=(5, 15),
                                headers={'User-Agent': 'spin.clinic deleted-post check'})
    except requests.RequestException:
        return None
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    return None


def find_archive(url: str, before) -> str | None:
    """Link do ostatniej kopii wpisu w Wayback Machine sprzed usunięcia; '' — brak kopii; None — archiwum nie odpowiada."""
    match = STATUS.search(url or '')
    if not match:
        return ''
    handle, status_id = match.groups()
    best = ''
    for host in ('x.com', 'twitter.com'):
        params = {'url': f'{host}/{handle}/status/{status_id}', 'output': 'json', 'filter': 'statuscode:200',
                  'fl': 'timestamp,original', 'limit': '-5'}
        if before:
            params['to'] = before.astimezone(dt_timezone.utc).strftime('%Y%m%d%H%M%S')
        try:
            response = requests.get(CDX, params=params, timeout=(5, 20), headers={'User-Agent': 'spin.clinic archive check'})
            response.raise_for_status()
            rows = response.json() if response.text.strip() else []
        except (requests.RequestException, ValueError):
            return None
        for timestamp, original in rows[1:]:  # pierwszy wiersz to nagłówek
            if timestamp > best[:14]:
                best = f'{timestamp}/{original}'
    return f'https://web.archive.org/web/{best}' if best else ''


def refresh_archive(post: PoliticalPost) -> None:
    found = find_archive(post.url, post.unavailable_at)
    if found is None:
        return
    post.archive_url, post.archive_checked_at = found or post.archive_url, timezone.now()
    post.save(update_fields=['archive_url', 'archive_checked_at'])


def mark_deleted(post: PoliticalPost) -> None:
    """Fakt usunięcia zostaje, treść wpisu znika (zasady X: honorujemy usunięcia)."""
    post.available, post.unavailable_at = False, timezone.now()
    post.text, post.source_data, post.media = '', {}, []
    post.save(update_fields=['available', 'unavailable_at', 'text', 'source_data', 'media'])
    refresh_archive(post)
    # Nasz wpis na X pokazywał treść tego wpisu (obrazek) — znika razem z nim.
    diagnosis = getattr(post, 'spin_diagnosis', None)
    if diagnosis is not None and diagnosis.x_posted_ids:
        from news.x_publish import unpublish_deleted
        unpublish_deleted(diagnosis)


def archive_batch(limit: int = 20, pause: float = 2.0) -> int:
    """Ponowne szukanie kopii dla niedawno usuniętych wpisów bez kopii — raz na dobę, przez tydzień."""
    now = timezone.now()
    rows = (PoliticalPost.objects.filter(available=False, archive_url='', unavailable_at__gte=now - timedelta(days=ARCHIVE_RETRY_DAYS))
            .exclude(archive_checked_at__gte=now - timedelta(hours=23)).order_by('-unavailable_at')[:limit])
    found = 0
    for index, post in enumerate(rows):
        if index:
            time.sleep(pause)
        refresh_archive(post)
        found += bool(post.archive_url)
    return found


def check_batch(limit: int = 60, pause: float = 2.0) -> dict:
    since = timezone.now() - timedelta(days=WINDOW_DAYS)
    rows = (PoliticalPost.objects.filter(available=True, published_at__gte=since)
            .order_by(F('availability_checked_at').asc(nulls_first=True), '-published_at')[:limit])
    checked = deleted = 0
    for index, post in enumerate(rows):
        if index:
            time.sleep(pause)
        exists = _exists(post.url)
        if exists is None:
            break  # limit albo awaria po stronie X — spróbujemy przy następnym przebiegu
        checked += 1
        if exists:
            post.availability_checked_at = timezone.now()
            post.save(update_fields=['availability_checked_at'])
        else:
            mark_deleted(post)
            deleted += 1
    return {'checked': checked, 'deleted': deleted, 'archived': archive_batch()}


def deleted_data(days: int = 30, limit: int = 60) -> dict:
    """Lista usuniętych postów z ostatnich dni (bez treści) i liczby na konto — do panelu w Klinice."""
    from news.clinic import CAMP_LABELS, VERDICT_LABELS, author_data, figures_by_account
    since = timezone.now() - timedelta(days=days)
    rows = list(PoliticalPost.objects.filter(available=False, unavailable_at__gte=since)
                .select_related('account').order_by('-unavailable_at')[:limit])
    figures = figures_by_account({row.account_id for row in rows})
    from news.clinic_models import SpinDiagnosis
    verdicts = dict(SpinDiagnosis.objects.filter(post__in=rows).exclude(verdict='').values_list('post_id', 'verdict'))
    items = [{
        'author': author_data(row, figures.get(row.account_id)),
        'camp': row.camp_at_collection, 'camp_label': CAMP_LABELS.get(row.camp_at_collection, ''),
        'published_at': row.published_at, 'unavailable_at': row.unavailable_at,
        'hours_visible': round((row.unavailable_at - row.published_at).total_seconds() / 3600, 1),
        'archive_url': row.archive_url,
        'archive_search_url': f'https://archive.ph/{row.url}',
        'verdict': verdicts.get(row.pk, ''), 'verdict_label': VERDICT_LABELS.get(verdicts.get(row.pk, ''), ''),
    } for row in rows]
    week = timezone.now() - timedelta(days=7)
    per_camp = dict(PoliticalPost.objects.filter(available=False, unavailable_at__gte=week)
                    .values_list('camp_at_collection').annotate(n=Count('id')))
    month = timezone.now() - timedelta(days=30)
    counts = (PoliticalPost.objects.filter(available=False, unavailable_at__gte=month).values('account_id')
              .annotate(n=Count('id')).filter(n__gte=2).order_by('-n')[:5])
    top_deleters = []
    for row in counts:
        latest = (PoliticalPost.objects.filter(account_id=row['account_id'], available=False)
                  .select_related('account').order_by('-unavailable_at').first())
        figure = figures_by_account({row['account_id']}).get(row['account_id'])
        top_deleters.append({'author': author_data(latest, figure), 'count': row['n']})
    return {'days': days, 'items': items, 'week_by_camp': per_camp, 'top_deleters': top_deleters}
