"""Kontrola wpisów z X u źródła (wymóg S2, pkt 8): wpis usunięty przez autora znika z odpowiedzi w ciągu 24 h.

spina3_sync (cron co 15 min) sprawdza najwyżej `X_CHECK_LIMIT` wpisów na przebieg przez publiczny oEmbed X (bez klucza API,
bez danych użytkowników), najpierw nigdy niesprawdzone, potem najdawniej sprawdzone. 404 albo 410 = wpis usunięty:
`importer.mark_post_removed` czyści treść (box zostaje z autorem i adresem źródła). Inne odpowiedzi i błędy sieci = brak zmiany.
Transport podstawialny (testy bez sieci).
"""
from __future__ import annotations

from typing import Callable

from django.db.models import F
from django.utils import timezone

from .models import Box

X_OEMBED_URL = 'https://publish.twitter.com/oembed'
X_CHECK_LIMIT = 60
REMOVED_STATUSES = (404, 410)


def oembed_status(url: str) -> int | None:
    import requests
    response = requests.get(X_OEMBED_URL, params={'url': url, 'omit_script': 'true', 'dnt': 'true'}, timeout=10)
    return response.status_code


def check_posts(limit: int = X_CHECK_LIMIT, transport: Callable[[str], int | None] | None = None, now=None) -> dict:
    from .importer import mark_post_removed
    now = now or timezone.now()
    transport = transport or oembed_status
    rows = list(Box.objects.filter(kind='post', source_status='active')
                .order_by(F('source_checked_at').asc(nulls_first=True), 'pk')[:min(limit, X_CHECK_LIMIT)])
    checked = removed = errors = 0
    for box in rows:
        Box.objects.filter(pk=box.pk).update(source_checked_at=now)   # także po błędzie: kolejka idzie dalej
        try:
            status = transport(box.url)
        except Exception:  # noqa: BLE001 - sieć albo limit X: wpis wróci w kolejnym okrążeniu
            errors += 1
            continue
        checked += 1
        if status in REMOVED_STATUSES:
            box.refresh_from_db()
            mark_post_removed(box, now)
            removed += 1
    return {'x_checked': checked, 'x_removed': removed, 'x_errors': errors}
