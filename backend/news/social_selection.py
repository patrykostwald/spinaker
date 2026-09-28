"""Najmocniejsza diagnoza dnia każdej strony, z naprzemiennym pierwszeństwem."""
from django.utils import timezone


def day_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def select(rows, history, limit):
    if limit <= 0:
        return []
    camps = ('government', 'opposition')
    used = {camp for camp, when in history if when >= day_start()}
    last = history[0][0] if history else None
    order = list(camps)
    if last in order:
        order.remove(last)
        order.append(last)
    best = {}
    for row in rows:
        camp = row.post.camp_at_collection
        if camp in camps and camp not in used and camp not in best:
            best[camp] = row
    return [best[camp] for camp in order if camp in best][:limit]
