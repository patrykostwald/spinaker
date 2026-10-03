"""Izba przyjęć tropów czytelników.

Trop czytelnika najpierw stoi w izbie; na główną listę przechodzi, gdy w ciągu 7 dni od publikacji zbierze co najmniej
10 ocen ✓ i ✓ stanowią co najmniej 60% wszystkich ocen. Liczą się oceny innych osób z kont starszych niż doba
(ochrona przed kontami założonymi tylko do podbicia tropu). Tropy Dr. Spina nie przechodzą przez izbę.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

POSITIVE = lambda: int(getattr(settings, 'ADMISSION_POSITIVE', 10))
RATIO = lambda: float(getattr(settings, 'ADMISSION_RATIO', 0.6))
WINDOW = timedelta(days=7)
MIN_ACCOUNT_AGE = timedelta(days=1)


def progress(thread, now=None):
    now = now or timezone.now()
    opinions = thread.opinions.exclude(user_id=thread.owner_id).filter(user__date_joined__lte=now - MIN_ACCOUNT_AGE)
    counts = {key: 0 for key in ('positive', 'doubt', 'negative')}
    for polarity in opinions.values_list('polarity', flat=True):
        counts[polarity] += 1
    total = sum(counts.values())
    start = thread.published_at or thread.created_at
    left = WINDOW - (now - start)
    return {'positive': counts['positive'], 'needed': POSITIVE(), 'ratio': round(counts['positive'] / total, 2) if total else 0,
            'ratio_needed': RATIO(), 'days_left': max(0, left.days + (1 if left.seconds else 0)) if left.total_seconds() > 0 else 0,
            'open': left.total_seconds() > 0}


def check_admission(thread, now=None):
    """Przenosi trop czytelnika na główną listę, gdy spełnia progi. Zwraca True, jeśli właśnie przyjęto."""
    if thread.owner_id is None or thread.admitted_at or not thread.is_public:
        return False
    data = progress(thread, now)
    if data['open'] and data['positive'] >= data['needed'] and data['ratio'] >= data['ratio_needed']:
        type(thread).objects.filter(pk=thread.pk, admitted_at__isnull=True).update(admitted_at=now or timezone.now())
        return True
    return False
