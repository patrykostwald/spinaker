"""Retencja danych spina3 (S2, 14.10.2026): komenda `spina3_retention` (cron raz na dobę, docs/SPINA3_BACKEND.md).

- Konto oznaczone do usunięcia (DELETE me/): po 30 dniach przypięcia usunięte, teza, komentarz autora i komentarze
  bez treści, oceny zostają w agregacie bez przypisania (user = null, waga zachowana), profil spina3 usunięty.
  Wspólne konto spin.clinic zostaje (osobny przepływ).
- Zgłoszenia, decyzje moderacji i odwołania: usuwane po 12 miesiącach.
- Dziennik zdarzeń: po `settings.SPINA3_EVENT_RETENTION_DAYS` dniach (domyślnie 90).
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events, legal
from .models import Appeal, ModerationDecision, Pin, Report, Spina3Profile


@transaction.atomic
def purge_account(user, now=None) -> int:
    from .pins import anonymize_user, remove_pin
    now = now or timezone.now()
    for pin in Pin.objects.filter(user=user).exclude(status='removed').exclude(kind='diagnosis'):
        remove_pin(user, pin, now)
    return anonymize_user(user, now)


def run(now=None) -> dict:
    now = now or timezone.now()
    out = {'accounts_purged': 0}
    due = now - timedelta(days=legal.ACCOUNT_DELETION_DAYS)
    for profile in Spina3Profile.objects.filter(deletion_requested_at__lte=due).select_related('user'):
        purge_account(profile.user, now)
        out['accounts_purged'] += 1
    cutoff = now - timedelta(days=legal.DECISION_RETENTION_DAYS)
    out['appeals_deleted'] = Appeal.objects.filter(created_at__lt=cutoff).exclude(status='open').delete()[0]
    out['decisions_deleted'] = ModerationDecision.objects.filter(created_at__lt=cutoff).exclude(appeal__status='open').delete()[0]
    out['reports_deleted'] = Report.objects.filter(created_at__lt=cutoff).exclude(status='new').delete()[0]
    out['events_deleted'] = events.purge(now)
    return out
