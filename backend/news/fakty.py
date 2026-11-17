"""„Tę tezę sprawdzili” (raport źródeł 6.10, punkt 13): weryfikacje tych samych tez z Google Fact Check Tools API.

Klucz: FACTCHECK_API_KEY (darmowy klucz Google Cloud, dodaje właściciel; bez klucza nic nie wychodzi do sieci).
Flaga: FACTCHECK_ENABLED (domyślnie wyłączona). Dzienny limit zapytań FACTCHECK_DAILY (domyślnie 100).
Przy diagnozie zapisujemy tylko wydawcę, werdykt, tytuł i link (bez treści weryfikacji) w usage['factchecks'];
diagnozy nie zmieniamy. Nowe diagnozy dostają te same dane już w laboratorium (news.clinic_lab.fact_checks).
"""
from datetime import timedelta
import os

from django.core.cache import cache
from django.utils import timezone

from news.repairer import flag


def enabled():
    return flag('FACTCHECK_ENABLED', False) and bool(os.environ.get('FACTCHECK_API_KEY', '').strip())


def _daily():
    try:
        return max(0, int(os.environ.get('FACTCHECK_DAILY', '100')))
    except ValueError:
        return 100


def _spend():
    key = f'factcheck:{timezone.localdate().isoformat()}'
    cache.add(key, 0, timeout=2 * 86400)
    return cache.incr(key) <= _daily()


def lookup(claims):
    from news.clinic_lab import fact_checks
    found = {}
    for claim in claims[:3]:
        if not claim or not _spend():
            break
        result = fact_checks(claim[:300])
        for item in result if isinstance(result, list) else []:
            found.setdefault(item['url'], {k: item.get(k, '') for k in ('publisher', 'rating', 'url', 'title', 'reviewed_claim')})
    return list(found.values())[:8]


def _claims(row):
    texts = [str(c.get('claim', '')) for c in row.claims or [] if isinstance(c, dict) and c.get('claim')]
    return texts or [row.headline]


def run(limit=20):
    """Opublikowane diagnozy z ostatnich 30 dni bez sprawdzenia: wpisy z X i wystąpienia z Sejmu."""
    from news.clinic import published_diagnoses
    from news.sejm_wideo import published as sejm_published
    if not enabled():
        return {'status': 'disabled'}
    since = timezone.now() - timedelta(days=30)
    done = found = 0
    for rows in (published_diagnoses().filter(diagnosed_at__gte=since), sejm_published().filter(diagnosed_at__gte=since)):
        for row in rows.order_by('-diagnosed_at')[:limit]:
            if (row.usage or {}).get('factchecks') is not None:
                continue
            items = lookup(_claims(row))
            row.usage = {**(row.usage or {}), 'factchecks': {'at': timezone.now().isoformat(timespec='minutes'), 'items': items}}
            type(row).objects.filter(pk=row.pk).update(usage=row.usage)
            done += 1
            found += len(items)
            if done >= limit:
                return {'status': 'ok', 'checked': done, 'found': found}
    return {'status': 'ok', 'checked': done, 'found': found}


def public(row):
    """Lista do strony diagnozy: zapis z usage i weryfikacje dopisane już w laboratorium (źródła tez)."""
    items = {i['url']: i for i in ((row.usage or {}).get('factchecks') or {}).get('items') or []}
    for claim in row.claims or []:
        for source in claim.get('sources') or [] if isinstance(claim, dict) else []:
            if isinstance(source, dict) and source.get('type') == 'istniejący fact-check' and source.get('url'):
                items.setdefault(source['url'], {k: source.get(k, '') for k in ('publisher', 'rating', 'url', 'title', 'reviewed_claim')})
    return list(items.values())[:8]
