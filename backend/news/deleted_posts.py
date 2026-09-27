"""Strażnica usuniętych postów polityków (OSINT): czy wpis nadal istnieje na X.

Sprawdzamy darmowym, publicznym oEmbed X (publish.twitter.com) — bez płatnego API. 404 oznacza, że wpis usunięto
albo stał się niedostępny. Zgodnie z zasadami X usuwamy wtedy jego treść u siebie; zostaje tylko fakt: kto, kiedy
opublikował, kiedy zniknął i czy Dr. Spin ocenił go jako spin. Tempo: najwyżej jedno zapytanie na 2 sekundy.
"""
import time
from datetime import timedelta

import requests
from django.db.models import Count, F
from django.utils import timezone

from news.political_models import PoliticalPost

OEMBED = 'https://publish.twitter.com/oembed'
WINDOW_DAYS = 14  # po dwóch tygodniach posty już nie znikają „po cichu” — nie sprawdzamy ich w kółko


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


def mark_deleted(post: PoliticalPost) -> None:
    """Fakt usunięcia zostaje, treść wpisu znika (zasady X: honorujemy usunięcia)."""
    post.available, post.unavailable_at = False, timezone.now()
    post.text, post.source_data, post.media = '', {}, []
    post.save(update_fields=['available', 'unavailable_at', 'text', 'source_data', 'media'])


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
    return {'checked': checked, 'deleted': deleted}


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
        'verdict': verdicts.get(row.pk, ''), 'verdict_label': VERDICT_LABELS.get(verdicts.get(row.pk, ''), ''),
    } for row in rows]
    week = timezone.now() - timedelta(days=7)
    per_camp = dict(PoliticalPost.objects.filter(available=False, unavailable_at__gte=week)
                    .values_list('camp_at_collection').annotate(n=Count('id')))
    return {'days': days, 'items': items, 'week_by_camp': per_camp}
