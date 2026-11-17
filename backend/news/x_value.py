"""Czytanie X według wartości konta (właściciel 6.10: „najwięcej tracimy na zapytaniach”, legalnie i taniej).

Płacimy X za każdy zwrócony wpis, więc najtańszy wpis to ten, którego nie pobieramy z kont, z których od miesiąca
nie wyszła żadna diagnoza. Raz dziennie liczymy wartość każdego konta z ostatnich 30 dni i ustawiamy, jak często je czytać:
- konta z diagnozą w 30 dniach: co 15 min (wpisy, które naprawdę analizujemy),
- konta aktywne, ale bez diagnoz: co 60 min,
- konta, które pisały mało albo wcale: co 240 min (wciąż nic nie gubimy: zaległe wpisy przyjdą przy następnym odczycie).
Opłata X jest za wpis, nie za odczyt, więc rzadsze czytanie nie gubi wpisów, ale zmniejsza puste zapytania i dzienny
limit zapytań. Ustawienie: X_VALUE_INTERVALS=false wyłącza (zostaje ręczny harmonogram)."""
import os
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

FAST, NORMAL, SLOW = 15, 60, 240


def enabled():
    return os.environ.get('X_VALUE_INTERVALS', 'true').strip().lower() != 'false'


def plan(days=30):
    """{account_id: (minuty, powód)} dla włączonych kont."""
    from news.political_models import PoliticalAccount
    since = timezone.now() - timedelta(days=days)
    rows = (PoliticalAccount.objects.filter(enabled=True)
            .annotate(n_posts=Count('posts', filter=Q(posts__published_at__gte=since)),
                      diagnosed=Count('posts__spin_diagnosis', filter=Q(posts__published_at__gte=since))))
    out = {}
    for a in rows:
        if a.diagnosed:
            out[a.pk] = (FAST, f'{a.diagnosed} diagnoz w {days} dni')
        elif a.n_posts >= 10:
            out[a.pk] = (NORMAL, f'{a.n_posts} wpisów, bez diagnoz')
        else:
            out[a.pk] = (SLOW, f'{a.n_posts} wpisów w {days} dni')
    return out


def apply(days=30):
    """Ustawia interwały; zwraca podsumowanie i szacunek zapytań na dobę przed i po."""
    from news.political_models import PoliticalAccount
    if not enabled():
        return {'enabled': False}
    target = plan(days)
    accounts = {a.pk: a for a in PoliticalAccount.objects.filter(pk__in=target)}
    before = sum(1440 / max(1, a.poll_interval_minutes) for a in accounts.values())
    changed = 0
    for pk, (minutes, _) in target.items():
        account = accounts[pk]
        if account.poll_interval_minutes != minutes:
            PoliticalAccount.objects.filter(pk=pk).update(poll_interval_minutes=minutes)
            changed += 1
    after = sum(1440 / minutes for minutes, _ in target.values())
    counts = {m: sum(1 for v, _ in target.values() if v == m) for m in (FAST, NORMAL, SLOW)}
    return {'enabled': True, 'accounts': len(target), 'changed': changed, 'fast': counts[FAST], 'normal': counts[NORMAL],
            'slow': counts[SLOW], 'requests_day_before': round(before), 'requests_day_after': round(after)}
